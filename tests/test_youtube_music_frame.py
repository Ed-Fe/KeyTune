from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.youtube_music import FrameYouTubeMusicMixin
import player.frames.youtube_music as youtube_music_frame_module


_ACTION_INSTALL_DENO = youtube_music_frame_module.YouTubeMusicJavascriptRuntimeDialog.ACTION_INSTALL_DENO


class _DummyFrame(FrameYouTubeMusicMixin):
    def __init__(self, service):
        self._youtube_music_service = service
        self.settings = types.SimpleNamespace(
            youtube_music_library_page_size=25,
            youtube_music_home_discovery_limit=30,
        )
        self._youtube_music_library_playlists = ["playlist antiga"]
        self._youtube_music_library_loaded = True
        self._youtube_music_library_more_playlists_available = True
        self._youtube_music_library_status_message = "status antigo"
        self._youtube_music_connected_account_name = "Conta antiga"
        self.announcements: list[str] = []
        self.status_updates: list[str] = []
        self.menu_refresh_calls = 0
        self.connect_calls = 0
        self.youtube_dependency_update_calls: list[tuple[bool, bool]] = []
        self.youtube_screen_refresh_calls = 0

    def _get_youtube_music_service(self):
        return self._youtube_music_service

    def _refresh_youtube_music_screen_later(self):
        self.youtube_screen_refresh_calls += 1
        return None

    def _refresh_youtube_music_menu_state(self):
        self.menu_refresh_calls += 1

    def _announce(self, message):
        self.announcements.append(str(message))

    def _set_status_message(self, message, auto_clear_ms=0):
        self.status_updates.append(str(message))

    def on_connect_youtube_music(self, _event):
        self.connect_calls += 1

    def _start_youtube_music_dependency_update(self, force_update=False, manual=False, announce_start=False):
        self.youtube_dependency_update_calls.append((bool(force_update), bool(manual)))
        return True


class YouTubeMusicFrameTests(unittest.TestCase):
    def test_invalid_saved_auth_disconnects_and_clears_library_state(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.is_authenticated.return_value = False

        frame = _DummyFrame(service)

        authenticated = frame._ensure_youtube_music_authenticated()

        self.assertFalse(authenticated)
        service.disconnect.assert_called_once_with()
        self.assertEqual(frame._youtube_music_account_name(), "")
        self.assertEqual(frame._youtube_music_library_cache(), [])
        self.assertFalse(frame._youtube_music_library_has_loaded())
        self.assertFalse(frame._youtube_music_library_has_more_playlists())
        self.assertEqual(
            frame._youtube_music_status_message(),
            "A autenticação salva do YouTube Music expirou ou não é mais válida. Conecte a conta novamente.",
        )
        self.assertEqual(
            frame.announcements,
            ["A autenticação salva do YouTube Music expirou ou não é mais válida. Conecte a conta novamente."],
        )
        self.assertEqual(
            frame.status_updates,
            ["A autenticação salva do YouTube Music expirou ou não é mais válida. Conecte a conta novamente."],
        )
        self.assertGreaterEqual(frame.menu_refresh_calls, 1)

    def test_valid_saved_auth_keeps_existing_connection(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.is_authenticated.return_value = True

        frame = _DummyFrame(service)

        authenticated = frame._ensure_youtube_music_authenticated()

        self.assertTrue(authenticated)
        service.disconnect.assert_not_called()
        self.assertEqual(frame._youtube_music_account_name(), "Conta antiga")
        self.assertEqual(frame._youtube_music_library_cache(), ["playlist antiga"])
        self.assertEqual(frame.announcements, [])
        self.assertEqual(frame.connect_calls, 0)

    def test_refresh_library_stops_immediately_after_invalid_auth_disconnect(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.is_authenticated.return_value = False

        frame = _DummyFrame(service)

        refreshed = frame.on_refresh_youtube_music_library(announce=True)

        self.assertFalse(refreshed)
        service.disconnect.assert_called_once_with()
        service.get_connected_account_name.assert_not_called()
        service.get_user_library_playlists.assert_not_called()
        service.get_personalized_mixes.assert_not_called()

    def test_handle_javascript_runtime_error_opens_winget_install(self):
        service = Mock()
        frame = _DummyFrame(service)
        frame._launch_youtube_music_javascript_runtime_install = Mock(return_value=True)

        class _FakeDialog:
            def __init__(self, _parent, *, winget_available):
                self.winget_available = winget_available

            def ShowModal(self):
                return youtube_music_frame_module.wx.ID_OK

            def get_selected_action(self):
                return _ACTION_INSTALL_DENO

            def Destroy(self):
                return None

        with patch(
            "player.frames.youtube_music.is_missing_javascript_runtime_error_message",
            return_value=True,
        ), patch("player.frames.youtube_music.shutil.which", return_value="C:/Windows/System32/winget.exe"), patch(
            "player.frames.youtube_music.YouTubeMusicJavascriptRuntimeDialog",
            _FakeDialog,
        ):
            handled = frame._handle_youtube_javascript_runtime_error("erro")

        self.assertTrue(handled)
        frame._launch_youtube_music_javascript_runtime_install.assert_called_once_with("DenoLand.Deno", "Deno")

    def test_handle_javascript_runtime_error_ignores_other_messages(self):
        service = Mock()
        frame = _DummyFrame(service)

        with patch(
            "player.frames.youtube_music.is_missing_javascript_runtime_error_message",
            return_value=False,
        ):
            handled = frame._handle_youtube_javascript_runtime_error("outro erro")

        self.assertFalse(handled)

    def test_prompt_for_missing_javascript_runtime_skips_dialog_when_runtime_exists(self):
        service = Mock()
        frame = _DummyFrame(service)
        frame._show_youtube_javascript_runtime_dialog = Mock(return_value=True)

        with patch(
            "player.frames.youtube_music.find_all_available_javascript_runtimes",
            return_value={"node": "C:/Program Files/nodejs/node.exe"},
        ):
            prompted = frame._prompt_for_missing_youtube_javascript_runtime()

        self.assertFalse(prompted)
        frame._show_youtube_javascript_runtime_dialog.assert_not_called()

    def test_preferences_change_prompts_for_runtime_when_enabling_managed_dependencies(self):
        service = Mock()
        frame = _DummyFrame(service)
        previous_settings = types.SimpleNamespace(
            youtube_music_manage_dependencies=False,
            youtube_music_use_nightly_yt_dlp=False,
        )
        frame.settings.youtube_music_manage_dependencies = True
        frame.settings.youtube_music_use_nightly_yt_dlp = False
        frame._prompt_for_missing_youtube_javascript_runtime = Mock(return_value=True)

        frame._handle_youtube_music_preferences_change(previous_settings)

        frame._prompt_for_missing_youtube_javascript_runtime.assert_called_once_with()
        self.assertEqual(frame.youtube_dependency_update_calls, [(False, True)])
        self.assertEqual(frame.youtube_screen_refresh_calls, 1)


if __name__ == "__main__":
    unittest.main()
