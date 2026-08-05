from ...i18n import _
import wx

from player.youtube_music.models import YOUTUBE_MUSIC_SCREEN_ID
from player.youtube_music.playlists import is_youtube_music_media

from ...playlists import ScreenTabState
from ._helpers import (
    _create_youtube_music_service,
    _youtube_music_has_saved_auth,
    _youtube_music_tab_panel_class,
)


class LibraryStateMixin:
    _YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE = 25
    _YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT = 30
    _YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE_MIN = 5
    _YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE_MAX = 200
    _YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT_MIN = 5
    _YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT_MAX = 200

    def _youtube_music_library_page_size(self):
        try:
            value = int(getattr(self.settings, "youtube_music_library_page_size", self._YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE))
        except (TypeError, ValueError):
            value = self._YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE
        return max(
            self._YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE_MIN,
            min(self._YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE_MAX, value),
        )

    def _youtube_music_home_discovery_limit(self):
        try:
            value = int(
                getattr(self.settings, "youtube_music_home_discovery_limit", self._YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT)
            )
        except (TypeError, ValueError):
            value = self._YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT
        return max(
            self._YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT_MIN,
            min(self._YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT_MAX, value),
        )

    def _get_youtube_music_service(self):
        self._configure_youtube_music_dependency_management()
        service = getattr(self, "_youtube_music_service", None)
        if service is None:
            service = _create_youtube_music_service()
            self._youtube_music_service = service
        return service

    def _get_youtube_music_media_feedback_status(self, media_path, force_refresh=False):
        normalized_media_path = str(media_path or "").strip()
        if not normalized_media_path or not is_youtube_music_media(normalized_media_path):
            return None

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            return None

        try:
            return service.get_media_feedback_status(normalized_media_path, force_refresh=force_refresh)
        except Exception:
            return None

    def _selected_youtube_music_media_paths_to_rate(self, media_paths, rating):
        normalized_rating = str(rating or "").strip().upper()
        if normalized_rating not in {"LIKE", "DISLIKE"}:
            return []

        rateable_paths = []
        for media_path in media_paths or []:
            normalized_media_path = str(media_path or "").strip()
            if not normalized_media_path or not is_youtube_music_media(normalized_media_path):
                continue

            current_status = self._get_youtube_music_media_feedback_status(normalized_media_path)
            if current_status == normalized_rating:
                continue

            rateable_paths.append(normalized_media_path)

        return rateable_paths

    def _youtube_music_account_name(self):
        return str(getattr(self, "_youtube_music_connected_account_name", "") or "").strip()

    def _set_youtube_music_account_name(self, account_name):
        self._youtube_music_connected_account_name = str(account_name or "").strip()

    def _youtube_music_library_cache(self):
        return list(getattr(self, "_youtube_music_library_playlists", []))

    def _youtube_music_search_results(self):
        return list(getattr(self, "_youtube_music_search_results_cache", []))

    def _youtube_music_search_summary(self):
        return str(getattr(self, "_youtube_music_search_summary_message", "") or "").strip()

    def _set_youtube_music_library_cache(self, playlists, *, status_message=None, has_more_playlists=None):
        self._youtube_music_library_playlists = list(playlists or [])
        self._youtube_music_library_loaded = True
        if status_message is not None:
            self._youtube_music_library_status_message = str(status_message or "").strip()
        if has_more_playlists is not None:
            self._youtube_music_library_more_playlists_available = bool(has_more_playlists)
        self._refresh_youtube_music_screen_later()

    def _youtube_music_library_has_more_playlists(self):
        return bool(getattr(self, "_youtube_music_library_more_playlists_available", False))

    def _youtube_music_current_library_limit(self):
        return int(
            getattr(
                self,
                "_youtube_music_library_limit",
                self._youtube_music_library_page_size(),
            )
        )

    def _set_youtube_music_search_results(self, search_results, *, search_summary=None, status_message=None):
        self._youtube_music_search_results_cache = list(search_results or [])
        if search_summary is not None:
            self._youtube_music_search_summary_message = str(search_summary or "").strip()
        if status_message is not None:
            self._youtube_music_library_status_message = str(status_message or "").strip()
        self._refresh_youtube_music_screen_later()

    def _clear_youtube_music_library_cache(self, *, loaded=False, status_message=None):
        self._youtube_music_library_playlists = []
        self._youtube_music_library_loaded = bool(loaded)
        self._youtube_music_library_more_playlists_available = False
        self._youtube_music_library_limit = self._youtube_music_library_page_size()
        if status_message is not None:
            self._youtube_music_library_status_message = str(status_message or "").strip()
        self._refresh_youtube_music_screen_later()

    def _youtube_music_library_has_loaded(self):
        return bool(getattr(self, "_youtube_music_library_loaded", False))

    def _youtube_music_status_message(self):
        return str(getattr(self, "_youtube_music_library_status_message", "") or "").strip()

    def _create_youtube_music_page(self, parent):
        panel_class = _youtube_music_tab_panel_class()
        return panel_class(
            parent,
            on_connect=self._on_youtube_music_connect_button,
            on_disconnect=self._on_youtube_music_disconnect_button,
            on_refresh_library=self._on_youtube_music_refresh_button,
            on_open_selected=self._on_youtube_music_open_selected_button,
            on_create_playlist=self._on_youtube_music_create_playlist_button,
            on_delete_playlist=self._on_youtube_music_delete_playlist_button,
            on_open_manual_source=self._on_youtube_music_open_manual_source_button,
            on_search=self._on_youtube_music_search_button,
            on_open_search_result=self._on_youtube_music_open_search_result_button,
            on_save_search_result=self._on_youtube_music_save_search_result_button,
            on_add_search_results_to_current_playlist=self._add_youtube_music_search_results_to_current_playlist,
            on_show_search_actions_menu=self._on_youtube_music_show_search_actions_menu,
            on_load_more_playlists=self._on_youtube_music_load_more_playlists_button,
            on_show_charts=self._on_youtube_music_charts_button,
            on_show_moods=self._on_youtube_music_moods_button,
            on_show_liked=self._on_youtube_music_liked_button,
            on_show_history=self._on_youtube_music_history_button,
            on_announce=self._announce,
        )

    def _get_youtube_music_panel(self):
        if not hasattr(self, "playlists") or not hasattr(self, "notebook"):
            return None

        panel_class = _youtube_music_tab_panel_class()

        for index, state in enumerate(self.playlists):
            if isinstance(state, ScreenTabState) and state.screen_id == YOUTUBE_MUSIC_SCREEN_ID:
                page = self.notebook.GetPage(index)
                if isinstance(page, panel_class):
                    return page

        return None

    def _refresh_youtube_music_screen_later(self):
        wx.CallAfter(self._refresh_youtube_music_screen)

    def _refresh_youtube_music_screen(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return

        service = getattr(self, "_youtube_music_service", None)
        connected = service.has_saved_browser_auth() if service is not None else _youtube_music_has_saved_auth()
        panel.update_view(
            connected=connected,
            account_name=self._youtube_music_account_name(),
            playlists=self._youtube_music_library_cache(),
            operation_in_progress=(
                self._is_youtube_music_operation_in_progress()
                or bool(getattr(self, "_youtube_music_dependency_update_in_progress", False))
            ),
            status_message=self._youtube_music_status_message(),
            search_results=self._youtube_music_search_results(),
            search_summary=self._youtube_music_search_summary(),
            has_more_playlists=self._youtube_music_library_has_more_playlists(),
        )

    def _playlist_summary_by_id(self, playlist_id):
        normalized_playlist_id = str(playlist_id or "").strip()
        if not normalized_playlist_id:
            return None

        for playlist in self._youtube_music_library_cache():
            if playlist.playlist_id == normalized_playlist_id:
                return playlist

        return None

    def _youtube_music_integration_enabled(self):
        return bool(getattr(self.settings, "youtube_music_manage_dependencies", False))

    def _announce_youtube_music_integration_disabled(self):
        message = _(
            "A integração com YouTube Music e YouTube está desativada. "
            "Ative essa opção em Preferências, na aba Recursos adicionais."
        )
        self._youtube_music_library_status_message = message
        self._refresh_youtube_music_screen_later()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        self._announce(message)
        return False

    def _refresh_youtube_music_menu_state(self):
        integration_enabled = self._youtube_music_integration_enabled()
        has_saved_auth = _youtube_music_has_saved_auth()
        operation_in_progress = (
            self._is_youtube_music_operation_in_progress()
            or bool(getattr(self, "_youtube_music_dependency_update_in_progress", False))
        )

        youtube_music_menu = getattr(self, "youtube_music_menu", None)
        login_item = None
        disconnect_item = None
        open_playlist_item = None
        refresh_item = None
        if youtube_music_menu is not None:
            login_item = youtube_music_menu.FindItemById(self.menu_youtube_music_login_id)
            disconnect_item = youtube_music_menu.FindItemById(self.menu_youtube_music_disconnect_id)
            open_playlist_item = youtube_music_menu.FindItemById(getattr(self, "menu_open_youtube_music_id", wx.ID_ANY))
            refresh_item = youtube_music_menu.FindItemById(getattr(self, "menu_youtube_music_refresh_library_id", wx.ID_ANY))
        open_tab_item = None
        if hasattr(self, "view_menu"):
            open_tab_item = self.view_menu.FindItemById(getattr(self, "menu_open_youtube_music_id", wx.ID_ANY))
        playback_menu = getattr(self, "playback_menu", None)
        file_menu = getattr(self, "file_menu", None)

        if login_item is not None:
            login_item.SetItemLabel(
                (_("Atualizar autenticação...") if has_saved_auth else _("Conectar &conta..."))
                if integration_enabled
                else _("Ativar integração nas &Preferências...")
            )
            login_item.Enable(integration_enabled and not operation_in_progress)

        if disconnect_item is not None:
            disconnect_item.Enable(integration_enabled and has_saved_auth and not operation_in_progress)

        if open_playlist_item is not None:
            open_playlist_item.SetItemLabel(
                _("Abrir &central do YouTube Music...\tCtrl+Shift+Y")
                if integration_enabled
                else _("Ative a integração do YouTube Music nas &Preferências...\tCtrl+Shift+Y")
            )
            open_playlist_item.Enable(integration_enabled and not operation_in_progress)

        if refresh_item is not None:
            refresh_item.Enable(integration_enabled and has_saved_auth and not operation_in_progress)

        if open_tab_item is not None:
            open_tab_item.SetItemLabel(
                _("YouTube &Music por aba\tCtrl+Shift+Y")
                if integration_enabled
                else _("YouTube &Music por aba (ative em Preferências)\tCtrl+Shift+Y")
            )
            open_tab_item.Enable(integration_enabled and not operation_in_progress)

        if playback_menu is not None:
            for item_id in (
                getattr(self, "menu_previous_track_id", None),
                getattr(self, "menu_next_track_id", None),
                getattr(self, "menu_toggle_shuffle_id", None),
                getattr(self, "menu_cycle_repeat_id", None),
                getattr(self, "menu_add_to_youtube_playlist_id", None),
            ):
                if item_id is None:
                    continue
                menu_item = playback_menu.FindItemById(item_id)
                if menu_item is not None:
                    menu_item.Enable(not operation_in_progress)

        if file_menu is not None:
            close_media_item = file_menu.FindItemById(getattr(self, "menu_close_media_id", None))
            if close_media_item is not None:
                close_media_item.Enable(not operation_in_progress)

        self._refresh_youtube_music_screen_later()
