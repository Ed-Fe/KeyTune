import os
import shutil
import subprocess
import sys
import threading
import time

import wx

from player.youtube_music.auth import get_browser_auth_file_path, sanitize_sensitive_text
from player.youtube_music.dialog import (
    YouTubeMusicBrowserAuthDialog,
    YouTubeMusicCreatePlaylistDialog,
    YouTubeMusicJavascriptRuntimeDialog,
)
from player.youtube_music.models import (
    YOUTUBE_MUSIC_SCREEN_ID,
    get_chart_country_groups,
    get_chart_country_label,
    get_search_scope_option,
)
from player.youtube_music.playlists import (
    extract_playlist_id_from_source,
    extract_playlist_id_from_text,
    extract_video_id_from_text,
    is_watch_playlist_id,
    is_youtube_music_media,
)

from ..playlists import PlaylistState, ScreenTabState


def _configure_youtube_dependency_management(*, managed_install_enabled, auto_update_enabled, prefer_nightly_yt_dlp):
    from player.youtube_music.dependencies import configure_youtube_dependency_management

    return configure_youtube_dependency_management(
        managed_install_enabled=managed_install_enabled,
        auto_update_enabled=auto_update_enabled,
        prefer_nightly_yt_dlp=prefer_nightly_yt_dlp,
    )


def _find_all_available_javascript_runtimes():
    from player.youtube_music.yt_dlp_runtime import find_all_available_javascript_runtimes

    return find_all_available_javascript_runtimes()


def _install_or_update_youtube_dependencies(*, force, include_prerelease):
    from player.youtube_music.dependencies import install_or_update_youtube_dependencies

    return install_or_update_youtube_dependencies(
        force=force,
        include_prerelease=include_prerelease,
    )


def _is_youtube_dependency_auto_update_due(last_update_epoch, *, interval_hours):
    from player.youtube_music.dependencies import is_youtube_dependency_auto_update_due

    return is_youtube_dependency_auto_update_due(last_update_epoch, interval_hours=interval_hours)


def _is_missing_javascript_runtime_error_message(error_message):
    from player.youtube_music.streams import is_missing_javascript_runtime_error_message

    return is_missing_javascript_runtime_error_message(error_message)


def _youtube_dependencies_available():
    from player.youtube_music.dependencies import youtube_dependencies_available

    return youtube_dependencies_available()


def _create_youtube_music_service():
    from player.youtube_music.service import YouTubeMusicService

    return YouTubeMusicService()


def _youtube_music_tab_panel_class():
    from player.youtube_music.panel import YouTubeMusicTabPanel

    return YouTubeMusicTabPanel


def _youtube_music_has_saved_auth():
    return os.path.isfile(get_browser_auth_file_path())


def find_all_available_javascript_runtimes():
    return _find_all_available_javascript_runtimes()


def is_missing_javascript_runtime_error_message(error_message):
    return _is_missing_javascript_runtime_error_message(error_message)


class FrameYouTubeMusicMixin:
    # Sentinel returned by the playlist picker when the user chooses to create
    # a brand-new playlist instead of selecting an existing one.
    _CREATE_NEW_PLAYLIST_CHOICE = object()
    _YOUTUBE_MUSIC_BACKGROUND_TASK_TIMEOUT_MS = 45000
    _YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE = 25
    _YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT = 30
    _YOUTUBE_MUSIC_LIKED_SONGS_LIMIT = 200
    _YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE_MIN = 5
    _YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE_MAX = 200
    _YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT_MIN = 5
    _YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT_MAX = 200
    _YOUTUBE_MUSIC_JS_RUNTIME_DENO_URL = "https://deno.com/"
    _YOUTUBE_MUSIC_JS_RUNTIME_NODE_URL = "https://nodejs.org/"
    _YOUTUBE_MUSIC_JS_RUNTIME_BUN_URL = "https://bun.sh/"
    _YOUTUBE_MUSIC_JS_RUNTIME_GUIDE_URL = "https://github.com/yt-dlp/yt-dlp/wiki/EJS"
    _YOUTUBE_MUSIC_JS_RUNTIME_DENO_WINGET_ID = "DenoLand.Deno"
    _YOUTUBE_MUSIC_JS_RUNTIME_NODE_WINGET_ID = "OpenJS.NodeJS.LTS"
    _YOUTUBE_MUSIC_JS_RUNTIME_BUN_WINGET_ID = "Oven-sh.Bun"

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

    def _open_external_url(self, url, *, failure_message):
        normalized_url = str(url or "").strip()
        if not normalized_url:
            return False

        try:
            launched = wx.LaunchDefaultBrowser(normalized_url)
        except Exception:
            launched = False

        if launched:
            return True

        wx.MessageBox(
            failure_message,
            "YouTube Music",
            wx.OK | wx.ICON_ERROR,
            self,
        )
        return False

    def _launch_youtube_music_javascript_runtime_install(self, package_id, runtime_label):
        normalized_package_id = str(package_id or "").strip()
        normalized_runtime_label = str(runtime_label or "").strip() or "runtime JavaScript"
        if not normalized_package_id:
            return False

        powershell_command = (
            f'winget install --id "{normalized_package_id}" -e --accept-source-agreements'
        )
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoExit",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    powershell_command,
                ]
            )
        except OSError:
            wx.MessageBox(
                f"Não foi possível abrir a instalação automática de {normalized_runtime_label}.",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        self._announce(
            f"A instalação de {normalized_runtime_label} foi aberta em uma nova janela."
        )
        if hasattr(self, "_set_status_message"):
            self._set_status_message(
                f"Instalação de {normalized_runtime_label} aberta no Windows Package Manager.",
            )
        return True

    def _show_youtube_javascript_runtime_dialog(self):

        winget_available = bool(shutil.which("winget"))
        dialog = YouTubeMusicJavascriptRuntimeDialog(self, winget_available=winget_available)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return True
            selected_action = dialog.get_selected_action()
        finally:
            dialog.Destroy()

        install_actions = {
            "install-deno": (
                self._YOUTUBE_MUSIC_JS_RUNTIME_DENO_WINGET_ID,
                "Deno",
            ),
            "install-node": (
                self._YOUTUBE_MUSIC_JS_RUNTIME_NODE_WINGET_ID,
                "Node.js",
            ),
            "install-bun": (
                self._YOUTUBE_MUSIC_JS_RUNTIME_BUN_WINGET_ID,
                "Bun",
            ),
        }
        url_actions = {
            "open-deno": self._YOUTUBE_MUSIC_JS_RUNTIME_DENO_URL,
            "open-node": self._YOUTUBE_MUSIC_JS_RUNTIME_NODE_URL,
            "open-bun": self._YOUTUBE_MUSIC_JS_RUNTIME_BUN_URL,
            "open-guide": self._YOUTUBE_MUSIC_JS_RUNTIME_GUIDE_URL,
        }

        if selected_action in install_actions:
            package_id, runtime_label = install_actions[selected_action]
            self._launch_youtube_music_javascript_runtime_install(package_id, runtime_label)
            return True

        if selected_action in url_actions:
            self._open_external_url(
                url_actions[selected_action],
                failure_message="Não foi possível abrir o navegador para mostrar a página solicitada.",
            )
            return True

        return True

    def _youtube_javascript_runtime_available(self):
        return bool(find_all_available_javascript_runtimes())

    def _prompt_for_missing_youtube_javascript_runtime(self):
        if self._youtube_javascript_runtime_available():
            return False
        return bool(self._show_youtube_javascript_runtime_dialog())

    def _handle_youtube_javascript_runtime_error(self, error_message):
        if not is_missing_javascript_runtime_error_message(error_message):
            return False
        return bool(self._show_youtube_javascript_runtime_dialog())

    def _is_youtube_music_operation_in_progress(self):
        return bool(getattr(self, "_youtube_music_operation_in_progress", False))

    def _is_track_navigation_blocked_by_youtube_music(self):
        return self._is_youtube_music_operation_in_progress()

    def _announce_track_navigation_blocked_by_youtube_music(self):
        self._announce(
            "Aguarde o término da operação do YouTube Music antes de ir para a faixa anterior ou próxima."
        )

    def _play_windows_youtube_music_blocked_sound(self):
        if not sys.platform.startswith("win"):
            return

        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _block_sensitive_action_during_youtube_music(self, action_kind):
        if not self._is_youtube_music_operation_in_progress():
            return False

        messages = {
            "track-navigation": (
                "Aguarde o término da operação do YouTube Music antes de ir para a faixa anterior ou próxima."
            ),
            "track-selection": (
                "Aguarde o término da operação do YouTube Music antes de trocar a faixa atual."
            ),
            "playback-order": (
                "Aguarde o término da operação do YouTube Music antes de alterar repetição, embaralhamento ou a ordem da playlist."
            ),
            "close-media": (
                "Aguarde o término da operação do YouTube Music antes de fechar ou remover a mídia atual."
            ),
        }

        if action_kind == "track-navigation":
            self._play_windows_youtube_music_blocked_sound()

        self._announce(messages.get(action_kind, "Aguarde o término da operação do YouTube Music."))
        return True

    def _configure_youtube_music_dependency_management(self):
        _configure_youtube_dependency_management(
            managed_install_enabled=bool(getattr(self.settings, "youtube_music_manage_dependencies", False)),
            auto_update_enabled=bool(getattr(self.settings, "youtube_music_auto_update_dependencies", True)),
            prefer_nightly_yt_dlp=bool(getattr(self.settings, "youtube_music_use_nightly_yt_dlp", False)),
        )

    def _youtube_music_dependency_update_interval_hours(self):
        try:
            interval_hours = int(getattr(self.settings, "youtube_music_dependency_update_interval_hours", 24))
        except (TypeError, ValueError):
            interval_hours = 24
        return max(1, min(720, interval_hours))

    def _youtube_music_dependency_versions_text(self, versions):
        normalized_versions = dict(versions or {})
        if not normalized_versions:
            return "versão indisponível"

        ordered_labels = []
        for package_name in sorted(normalized_versions.keys()):
            package_version = str(normalized_versions.get(package_name) or "desconhecida").strip() or "desconhecida"
            ordered_labels.append(f"{package_name} {package_version}")

        return ", ".join(ordered_labels)

    def _format_youtube_music_error_detail(self, error):
        normalized_error_detail = sanitize_sensitive_text(error, max_length=2000)
        if normalized_error_detail:
            return normalized_error_detail
        return "Falha desconhecida."

    def _start_youtube_music_dependency_update(self, *, force_update, manual, announce_start=False):
        self._configure_youtube_music_dependency_management()
        if not bool(getattr(self.settings, "youtube_music_manage_dependencies", False)):
            return False

        # The dependency update runs outside the UI thread and can touch both
        # the Python-side ytmusicapi package and the managed yt-dlp executable.
        # We deliberately bypass the YouTube Music operation lock used by API
        # calls so startup follow-up work can resume as soon as the update finishes.
        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            return False
        self._youtube_music_dependency_update_in_progress = True
        self._refresh_youtube_music_menu_state()

        if announce_start:
            status_message = (
                "Atualizando os recursos adicionais do YouTube Music. "
                "A central ficará disponível quando a atualização terminar."
            )
            self._youtube_music_library_status_message = status_message
            self._refresh_youtube_music_screen_later()
            if hasattr(self, "_set_status_message"):
                self._set_status_message(status_message, auto_clear_ms=0)
            self._announce(status_message)

        def on_success(result):
            self.settings.youtube_music_dependency_last_auto_update_epoch = int(time.time())
            self._save_settings()

            versions_text = self._youtube_music_dependency_versions_text(getattr(result, "versions", {}))
            if getattr(result, "updated", False):
                status_message = f"Recursos adicionais do YouTube Music atualizados ({versions_text})."
            else:
                status_message = f"Recursos adicionais do YouTube Music prontos ({versions_text})."

            self._youtube_music_library_status_message = status_message
            self._refresh_youtube_music_screen_later()
            if hasattr(self, "_set_status_message"):
                self._set_status_message(status_message)
            if manual or getattr(result, "updated", False):
                self._announce(status_message)

            self._continue_youtube_music_startup_after_dependency_setup()

        def on_error(exc):
            status_message = "Não foi possível atualizar automaticamente os recursos adicionais do YouTube Music."
            self._youtube_music_library_status_message = status_message
            self._refresh_youtube_music_screen_later()
            if hasattr(self, "_set_status_message"):
                self._set_status_message(status_message)
            if _youtube_dependencies_available():
                self._continue_youtube_music_startup_after_dependency_setup()
            if manual:
                wx.MessageBox(
                    f"{status_message}\n\nDetalhes: {self._format_youtube_music_error_detail(exc)}",
                    "YouTube Music",
                    wx.OK | wx.ICON_ERROR,
                    self,
                )

        def runner():
            try:
                result = _install_or_update_youtube_dependencies(
                    force=force_update,
                    include_prerelease=bool(
                        getattr(self.settings, "youtube_music_use_nightly_yt_dlp", False)
                    ),
                )
            except Exception as exc:
                wx.CallAfter(self._finish_youtube_music_dependency_update, on_success, on_error, None, exc)
                return
            wx.CallAfter(self._finish_youtube_music_dependency_update, on_success, on_error, result, None)

        threading.Thread(target=runner, daemon=True, name="ytmusic-dep-update").start()
        return True

    def _finish_youtube_music_dependency_update(self, on_success, on_error, result, error):
        self._youtube_music_dependency_update_in_progress = False
        self._refresh_youtube_music_menu_state()
        self._refresh_youtube_music_screen_later()
        if error is not None:
            if callable(on_error):
                on_error(error)
            return
        if callable(on_success):
            on_success(result)

    def _maybe_auto_update_youtube_music_dependencies(self):
        self._configure_youtube_music_dependency_management()
        if not bool(getattr(self.settings, "youtube_music_manage_dependencies", False)):
            return False

        if not bool(getattr(self.settings, "youtube_music_auto_update_dependencies", True)):
            return False

        interval_hours = self._youtube_music_dependency_update_interval_hours()
        last_update_epoch = getattr(self.settings, "youtube_music_dependency_last_auto_update_epoch", 0)
        if not _is_youtube_dependency_auto_update_due(
            last_update_epoch,
            interval_hours=interval_hours,
        ):
            return False

        return self._start_youtube_music_dependency_update(
            force_update=True,
            manual=False,
            announce_start=True,
        )

    def _handle_youtube_music_preferences_change(self, previous_settings):
        self._configure_youtube_music_dependency_management()

        had_managed_dependencies = bool(getattr(previous_settings, "youtube_music_manage_dependencies", False))
        has_managed_dependencies = bool(getattr(self.settings, "youtube_music_manage_dependencies", False))
        if has_managed_dependencies and not had_managed_dependencies:
            self._prompt_for_missing_youtube_javascript_runtime()
            self._youtube_music_library_status_message = "Recursos adicionais do YouTube Music ativados. Preparando dependências..."
            self._refresh_youtube_music_screen_later()
            self._start_youtube_music_dependency_update(force_update=False, manual=True)
            return

        if has_managed_dependencies:
            # If the user toggled the nightly/stable channel, force a fresh
            # managed yt-dlp download so the executable actually switches channel.
            had_nightly = bool(getattr(previous_settings, "youtube_music_use_nightly_yt_dlp", False))
            has_nightly = bool(getattr(self.settings, "youtube_music_use_nightly_yt_dlp", False))
            if had_nightly != has_nightly:
                channel_label = "nightly" if has_nightly else "estável"
                self._youtube_music_library_status_message = (
                    f"Reinstalando yt-dlp na versão {channel_label}..."
                )
                self._refresh_youtube_music_screen_later()
                self._start_youtube_music_dependency_update(force_update=True, manual=True)
                return

            self._maybe_auto_update_youtube_music_dependencies()

    def _on_manual_check_for_additional_updates(self):
        if not bool(getattr(self.settings, "youtube_music_manage_dependencies", False)):
            return False
        return self._start_youtube_music_dependency_update(force_update=True, manual=True, announce_start=True)

    def _get_youtube_music_service(self):
        self._configure_youtube_music_dependency_management()
        service = getattr(self, "_youtube_music_service", None)
        if service is None:
            service = _create_youtube_music_service()
            self._youtube_music_service = service
        return service

    def _get_youtube_music_media_feedback_status(self, media_path):
        normalized_media_path = str(media_path or "").strip()
        if not normalized_media_path or not is_youtube_music_media(normalized_media_path):
            return None

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            return None

        try:
            return service.get_media_feedback_status(normalized_media_path)
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

    def _handle_invalid_youtube_music_auth(self, service, *, announce=True):
        message = "Não foi possível validar a autenticação salva do YouTube Music. Conecte a conta novamente."
        try:
            service.disconnect()
        except Exception:
            service.clear_client_cache()

        self._set_youtube_music_account_name("")
        self._clear_youtube_music_library_cache(
            loaded=False,
            status_message=message,
        )
        self._refresh_youtube_music_menu_state()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        if announce:
            self._announce(message)
        return False

    def _handle_youtube_music_auth_validation_failure(self, service, error, *, announce=True):
        if bool(getattr(error, "should_disconnect", True)):
            return self._handle_invalid_youtube_music_auth(service, announce=announce)

        message = "Não foi possível validar a autenticação salva do YouTube Music agora. Tente novamente em instantes."
        service.clear_client_cache()
        self._youtube_music_library_status_message = message
        self._refresh_youtube_music_screen_later()
        self._refresh_youtube_music_menu_state()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        if announce:
            self._announce(message)
        return False

    def _ensure_youtube_music_authenticated(self):
        service = self._get_youtube_music_service()
        if service.has_saved_browser_auth():
            try:
                return service.validate_saved_authentication()
            except Exception as exc:
                return self._handle_youtube_music_auth_validation_failure(service, exc)

        self.on_connect_youtube_music(None)
        if not service.has_saved_browser_auth():
            return False

        try:
            return service.validate_saved_authentication()
        except Exception as exc:
            return self._handle_youtube_music_auth_validation_failure(service, exc)

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
                ("Atualizar autenticação..." if has_saved_auth else "Conectar &conta...")
                if integration_enabled
                else "Ativar integração nas &Preferências..."
            )
            login_item.Enable(integration_enabled and not operation_in_progress)

        if disconnect_item is not None:
            disconnect_item.Enable(integration_enabled and has_saved_auth and not operation_in_progress)

        if open_playlist_item is not None:
            open_playlist_item.SetItemLabel(
                "Abrir &central do YouTube Music...\tCtrl+Shift+Y"
                if integration_enabled
                else "Ative a integração do YouTube Music nas &Preferências...\tCtrl+Shift+Y"
            )
            open_playlist_item.Enable(integration_enabled and not operation_in_progress)

        if refresh_item is not None:
            refresh_item.Enable(integration_enabled and has_saved_auth and not operation_in_progress)

        if open_tab_item is not None:
            open_tab_item.SetItemLabel(
                "YouTube &Music por aba\tCtrl+Shift+Y"
                if integration_enabled
                else "YouTube &Music por aba (ative em Preferências)\tCtrl+Shift+Y"
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

    def _youtube_music_integration_enabled(self):
        return bool(getattr(self.settings, "youtube_music_manage_dependencies", False))

    def _announce_youtube_music_integration_disabled(self):
        message = (
            "A integração com YouTube Music e YouTube está desativada. "
            "Ative essa opção em Preferências, na aba Recursos adicionais."
        )
        self._youtube_music_library_status_message = message
        self._refresh_youtube_music_screen_later()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        self._announce(message)
        return False

    def _set_youtube_music_operation_state(self, in_progress):
        self._youtube_music_operation_in_progress = bool(in_progress)
        self._refresh_youtube_music_menu_state()

    def _on_youtube_music_screen_closed(self):
        # When the user closes the YouTube Music tab while a background task
        # is still in flight (e.g. library refresh, search, save), detach it:
        # the worker thread will run to completion but its result is ignored
        # because the active task id no longer matches. This prevents the
        # busy cursor and the global "operation in progress" lock (which
        # blocks track navigation, shuffle/repeat and Stop) from staying
        # active until the watchdog timeout fires.
        if not getattr(self, "_youtube_music_operation_in_progress", False):
            return
        self._youtube_music_active_task_id = None
        self._cancel_youtube_music_task_watchdog()
        self._end_youtube_music_busy_state()

    def _cancel_youtube_music_task_watchdog(self):
        watchdog = getattr(self, "_youtube_music_task_watchdog", None)
        self._youtube_music_task_watchdog = None
        if watchdog is not None:
            try:
                watchdog.Stop()
            except Exception:
                pass

    def _begin_youtube_music_busy_state(self):
        started = False
        if not wx.IsBusy():
            wx.BeginBusyCursor()
            started = True
        self._youtube_music_busy_cursor_started = started
        self._set_youtube_music_operation_state(True)

    def _end_youtube_music_busy_state(self):
        started = bool(getattr(self, "_youtube_music_busy_cursor_started", False))
        self._youtube_music_busy_cursor_started = False
        if started and wx.IsBusy():
            wx.EndBusyCursor()
        self._set_youtube_music_operation_state(False)

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None):
        if getattr(self, "_youtube_music_operation_in_progress", False):
            self._announce("O YouTube Music já está processando uma solicitação. Aguarde um momento.")
            return False

        self._begin_youtube_music_busy_state()
        task_id = int(getattr(self, "_youtube_music_task_sequence", 0)) + 1
        self._youtube_music_task_sequence = task_id
        self._youtube_music_active_task_id = task_id
        self._cancel_youtube_music_task_watchdog()
        self._youtube_music_task_watchdog = wx.CallLater(
            self._YOUTUBE_MUSIC_BACKGROUND_TASK_TIMEOUT_MS,
            self._handle_youtube_music_background_task_timeout,
            task_id,
        )

        def runner():
            try:
                result = worker()
            except Exception as exc:
                wx.CallAfter(self._finish_youtube_music_background_task, task_id, on_success, on_error, None, exc)
                return

            wx.CallAfter(self._finish_youtube_music_background_task, task_id, on_success, on_error, result, None)

        threading.Thread(target=runner, daemon=True).start()
        return True

    def _handle_youtube_music_background_task_timeout(self, task_id):
        if task_id != getattr(self, "_youtube_music_active_task_id", None):
            return

        self._youtube_music_active_task_id = None
        self._cancel_youtube_music_task_watchdog()
        self._end_youtube_music_busy_state()
        self._announce(
            "A operação do YouTube Music demorou mais do que o esperado e foi cancelada para evitar travamento."
        )
        self._drain_youtube_music_pending_callbacks()

    def _finish_youtube_music_background_task(self, task_id, on_success, on_error, result, error):
        if task_id != getattr(self, "_youtube_music_active_task_id", None):
            return

        self._youtube_music_active_task_id = None
        self._cancel_youtube_music_task_watchdog()
        self._end_youtube_music_busy_state()
        try:
            if error is not None:
                if callable(on_error):
                    on_error(error)
                return

            if callable(on_success):
                on_success(result)
        finally:
            self._drain_youtube_music_pending_callbacks()

    def _queue_youtube_music_post_operation_callback(self, callback):
        if not callable(callback):
            return
        pending = getattr(self, "_youtube_music_pending_post_operation_callbacks", None)
        if pending is None:
            pending = []
            self._youtube_music_pending_post_operation_callbacks = pending
        # Avoid stacking duplicates of the same bound method.
        for existing in pending:
            if existing == callback:
                return
        pending.append(callback)

    def _drain_youtube_music_pending_callbacks(self):
        pending = getattr(self, "_youtube_music_pending_post_operation_callbacks", None)
        if not pending:
            return
        # Snapshot and clear before invoking so callbacks that re-enqueue
        # themselves (e.g. because another task started in the meantime)
        # don't get dropped.
        callbacks = list(pending)
        self._youtube_music_pending_post_operation_callbacks = []
        for callback in callbacks:
            try:
                callback()
            except Exception:
                continue

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
            message = (
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
                    "Atualizando recursos adicionais do YouTube Music. A biblioteca ser\u00e1 carregada em seguida."
                )
            else:
                self._announce(
                    "Carregando conta e biblioteca do YouTube Music. Por favor, aguarde."
                )

        self._open_screen_tab(
            YOUTUBE_MUSIC_SCREEN_ID,
            "YouTube Music",
            self._create_youtube_music_page,
            select=True,
            activation_message=(
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
                "Atualizando recursos adicionais do YouTube Music. A biblioteca ser\u00e1 carregada em seguida."
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
            self._announce("Selecione uma playlist ou mix do YouTube Music para abrir.")
            return

        playlist = self._playlist_summary_by_id(playlist_id)
        if playlist is None:
            self._announce("A playlist selecionada não está mais disponível na lista atual.")
            return

        self._load_youtube_music_playlist(playlist)

    def _on_youtube_music_open_manual_source_button(self):
        panel = self._get_youtube_music_panel()
        manual_source = panel.get_manual_source() if panel is not None else ""
        if not manual_source:
            self._announce("Cole um link de playlist, mix ou vídeo do YouTube Music/YouTube para abrir.")
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
            "Informe um link válido de playlist, mix ou vídeo do YouTube Music/YouTube.",
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _open_youtube_music_manual_video(self, video_url, video_id):
        title = f"Vídeo do YouTube ({video_id})"
        self._open_prepared_media_playlist(
            [video_url],
            title,
            browser_item_labels=[title],
            source_path=video_url,
            announce_message=f"Vídeo do YouTube aberto: {title}.",
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

    def _on_youtube_music_show_search_actions_menu(self, panel, anchor_window=None):
        selected_results = self._selected_youtube_music_search_results()
        if not selected_results:
            self._announce("Selecione ao menos um resultado da busca para abrir o menu de ações.")
            return False

        menu = wx.Menu()
        add_menu = wx.Menu()
        open_new_item = add_menu.Append(wx.ID_ANY, "Abrir seleção em nova playlist")

        add_targets = self._youtube_music_search_playlist_tab_targets()
        target_items = []
        if add_targets:
            add_menu.AppendSeparator()
        for target in add_targets:
            menu_item = add_menu.Append(wx.ID_ANY, target["label"])
            target_items.append((menu_item, target))

        can_add_selection = bool(self._search_results_can_add_to_current_playlist(selected_results))
        open_new_item.Enable(can_add_selection)
        for menu_item, _target in target_items:
            menu_item.Enable(can_add_selection)

        menu.AppendSubMenu(add_menu, "Adicionar seleção...")

        add_menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._open_youtube_music_search_results_in_new_playlist(),
            id=open_new_item.GetId(),
        )
        for menu_item, target in target_items:
            add_menu.Bind(
                wx.EVT_MENU,
                lambda _event, target_index=target["index"]: self._add_youtube_music_search_results_to_playlist_tab(target_index),
                id=menu_item.GetId(),
            )

        popup_parent = anchor_window or getattr(panel, "search_results_list", None) or self
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def _selected_youtube_music_search_result(self):
        selected_results = self._selected_youtube_music_search_results()
        if not selected_results:
            return None
        return selected_results[0]

    def _selected_youtube_music_search_results(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return []
        return list(panel.get_selected_search_results())

    def _search_results_can_add_to_current_playlist(self, search_results):
        for search_result in search_results or []:
            if getattr(search_result, "playlist_id", "") or getattr(search_result, "playback_url", ""):
                return True
        return False

    def _youtube_music_search_playlist_tab_targets(self):
        current_index = self._get_current_tab_index()
        active_index = self._get_active_playlist_index()
        targets = []
        for index, state in enumerate(getattr(self, "playlists", [])):
            if not isinstance(state, PlaylistState) or state.is_folder_tab or state.is_loading:
                continue

            label = str(state.title or f"Playlist {index + 1}").strip()
            if index == current_index:
                label = f"{label} (aba atual)"
            elif index == active_index:
                label = f"{label} (playlist ativa)"

            targets.append({
                "index": index,
                "state": state,
                "label": label,
            })
        return targets

    def _prepare_youtube_music_search_results_for_playlist(self, search_results):
        service = self._get_youtube_music_service()
        prepared_items = []
        prepared_labels = []
        playlist_result_count = 0
        skipped_count = 0
        for search_result in search_results:
            playlist_id = str(getattr(search_result, "playlist_id", "") or "").strip()
            if playlist_id:
                playlist_content = service.get_playlist_content(playlist_id, fallback_title=search_result.title)
                if not playlist_content.item_urls:
                    skipped_count += 1
                    continue
                prepared_items.extend(playlist_content.item_urls)
                prepared_labels.extend(playlist_content.item_labels)
                playlist_result_count += 1
                continue

            playback_url = str(getattr(search_result, "playback_url", "") or "").strip()
            if not playback_url:
                skipped_count += 1
                continue
            prepared_items.append(playback_url)
            prepared_labels.append(search_result.choice_label)

        if not prepared_items:
            raise RuntimeError("A seleção atual não tem resultados reproduzíveis para adicionar à playlist escolhida.")

        return prepared_items, prepared_labels, playlist_result_count, skipped_count

    def _youtube_music_search_results_playlist_title(self, search_results):
        if len(search_results) == 1:
            title = str(getattr(search_results[0], "title", "") or "").strip()
            if title:
                return title
        return "Seleção do YouTube Music"

    def _announce_youtube_music_playlist_addition(self, added_count, target_title, playlist_result_count, skipped_count):
        normalized_message = f"{added_count} item(ns) adicionado(s) à playlist: {target_title}."
        if playlist_result_count:
            normalized_message = f"{normalized_message} {playlist_result_count} playlist(s) da busca foram expandidas."
        if skipped_count:
            normalized_message = f"{normalized_message} {skipped_count} item(ns) da seleção foram ignorados."
        self._announce(normalized_message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(normalized_message)

    def _open_youtube_music_search_results_in_new_playlist(self):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce("Selecione ao menos um resultado da busca para abrir em uma nova playlist.")
            return False

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            target_index = self._create_empty_playlist_tab(select=False)
            target_state = self._get_playlist_state(target_index)
            if not isinstance(target_state, PlaylistState):
                self._announce("Não foi possível criar uma nova playlist para a seleção atual.")
                return

            target_state.finish_library_load()
            target_state.clear_folder_location()
            target_state.title = self._youtube_music_search_results_playlist_title(search_results)
            target_state.set_items_prepared(
                prepared_items,
                {item: index for index, item in enumerate(prepared_items)},
                prepared_labels,
                start_index=0,
            )
            self.notebook.SetPageText(target_index, target_state.title)
            self._add_recent_media_paths(prepared_items)
            self.active_playlist_index = target_index
            self._select_tab(target_index, announce=False)
            self._refresh_playlist_browser()
            self._update_title()

            announce_message = f"Seleção aberta em nova playlist: {target_state.title}."
            if playlist_result_count:
                announce_message = f"{announce_message} {playlist_result_count} playlist(s) da busca foram expandidas."
            if skipped_count:
                announce_message = f"{announce_message} {skipped_count} item(ns) da seleção foram ignorados."
            self._play_media(index=target_index, announce_message=announce_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(announce_message)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível abrir a seleção em uma nova playlist.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _add_youtube_music_search_results_to_playlist_tab(self, target_index):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce("Selecione ao menos um resultado da busca para adicionar à playlist escolhida.")
            return False

        target_state = self._get_playlist_state(target_index)
        if not isinstance(target_state, PlaylistState) or target_state.is_folder_tab or target_state.is_loading:
            self._announce("A playlist escolhida não está disponível para receber a seleção atual.")
            return False

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            added_count, _play_item = self._append_prepared_items_to_playlist(
                prepared_items,
                target_state,
                browser_item_labels=prepared_labels,
            )

            if added_count == 0:
                self._announce(f"Os itens selecionados já estavam presentes na playlist: {target_state.title}.")
                return

            self._add_recent_media_paths(prepared_items)
            self.active_playlist_index = target_index
            self._select_tab(target_index, announce=False)
            self._refresh_playlist_browser()
            self._update_title()
            self._announce_youtube_music_playlist_addition(
                added_count,
                target_state.title,
                playlist_result_count,
                skipped_count,
            )

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível adicionar a seleção à playlist escolhida.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _resolve_youtube_music_player_playlist_target(self):
        candidates = [
            self._get_playlist_state(self._get_current_tab_index()),
            self._get_active_playlist_state(),
        ]
        for candidate in candidates:
            if isinstance(candidate, PlaylistState) and not candidate.is_folder_tab and not candidate.is_loading:
                return candidate

        tab_index = self._create_empty_playlist_tab(select=False)
        return self._get_playlist_state(tab_index)

    def _save_youtube_music_search_result(self):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce("Selecione ao menos um resultado da busca para salvar.")
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        def worker():
            success_count = 0
            playlist_saved = False
            for search_result in search_results:
                if not getattr(search_result, "can_save", False):
                    continue
                service.save_search_result(search_result)
                success_count += 1
                if getattr(search_result, "result_type", "") == "playlist":
                    playlist_saved = True
            if success_count == 0:
                raise RuntimeError("A seleção atual não tem resultados compatíveis para salvar na biblioteca.")
            return success_count, playlist_saved

        def on_success(result):
            success_count, playlist_saved = result
            normalized_message = (
                "Resultado salvo no YouTube Music."
                if success_count == 1
                else f"{success_count} resultado(s) salvo(s) no YouTube Music."
            )
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if playlist_saved:
                self.on_refresh_youtube_music_library(None, announce=False)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível salvar o resultado no YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _add_youtube_music_search_results_to_current_playlist(self):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce("Selecione ao menos um resultado da busca para adicionar à playlist atual.")
            return False

        target_state = self._resolve_youtube_music_player_playlist_target()
        if not isinstance(target_state, PlaylistState):
            self._announce("Não foi possível localizar uma playlist de destino no player.")
            return False

        service = self._get_youtube_music_service()

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            added_count, _play_item = self._append_prepared_items_to_playlist(
                prepared_items,
                target_state,
                browser_item_labels=prepared_labels,
            )

            if added_count == 0:
                self._announce("Os itens selecionados já estavam presentes na playlist atual.")
                return

            self._add_recent_media_paths(prepared_items)
            self._refresh_playlist_browser()
            self._update_title()
            self._announce_youtube_music_playlist_addition(
                added_count,
                target_state.title,
                playlist_result_count,
                skipped_count,
            )

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível adicionar a seleção à playlist atual.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _rate_current_youtube_music_media(self, rating):
        state = self._get_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip() if state is not None else ""
        if not media_path:
            self._announce("Nenhuma mídia está carregada para avaliar.")
            return False

        if not is_youtube_music_media(media_path):
            self._announce("A mídia atual não veio do YouTube Music ou do YouTube.")
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        current_status = self._get_youtube_music_media_feedback_status(media_path)
        normalized_rating = str(rating or "").strip().upper()
        if current_status == normalized_rating:
            if normalized_rating == "DISLIKE":
                normalized_message = "A mídia atual já está marcada como não gostei no YouTube Music."
            else:
                normalized_message = "A mídia atual já está curtida no YouTube Music."
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)
            return False

        def worker():
            return service.rate_media_feedback(media_path, rating)

        def on_success(message):
            normalized_message = str(message or "Avaliação da mídia atual enviada ao YouTube Music.").strip()
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível avaliar a mídia atual no YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _youtube_music_video_ids_from_paths(self, media_paths):
        """Extract the YouTube Music video ids from a list of media paths.

        Non-YouTube items are skipped and duplicates are collapsed while
        preserving order, mirroring how the rating flow filters its selection.
        """
        video_ids = []
        seen_video_ids = set()
        for media_path in media_paths or []:
            normalized_media_path = str(media_path or "").strip()
            if not normalized_media_path or not is_youtube_music_media(normalized_media_path):
                continue
            video_id = extract_video_id_from_text(normalized_media_path)
            if video_id and video_id not in seen_video_ids:
                video_ids.append(video_id)
                seen_video_ids.add(video_id)
        return video_ids

    def _current_tab_youtube_music_playlist_id(self):
        """Return the editable remote playlist id backing the current tab.

        Returns ``None`` unless the active tab is a YouTube Music *user*
        playlist (watch playlists / mixes are not editable).
        """
        state = self._get_playlist_state()
        if state is None or state.is_folder_tab:
            return None
        playlist_id = extract_playlist_id_from_source(getattr(state, "source_path", None))
        if not playlist_id or is_watch_playlist_id(playlist_id):
            return None
        return playlist_id

    def _editable_youtube_music_playlists(self):
        """Return only the playlists the user can edit.

        Personalized mixes / radios (watch playlist ids starting with ``RD``)
        share the library cache but cannot receive ``add_playlist_items``
        edits, so they are excluded from the picker.
        """
        return [
            playlist
            for playlist in self._youtube_music_library_cache()
            if not is_watch_playlist_id(getattr(playlist, "playlist_id", ""))
        ]

    def _prompt_for_youtube_music_playlist(self, playlists, prompt, *, allow_create=False):
        """Pick a target playlist, optionally offering to create a new one.

        When ``allow_create`` is set, the first entry is a "create new
        playlist" choice (mirroring the YouTube Music app's own add dialog).
        Returns the chosen playlist, the :data:`_CREATE_NEW_PLAYLIST_CHOICE`
        sentinel, or ``None`` when cancelled.
        """
        choice_labels = []
        if allow_create:
            choice_labels.append("Criar nova playlist...")
        choice_labels.extend(playlist.choice_label for playlist in playlists)

        dialog = wx.SingleChoiceDialog(self, prompt, "Playlists do YouTube Music", choice_labels)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            selected_index = dialog.GetSelection()
        finally:
            dialog.Destroy()

        if not 0 <= selected_index < len(choice_labels):
            return None
        if allow_create:
            if selected_index == 0:
                return self._CREATE_NEW_PLAYLIST_CHOICE
            selected_index -= 1
        if not 0 <= selected_index < len(playlists):
            return None
        return playlists[selected_index]

    def _add_current_media_to_youtube_playlist(self):
        state = self._get_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip() if state is not None else ""
        if not media_path:
            self._announce("Nenhuma mídia está tocando para ser adicionada.")
            return False
        return self._add_media_paths_to_youtube_playlist([media_path])

    def _add_selected_media_to_youtube_playlist(self, media_paths):
        return self._add_media_paths_to_youtube_playlist(media_paths)

    def _add_media_paths_to_youtube_playlist(self, media_paths):
        video_ids = self._youtube_music_video_ids_from_paths(media_paths)
        if not video_ids:
            self._announce("A seleção não contém faixas do YouTube Music para adicionar.")
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        track_count = len(video_ids)
        track_label = "faixa" if track_count == 1 else "faixas"

        playlists = self._editable_youtube_music_playlists()
        if not playlists:
            # With no editable playlists yet, the only sensible action is to
            # create one seeded with the current selection.
            return self._create_youtube_music_playlist_with_video_ids(video_ids)

        selected_playlist = self._prompt_for_youtube_music_playlist(
            playlists,
            f"Selecione a playlist para adicionar {track_count} {track_label}:",
            allow_create=True,
        )
        if selected_playlist is None:
            return False
        if selected_playlist is self._CREATE_NEW_PLAYLIST_CHOICE:
            return self._create_youtube_music_playlist_with_video_ids(video_ids)

        def worker():
            return service.add_tracks_to_playlist(selected_playlist.playlist_id, video_ids)

        def on_success(added_count):
            try:
                normalized_added = int(added_count)
            except (TypeError, ValueError):
                normalized_added = track_count
            added_verb = "adicionada" if normalized_added == 1 else "adicionadas"
            added_noun = "faixa" if normalized_added == 1 else "faixas"
            message = (
                f"{normalized_added} {added_noun} {added_verb} à playlist {selected_playlist.title}"
                " no YouTube Music."
            )
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível adicionar à playlist do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(f"Adicionando {track_count} {track_label} à playlist {selected_playlist.title}...")
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _remove_selected_media_from_youtube_playlist(self, media_paths, item_indexes):
        state = self._get_playlist_state()
        if state is None or state.is_folder_tab:
            self._announce("Abra uma playlist do YouTube Music para remover faixas dela.")
            return False

        playlist_id = extract_playlist_id_from_source(getattr(state, "source_path", None))
        if not playlist_id or is_watch_playlist_id(playlist_id):
            self._announce("A aba atual não é uma playlist editável do YouTube Music.")
            return False

        video_ids = self._youtube_music_video_ids_from_paths(media_paths)
        if not video_ids:
            self._announce("A seleção não contém faixas do YouTube Music para remover.")
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        playlist_summary = self._playlist_summary_by_id(playlist_id)
        playlist_title = (
            playlist_summary.title
            if playlist_summary is not None
            else str(getattr(state, "title", "") or "playlist")
        )

        track_count = len(video_ids)
        track_label = "faixa" if track_count == 1 else "faixas"

        # Editing a remote playlist changes the user's account and is not
        # undoable from the player, so confirm before touching the server.
        confirmation = wx.MessageBox(
            f"Remover {track_count} {track_label} da playlist \"{playlist_title}\" no YouTube Music?\n\n"
            "Isso altera a playlist diretamente na sua conta e não pode ser desfeito pelo player.",
            "Remover da playlist do YouTube Music",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if confirmation != wx.YES:
            return False

        local_indexes = list(item_indexes or [])

        def worker():
            return service.remove_tracks_from_playlist(playlist_id, video_ids)

        def on_success(removed_count):
            try:
                normalized_removed = int(removed_count)
            except (TypeError, ValueError):
                normalized_removed = track_count
            # Mirror the removal in the open tab so the list matches the server.
            # This announces its own result, so we only update the status line.
            if local_indexes:
                self._remove_items_from_current_playlist(
                    local_indexes,
                    announce_prefix="Removido da playlist do YouTube Music",
                )
            removed_noun = "faixa removida" if normalized_removed == 1 else "faixas removidas"
            message = f"{normalized_removed} {removed_noun} da playlist {playlist_title} no YouTube Music."
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            if not local_indexes:
                self._announce(message)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível remover da playlist do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(f"Removendo {track_count} {track_label} da playlist {playlist_title}...")
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    _PLAYLIST_PRIVACY_LABELS = {
        "PRIVATE": "privada",
        "UNLISTED": "não listada",
        "PUBLIC": "pública",
    }

    def _prompt_for_new_youtube_music_playlist(self, *, track_count=0, default_name=""):
        """Ask for the new playlist's name and privacy level.

        Returns a ``(name, privacy_status)`` tuple, or ``None`` when cancelled.
        """
        dialog = YouTubeMusicCreatePlaylistDialog(
            self,
            default_name=default_name,
            track_count=track_count,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return dialog.get_playlist_name(), dialog.get_privacy_status()
        finally:
            dialog.Destroy()

    def _on_youtube_music_create_playlist_button(self):
        return self._create_empty_youtube_music_playlist()

    def _create_empty_youtube_music_playlist(self):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False
        return self._create_youtube_music_playlist_with_video_ids([])

    def _create_youtube_music_playlist_with_video_ids(self, video_ids):
        """Create a new remote playlist, optionally seeded with ``video_ids``.

        Authentication is assumed to be ensured by the caller (the add flow and
        the central panel both do so before reaching here). The user picks the
        name and privacy level (Private/Unlisted/Public) in the dialog.
        """
        service = self._get_youtube_music_service()
        normalized_video_ids = list(video_ids or [])
        track_count = len(normalized_video_ids)

        prompt_result = self._prompt_for_new_youtube_music_playlist(track_count=track_count)
        if not prompt_result:
            return False
        playlist_name, privacy_status = prompt_result
        privacy_label = self._PLAYLIST_PRIVACY_LABELS.get(privacy_status, "privada")

        def worker():
            return service.create_playlist(
                playlist_name,
                privacy_status=privacy_status,
                video_ids=normalized_video_ids or None,
            )

        def on_success(_new_playlist_id):
            if track_count:
                track_label = "faixa" if track_count == 1 else "faixas"
                message = (
                    f"Playlist \"{playlist_name}\" ({privacy_label}) criada no YouTube Music"
                    f" com {track_count} {track_label}."
                )
            else:
                message = f"Playlist \"{playlist_name}\" ({privacy_label}) criada no YouTube Music."
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            # Surface the new playlist in the library list right away.
            self.on_refresh_youtube_music_library(None, announce=False)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível criar a playlist no YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(f"Criando a playlist \"{playlist_name}\" no YouTube Music...")
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _on_youtube_music_delete_playlist_button(self):
        return self._delete_selected_youtube_music_library_playlist()

    def _delete_selected_youtube_music_library_playlist(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return False

        playlist_id = panel.get_selected_playlist_id()
        if not playlist_id:
            self._announce("Selecione uma playlist do YouTube Music para excluir.")
            return False
        if is_watch_playlist_id(playlist_id):
            self._announce("Mixes e rádios do YouTube Music não podem ser excluídos.")
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        playlist_summary = self._playlist_summary_by_id(playlist_id)
        playlist_title = playlist_summary.title if playlist_summary is not None else "playlist"

        # Deleting a remote playlist removes it from the account entirely and
        # is not undoable from the player, so confirm before touching the server.
        confirmation = wx.MessageBox(
            f"Excluir a playlist \"{playlist_title}\" do YouTube Music?\n\n"
            "Isso remove a playlist inteira da sua conta e não pode ser desfeito pelo player.",
            "Excluir playlist do YouTube Music",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if confirmation != wx.YES:
            return False

        def worker():
            return service.delete_playlist(playlist_id)

        def on_success(_deleted_playlist_id):
            message = f"Playlist \"{playlist_title}\" excluída do YouTube Music."
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            self.on_refresh_youtube_music_library(None, announce=False)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível excluir a playlist do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(f"Excluindo a playlist \"{playlist_title}\" do YouTube Music...")
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _rate_selected_playlist_items(self, media_paths, rating):
        normalized_media_paths = [
            str(media_path or "").strip()
            for media_path in (media_paths or [])
            if str(media_path or "").strip()
        ]
        youtube_media_paths = [media_path for media_path in normalized_media_paths if is_youtube_music_media(media_path)]
        if not youtube_media_paths:
            self._announce("A seleção atual não contém itens do YouTube Music ou do YouTube.")
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        rateable_media_paths = self._selected_youtube_music_media_paths_to_rate(youtube_media_paths, rating)
        if not rateable_media_paths:
            if str(rating or "").strip().upper() == "DISLIKE":
                normalized_message = "Os itens selecionados já estão marcados como não gostei no YouTube Music."
            else:
                normalized_message = "Os itens selecionados já estão curtidos no YouTube Music."
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)
            return False

        def worker():
            rated_count = 0
            for media_path in rateable_media_paths:
                service.rate_media_feedback(media_path, rating)
                rated_count += 1
            return rated_count

        def on_success(rated_count):
            if str(rating or "").strip().upper() == "DISLIKE":
                normalized_message = (
                    "Item marcado como não gostei no YouTube Music."
                    if rated_count == 1
                    else f"{rated_count} item(ns) marcados como não gostei no YouTube Music."
                )
            else:
                normalized_message = (
                    "Item curtido no YouTube Music."
                    if rated_count == 1
                    else f"{rated_count} item(ns) curtidos no YouTube Music."
                )
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível avaliar a seleção atual no YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_search_youtube_music(self, _event=None):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return False

        query = panel.get_search_query()
        if not query:
            self._announce("Digite algo para pesquisar no YouTube Music ou no YouTube.")
            return False

        search_scope_id = panel.get_search_scope_id()
        scope_option = get_search_scope_option(search_scope_id)
        if scope_option.requires_auth and not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce(f"Pesquisando em {scope_option.label}: {query}.")

        def worker():
            return service.search(query, search_scope=search_scope_id)

        def on_success(search_results):
            result_count = len(search_results)
            if result_count == 0:
                search_summary = f"Busca em {scope_option.label}: nenhum resultado para {query}."
            else:
                search_summary = (
                    f"Busca em {scope_option.label}: {result_count} resultado(s) para {query}."
                )
            self._set_youtube_music_search_results(
                search_results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                f"Não foi possível concluir a busca agora.\n\nDetalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_charts(self, panel=None, anchor_window=None):
        panel = panel or self._get_youtube_music_panel()
        if panel is None:
            return False

        self._announce("Escolha um país no menu para carregar o que está em alta.")
        self._show_youtube_music_charts_menu(panel, anchor_window, get_chart_country_groups())
        return True

    def _show_youtube_music_charts_menu(self, panel, anchor_window, sections):
        menu = wx.Menu()
        for section_title, countries in sections:
            if not section_title:
                # Global (and any other top-level shortcut) goes straight onto
                # the root menu, followed by a separator before the continents.
                for code, label in countries:
                    menu_item = menu.Append(wx.ID_ANY, label)
                    menu.Bind(
                        wx.EVT_MENU,
                        lambda _event, chosen_code=code, chosen_label=label: self._load_youtube_music_charts(
                            chosen_code, chosen_label
                        ),
                        id=menu_item.GetId(),
                    )
                menu.AppendSeparator()
                continue
            submenu = wx.Menu()
            for code, label in countries:
                menu_item = submenu.Append(wx.ID_ANY, label)
                submenu.Bind(
                    wx.EVT_MENU,
                    lambda _event, chosen_code=code, chosen_label=label: self._load_youtube_music_charts(
                        chosen_code, chosen_label
                    ),
                    id=menu_item.GetId(),
                )
            menu.AppendSubMenu(submenu, section_title)

        anchor = anchor_window or getattr(panel, "charts_button", None) or self
        try:
            anchor.PopupMenu(menu)
        finally:
            menu.Destroy()

    def _load_youtube_music_charts(self, country_code, country_label=""):
        country_label = str(country_label or "").strip() or get_chart_country_label(country_code)
        service = self._get_youtube_music_service()
        self._announce(f"Carregando o que está em alta em {country_label}.")

        def worker():
            return service.get_charts(country_code)

        def on_success(chart_results):
            result_count = len(chart_results)
            if result_count == 0:
                search_summary = f"Em alta em {country_label}: nenhum destaque disponível."
            else:
                search_summary = (
                    f"Em alta em {country_label}: {result_count} lista(s) de destaque."
                )
            self._set_youtube_music_search_results(
                chart_results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                f"Não foi possível carregar as paradas agora.\n\nDetalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_moods(self, panel=None, anchor_window=None):
        panel = panel or self._get_youtube_music_panel()
        if panel is None:
            return False

        service = self._get_youtube_music_service()
        self._announce("Carregando as categorias de moods e gêneros do YouTube Music.")

        def worker():
            return service.get_mood_categories()

        def on_success(sections):
            if not sections:
                message = "Nenhuma categoria de moods e gêneros está disponível agora."
                self._youtube_music_library_status_message = message
                self._refresh_youtube_music_screen_later()
                self._announce(message)
                return
            self._announce(
                "Escolha uma categoria de moods e gêneros no menu para carregar as playlists."
            )
            self._show_youtube_music_mood_menu(panel, anchor_window, sections)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível carregar as categorias de moods e gêneros agora.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _show_youtube_music_mood_menu(self, panel, anchor_window, sections):
        menu = wx.Menu()
        for section_title, categories in sections:
            submenu = wx.Menu()
            for category in categories:
                menu_item = submenu.Append(wx.ID_ANY, category.title)
                submenu.Bind(
                    wx.EVT_MENU,
                    lambda _event, chosen=category: self._load_youtube_music_mood_playlists(chosen),
                    id=menu_item.GetId(),
                )
            menu.AppendSubMenu(submenu, section_title or "Categorias")

        anchor = anchor_window or getattr(panel, "moods_button", None) or self
        try:
            anchor.PopupMenu(menu)
        finally:
            menu.Destroy()

    def _load_youtube_music_mood_playlists(self, category):
        category_title = str(getattr(category, "title", "") or "").strip() or "Categoria"
        service = self._get_youtube_music_service()
        self._announce(f"Carregando playlists de {category_title}.")

        def worker():
            return service.get_mood_playlists(category.params, badge=category_title)

        def on_success(results):
            result_count = len(results)
            if result_count == 0:
                search_summary = f"Moods e gêneros — {category_title}: nenhuma playlist disponível."
            else:
                search_summary = (
                    f"Moods e gêneros — {category_title}: {result_count} playlist(s)."
                )
            self._set_youtube_music_search_results(
                results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível carregar as playlists desta categoria agora.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_liked(self):
        if self._get_youtube_music_panel() is None:
            return False
        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce("Carregando suas músicas curtidas do YouTube Music.")

        def worker():
            return service.get_liked_songs(limit=self._YOUTUBE_MUSIC_LIKED_SONGS_LIMIT)

        def on_success(results):
            result_count = len(results)
            if result_count == 0:
                search_summary = "Curtidas: nenhuma faixa curtida encontrada."
            else:
                search_summary = f"Curtidas: {result_count} faixa(s)."
            self._set_youtube_music_search_results(
                results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível carregar suas músicas curtidas agora.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_history(self):
        if self._get_youtube_music_panel() is None:
            return False
        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce("Carregando seu histórico do YouTube Music.")

        def worker():
            return service.get_history()

        def on_success(results):
            result_count = len(results)
            if result_count == 0:
                search_summary = "Histórico: nenhuma faixa recente encontrada."
            else:
                search_summary = f"Histórico: {result_count} faixa(s) recentes."
            self._set_youtube_music_search_results(
                results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível carregar seu histórico agora.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_refresh_youtube_music_library(self, _event=None, announce=True):
        if not self._ensure_youtube_music_authenticated():
            return False

        # Don't issue API calls while the dependency update may be refreshing
        # ytmusicapi files or replacing the managed yt-dlp executable.
        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            message = (
                "Atualizando recursos adicionais do YouTube Music. Tente novamente em instantes."
            )
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            if announce:
                self._announce(message)
            return False

        service = self._get_youtube_music_service()
        if announce:
            self._announce("Atualizando playlists e mixes do YouTube Music.")

        page_size = int(self._youtube_music_library_page_size())
        self._youtube_music_library_limit = page_size
        home_limit = self._youtube_music_home_discovery_limit()

        def worker():
            # Run the three independent network calls in parallel: account
            # name, library playlists, and personalized mixes (home rows).
            # ytmusicapi reuses a single requests.Session under the hood and
            # the cached visitor id, so concurrent calls share TLS/cookies.
            results = {}

            def run_account():
                try:
                    results["account_name"] = service.get_connected_account_name()
                except Exception as exc:
                    results["account_error"] = exc

            def run_playlists():
                try:
                    playlists, has_more = service.get_user_library_playlists(limit=page_size)
                    results["playlists"] = (playlists, has_more)
                except Exception as exc:
                    results["playlists_error"] = exc

            def run_mixes():
                try:
                    results["mixes"] = service.get_personalized_mixes(limit=home_limit)
                except Exception as exc:
                    results["mixes_error"] = exc

            threads = [
                threading.Thread(target=run_account, daemon=True),
                threading.Thread(target=run_playlists, daemon=True),
                threading.Thread(target=run_mixes, daemon=True),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            # Library playlists are required; account name and mixes are
            # best-effort enhancements.
            if "playlists_error" in results:
                raise results["playlists_error"]

            account_name = results.get("account_name", "") or ""
            playlists, has_more = results["playlists"]
            mixes = results.get("mixes") or []
            return account_name, playlists, has_more, mixes

        def on_success(result):
            account_name, playlists, has_more, mixes = result
            self._set_youtube_music_account_name(account_name)

            existing_ids = {playlist.playlist_id for playlist in playlists}
            merged = list(playlists)
            mix_added = 0
            for mix in mixes or []:
                if mix.playlist_id in existing_ids:
                    continue
                merged.append(mix)
                existing_ids.add(mix.playlist_id)
                mix_added += 1
            merged.sort(key=lambda playlist: playlist.title.casefold())

            playlist_count = len(playlists)
            if has_more:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s)"
                    f" e {mix_added} mix(es) personalizada(s)."
                    " Use 'Carregar mais' ou desça até o final da lista para trazer mais."
                )
            else:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s)"
                    f" e {mix_added} mix(es) personalizada(s)."
                )
            self._set_youtube_music_library_cache(
                merged,
                status_message=summary_message,
                has_more_playlists=has_more,
            )
            self._refresh_youtube_music_menu_state()
            if announce:
                self._announce(
                    f"Biblioteca do YouTube Music atualizada: {playlist_count} playlist(s)"
                    f" e {mix_added} mix(es)."
                )

        def on_error(exc):
            self._refresh_youtube_music_menu_state()
            self._youtube_music_library_status_message = "Não foi possível atualizar a biblioteca do YouTube Music."
            self._refresh_youtube_music_screen_later()
            wx.MessageBox(
                "Não foi possível listar as playlists do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _on_youtube_music_load_more_playlists_button(self):
        self._load_more_youtube_music_playlists()

    def _load_more_youtube_music_playlists(self):
        if not self._youtube_music_library_has_more_playlists():
            self._announce("Não há mais playlists para carregar.")
            return False

        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        next_limit = self._youtube_music_current_library_limit() + int(self._youtube_music_library_page_size())
        self._announce("Carregando mais playlists do YouTube Music.")

        def worker():
            return service.get_user_library_playlists(limit=next_limit)

        def on_success(result):
            playlists, has_more = result
            existing_playlists = self._youtube_music_library_cache()
            existing_mix_ids = {
                playlist.playlist_id
                for playlist in existing_playlists
                if str(getattr(playlist, "source_badge", "") or "").strip()
            }
            existing_mixes = [
                playlist
                for playlist in existing_playlists
                if playlist.playlist_id in existing_mix_ids
            ]
            previous_user_playlist_count = sum(
                1
                for playlist in existing_playlists
                if playlist.playlist_id not in existing_mix_ids
            )

            new_playlist_ids = {playlist.playlist_id for playlist in playlists}
            merged = list(playlists)
            for mix in existing_mixes:
                if mix.playlist_id in new_playlist_ids:
                    continue
                merged.append(mix)
                new_playlist_ids.add(mix.playlist_id)
            merged.sort(key=lambda playlist: playlist.title.casefold())

            playlist_count = len(playlists)
            if playlist_count <= previous_user_playlist_count:
                has_more = False

            self._youtube_music_library_limit = next_limit
            if has_more:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s)."
                    " Há mais para carregar."
                )
            else:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s) (todas)."
                )
            self._set_youtube_music_library_cache(
                merged,
                status_message=summary_message,
                has_more_playlists=has_more,
            )
            self._refresh_youtube_music_menu_state()
            self._announce(f"{playlist_count} playlist(s) na biblioteca agora.")

        def on_error(exc):
            wx.MessageBox(
                "Não foi possível carregar mais playlists do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _refresh_youtube_music_personalized_mixes(self, announce=False):
        service = self._get_youtube_music_service()
        home_limit = self._youtube_music_home_discovery_limit()

        def worker():
            return service.get_personalized_mixes(limit=home_limit)

        def on_success(mixes):
            existing_playlists = self._youtube_music_library_cache()
            existing_ids = {playlist.playlist_id for playlist in existing_playlists}
            merged = list(existing_playlists)
            added = 0
            for mix in mixes or []:
                if mix.playlist_id in existing_ids:
                    continue
                merged.append(mix)
                existing_ids.add(mix.playlist_id)
                added += 1
            merged.sort(key=lambda playlist: playlist.title.casefold())
            summary_message = (
                f"Biblioteca do YouTube Music: {len(merged)} item(ns) "
                f"({added} mix(es) personalizada(s) adicionada(s))."
            )
            self._set_youtube_music_library_cache(merged, status_message=summary_message)
            self._refresh_youtube_music_menu_state()
            if announce and added:
                self._announce(f"{added} mix(es) personalizada(s) carregada(s).")

        def on_error(_exc):
            existing_playlists = self._youtube_music_library_cache()
            summary_message = (
                f"Biblioteca do YouTube Music: {len(existing_playlists)} item(ns)."
                " Não foi possível carregar mixes personalizadas."
            )
            self._youtube_music_library_status_message = summary_message
            self._refresh_youtube_music_screen_later()
            self._refresh_youtube_music_menu_state()

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)


    def on_connect_youtube_music(self, _event):
        service = self._get_youtube_music_service()
        dialog = YouTubeMusicBrowserAuthDialog(self)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                self._announce("Conexão com o YouTube Music cancelada.")
                return

            headers_raw = dialog.get_headers_raw()
            browser_json_path = dialog.get_browser_json_path()
        finally:
            dialog.Destroy()

        if not headers_raw and not browser_json_path:
            wx.MessageBox(
                "Cole os dados de conexão do navegador ou selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt.",
                "YouTube Music",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        try:
            saved_path = service.save_browser_auth(headers_raw=headers_raw, source_file_path=browser_json_path)
            account_name = service.get_connected_account_name()
        except Exception as exc:
            service.clear_client_cache()
            self._set_youtube_music_account_name("")
            wx.MessageBox(
                "Não foi possível conectar a conta do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            self._refresh_youtube_music_menu_state()
            return

        self._set_youtube_music_account_name(account_name)
        self._youtube_music_library_status_message = f"Conta conectada: {account_name}."
        self._clear_youtube_music_library_cache(loaded=False, status_message=self._youtube_music_status_message())
        self._refresh_youtube_music_menu_state()
        self._refresh_pending_restored_youtube_music_tabs()
        self._announce(f"Conta do YouTube Music conectada: {account_name}.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message(f"YouTube Music conectado como {account_name}.")
        self.on_refresh_youtube_music_library(None, announce=False)
        wx.MessageBox(
            f"Autenticação do navegador salva em:\n{saved_path}\n\nConta conectada: {account_name}",
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def on_disconnect_youtube_music(self, _event):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            self._announce("Nenhuma conta do YouTube Music está conectada.")
            self._refresh_youtube_music_menu_state()
            return

        with wx.MessageDialog(
            self,
            "Deseja remover a autenticação salva do YouTube Music neste computador?",
            "YouTube Music",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_YES:
                return

        service.disconnect()
        self._set_youtube_music_account_name("")
        self._clear_youtube_music_library_cache(
            loaded=False,
            status_message="A conta do YouTube Music foi desconectada desta instalação.",
        )
        self._refresh_youtube_music_menu_state()
        self._announce("Conta do YouTube Music desconectada.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message("YouTube Music desconectado.")
        wx.MessageBox(
            "A autenticação salva do YouTube Music foi removida.",
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _initialize_youtube_music_startup_state(self):
        # Avoid an eager network round trip on startup just to fetch the
        # account name. The account is validated lazily when the user opens
        # the YouTube Music tab (the library refresh already authenticates
        # and updates the displayed account name). Restored YouTube Music
        # playlist tabs that need their item labels refreshed are still
        # handled here, since their refresh cannot wait for user action.
        self._refresh_youtube_music_menu_state()
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
                self._youtube_music_library_status_message = f"Conta conectada: {account_name}."
            self._refresh_youtube_music_menu_state()
            if account_name:
                self._announce(f"YouTube Music reconectado: {account_name}.")
                if hasattr(self, "_set_status_message"):
                    self._set_status_message(f"YouTube Music conectado como {account_name}.")
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
        self._announce(f"Carregando playlist do YouTube Music: {display_title}.")

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
                    "A playlist selecionada não tem faixas reproduzíveis no momento.",
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
                announce_message=(
                    f"Playlist do YouTube Music carregada: {playlist_content.title}. "
                    f"{len(playlist_content.item_urls)} item(ns)."
                ),
            )

        def on_error(exc):
            service.clear_client_cache()
            self._refresh_youtube_music_menu_state()
            wx.MessageBox(
                "Não foi possível carregar a playlist do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
