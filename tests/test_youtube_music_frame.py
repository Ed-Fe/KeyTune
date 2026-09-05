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
from player.frames.youtube_music.auth import AuthMixin
from player.playlists import PlaylistState, ScreenTabState
from player.youtube_music.service import InvalidYouTubeMusicAuthError, TemporaryYouTubeMusicAuthError


_ACTION_INSTALL_DENO = youtube_music_frame_module.YouTubeMusicJavascriptRuntimeDialog.ACTION_INSTALL_DENO


class _DummyFrame(FrameYouTubeMusicMixin):
    def __init__(self, service):
        self._youtube_music_service = service
        self.settings = types.SimpleNamespace(
            youtube_music_manage_dependencies=False,
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
        self.playlists = []
        self.active_playlist_index = 0
        self._current_tab_index = 0

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

    def _get_current_tab_index(self):
        return self._current_tab_index

    def _get_active_playlist_index(self):
        return self.active_playlist_index

    def _get_playlist_state(self, index=None):
        if index is None or index == -1:
            index = self._current_tab_index
        if not 0 <= index < len(self.playlists):
            return None
        state = self.playlists[index]
        return state if isinstance(state, PlaylistState) else None


class YouTubeMusicFrameTests(unittest.TestCase):
    def test_connect_from_browser_runs_export_outside_the_ui_handler(self):
        service = Mock()
        service.save_browser_auth_from_browser.return_value = "C:/KeyTune/ytmusic_browser.json"
        service.get_connected_account_name.return_value = "Conta teste"
        frame = _DummyFrame(service)
        captured_task = {}

        class _FakeDialog:
            def __init__(self, _parent):
                pass

            def ShowModal(self):
                return youtube_music_frame_module.wx.ID_OK

            def get_auth_mode(self):
                return "browser"

            def get_selected_browser(self):
                return "firefox"

            def get_headers_raw(self):
                return ""

            def get_browser_json_path(self):
                return ""

            def Destroy(self):
                return None

        def capture_background_task(worker, on_success, *, on_error=None, timeout_ms=None):
            captured_task.update(
                worker=worker,
                on_success=on_success,
                on_error=on_error,
                timeout_ms=timeout_ms,
            )
            return True

        frame._run_youtube_music_background_task = capture_background_task
        with patch("player.frames.youtube_music.auth.YouTubeMusicBrowserAuthDialog", _FakeDialog):
            started = AuthMixin.on_connect_youtube_music(frame, None)

        self.assertTrue(started)
        service.save_browser_auth_from_browser.assert_not_called()
        self.assertEqual(captured_task["timeout_ms"], 90000)

        result = captured_task["worker"]()

        self.assertEqual(result, ("C:/KeyTune/ytmusic_browser.json", "Conta teste"))
        service.save_browser_auth_from_browser.assert_called_once_with("firefox")

    def test_connect_uses_manual_input_when_the_dialog_reports_manual_mode(self):
        service = Mock()
        service.save_browser_auth.return_value = "C:/KeyTune/ytmusic_browser.json"
        service.get_connected_account_name.return_value = "Conta teste"
        frame = _DummyFrame(service)
        captured_task = {}

        class _FakeDialog:
            def __init__(self, _parent):
                pass

            def ShowModal(self):
                return youtube_music_frame_module.wx.ID_OK

            def get_auth_mode(self):
                return "manual"

            def get_selected_browser(self):
                return "firefox"

            def get_headers_raw(self):
                return "Cookie: SID=teste"

            def get_browser_json_path(self):
                return ""

            def Destroy(self):
                return None

        def capture_background_task(worker, on_success, *, on_error=None, timeout_ms=None):
            captured_task["worker"] = worker
            return True

        frame._run_youtube_music_background_task = capture_background_task
        with patch("player.frames.youtube_music.auth.YouTubeMusicBrowserAuthDialog", _FakeDialog):
            started = AuthMixin.on_connect_youtube_music(frame, None)

        self.assertTrue(started)
        captured_task["worker"]()
        service.save_browser_auth.assert_called_once_with(
            headers_raw="Cookie: SID=teste",
            source_file_path="",
        )
        service.save_browser_auth_from_browser.assert_not_called()

    def test_dislike_does_not_skip_another_track_if_playback_already_advanced(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.rate_media_feedback.return_value = "Mídia atual marcada como não gostei no YouTube Music."
        frame = _DummyFrame(service)
        state = PlaylistState(title="Teste")
        state.items = ["https://music.youtube.com/watch?v=abc123DEF45"]
        state.current_index = 0
        state.current_media_path = state.items[0]
        frame.playlists = [state]
        frame._get_youtube_music_media_feedback_status = Mock(return_value="INDIFFERENT")
        frame._play_adjacent_item = Mock()

        def complete_after_advancing(worker, on_success, *, on_error=None):
            result = worker()
            state.current_media_path = "https://music.youtube.com/watch?v=next1234567"
            on_success(result)
            return True

        frame._run_youtube_music_background_task = complete_after_advancing

        started = frame._rate_current_youtube_music_media("DISLIKE")

        self.assertTrue(started)
        frame._play_adjacent_item.assert_not_called()

    def test_dislike_skips_when_account_already_has_the_rating(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        frame = _DummyFrame(service)
        state = PlaylistState(title="Teste")
        state.items = ["https://music.youtube.com/watch?v=abc123DEF45"]
        state.current_index = 0
        state.current_media_path = state.items[0]
        frame.playlists = [state]
        frame._get_youtube_music_media_feedback_status = Mock(return_value="DISLIKE")
        frame._play_adjacent_item = Mock()

        started = frame._rate_current_youtube_music_media("DISLIKE")

        self.assertFalse(started)
        frame._play_adjacent_item.assert_called_once_with(1)
        service.rate_media_feedback.assert_not_called()

    def test_invalid_saved_auth_preserves_saved_files_and_clears_library_state(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.validate_saved_authentication.side_effect = InvalidYouTubeMusicAuthError()

        frame = _DummyFrame(service)

        authenticated = frame._ensure_youtube_music_authenticated()

        self.assertFalse(authenticated)
        service.disconnect.assert_not_called()
        service.clear_client_cache.assert_called_once_with()
        self.assertEqual(frame._youtube_music_account_name(), "")
        self.assertEqual(frame._youtube_music_library_cache(), [])
        self.assertFalse(frame._youtube_music_library_has_loaded())
        self.assertFalse(frame._youtube_music_library_has_more_playlists())
        self.assertEqual(
            frame._youtube_music_status_message(),
            "Não foi possível validar a autenticação salva do YouTube Music. Conecte a conta novamente.",
        )
        self.assertEqual(
            frame.announcements,
            ["Não foi possível validar a autenticação salva do YouTube Music. Conecte a conta novamente."],
        )
        self.assertEqual(
            frame.status_updates,
            ["Não foi possível validar a autenticação salva do YouTube Music. Conecte a conta novamente."],
        )
        self.assertGreaterEqual(frame.menu_refresh_calls, 1)

    def test_valid_saved_auth_keeps_existing_connection(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.validate_saved_authentication.return_value = True

        frame = _DummyFrame(service)

        authenticated = frame._ensure_youtube_music_authenticated()

        self.assertTrue(authenticated)
        service.disconnect.assert_not_called()
        self.assertEqual(frame._youtube_music_account_name(), "Conta antiga")
        self.assertEqual(frame._youtube_music_library_cache(), ["playlist antiga"])
        self.assertEqual(frame.announcements, [])
        self.assertEqual(frame.connect_calls, 0)

    def test_refresh_library_stops_immediately_after_invalid_auth_validation(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.validate_saved_authentication.side_effect = InvalidYouTubeMusicAuthError()

        frame = _DummyFrame(service)

        refreshed = frame.on_refresh_youtube_music_library(announce=True)

        self.assertFalse(refreshed)
        service.disconnect.assert_not_called()
        service.clear_client_cache.assert_called_once_with()
        service.get_connected_account_name.assert_not_called()
        service.get_user_library_playlists.assert_not_called()
        service.get_personalized_mixes.assert_not_called()

    def test_transient_auth_validation_keeps_saved_connection_and_cache(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = True
        service.validate_saved_authentication.side_effect = TemporaryYouTubeMusicAuthError()

        frame = _DummyFrame(service)

        authenticated = frame._ensure_youtube_music_authenticated()

        self.assertFalse(authenticated)
        service.disconnect.assert_not_called()
        service.clear_client_cache.assert_called_once_with()
        self.assertEqual(frame._youtube_music_account_name(), "Conta antiga")
        self.assertEqual(frame._youtube_music_library_cache(), ["playlist antiga"])
        self.assertTrue(frame._youtube_music_library_has_loaded())
        self.assertTrue(frame._youtube_music_library_has_more_playlists())
        self.assertEqual(
            frame._youtube_music_status_message(),
            "Não foi possível validar a autenticação salva do YouTube Music agora. Tente novamente em instantes.",
        )
        self.assertEqual(
            frame.announcements,
            ["Não foi possível validar a autenticação salva do YouTube Music agora. Tente novamente em instantes."],
        )
        self.assertEqual(
            frame.status_updates,
            ["Não foi possível validar a autenticação salva do YouTube Music agora. Tente novamente em instantes."],
        )

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
            "player.frames.youtube_music.dependencies.is_missing_javascript_runtime_error_message",
            return_value=True,
        ), patch("player.frames.youtube_music.dependencies.shutil.which", return_value="C:/Windows/System32/winget.exe"), patch(
            "player.frames.youtube_music.dependencies.YouTubeMusicJavascriptRuntimeDialog",
            _FakeDialog,
        ):
            handled = frame._handle_youtube_javascript_runtime_error("erro")

        self.assertTrue(handled)
        frame._launch_youtube_music_javascript_runtime_install.assert_called_once_with("DenoLand.Deno", "Deno")

    def test_handle_javascript_runtime_error_ignores_other_messages(self):
        service = Mock()
        frame = _DummyFrame(service)

        with patch(
            "player.frames.youtube_music.dependencies.is_missing_javascript_runtime_error_message",
            return_value=False,
        ):
            handled = frame._handle_youtube_javascript_runtime_error("outro erro")

        self.assertFalse(handled)

    def test_prompt_for_missing_javascript_runtime_skips_dialog_when_runtime_exists(self):
        service = Mock()
        frame = _DummyFrame(service)
        frame._show_youtube_javascript_runtime_dialog = Mock(return_value=True)

        with patch(
            "player.frames.youtube_music.dependencies.find_all_available_javascript_runtimes",
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

    def test_open_youtube_music_announces_when_integration_is_disabled(self):
        service = Mock()
        frame = _DummyFrame(service)

        opened = frame.on_open_youtube_music(None)

        self.assertFalse(opened)
        self.assertEqual(
            frame.announcements,
            [
                "A integração com YouTube Music e YouTube está desativada. "
                "Ative essa opção em Preferências, na aba Recursos adicionais."
            ],
        )
        self.assertEqual(
            frame.status_updates,
            [
                "A integração com YouTube Music e YouTube está desativada. "
                "Ative essa opção em Preferências, na aba Recursos adicionais."
            ],
        )
        self.assertEqual(frame.youtube_screen_refresh_calls, 1)
        service.has_saved_browser_auth.assert_not_called()

    def test_search_playlist_tab_targets_only_include_playlist_tabs(self):
        service = Mock()
        frame = _DummyFrame(service)
        frame.playlists = [
            ScreenTabState(title="YouTube Music", screen_id="youtube_music"),
            PlaylistState(title="Minha playlist"),
            PlaylistState(title="Pasta", tab_type="folder"),
            PlaylistState(title="Carregando", is_loading=True),
            PlaylistState(title="Lista ativa"),
        ]
        frame._current_tab_index = 0
        frame.active_playlist_index = 4

        targets = frame._youtube_music_search_playlist_tab_targets()

        self.assertEqual(
            [(target["index"], target["label"]) for target in targets],
            [
                (1, "Minha playlist"),
                (4, "Lista ativa (playlist ativa)"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
