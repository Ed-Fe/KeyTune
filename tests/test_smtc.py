from __future__ import annotations

import pathlib
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.playback.audio_output import AudioOutputMixin
from player.frames.smtc import FrameSmtcMixin


class SmtcReconnectTests(unittest.TestCase):
    def test_audio_device_reappearance_rebuilds_smtc_session(self):
        frame = AudioOutputMixin.__new__(AudioOutputMixin)
        frame._known_audio_output_device_ids = {"wasapi/{device-1}"}
        frame._known_audio_output_device_labels = {}
        frame._suppress_smtc_pause_until = 0.0
        frame._reassert_smtc_after_reconnect = Mock()
        frame._selected_audio_output_device_id = Mock(return_value="")
        frame._current_audio_output_device_id = Mock(return_value="")
        frame._reload_audio_output_if_null = Mock()
        frame._refresh_audio_output_menu = Mock()
        frame._announce = Mock()

        frame._handle_audio_output_device_list_changed(
            [
                SimpleNamespace(
                    device_id="wasapi/{device-1}",
                    menu_label="Alto-falantes",
                ),
                SimpleNamespace(
                    device_id="wasapi/{device-2}",
                    menu_label="Echo",
                ),
            ]
        )

        frame._reassert_smtc_after_reconnect.assert_called_once_with()
        self.assertGreater(frame._suppress_smtc_pause_until, time.monotonic())

    def test_reconnect_forces_fresh_smtc_registration(self):
        frame = FrameSmtcMixin.__new__(FrameSmtcMixin)
        frame._smtc_service = Mock()
        frame._smtc_service.reassert.return_value = True
        frame._smtc_last_keepalive = 10.0
        frame._refresh_smtc_state = Mock()

        frame._reassert_smtc_after_reconnect()

        frame._smtc_service.reassert.assert_called_once_with(force_rebuild=True)
        self.assertEqual(frame._smtc_last_keepalive, 0.0)
        frame._refresh_smtc_state.assert_called_once_with()

    def test_keepalive_retries_unavailable_smtc_service(self):
        frame = FrameSmtcMixin.__new__(FrameSmtcMixin)
        frame._smtc_service = Mock()
        frame._smtc_service.is_available.return_value = False
        frame._smtc_service.reassert.return_value = True
        frame._smtc_last_keepalive = 0.0
        frame.player = Mock()
        frame.player.get_media.return_value = object()
        frame._refresh_smtc_state = Mock()

        frame._maybe_keepalive_smtc()

        frame._smtc_service.reassert.assert_called_once_with()
        frame._refresh_smtc_state.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
