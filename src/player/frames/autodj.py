"""Lifecycle and playback coordination for the AutoDJ engine."""

from pathlib import Path
import threading
import time

import wx

from ..autodj import (
    AudioAnalysis,
    AutoDJPlanner,
    AutoDJQueuePlanner,
    AutoDJService,
    QueueCandidate,
    TransitionProfile,
)
from ..i18n import _
from ..library import build_supported_media_wildcard, is_audio_playback_media
from ..log import get_logger
from ..session import get_app_storage_dir


_logger = get_logger(__name__)
AUTODJ_SESSION_CANDIDATE_WAIT_SECONDS = 45


class FrameAutoDJMixin:
    def _initialize_autodj_service(self):
        self.autodj_service = AutoDJService(
            Path(get_app_storage_dir()) / "autodj-analysis.db",
            remote_resolver=lambda media_path: self._get_youtube_music_service().resolve_stream_playback(media_path),
            remote_retry_handler=self._handle_autodj_remote_download_retry,
        )
        self._autodj_transition_requests = {}
        self._autodj_session_requests = {}
        self._autodj_session_results = {}
        self._autodj_session_retry_at = {}
        self._refresh_autodj_menu_state()

    def _handle_autodj_remote_download_retry(self, media_path, error):
        service = self._get_youtube_music_service()
        service.invalidate_cached_stream(media_path)
        if int(getattr(error, "code", 0) or 0) == 403:
            service.advance_stream_playback_after_http_403()

    def _shutdown_autodj_service(self):
        self._autodj_transition_requests = {}
        for request in getattr(self, "_autodj_session_requests", {}).values():
            request.set()
        self._autodj_session_requests = {}
        self._autodj_session_results = {}
        self._autodj_session_retry_at = {}
        self.autodj_service = None

    def on_start_autodj_session(self, _event):
        source = self._get_playlist_state()
        if source is None or source.is_folder_tab or source.is_loading or source.autodj_session:
            self._announce(_("Abra uma playlist comum para iniciar uma sessão AutoDJ."))
            return False
        if len(source.items) < 2:
            self._announce(_("A playlist precisa ter pelo menos duas faixas para iniciar o AutoDJ."))
            return False

        seed_index = source.current_index if 0 <= source.current_index < len(source.items) else 0
        seed_path = source.items[seed_index]
        source_items = list(source.items)
        source_labels = list(source.browser_item_labels)
        label_by_path = dict(zip(source_items, source_labels))
        remaining = source_items[seed_index + 1:] + source_items[:seed_index]
        session_title = _("AutoDJ — {title}").format(title=source.title)
        target_index = self._create_empty_playlist_tab(select=False)
        state = self._get_playlist_state(target_index)
        state.title = session_title
        state.set_items_prepared([seed_path], {seed_path: 0}, [label_by_path.get(seed_path, seed_path)])
        state.autodj_session = True
        state.autodj_source_title = source.title
        state.autodj_source_items = source_items
        state.autodj_source_labels = source_labels
        state.autodj_remaining_items = remaining
        state.autodj_history = []
        state.autodj_preparation_paused = False
        state.autodj_waiting_for_next = False
        state.shuffle_enabled = False
        state.repeat_mode = "off"
        self.notebook.SetPageText(target_index, session_title)
        self._select_tab(target_index, announce=False)
        self._refresh_playlist_browser()
        self._play_media(
            index=target_index,
            announce_message=_("Sessão AutoDJ iniciada. A sequência será preparada em segundo plano."),
            allow_crossfade=False,
        )
        self._maybe_fill_autodj_session(state)
        self._refresh_autodj_menu_state()
        return True

    def on_stop_autodj_session(self, _event):
        state = self._get_playlist_state()
        if state is None or not state.autodj_session:
            self._announce(_("Nenhuma sessão AutoDJ está ativa nesta aba."))
            return False
        self._cancel_autodj_session(state)
        state.autodj_session = False
        state.autodj_remaining_items = []
        state.autodj_source_items = []
        state.autodj_source_labels = []
        state.autodj_history = []
        state.autodj_preparation_paused = False
        state.autodj_waiting_for_next = False
        state.autodj_next_path = None
        source_title = state.autodj_source_title
        state.autodj_source_title = None
        if source_title:
            state.title = _("Sequência AutoDJ — {title}").format(title=source_title)
            tab_index = self._resolve_playlist_state_index(state)
            if tab_index != wx.NOT_FOUND:
                self.notebook.SetPageText(tab_index, state.title)
        self._refresh_playlist_browser()
        self._refresh_autodj_menu_state()
        self._announce(_("Sessão AutoDJ encerrada. A sequência preparada foi preservada como playlist."))
        return True

    def on_replace_autodj_next(self, _event):
        state = self._get_playlist_state()
        if state is None or not state.autodj_session:
            self._announce(_("Nenhuma sessão AutoDJ está ativa nesta aba."))
            return False
        next_path = state.peek_in_playback_order(1, wrap=False)
        alternatives = [path for path in state.autodj_remaining_items if path != next_path]
        if not next_path or not alternatives:
            self._announce(_("Não há outra faixa disponível para substituir a próxima."))
            return False

        self._cancel_autodj_session(state)
        if not self._remove_autodj_prepared_paths(state, [next_path]):
            return False
        state.autodj_remaining_items = alternatives + [next_path]
        self._autodj_transition_requests = {}
        self._refresh_playlist_browser()
        self._announce(_("Escolhendo outra próxima faixa."))
        self._maybe_fill_autodj_session(state)
        return True

    def on_recalculate_autodj_session(self, _event):
        state = self._get_playlist_state()
        if state is None or not state.autodj_session:
            self._announce(_("Nenhuma sessão AutoDJ está ativa nesta aba."))
            return False
        prepared_paths = list(state.items[state.current_index + 1:])
        if not prepared_paths and not state.autodj_remaining_items:
            self._announce(_("Não há faixas restantes para recalcular a sequência."))
            return False

        self._cancel_autodj_session(state)
        self._remove_autodj_prepared_paths(state, prepared_paths)
        combined = list(state.autodj_remaining_items) + prepared_paths
        state.autodj_remaining_items = list(dict.fromkeys(combined))
        self._autodj_transition_requests = {}
        self._refresh_playlist_browser()
        self._announce(_("Recalculando a sequência AutoDJ."))
        self._maybe_fill_autodj_session(state)
        return True

    def on_add_media_to_autodj_session(self, _event):
        state = self._get_playlist_state()
        if state is None or not state.autodj_session:
            self._announce(_("Nenhuma sessão AutoDJ está ativa nesta aba."))
            return False

        with wx.FileDialog(
            self,
            _("Adicionar músicas à sessão AutoDJ"),
            defaultDir=self._default_dialog_directory(),
            wildcard=build_supported_media_wildcard(include_playlists=False),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return False
            selected_paths = dialog.GetPaths()

        media_paths, _playlist_paths = self._split_selected_files(selected_paths)
        known_paths = set(state.autodj_source_items)
        added_paths = [path for path in media_paths if path not in known_paths]
        if not added_paths:
            self._announce(_("Nenhuma música nova foi adicionada à sessão AutoDJ."))
            return False

        state.autodj_source_items.extend(added_paths)
        state.autodj_source_labels.extend(Path(path).name or path for path in added_paths)
        state.autodj_remaining_items.extend(added_paths)
        remember_directory = getattr(self, "_remember_directory", None)
        if callable(remember_directory):
            remember_directory(added_paths[0])
        register_in_library = getattr(self, "_register_media_paths_in_library", None)
        if callable(register_in_library):
            register_in_library(added_paths, [Path(path).name or path for path in added_paths])
        self._refresh_playlist_browser()
        self._announce(
            _("{count} músicas adicionadas à sessão AutoDJ.").format(count=len(added_paths))
        )
        self._maybe_fill_autodj_session(state)
        return True

    def on_toggle_autodj_preparation(self, _event):
        state = self._get_playlist_state()
        if state is None or not state.autodj_session:
            self._announce(_("Nenhuma sessão AutoDJ está ativa nesta aba."))
            return False
        state.autodj_preparation_paused = not state.autodj_preparation_paused
        if state.autodj_preparation_paused:
            self._cancel_autodj_session(state)
            state.autodj_waiting_for_next = False
            message = _("Preparação da sessão AutoDJ pausada.")
        else:
            message = _("Preparação da sessão AutoDJ retomada.")
        self._refresh_playlist_browser()
        self._announce(message)
        if not state.autodj_preparation_paused:
            self._maybe_fill_autodj_session(state)
        return True

    @staticmethod
    def _remove_autodj_prepared_paths(state, media_paths):
        removable = set(media_paths or ())
        removable.discard(state.current_media_path)
        indexes = [
            index
            for index in range(state.current_index + 1, len(state.items))
            if state.items[index] in removable
        ]
        if not indexes:
            return False
        for index in reversed(indexes):
            state.items.pop(index)
            if index < len(state.browser_item_labels):
                state.browser_item_labels.pop(index)
        state.refresh_browser_item_labels()
        state.current_index = state.item_index_map.get(state.current_media_path, state.current_index)
        state.autodj_next_path = None
        state.reset_playback_order(preferred_index=state.current_index)
        return True

    def _cancel_autodj_session(self, state):
        state_key = id(state)
        request = getattr(self, "_autodj_session_requests", {}).pop(state_key, None)
        if request is not None:
            request.set()
        getattr(self, "_autodj_session_results", {}).pop(state_key, None)
        getattr(self, "_autodj_session_retry_at", {}).pop(state_key, None)

    def _defer_autodj_advance(self, state):
        """Resume an exhausted AutoDJ session after its next track is ready."""
        if (
            state is None
            or not state.autodj_session
            or state.autodj_preparation_paused
            or not state.autodj_remaining_items
        ):
            return False
        state.autodj_waiting_for_next = True
        self._maybe_fill_autodj_session(state)
        self._refresh_autodj_session_ui(state)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(
                _("AutoDJ preparando a próxima faixa para continuar a reprodução..."),
                auto_clear_ms=0,
            )
        return True

    def _maybe_fill_autodj_session(self, state=None):
        state = state or self._get_active_playlist_state()
        service = getattr(self, "autodj_service", None)
        if (
            service is None
            or state is None
            or not state.autodj_session
            or state.autodj_preparation_paused
            or not any(item is state for item in self.playlists)
        ):
            return False
        self._drain_autodj_session_result(state)
        upcoming_count = max(0, len(state.items) - state.current_index - 1)
        needed = max(0, 5 - upcoming_count)
        if needed <= 0 or not state.autodj_remaining_items:
            return False
        state_key = id(state)
        if state_key in self._autodj_session_requests:
            return True
        if time.monotonic() < float(self._autodj_session_retry_at.get(state_key, 0.0)):
            return False

        cancel_event = threading.Event()
        self._autodj_session_requests[state_key] = cancel_event
        current_path = str(state.current_media_path or "")
        candidate_paths = list(state.autodj_remaining_items[:max(6, needed)])
        profile_name = str(getattr(self.settings, "autodj_profile", "smooth") or "smooth")
        beat_count = int(getattr(self.settings, "autodj_beats", 16) or 16)
        recent_artists = self._autodj_recent_artists(state)

        def worker():
            try:
                current_analysis = self._audio_analysis_from_result(service.analyze(current_path))
                pending = iter(enumerate(candidate_paths))
                worker_lock = threading.Lock()
                candidates = []

                def consume():
                    while not cancel_event.is_set():
                        with worker_lock:
                            try:
                                source_index, candidate_path = next(pending)
                            except StopIteration:
                                return
                        try:
                            analysis = self._audio_analysis_from_result(service.analyze(candidate_path))
                            candidate = QueueCandidate(
                                candidate_path,
                                self._autodj_source_artist(state, candidate_path),
                                analysis,
                                source_index,
                            )
                            with worker_lock:
                                candidates.append(candidate)
                        except Exception as exc:
                            _logger.warning("AutoDJ session candidate analysis failed for %r: %s", candidate_path, exc)

                workers = [
                    threading.Thread(target=consume, daemon=True, name=f"autodj-session-{index + 1}")
                    for index in range(min(3, max(1, len(candidate_paths))))
                ]
                for candidate_worker in workers:
                    candidate_worker.start()
                for candidate_worker in workers:
                    remaining_wait = max(
                        0.0,
                        float(getattr(self, "_autodj_session_candidate_wait_seconds", AUTODJ_SESSION_CANDIDATE_WAIT_SECONDS))
                        - (time.monotonic() - worker_started_at),
                    )
                    candidate_worker.join(remaining_wait)
                if cancel_event.is_set():
                    return
                with worker_lock:
                    completed_candidates = list(candidates)
                selections = AutoDJQueuePlanner().plan(
                    current_analysis,
                    completed_candidates,
                    count=needed,
                    recent_artists=recent_artists,
                    beats=beat_count,
                    profile=TransitionProfile(profile_name),
                )
                self._queue_autodj_session_fill(state, current_path, selections, "", cancel_event)
            except Exception as exc:
                _logger.warning("AutoDJ session planning failed for %r: %s", current_path, exc, exc_info=True)
                self._queue_autodj_session_fill(
                    state,
                    current_path,
                    (),
                    str(exc) or exc.__class__.__name__,
                    cancel_event,
                )

        worker_started_at = time.monotonic()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("AutoDJ preparando as próximas faixas da sessão..."), auto_clear_ms=0)
        self._refresh_autodj_session_ui(state)
        threading.Thread(target=worker, daemon=True, name="autodj-session-planner").start()
        return True

    def _queue_autodj_session_fill(self, state, current_path, selections, error_message, cancel_event):
        """Publish a worker result for the UI thread to consume exactly once."""
        state_key = id(state)
        results = getattr(self, "_autodj_session_results", None)
        if results is None:
            results = self._autodj_session_results = {}
        results[state_key] = (current_path, selections, error_message, cancel_event)
        wx.CallAfter(self._drain_autodj_session_result, state)

    def _drain_autodj_session_result(self, state):
        """Finish a completed session analysis, including after a missed CallAfter."""
        state_key = id(state)
        result = getattr(self, "_autodj_session_results", {}).pop(state_key, None)
        if result is None:
            return False
        current_path, selections, error_message, cancel_event = result
        self._finish_autodj_session_fill(
            state,
            current_path,
            selections,
            error_message,
            cancel_event,
        )
        return True

    def _finish_autodj_session_fill(self, state, current_path, selections, error_message, cancel_event):
        state_key = id(state)
        if self._autodj_session_requests.get(state_key) is not cancel_event:
            return
        self._autodj_session_requests.pop(state_key, None)
        if cancel_event.is_set() or not any(item is state for item in self.playlists) or not state.autodj_session:
            return
        if state.current_media_path != current_path:
            return
        if error_message or not selections:
            self._autodj_session_retry_at[state_key] = time.monotonic() + 30
            if hasattr(self, "_set_status_message"):
                self._set_status_message(
                    _("O AutoDJ não conseguiu completar a fila agora; tentará novamente."),
                    auto_clear_ms=7000,
                )
            self._refresh_autodj_session_ui(state)
            return

        selected_paths = [selection.path for selection in selections if selection.path not in state.items]
        selected_labels = [self._autodj_source_label(state, path) for path in selected_paths]
        state.append_items(selected_paths, selected_labels)
        selected_set = set(selected_paths)
        state.autodj_remaining_items = [path for path in state.autodj_remaining_items if path not in selected_set]
        self._autodj_session_retry_at.pop(state_key, None)
        resume_waiting_session = bool(state.autodj_waiting_for_next)
        state.autodj_waiting_for_next = False
        if state is self._get_active_playlist_state():
            self._refresh_playlist_browser()
        if resume_waiting_session and state is self._get_active_playlist_state():
            if state.move_in_playback_order(1, wrap=False):
                self._play_media(index=self._get_active_playlist_index())
                return
        if hasattr(self, "_set_status_message"):
            self._set_status_message(
                _("AutoDJ preparou {count} próximas faixas.").format(count=len(selected_paths)),
                auto_clear_ms=5000,
            )

    def _refresh_autodj_session_ui(self, state=None):
        current_index = self.notebook.GetSelection() if hasattr(self, "notebook") else wx.NOT_FOUND
        if current_index == wx.NOT_FOUND or not 0 <= current_index < self.notebook.GetPageCount():
            return
        page = self.notebook.GetPage(current_index)
        panel = getattr(page, "autodj_panel", None)
        browser = getattr(page, "browser_panel", None)
        state = state or self._get_playlist_state(current_index)
        if state is None or not state.autodj_session:
            if panel is not None:
                panel.update_session(visible=False)
            if browser is not None and hasattr(browser, "set_item_statuses"):
                browser.set_item_statuses({})
            return

        prepared_count = max(0, len(state.items) - state.current_index - 1)
        remaining_count = len(state.autodj_remaining_items)
        if state.autodj_preparation_paused:
            activity = _("Preparação pausada.")
        elif id(state) in getattr(self, "_autodj_session_requests", {}):
            activity = _("Analisando próximas faixas.")
        else:
            activity = _("Sessão ativa.")
        summary = _(
            "{activity} Origem: {source}. Preparadas: {prepared}. Restantes: {remaining}."
        ).format(
            activity=activity,
            source=state.autodj_source_title or _("playlist original"),
            prepared=prepared_count,
            remaining=remaining_count,
        )
        details, next_status = self._autodj_transition_description(state)
        statuses = {}
        for index, path in enumerate(state.items):
            if index < state.current_index:
                statuses[path] = _("Tocada")
            elif index == state.current_index:
                statuses[path] = _("Tocando")
            elif index == state.current_index + 1:
                statuses[path] = next_status
            else:
                statuses[path] = _("Preparada")
        if browser is not None and hasattr(browser, "set_item_statuses"):
            browser.set_item_statuses(statuses)
        if panel is not None:
            panel.update_session(
                visible=True,
                summary=summary,
                details=details,
                preparation_paused=state.autodj_preparation_paused,
                can_replace_next=bool(prepared_count and remaining_count),
                can_recalculate=bool(prepared_count or remaining_count),
            )

    def _autodj_transition_description(self, state):
        pair = self._autodj_transition_pair(state)
        if pair is None:
            return _("Próxima transição: aguardando uma faixa preparada."), _("Preparada")
        request = getattr(self, "_autodj_transition_requests", {}).get(pair)
        if not request or request.get("status") == "pending":
            return _("Próxima transição: analisando."), _("Próxima, analisando transição")
        if request.get("status") == "failed":
            reason = str(request.get("error") or _("falha ao analisar as faixas"))
            return (
                _("Próxima transição: aguardando nova tentativa. Motivo: {reason}.").format(
                    reason=reason
                ),
                _("Próxima, análise pendente"),
            )
        plan = request.get("plan")
        if plan is None or plan.fallback_crossfade:
            reason = self._autodj_fallback_reason(getattr(plan, "reason", ""))
            details = _("Próxima transição: comum. Motivo: {reason}.").format(reason=reason)
            analysis_details = self._autodj_analysis_description(
                request.get("outgoing"), request.get("incoming")
            )
            if analysis_details:
                details += "\r\n" + analysis_details
            return details, _("Próxima, transição comum")
        details = _("Próxima transição: {count} batidas.").format(count=plan.beat_count)
        analysis_details = self._autodj_analysis_description(
            request.get("outgoing"), request.get("incoming")
        )
        if analysis_details:
            details += "\r\n" + analysis_details
        details += " " + _("Ajuste de tempo: {adjustment:+.1%}.").format(
            adjustment=float(plan.tempo_ratio) - 1.0
        )
        if getattr(plan, "vocal_overlap", False):
            details += " " + _("Vocais protegidos.")
        incoming_gain_db = float(getattr(plan, "incoming_gain_db", 0.0) or 0.0)
        if incoming_gain_db < -0.1:
            details += " " + _("Volume da próxima faixa ajustado em {gain:.1f} dB.").format(
                gain=incoming_gain_db
            )
        return details, _("Próxima, transição de {count} batidas").format(count=plan.beat_count)

    @staticmethod
    def _autodj_fallback_reason(reason):
        return {
            "confiança insuficiente": _("confiança rítmica insuficiente"),
            "ajuste de tempo excederia o limite": _("diferença de BPM acima do limite seguro"),
            "grade de batidas insuficiente": _("poucas batidas utilizáveis na faixa atual"),
            "ponto de entrada indisponível": _("nenhum ponto de entrada adequado na próxima faixa"),
        }.get(str(reason or ""), _("análise incompatível"))

    @staticmethod
    def _autodj_analysis_description(outgoing, incoming):
        if outgoing is None or incoming is None:
            return ""
        return _(
            "Análise rítmica: faixa atual {outgoing_bpm:.1f} BPM, confiança {outgoing_confidence:.0%}; "
            "próxima faixa {incoming_bpm:.1f} BPM, confiança {incoming_confidence:.0%}."
        ).format(
            outgoing_bpm=float(outgoing.bpm or 0.0),
            outgoing_confidence=float(outgoing.confidence or 0.0),
            incoming_bpm=float(incoming.bpm or 0.0),
            incoming_confidence=float(incoming.confidence or 0.0),
        )

    @staticmethod
    def _autodj_source_label(state, media_path):
        for path, label in zip(state.autodj_source_items, state.autodj_source_labels):
            if path == media_path:
                return label
        return Path(media_path).name or media_path

    def _autodj_source_artist(self, state, media_path):
        return self._autodj_artist_from_label(self._autodj_source_label(state, media_path))

    def on_toggle_autodj(self, _event):
        self.settings.autodj_enabled = not bool(getattr(self.settings, "autodj_enabled", False))
        self._autodj_transition_requests = {}
        self._refresh_autodj_menu_state()
        apply_filters = getattr(self, "_apply_equalizer_state_to_current_playback", None)
        if callable(apply_filters):
            apply_filters()
        self._save_settings()
        status = _("ativado") if self.settings.autodj_enabled else _("desativado")
        self._announce(_("AutoDJ {status}.").format(status=status))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("AutoDJ: {status}.").format(status=status))

    def _handle_autodj_preferences_change(self, previous_settings):
        previous_values = (
            getattr(previous_settings, "autodj_enabled", False),
            getattr(previous_settings, "autodj_profile", "smooth"),
            getattr(previous_settings, "autodj_beats", 16),
        )
        current_values = (
            getattr(self.settings, "autodj_enabled", False),
            getattr(self.settings, "autodj_profile", "smooth"),
            getattr(self.settings, "autodj_beats", 16),
        )
        if current_values != previous_values:
            self._autodj_transition_requests = {}
            apply_filters = getattr(self, "_apply_equalizer_state_to_current_playback", None)
            if callable(apply_filters):
                apply_filters()
        self._refresh_autodj_menu_state()

    def _refresh_autodj_menu_state(self):
        menu = getattr(self, "playback_menu", None)
        item_id = getattr(self, "menu_toggle_autodj_id", None)
        if menu is None or item_id is None:
            return
        item = menu.FindItemById(item_id)
        if item is not None:
            item.Check(bool(getattr(self.settings, "autodj_enabled", False)))
        state = self._get_playlist_state() if hasattr(self, "_get_playlist_state") else None
        start_item = menu.FindItemById(getattr(self, "menu_start_autodj_session_id", -1))
        stop_item = menu.FindItemById(getattr(self, "menu_stop_autodj_session_id", -1))
        if start_item is not None:
            start_item.Enable(bool(state and not state.is_folder_tab and not state.is_loading and not state.autodj_session and len(state.items) > 1))
        if stop_item is not None:
            stop_item.Enable(bool(state and state.autodj_session))

    def _autodj_transition_pair(self, state):
        if not bool(getattr(self.settings, "autodj_enabled", False)) and not bool(getattr(state, "autodj_session", False)):
            return None
        if state is None or state.is_folder_tab or not state.current_media_path:
            return None
        if getattr(state, "repeat_mode", "off") == "one":
            return None

        should_wrap = getattr(state, "repeat_mode", "off") == "all"
        incoming_path = state.peek_in_playback_order(1, wrap=should_wrap)
        outgoing_path = str(state.current_media_path or "").strip()
        incoming_path = str(incoming_path or "").strip()
        if not outgoing_path or not incoming_path or outgoing_path == incoming_path:
            return None
        if not is_audio_playback_media(outgoing_path) or not is_audio_playback_media(incoming_path):
            return None
        return outgoing_path, incoming_path

    @staticmethod
    def _autodj_artist_from_label(label):
        normalized = str(label or "").strip()
        return normalized.split(" — ", 1)[0].strip() if " — " in normalized else ""

    def _autodj_candidate_paths(self, state, limit=6):
        should_wrap = getattr(state, "repeat_mode", "off") == "all"
        if state.custom_queue:
            candidate = state.peek_in_playback_order(1, wrap=should_wrap)
            return [candidate] if candidate else []
        if state.autodj_session:
            candidate = state.peek_in_playback_order(1, wrap=False)
            return [candidate] if candidate else []

        state.sync_playback_order()
        candidates = []
        if state.shuffle_enabled:
            order = state.playback_order
            start = state.playback_order_position + 1
            indexes = order[start:]
            if should_wrap:
                indexes += order[:start]
        else:
            indexes = list(range(state.current_index + 1, len(state.items)))
            if should_wrap:
                indexes += list(range(0, state.current_index))
        for index in indexes:
            path = state.items[index]
            if path != state.current_media_path and is_audio_playback_media(path) and path not in candidates:
                candidates.append(path)
            if len(candidates) >= limit:
                break
        return candidates

    def _autodj_artist_for_path(self, state, media_path):
        index = state.item_index_map.get(media_path)
        if index is None or not 0 <= index < len(state.browser_item_labels):
            return ""
        return self._autodj_artist_from_label(state.browser_item_labels[index])

    def _autodj_recent_artists(self, state, limit=3):
        if state.current_index < 0:
            return ()
        indexes = range(max(0, state.current_index - limit + 1), state.current_index + 1)
        return tuple(
            artist
            for artist in (
                self._autodj_artist_for_path(state, state.items[index])
                for index in indexes
            )
            if artist
        )

    def _maybe_prepare_autodj_transition(self):
        self._maybe_fill_autodj_session()
        service = getattr(self, "autodj_service", None)
        if service is None:
            return False
        player = getattr(self, "player", None)
        if player is None or player.get_media() is None or not player.is_playing():
            return False

        state = self._get_active_playlist_state()
        pair = self._autodj_transition_pair(state)
        if pair is None:
            return False

        requests = getattr(self, "_autodj_transition_requests", {})
        self._autodj_transition_requests = {key: value for key, value in requests.items() if key == pair}
        if pair in self._autodj_transition_requests:
            existing_request = self._autodj_transition_requests[pair]
            if (
                existing_request.get("status") == "failed"
                and time.monotonic() >= float(existing_request.get("retry_at", 0) or 0)
            ):
                self._autodj_transition_requests.pop(pair, None)
            else:
                return existing_request.get("status") == "ready"

        request = {"status": "pending", "plan": None, "outgoing": None, "incoming": None}
        self._autodj_transition_requests[pair] = request
        profile_name = str(getattr(self.settings, "autodj_profile", "smooth") or "smooth")
        beat_count = int(getattr(self.settings, "autodj_beats", 16) or 16)
        candidate_paths = self._autodj_candidate_paths(state)
        recent_artists = self._autodj_recent_artists(state)
        candidate_artists = {
            path: self._autodj_artist_for_path(state, path)
            for path in candidate_paths
        }

        def worker():
            try:
                outgoing = self._audio_analysis_from_result(service.analyze(pair[0]))
                analyzed_candidates = []

                def analyze_candidate(candidate_index, candidate_path):
                    try:
                        result = service.analyze(candidate_path)
                        incoming = self._audio_analysis_from_result(result)
                        plan = AutoDJPlanner().plan(
                            outgoing,
                            incoming,
                            beats=beat_count,
                            profile=TransitionProfile(profile_name),
                        )
                        loudness_delta = 0.0
                        if outgoing.loudness_db is not None and incoming.loudness_db is not None:
                            loudness_delta = abs(outgoing.loudness_db - incoming.loudness_db)
                        return {
                            "path": candidate_path,
                            "artist": candidate_artists.get(candidate_path, ""),
                            "energy": incoming.energy,
                            "entry_energy": incoming.entry_energy,
                            "musical_key": incoming.musical_key,
                            "musical_mode": incoming.musical_mode,
                            "key_confidence": incoming.key_confidence,
                            "current_key": outgoing.musical_key,
                            "current_mode": outgoing.musical_mode,
                            "tempo_delta": abs(float(plan.tempo_ratio) - 1.0),
                            "loudness_delta": loudness_delta,
                            "analysis_confidence": min(outgoing.confidence, incoming.confidence),
                            "current_exit_vocal": outgoing.exit_vocal_probability,
                            "entry_vocal": incoming.entry_vocal_probability,
                            "order_index": candidate_index,
                            "fallback_crossfade": plan.fallback_crossfade,
                            "analysis": incoming,
                            "plan": plan,
                        }
                    except Exception as exc:
                        _logger.warning("AutoDJ candidate analysis failed for %r: %s", candidate_path, exc)
                        return None

                pending_candidates = iter(enumerate(candidate_paths))
                candidate_lock = threading.Lock()

                def consume_candidates():
                    while True:
                        with candidate_lock:
                            try:
                                candidate_index, candidate_path = next(pending_candidates)
                            except StopIteration:
                                return
                        candidate = analyze_candidate(candidate_index, candidate_path)
                        if candidate is not None:
                            with candidate_lock:
                                analyzed_candidates.append(candidate)

                candidate_workers = [
                    threading.Thread(
                        target=consume_candidates,
                        daemon=True,
                        name=f"autodj-candidate-{index + 1}",
                    )
                    for index in range(min(3, max(1, len(candidate_paths))))
                ]
                for candidate_worker in candidate_workers:
                    candidate_worker.start()
                for candidate_worker in candidate_workers:
                    candidate_worker.join()
                chosen = AutoDJPlanner.choose_next(
                    analyzed_candidates,
                    recent_artists=recent_artists,
                    current_energy=(
                        outgoing.exit_energy
                        if outgoing.exit_energy is not None
                        else outgoing.energy
                    ),
                    profile=TransitionProfile(profile_name),
                )
                if chosen is None:
                    raise RuntimeError("Nenhuma próxima faixa pôde ser analisada.")
                wx.CallAfter(
                    self._finish_autodj_transition_analysis,
                    pair,
                    chosen["path"],
                    outgoing,
                    chosen["analysis"],
                    chosen["plan"],
                    "",
                )
            except Exception as exc:
                _logger.warning("AutoDJ analysis failed for %r -> %r: %s", pair[0], pair[1], exc, exc_info=True)
                wx.CallAfter(
                    self._finish_autodj_transition_analysis,
                    pair,
                    pair[1],
                    None,
                    None,
                    None,
                    str(exc) or exc.__class__.__name__,
                )

        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("AutoDJ analisando a faixa atual e as próximas opções..."), auto_clear_ms=0)
        self._refresh_autodj_session_ui(state)
        threading.Thread(target=worker, daemon=True, name="autodj-analysis").start()
        return True

    @staticmethod
    def _warm_autodj_candidate(service, media_path):
        try:
            service.analyze(media_path)
        except Exception as exc:
            _logger.debug("AutoDJ cache warmup failed for %r: %s", media_path, exc)

    @staticmethod
    def _audio_analysis_from_result(result):
        values = dict(result or {})
        values["beats_ms"] = tuple(values.get("beats_ms") or ())
        return AudioAnalysis(**values)

    def _finish_autodj_transition_analysis(self, pair, selected_path, outgoing, incoming, plan, error_message):
        request = getattr(self, "_autodj_transition_requests", {}).get(pair)
        if request is None:
            return
        if pair != self._autodj_transition_pair(self._get_active_playlist_state()):
            self._autodj_transition_requests.pop(pair, None)
            return
        if error_message:
            request.update(
                status="failed",
                error=error_message,
                retry_at=time.monotonic() + 30,
            )
            if hasattr(self, "_set_status_message"):
                self._set_status_message(
                    _("O AutoDJ não conseguiu analisar estas faixas. Uma nova tentativa será feita automaticamente."),
                    auto_clear_ms=7000,
                )
            self._refresh_autodj_session_ui(self._get_active_playlist_state())
            return
        state = self._get_active_playlist_state()
        selected_pair = (pair[0], selected_path)
        if selected_path != pair[1] and not state.set_autodj_next(selected_path):
            selected_pair = pair
        if selected_pair != pair:
            self._autodj_transition_requests.pop(pair, None)
            self._autodj_transition_requests[selected_pair] = request
        request.update(status="ready", outgoing=outgoing, incoming=incoming, plan=plan)
        self._refresh_autodj_session_ui(state)
        if hasattr(self, "_set_status_message"):
            if plan.fallback_crossfade:
                message = _("O AutoDJ não encontrou batidas compatíveis. Será usada a transição normal.")
            else:
                message = _("AutoDJ preparado: transição de {count} batidas.").format(count=plan.beat_count)
            self._set_status_message(message, auto_clear_ms=7000)

    def _prepared_autodj_transition(self, state):
        pair = self._autodj_transition_pair(state)
        if pair is None:
            return None
        request = getattr(self, "_autodj_transition_requests", {}).get(pair)
        if not request or request.get("status") != "ready":
            return None
        plan = request.get("plan")
        if plan is None or plan.fallback_crossfade:
            return None
        return {
            "pair": pair,
            "plan": plan,
            "outgoing": request.get("outgoing"),
            "incoming": request.get("incoming"),
            "profile": str(getattr(self.settings, "autodj_profile", "smooth") or "smooth"),
        }

    @staticmethod
    def _autodj_transition_duration_ms(transition):
        outgoing = transition.get("outgoing")
        plan = transition.get("plan")
        start_ms = getattr(plan, "outgoing_start_ms", None) if plan is not None else None
        end_ms = getattr(plan, "outgoing_end_ms", None) if plan is not None else None
        if start_ms is not None and end_ms is not None and end_ms > start_ms:
            return max(500, min(30000, int(end_ms - start_ms)))
        bpm = float(getattr(outgoing, "bpm", 0) or 0)
        if bpm <= 0 or plan is None:
            return 0
        return max(500, min(30000, int(round(plan.beat_count * 60000.0 / bpm))))
