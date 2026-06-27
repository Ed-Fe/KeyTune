import shutil
import subprocess
import threading
import time

import wx

from player.youtube_music.dialog import YouTubeMusicJavascriptRuntimeDialog

from ._helpers import (
    _configure_youtube_dependency_management,
    _install_or_update_youtube_dependencies,
    _is_youtube_dependency_auto_update_due,
    _youtube_dependencies_available,
    find_all_available_javascript_runtimes,
    is_missing_javascript_runtime_error_message,
)


class DependencyMixin:
    _YOUTUBE_MUSIC_JS_RUNTIME_DENO_URL = "https://deno.com/"
    _YOUTUBE_MUSIC_JS_RUNTIME_NODE_URL = "https://nodejs.org/"
    _YOUTUBE_MUSIC_JS_RUNTIME_BUN_URL = "https://bun.sh/"
    _YOUTUBE_MUSIC_JS_RUNTIME_GUIDE_URL = "https://github.com/yt-dlp/yt-dlp/wiki/EJS"
    _YOUTUBE_MUSIC_JS_RUNTIME_DENO_WINGET_ID = "DenoLand.Deno"
    _YOUTUBE_MUSIC_JS_RUNTIME_NODE_WINGET_ID = "OpenJS.NodeJS.LTS"
    _YOUTUBE_MUSIC_JS_RUNTIME_BUN_WINGET_ID = "Oven-sh.Bun"

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
