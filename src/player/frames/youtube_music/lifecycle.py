from ...i18n import _, ngettext
import os
import threading

import wx

from player.youtube_music.models import YOUTUBE_MUSIC_SCREEN_ID
from player.youtube_music.playlists import (
    extract_playlist_id_from_source,
    extract_playlist_id_from_text,
    extract_video_id_from_text,
)

from ...playlists import PlaylistState
from ._helpers import _youtube_music_has_saved_auth


class LifecycleMixin:
    def _remember_restored_youtube_music_states(self, restored_states):
        pending_states = []
        for state in restored_states or []:
            if self._youtube_music_state_needs_label_refresh(state):
                pending_states.append(state)
        self._restored_youtube_music_states_pending_refresh = pending_states

    def _youtube_music_state_needs_label_refresh(self, state):
        if not isinstance(state, PlaylistState) or not state.items:
            return False

        if not extract_playlist_id_from_source(getattr(state, "source_path", None)):
            return False

        if len(state.browser_item_labels) != len(state.items):
            return True

        return all(
            str(label or "").strip() == (os.path.basename(item) or item)
            for item, label in zip(state.items, state.browser_item_labels)
        )

    def _merge_restored_youtube_music_labels(self, state, playlist_content):
        if not isinstance(state, PlaylistState) or not state.items:
            return False

        labels_by_url = {}
        for item_url, item_label in zip(playlist_content.item_urls, playlist_content.item_labels):
            normalized_label = str(item_label or "").strip()
            if not normalized_label:
                continue
            labels_by_url.setdefault(item_url, []).append(normalized_label)

        updated_labels = []
        for index, item in enumerate(state.items):
            existing_label = state.browser_item_labels[index] if index < len(state.browser_item_labels) else ""
            matching_labels = labels_by_url.get(item)
            if matching_labels:
                updated_labels.append(matching_labels.pop(0))
                continue

            normalized_existing_label = str(existing_label or "").strip()
            updated_labels.append(normalized_existing_label or (os.path.basename(item) or item))

        if updated_labels == state.browser_item_labels:
            return False

        state.browser_item_labels = updated_labels
        state.refresh_browser_item_labels()
        return True

    def _refresh_pending_restored_youtube_music_tabs(self):
        pending_states = [
            state
            for state in getattr(self, "_restored_youtube_music_states_pending_refresh", [])
            if self._youtube_music_state_needs_label_refresh(state)
        ]
        if not pending_states:
            self._restored_youtube_music_states_pending_refresh = []
            return False

        service = self._get_youtube_music_service()

        def worker():
            refreshed_states = []
            for state in pending_states:
                playlist_id = extract_playlist_id_from_source(getattr(state, "source_path", None))
                if not playlist_id:
                    continue

                try:
                    playlist_content = service.get_playlist_content(
                        playlist_id,
                        fallback_title=state.title,
                    )
                except Exception:
                    continue

                refreshed_states.append((state, playlist_content))

            return refreshed_states

        def on_success(refreshed_states):
            self._restored_youtube_music_states_pending_refresh = []
            active_state = self._get_active_playlist_state()
            refreshed_visible_state = False

            for state, playlist_content in refreshed_states:
                if self._merge_restored_youtube_music_labels(state, playlist_content):
                    if state is active_state:
                        refreshed_visible_state = True

            if refreshed_visible_state:
                self._update_title()
                self._refresh_playlist_browser()
            self._auto_load_youtube_music_library_if_needed()

        def on_error(_error):
            self._restored_youtube_music_states_pending_refresh = []
            self._auto_load_youtube_music_library_if_needed()

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_open_youtube_music(self, _event):
        if not self._youtube_music_integration_enabled():
            return self._announce_youtube_music_integration_disabled()

        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            message = _(
                "Os recursos adicionais do YouTube Music ainda estão sendo atualizados. "
                "Aguarde a conclusão para abrir a central."
            )
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            self._announce(message)
            return False

        # Building the panel for the first time can take a moment (widget
        # construction). Announce as early as possible so screen-reader users
        # know the shortcut was registered.
        service = self._get_youtube_music_service()
        if (
            service.has_saved_browser_auth()
            and not self._youtube_music_library_has_loaded()
        ):
            if getattr(self, "_youtube_music_dependency_update_in_progress", False):
                self._announce(
                    _("Atualizando recursos adicionais do YouTube Music. A biblioteca será carregada em seguida.")
                )
            else:
                self._announce(
                    _("Carregando conta e biblioteca do YouTube Music. Por favor, aguarde.")
                )

        self._open_screen_tab(
            YOUTUBE_MUSIC_SCREEN_ID,
            "YouTube Music",
            self._create_youtube_music_page,
            select=True,
            activation_message=_(
                "Aba YouTube Music. Use os controles para conectar a conta, atualizar a biblioteca, pesquisar "
                "no catálogo e abrir playlists, mixes, músicas ou vídeos."
            ),
            on_activate=self._refresh_youtube_music_screen_later,
            on_close=self._on_youtube_music_screen_closed,
        )

        # Library auto-load. Dependency auto-update no longer runs here: it
        # was moved to startup so it can finish (or fail) before the user even
        # opens the tab, instead of stalling tab opening for several seconds.
        self._auto_load_youtube_music_library_if_needed()

    def _auto_load_youtube_music_library_if_needed(self):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            return
        if self._youtube_music_library_has_loaded():
            return

        # If the dependency auto-update is still running, don't touch the
        # YouTube Music runtime yet. The dep update's on_success path will
        # trigger this auto-load when it finishes.
        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            self._youtube_music_library_status_message = (
                _("Atualizando recursos adicionais do YouTube Music. A biblioteca será carregada em seguida.")
            )
            self._refresh_youtube_music_screen_later()
            return

        # If another YouTube Music background task is already running (typically
        # the startup _verify_youtube_music_connection account-name fetch),
        # don't drop the auto-load: queue it so the library refresh fires as
        # soon as the running task finishes.
        if self._is_youtube_music_operation_in_progress():
            self._queue_youtube_music_post_operation_callback(
                self._auto_load_youtube_music_library_if_needed
            )
            return

        self.on_refresh_youtube_music_library(None, announce=False)

    def _continue_youtube_music_startup_after_dependency_setup(self):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            return False

        self._prewarm_youtube_music_client()
        if getattr(self, "_restored_youtube_music_states_pending_refresh", None):
            if self._refresh_pending_restored_youtube_music_tabs():
                return True

        self._auto_load_youtube_music_library_if_needed()
        return True

    def _on_youtube_music_connect_button(self):
        self.on_connect_youtube_music(None)

    def _on_youtube_music_disconnect_button(self):
        self.on_disconnect_youtube_music(None)

    def _on_youtube_music_refresh_button(self):
        self.on_refresh_youtube_music_library(None, announce=True)

    def _on_youtube_music_open_selected_button(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return

        playlist_id = panel.get_selected_playlist_id()
        if not playlist_id:
            self._announce(_("Selecione uma playlist ou mix do YouTube Music para abrir."))
            return

        playlist = self._playlist_summary_by_id(playlist_id)
        if playlist is None:
            self._announce(_("A playlist selecionada não está mais disponível na lista atual."))
            return

        self._load_youtube_music_playlist(playlist)

    def _on_youtube_music_open_manual_source_button(self):
        panel = self._get_youtube_music_panel()
        manual_source = panel.get_manual_source() if panel is not None else ""
        if not manual_source:
            self._announce(_("Cole um link de playlist, mix ou vídeo do YouTube Music/YouTube para abrir."))
            return

        playlist_id = extract_playlist_id_from_text(manual_source)
        if playlist_id:
            playlist = self._playlist_summary_by_id(playlist_id)
            fallback_title = playlist.title if playlist is not None else f"Playlist {playlist_id}"
            self._load_youtube_music_playlist_by_id(playlist_id, fallback_title=fallback_title)
            return

        video_id = extract_video_id_from_text(manual_source)
        if video_id:
            self._open_youtube_music_manual_video(manual_source, video_id)
            return

        wx.MessageBox(
            _("Informe um link válido de playlist, mix ou vídeo do YouTube Music/YouTube."),
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _open_youtube_music_manual_video(self, video_url, video_id):
        title = _("Vídeo do YouTube ({id})").format(id=video_id)
        self._open_prepared_media_playlist(
            [video_url],
            title,
            browser_item_labels=[title],
            source_path=video_url,
            announce_message=_("Vídeo do YouTube aberto: {title}.").format(title=title),
        )

    def _on_youtube_music_search_button(self):
        self.on_search_youtube_music(None)

    def _on_youtube_music_charts_button(self, panel, anchor_window=None):
        self.on_show_youtube_music_charts(panel, anchor_window)

    def _on_youtube_music_moods_button(self, panel, anchor_window=None):
        self.on_show_youtube_music_moods(panel, anchor_window)

    def _on_youtube_music_liked_button(self):
        self.on_show_youtube_music_liked()

    def _on_youtube_music_history_button(self):
        self.on_show_youtube_music_history()

    def _on_youtube_music_open_search_result_button(self):
        self._open_youtube_music_search_results_in_new_playlist()

    def _on_youtube_music_save_search_result_button(self):
        self._save_youtube_music_search_result()

    def _initialize_youtube_music_startup_state(self):
        # Avoid an eager network round trip on startup just to fetch the
        # account name. The account is validated lazily when the user opens
        # the YouTube Music tab (the library refresh already authenticates
        # and updates the displayed account name). Restored YouTube Music
        # playlist tabs that need their item labels refreshed are still
        # handled here, since their refresh cannot wait for user action.
        self._refresh_youtube_music_menu_state()
        if (
            bool(getattr(self.settings, "youtube_music_manage_dependencies", False))
            and bool(getattr(self.settings, "youtube_music_use_youtubejs", True))
        ):
            from player.youtube_music.youtubejs_runtime import youtubejs_dependencies_available

            if not youtubejs_dependencies_available():
                if self._start_youtube_music_dependency_update(
                    force_update=False,
                    manual=False,
                    announce_start=True,
                ):
                    return
        if not _youtube_music_has_saved_auth():
            return
        service = self._get_youtube_music_service()

        # If a dependency auto-update is due, kick it off now (in its own
        # background thread, no operation lock). It must run BEFORE the
        # pre-warm, otherwise pre-warm would import ytmusicapi and keep the
        # package loaded while an update is trying to refresh its files on
        # Windows. When a dep update kicks off, the pre-warm is deferred and
        # will run from the dep update's on_success.
        dep_update_started = self._maybe_auto_update_youtube_music_dependencies()
        if dep_update_started:
            return

        self._continue_youtube_music_startup_after_dependency_setup()

    def _prewarm_youtube_music_client(self):
        if getattr(self, "_youtube_music_client_prewarm_started", False):
            return
        self._youtube_music_client_prewarm_started = True
        service = self._get_youtube_music_service()

        def warm():
            try:
                client = service.get_client()
                # Touching base_headers forces the visitor-id round trip
                # that ytmusicapi otherwise defers until the first real call.
                _ = getattr(client, "base_headers", None)
            except Exception:
                pass

        threading.Thread(target=warm, daemon=True, name="ytmusic-prewarm").start()

    def _verify_youtube_music_connection(self):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            self._refresh_youtube_music_menu_state()
            return

        def worker():
            return service.get_connected_account_name()

        def on_success(account_name):
            self._set_youtube_music_account_name(account_name)
            if account_name:
                self._youtube_music_library_status_message = _("Conta conectada: {name}.").format(name=account_name)
            self._refresh_youtube_music_menu_state()
            if account_name:
                self._announce(_("YouTube Music reconectado: {name}.").format(name=account_name))
                if hasattr(self, "_set_status_message"):
                    self._set_status_message(_("YouTube Music conectado como {name}.").format(name=account_name))
            self._refresh_pending_restored_youtube_music_tabs()

        def on_error(_error):
            self._handle_youtube_music_auth_validation_failure(service, _error, announce=False)

        self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_open_youtube_music_playlist(self, _event):
        self.on_open_youtube_music(None)
        if self._get_youtube_music_service().has_saved_browser_auth():
            self.on_refresh_youtube_music_library(None, announce=False)

    def _load_youtube_music_playlist(self, selected_playlist):
        self._load_youtube_music_playlist_by_id(
            selected_playlist.playlist_id,
            fallback_title=selected_playlist.title,
            require_auth=True,
        )

    def _load_youtube_music_playlist_by_id(self, playlist_id, *, fallback_title="", require_auth=False):
        service = self._get_youtube_music_service()
        normalized_playlist_id = str(playlist_id or "").strip()
        if not normalized_playlist_id:
            return False

        display_title = str(fallback_title or normalized_playlist_id).strip() or normalized_playlist_id
        self._announce(_("Carregando playlist do YouTube Music: {title}.").format(title=display_title))

        def worker():
            return service.get_playlist_content(
                normalized_playlist_id,
                fallback_title=display_title,
                require_auth=require_auth,
            )

        def on_success(playlist_content):
            self._refresh_youtube_music_menu_state()
            if not playlist_content.item_urls:
                wx.MessageBox(
                    _("A playlist selecionada não tem faixas reproduzíveis no momento."),
                    "YouTube Music",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
                return

            self._open_prepared_media_playlist(
                playlist_content.item_urls,
                playlist_content.title,
                browser_item_labels=playlist_content.item_labels,
                source_path=service.build_playlist_source(normalized_playlist_id),
                announce_message=ngettext(
                    "Playlist do YouTube Music carregada: {title}. {count} item.",
                    "Playlist do YouTube Music carregada: {title}. {count} itens.",
                    len(playlist_content.item_urls),
                ).format(title=playlist_content.title, count=len(playlist_content.item_urls)),
            )

        def on_error(exc):
            service.clear_client_cache()
            self._refresh_youtube_music_menu_state()
            wx.MessageBox(
                _("Não foi possível carregar a playlist do YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
