"""SponsorBlock na reprodução: pular os trechos marcados e, se o usuário quiser, contribuir."""

import threading
import time

import wx

from ... import interface_sounds
from ...i18n import _
from .helpers import is_youtube_music_media

# Folga para não pular um trecho que já está terminando, nem voltar a pulá-lo logo após o fim.
_SEGMENT_END_MARGIN_SECONDS = 0.5
# Voltar para antes do início de um trecho já pulado faz ele valer de novo.
_SEGMENT_REARM_MARGIN_SECONDS = 1.0
_MINIMUM_SUBMITTED_SEGMENT_SECONDS = 1.0
# Quando a busca falha (rede ou servidor), tenta de novo algumas vezes neste intervalo.
_FETCH_RETRY_SECONDS = 30.0
_FETCH_MAX_ATTEMPTS = 3


def _sponsorblock():
    from ...youtube_music import sponsorblock

    return sponsorblock


def _video_id_for(media_path):
    media_path = str(media_path or "").strip()
    if not media_path or not is_youtube_music_media(media_path):
        return ""
    from ...youtube_music.playlists import extract_video_id_from_text

    return str(extract_video_id_from_text(media_path) or "")


class SponsorBlockMixin:
    def _sponsorblock_settings_enabled(self):
        settings = getattr(self, "settings", None)
        return bool(settings is not None and getattr(settings, "sponsorblock_enabled", False))

    def _sponsorblock_contribution_enabled(self):
        settings = getattr(self, "settings", None)
        return bool(settings is not None and getattr(settings, "sponsorblock_contribute", False))

    def _sponsorblock_current_video_id(self):
        loaded_media_path = self._player_loaded_media_path()
        return _video_id_for(loaded_media_path)

    def _sponsorblock_position_seconds(self):
        if not hasattr(self, "player") or self.player.get_media() is None:
            return None
        position_ms = self.player.get_time()
        if position_ms is None or position_ms < 0:
            return None
        return position_ms / 1000.0

    def _sponsorblock_state_for(self, video_id):
        # Mudar as categorias nas preferências também refaz a busca.
        categories = tuple(getattr(self.settings, "sponsorblock_categories", ()) or ())
        state = getattr(self, "_sponsorblock_state", None)
        if state is None or state.get("video_id") != video_id or state.get("categories") != categories:
            state = {
                "video_id": video_id,
                "categories": categories,
                "segments": None,
                "handled": set(),
                "pending": None,
                "attempts": 0,
                "retry_at": None,
            }
            self._sponsorblock_state = state
            if video_id:
                self._start_sponsorblock_fetch(state)
        return state

    def _start_sponsorblock_fetch(self, state):
        video_id = state["video_id"]
        categories = list(state["categories"])
        state["attempts"] += 1
        state["retry_at"] = None

        def worker():
            segments = _sponsorblock().fetch_segments(video_id, categories)

            def deliver():
                if getattr(self, "_sponsorblock_state", None) is not state:
                    return
                if segments is None:
                    # Falhou: sem trechos por ora, e outra tentativa mais tarde.
                    state["segments"] = state["segments"] or []
                    if state["attempts"] < _FETCH_MAX_ATTEMPTS:
                        state["retry_at"] = time.monotonic() + _FETCH_RETRY_SECONDS
                else:
                    state["segments"] = segments

            wx.CallAfter(deliver)

        threading.Thread(target=worker, daemon=True, name="sponsorblock-fetch").start()

    def _maybe_retry_sponsorblock_fetch(self, state):
        retry_at = state.get("retry_at")
        if retry_at is not None and state.get("video_id") and time.monotonic() >= retry_at:
            self._start_sponsorblock_fetch(state)

    def _maybe_handle_sponsorblock_segment(self):
        """Chamado pelo timer de progresso: pula, silencia ou avisa ao entrar num trecho marcado."""
        if not self._sponsorblock_settings_enabled():
            self._end_sponsorblock_mute()
            self._sponsorblock_state = None
            return False
        state = self._sponsorblock_state_for(self._sponsorblock_current_video_id())
        self._maybe_retry_sponsorblock_fetch(state)
        position = self._sponsorblock_position_seconds()
        self._update_sponsorblock_mute(state, position)
        segments = state.get("segments")
        if not segments or position is None:
            return False

        handled = state["handled"]
        for segment in segments:
            if position < segment.start_seconds - _SEGMENT_REARM_MARGIN_SECONDS:
                handled.discard(segment.uuid)
                continue
            if segment.uuid in handled:
                continue
            if segment.start_seconds <= position < segment.end_seconds - _SEGMENT_END_MARGIN_SECONDS:
                handled.add(segment.uuid)
                self._sponsorblock_last_segment = (state["video_id"], segment)
                if self.settings.sponsorblock_mode == _sponsorblock().MODE_NOTIFY:
                    state["pending"] = segment
                    self._announce(
                        _("Trecho de {category} aqui, até {end}.").format(
                            category=_sponsorblock().category_label(segment.category),
                            end=self._format_sponsorblock_time(segment.end_seconds),
                        )
                    )
                elif segment.action_type == _sponsorblock().ACTION_MUTE:
                    self._start_sponsorblock_mute(state, segment)
                else:
                    self._skip_sponsorblock_segment(segment)
                return True
        return False

    # Trechos de silenciar: o som volta ao sair do trecho, ao trocar de mídia ou ao desligar.

    def _start_sponsorblock_mute(self, state, segment):
        self._end_sponsorblock_mute()
        self.player.audio_set_mute(True)
        self._sponsorblock_muted = (state, segment, self.player)
        self._announce(
            _("Trecho silenciado: {category}.").format(category=_sponsorblock().category_label(segment.category))
        )
        self._report_sponsorblock_skip(segment)

    def _update_sponsorblock_mute(self, state, position):
        muted = getattr(self, "_sponsorblock_muted", None)
        if muted is None:
            return
        muted_state, segment, player = muted
        if (
            muted_state is not state
            or player is not getattr(self, "player", None)
            or position is None
            or not (segment.start_seconds <= position < segment.end_seconds)
        ):
            self._end_sponsorblock_mute()

    def _end_sponsorblock_mute(self):
        muted = getattr(self, "_sponsorblock_muted", None)
        if muted is None:
            return
        self._sponsorblock_muted = None
        muted[2].audio_set_mute(False)

    def _skip_sponsorblock_segment(self, segment):
        self.player.set_time(int(segment.end_seconds * 1000))
        self._update_time_bar()
        interface_sounds.play_for(self, interface_sounds.SOUND_SEGMENT_SKIPPED)
        self._announce(
            _("Trecho pulado: {category}.").format(category=_sponsorblock().category_label(segment.category))
        )
        self._report_sponsorblock_skip(segment)

    def _report_sponsorblock_skip(self, segment):
        if self._sponsorblock_contribution_enabled() and segment.uuid:
            uuid = segment.uuid
            threading.Thread(
                target=lambda: _sponsorblock().report_skip(uuid), daemon=True, name="sponsorblock-skip"
            ).start()

    @staticmethod
    def _format_sponsorblock_time(seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

    def _last_sponsorblock_segment_here(self):
        last = getattr(self, "_sponsorblock_last_segment", None)
        video_id = self._sponsorblock_current_video_id()
        if not last or not video_id or last[0] != video_id:
            return None
        return last[1]

    # Comandos de uso: pular quando só avisado e desfazer um pulo.

    def on_sponsorblock_skip_segment(self, _event):
        state = getattr(self, "_sponsorblock_state", None) or {}
        segment = state.get("pending")
        position = self._sponsorblock_position_seconds()
        if segment is None or position is None or not (
            segment.start_seconds - _SEGMENT_REARM_MARGIN_SECONDS <= position < segment.end_seconds
        ):
            self._announce(_("Não há trecho do SponsorBlock para pular agora."))
            return False
        state["pending"] = None
        self._skip_sponsorblock_segment(segment)
        return True

    def on_sponsorblock_undo_skip(self, _event):
        segment = self._last_sponsorblock_segment_here()
        if segment is None:
            self._announce(_("Nenhum trecho do SponsorBlock foi pulado nesta mídia."))
            return False
        # O trecho continua marcado como tratado: voltar a ele não o pula nem silencia de novo.
        self._end_sponsorblock_mute()
        self.player.set_time(int(segment.start_seconds * 1000))
        self._update_time_bar()
        self._announce(
            _("De volta ao início do trecho de {category}.").format(
                category=_sponsorblock().category_label(segment.category)
            )
        )
        return True

    # Contribuição: marcar e enviar trechos novos, votar nos existentes.

    def _sponsorblock_contribution_target(self):
        """O id do vídeo atual, ou "" depois de explicar por que não dá para contribuir."""
        if not self._sponsorblock_contribution_enabled():
            self._announce(
                _("Para ajudar o SponsorBlock, ative a opção em Preferências, guia KeyTube, grupo SponsorBlock.")
            )
            return ""
        video_id = self._sponsorblock_current_video_id()
        if not video_id:
            self._announce(_("A mídia atual não é um vídeo do YouTube."))
        return video_id

    def _sponsorblock_user_id(self):
        user_id = str(getattr(self.settings, "sponsorblock_user_id", "") or "")
        if not user_id:
            user_id = _sponsorblock().generate_user_id()
            self.settings.sponsorblock_user_id = user_id
            self._save_settings()
        return user_id

    def on_sponsorblock_mark_start(self, _event):
        video_id = self._sponsorblock_contribution_target()
        position = self._sponsorblock_position_seconds()
        if not video_id or position is None:
            return False
        self._sponsorblock_marked_start = (video_id, position)
        self._announce(
            _("Início do trecho marcado em {time}.").format(time=self._format_sponsorblock_time(position))
        )
        return True

    def on_sponsorblock_submit_segment(self, _event):
        video_id = self._sponsorblock_contribution_target()
        end = self._sponsorblock_position_seconds()
        if not video_id or end is None:
            return False
        marked = getattr(self, "_sponsorblock_marked_start", None)
        if not marked or marked[0] != video_id:
            self._announce(_("Marque primeiro o início do trecho neste vídeo."))
            return False
        start = marked[1]
        if end - start < _MINIMUM_SUBMITTED_SEGMENT_SECONDS:
            self._announce(_("O fim do trecho precisa vir depois do início marcado."))
            return False
        # A duração é lida já: com o diálogo aberto a mídia pode avançar para a próxima.
        length_ms = self.player.get_length() if hasattr(self, "player") else -1
        duration = length_ms / 1000.0 if length_ms and length_ms > 0 else 0.0

        sponsorblock = _sponsorblock()
        categories = list(sponsorblock.CATEGORIES)
        dialog = wx.SingleChoiceDialog(
            self,
            _("Trecho de {start} a {end}. Categoria:").format(
                start=self._format_sponsorblock_time(start), end=self._format_sponsorblock_time(end)
            ),
            _("Enviar trecho ao SponsorBlock"),
            [sponsorblock.category_label(category) for category in categories],
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            category = categories[dialog.GetSelection()]
        finally:
            dialog.Destroy()

        user_id = self._sponsorblock_user_id()
        self._sponsorblock_marked_start = None

        def worker():
            try:
                sponsorblock.submit_segment(video_id, user_id, start, end, category, duration)
                message = _("Trecho enviado ao SponsorBlock. Obrigado por ajudar!")
            except sponsorblock.SponsorBlockError as exc:
                message = str(exc)
            wx.CallAfter(self._announce, message)

        self._announce(_("Enviando o trecho..."))
        threading.Thread(target=worker, daemon=True, name="sponsorblock-submit").start()
        return True

    def _vote_on_last_sponsorblock_segment(self, upvote):
        if not self._sponsorblock_contribution_target():
            return False
        segment = self._last_sponsorblock_segment_here()
        if segment is None or not segment.uuid:
            self._announce(_("Nenhum trecho do SponsorBlock passou nesta mídia para votar."))
            return False
        sponsorblock = _sponsorblock()
        user_id = self._sponsorblock_user_id()

        def worker():
            try:
                sponsorblock.vote_segment(segment.uuid, user_id, upvote)
                message = _("Voto registrado. Obrigado por ajudar!")
            except sponsorblock.SponsorBlockError as exc:
                message = str(exc)
            wx.CallAfter(self._announce, message)

        threading.Thread(target=worker, daemon=True, name="sponsorblock-vote").start()
        return True

    def on_sponsorblock_vote_up(self, _event):
        return self._vote_on_last_sponsorblock_segment(True)

    def on_sponsorblock_vote_down(self, _event):
        return self._vote_on_last_sponsorblock_segment(False)
