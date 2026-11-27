from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import interface_sounds, windows_notification
from player.frames.youtube_music.tasks import BackgroundTaskMixin


class SilentWindowsNotifierTests(unittest.TestCase):
    def test_fit_text_normalizes_whitespace_and_respects_win32_buffer_limits(self):
        self.assertEqual(windows_notification._fit_text("  Oi\n  mundo  ", 63), "Oi mundo")
        fitted = windows_notification._fit_text("a" * 300, 63)
        self.assertEqual(len(fitted), 63)
        self.assertTrue(fitted.endswith("..."))

    def test_notification_data_always_sets_no_sound_flag(self):
        notifier = windows_notification.SilentWindowsNotifier()
        notifier._hwnd = 1234
        notifier._hicon = 5678

        data = notifier._build_data(title="Notificações", message="Novo vídeo", include_info=True)

        self.assertTrue(data.dwInfoFlags & windows_notification._NIIF_NOSOUND)
        self.assertEqual(data.szInfoTitle, "Notificações")
        self.assertEqual(data.szInfo, "Novo vídeo")

    def test_show_adds_modifies_and_handles_click_without_sound(self):
        notifier = windows_notification.SilentWindowsNotifier()
        notifier._ensure_resources = Mock(return_value=True)
        notifier._hwnd = 1234
        notifier._hicon = 5678
        shell32 = Mock()
        shell32.Shell_NotifyIconW.return_value = 1
        on_click = Mock()

        with patch.object(windows_notification.sys, "platform", "win32"), patch.object(
            windows_notification, "_load_win32_apis", return_value=(Mock(), Mock(), shell32)
        ), patch.object(windows_notification, "_dispatch_click", side_effect=lambda cb: cb()):
            self.assertTrue(notifier.show("Notificações", "Vídeo 1", on_click=on_click))
            self.assertEqual(shell32.Shell_NotifyIconW.call_args_list[0].args[0], windows_notification._NIM_ADD)

            self.assertTrue(notifier.show("Notificações", "Vídeo 2", on_click=on_click))
            self.assertEqual(shell32.Shell_NotifyIconW.call_args_list[1].args[0], windows_notification._NIM_MODIFY)

            notifier._handle_tray_callback(windows_notification._NIN_BALLOONUSERCLICK)
            on_click.assert_called_once_with()
            self.assertEqual(shell32.Shell_NotifyIconW.call_args_list[2].args[0], windows_notification._NIM_DELETE)


class BlockedActionSoundTests(unittest.TestCase):
    def test_blocked_track_navigation_uses_interface_failure_sound(self):
        class _Dummy(BackgroundTaskMixin):
            def __init__(self):
                self._youtube_music_operation_in_progress = True
                self.announcements = []

            def _announce(self, message, category=None):
                self.announcements.append((message, category))

        frame = _Dummy()
        with patch.object(interface_sounds, "play_for") as play_for:
            blocked = frame._block_sensitive_action_during_youtube_music("track-navigation")

        self.assertTrue(blocked)
        play_for.assert_called_once_with(frame, interface_sounds.SOUND_FAILURE)


if __name__ == "__main__":
    unittest.main()
