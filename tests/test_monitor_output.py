from array import array
from contextlib import nullcontext
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.announcements import ANNOUNCE_PLAYBACK
from player.audio_output import AudioOutputDevice
from player.frames.keyboard import FrameKeyboardMixin
from player.frames.playback import FramePlaybackMixin
from player.keyboard.shortcuts import SCOPE_GLOBAL, SCOPE_LOCAL, action_by_id
from player.monitor_output import (
    MonitorOutput,
    _MonitorError,
    _PCMConverter,
    _apply_gain,
    _logger,
    _stream_audio,
    same_monitor_device,
)
from player.preferences.models import AppSettings
from player.session import DEFAULT_MONITOR_VOLUME, session_monitor_volume


BROADCAST = AudioOutputDevice("wasapi/{broadcast}", "Broadcast")
HEADPHONES = AudioOutputDevice("wasapi/{headphones}", "Headphones")


class _Frame(FramePlaybackMixin, FrameKeyboardMixin):
    def __init__(self, monitoring):
        self.settings = AppSettings(
            monitor_output_enabled=monitoring,
            audio_output_device_id=BROADCAST.device_id,
            monitor_output_device_id=HEADPHONES.device_id,
            broadcast_volume=80,
            volume_step=5,
        )
        self.current_volume = 60
        self.monitor_volume = 35
        self._monitor_output = Mock(spec=MonitorOutput)
        self._announce = Mock()
        self._set_status_message = Mock()
        self._save_settings = Mock()
        self._crossfade_state = None
        self._active_player_key = "primary"
        self.player = Mock()
        self._players = {"primary": self.player, "secondary": Mock()}


class MonitorPlaybackTests(unittest.TestCase):
    def setUp(self):
        platform = patch("player.frames.playback.monitor.sys.platform", "win32")
        platform.start()
        self.addCleanup(platform.stop)

    def test_arrows_and_global_hotkeys_change_only_monitor(self):
        frame = _Frame(monitoring=True)
        frame._shortcut_volume_down()
        frame._shortcut_volume_down_announced()
        frame._monitor_output.set_volume.assert_called_with(25)
        self.assertEqual(frame.current_volume, 60)
        self.assertEqual(frame.settings.broadcast_volume, 80)
        frame.player.audio_set_volume.assert_not_called()
        frame._players["secondary"].audio_set_volume.assert_not_called()
        self.assertEqual(frame._announce.call_count, 2)
        frame._announce.assert_called_with("Volume da monitoração: 25%.", ANNOUNCE_PLAYBACK)
        frame._announce_current_volume()
        frame._announce.assert_called_with("Monitoração 25%. Transmissão 80%.")

    def test_disabled_uses_legacy_volume_and_announcements(self):
        frame = _Frame(monitoring=False)
        frame._shortcut_volume_up()
        frame.player.audio_set_volume.assert_called_once_with(65)
        frame._announce.assert_not_called()
        frame._shortcut_volume_down_announced()
        frame.player.audio_set_volume.assert_called_with(60)
        frame._announce.assert_called_once_with("60%.")
        frame._shortcut_broadcast_volume_down()
        frame._monitor_output.set_volume.assert_not_called()
        frame._save_settings.assert_not_called()

    def test_tracks_and_crossfade_use_broadcast_level_with_track_gain(self):
        frame = _Frame(monitoring=True)
        frame._current_track_gain_db = -6.0
        frame._apply_current_volume()
        frame.player.audio_set_volume.assert_called_once_with(40)
        frame._crossfade_state = {
            "phase": "running", "started_at": 10.0, "duration_ms": 2000,
            "outgoing_key": "primary", "incoming_key": "secondary", "outgoing_gain_db": -6.0,
        }
        with patch("player.frames.playback.crossfade.time.monotonic", return_value=11.0):
            frame._apply_current_volume()
        frame._players["secondary"].audio_set_volume.assert_called_once_with(57)
        frame.player.audio_set_volume.assert_called_with(29)

    def test_broadcast_shortcuts_and_transition_sound_use_broadcast_volume(self):
        frame = _Frame(monitoring=True)
        frame._autodj_sound_instance = Mock()
        frame._autodj_sound_player = Mock()
        frame._shortcut_broadcast_volume_down()
        frame.player.audio_set_volume.assert_called_once_with(75)
        frame._save_settings.assert_called_once()
        frame._announce.assert_called_once_with("Volume da transmissão: 75%.", ANNOUNCE_PLAYBACK)
        with patch("player.frames.playback.backend.transition_sound_path", return_value=Path("sound.wav")):
            self.assertTrue(frame._play_autodj_transition_sound(None))
        frame._autodj_sound_player.audio_set_volume.assert_called_with(75)
        for scope in (SCOPE_LOCAL, SCOPE_GLOBAL):
            for action in ("broadcast_volume_up", "broadcast_volume_down"):
                self.assertEqual(action_by_id(action, scope).default, "")

    def test_disabling_restores_session_volume_on_main_output(self):
        frame = _Frame(monitoring=True)
        previous = frame.settings
        frame.settings = AppSettings()
        announcement = frame._apply_monitor_preferences(previous, 25)
        frame._monitor_output.stop.assert_called_once()
        frame.player.audio_set_volume.assert_called_once_with(60)
        self.assertEqual(frame.monitor_volume, 25)
        self.assertIn("60%", announcement)

    def test_refresh_applies_the_session_monitor_volume(self):
        frame = _Frame(monitoring=True)
        frame.monitor_volume = 15
        frame._refresh_monitor_output([])
        frame._monitor_output.set_volume.assert_called_with(15)

    def test_monitoring_stays_closed_until_the_session_volume_is_restored(self):
        frame = _Frame(monitoring=True)
        frame._monitor_output = None
        frame._monitor_volume_restored = False
        frame.monitor_volume = 50
        with patch("player.frames.playback.monitor.MonitorOutput") as build:
            frame._refresh_monitor_output([])
            build.assert_not_called()
            frame.monitor_volume = 15
            frame._monitor_volume_restored = True
            build.side_effect = lambda volume, on_error: Mock(spec=MonitorOutput)
            frame._refresh_monitor_output([])
        build.assert_called_once()
        self.assertEqual(build.call_args.args[0], 15)
        frame._monitor_output.set_volume.assert_called_with(15)

    def test_device_list_change_retries_a_failed_monitor(self):
        frame = _Frame(monitoring=True)
        frame._current_audio_output_device_id = lambda: BROADCAST.device_id
        frame._monitor_output.has_failed.return_value = True
        frame._handle_audio_output_device_list_changed([BROADCAST, HEADPHONES])
        self.assertIs(frame._monitor_output.configure.call_args.kwargs["retry"], True)

        frame._monitor_output.has_failed.return_value = False
        frame._monitor_output.configure.reset_mock()
        frame._handle_audio_output_device_list_changed([BROADCAST, HEADPHONES])
        self.assertIs(frame._monitor_output.configure.call_args.kwargs["retry"], False)

    def test_switching_transmission_to_headphones_is_rejected(self):
        frame = _Frame(monitoring=True)
        frame._apply_audio_output_device_to_players = Mock()
        self.assertFalse(frame._set_audio_output_device(HEADPHONES.device_id))
        frame._apply_audio_output_device_to_players.assert_not_called()
        self.assertEqual(frame.settings.audio_output_device_id, BROADCAST.device_id)
        frame._announce.assert_called_once_with(
            "A monitoração e a transmissão precisam usar dispositivos diferentes.", ANNOUNCE_PLAYBACK
        )


class MonitorBackendTests(unittest.TestCase):
    def _callbacks(self, volume=25):
        pa = Mock(paWASAPI=13, paInt16=8, paContinue=0, paAbort=2)
        audio = Mock()
        wrapper = Mock()
        pa.PyAudio.return_value = nullcontext(audio)
        audio.get_device_info_generator_by_host_api.return_value = [
            {"index": 1, "name": "Broadcast", "maxOutputChannels": 2, "isLoopbackDevice": False},
            {"index": 2, "name": "Headphones", "maxOutputChannels": 2, "isLoopbackDevice": False,
             "defaultSampleRate": 48000},
        ]
        audio.get_loopback_device_info_generator.return_value = [
            {"index": 5, "name": "Broadcast [Loopback]", "maxInputChannels": 2, "defaultSampleRate": 48000},
        ]
        audio.open.side_effect = [nullcontext(wrapper), nullcontext(wrapper)]
        stopped = Mock(spec=Event)
        stopped.is_set.return_value = False
        stopped.wait.return_value = True
        devices = (("{broadcast}", "Broadcast"), ("{headphones}", "Headphones"))
        _stream_audio(
            pa, BROADCAST.device_id, HEADPHONES.device_id, devices, stopped, lambda: volume, lambda: False
        )
        capture, play = (entry.kwargs for entry in audio.open.call_args_list)
        return pa, capture, play

    def test_same_device_recognizes_mpv_short_id_and_windows_default(self):
        with patch(
            "player.monitor_output.default_wasapi_device_id",
            return_value="wasapi/{0.0.0.00000000}.{HEADPHONES}",
        ):
            self.assertTrue(same_monitor_device("", HEADPHONES.device_id))
            self.assertFalse(same_monitor_device("", BROADCAST.device_id))

    def test_loopback_callbacks_attenuate_the_copy(self):
        pa, capture, play = self._callbacks()
        self.assertEqual(capture["input_device_index"], 5)
        self.assertEqual(play["output_device_index"], 2)
        capture["stream_callback"](array("h", [8000, -8000]).tobytes(), 1, None, 0)
        data, status = play["stream_callback"](None, 2, None, 0)
        self.assertEqual(list(array("h", data)), [2000, -2000, 0, 0])
        self.assertEqual(status, pa.paContinue)

    def test_monitor_gain_matches_rounded_attenuation(self):
        raw = array("h", [8000, -8000, 100, -100, 32767, -32768, 1, -1])
        for volume in (1, 25, 50, 99):
            gained = array("h", _apply_gain(raw.tobytes(), volume))
            self.assertEqual(list(gained), [round(value * volume / 100) for value in raw])
        self.assertEqual(_apply_gain(raw.tobytes(), 100), raw.tobytes())
        self.assertEqual(_apply_gain(raw.tobytes(), 0), b"")

    def test_capture_callback_logs_the_first_error_only(self):
        pa, capture, _play = self._callbacks()
        read = capture["stream_callback"]
        with self.assertLogs(_logger, level="ERROR") as captured:
            self.assertEqual(read(object(), 1, None, 0), (None, pa.paContinue))
            self.assertEqual(read(object(), 1, None, 0), (None, pa.paContinue))
        self.assertEqual(len(captured.records), 1)

    def test_playback_callback_returns_silence_when_gain_fails(self):
        pa, capture, play = self._callbacks()
        capture["stream_callback"](array("h", [8000, -8000]).tobytes(), 1, None, 0)
        write = play["stream_callback"]
        with patch("player.monitor_output._apply_gain", side_effect=RuntimeError("gain")):
            with self.assertLogs(_logger, level="ERROR") as played:
                data, status = write(None, 2, None, 0)
                again, again_status = write(None, 2, None, 0)
        self.assertEqual(data, b"\x00" * 8)
        self.assertEqual(again, b"\x00" * 8)
        self.assertEqual(status, pa.paContinue)
        self.assertEqual(again_status, pa.paContinue)
        self.assertEqual(len(played.records), 1)

    def test_loopback_failure_is_reported_without_touching_main_player(self):
        error = Mock()
        stopped = Event()

        def report(active, message):
            active.set()
            error(active, message)

        output = MonitorOutput(25, report)
        try:
            with (
                patch("player.monitor_output.sys.platform", "win32"),
                patch.dict(sys.modules, pyaudiowpatch=Mock()),
                patch("player.monitor_output._stream_audio", side_effect=OSError("disconnected")),
                self.assertLogs(_logger, level="ERROR"),
            ):
                output._monitor((BROADCAST.device_id, HEADPHONES.device_id, ()), stopped)
            error.assert_called_once_with(stopped, "A monitoração parou. Confira os dispositivos de áudio.")
        finally:
            output.close()

    def test_chosen_device_retries_and_announces_recovery_once(self):
        messages = []
        output = MonitorOutput(25, lambda _active, message: messages.append(message))
        stopped = Event()
        attempts = {"count": 0}

        def stream(*_args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise _MonitorError("fone caiu")
            kwargs["on_started"]()
            stopped.set()

        try:
            with (
                patch("player.monitor_output.sys.platform", "win32"),
                patch.dict(sys.modules, {"pyaudiowpatch": Mock()}),
                patch("player.monitor_output._stream_audio", side_effect=stream),
                patch("player.monitor_output._MONITOR_RETRY_SECONDS", 0),
                self.assertLogs(_logger, level="WARNING"),
            ):
                output._monitor((BROADCAST.device_id, HEADPHONES.device_id, ()), stopped)
        finally:
            output.close()

        self.assertEqual(attempts["count"], 2)
        self.assertEqual(messages, ["fone caiu", "Monitoração retomada."])
        self.assertFalse(output.has_failed())

    def test_retry_speaks_the_drop_once(self):
        messages = []
        output = MonitorOutput(25, lambda _active, message: messages.append(message))
        stopped = Event()
        attempts = {"count": 0}

        def stream(*_args, **_kwargs):
            attempts["count"] += 1
            if attempts["count"] >= 3:
                stopped.set()
                return None
            raise _MonitorError("fone caiu")

        try:
            with (
                patch("player.monitor_output.sys.platform", "win32"),
                patch.dict(sys.modules, {"pyaudiowpatch": Mock()}),
                patch("player.monitor_output._stream_audio", side_effect=stream),
                patch("player.monitor_output._MONITOR_RETRY_SECONDS", 0),
                self.assertLogs(_logger, level="WARNING"),
            ):
                output._monitor((BROADCAST.device_id, HEADPHONES.device_id, ()), stopped)
        finally:
            output.close()

        self.assertEqual(attempts["count"], 3)
        self.assertEqual(messages, ["fone caiu"])

    def test_failure_flag_tracks_the_active_request(self):
        messages = []
        output = MonitorOutput(25, lambda _active, message: messages.append(message))
        try:
            self.assertFalse(output.has_failed())
            output._report(output._stopped, "caiu")
            self.assertTrue(output.has_failed())
            output._report_recovery(output._stopped)
            self.assertFalse(output.has_failed())
        finally:
            output.close()
        self.assertEqual(messages, ["caiu", "Monitoração retomada."])

    def test_close_waits_three_seconds_and_logs_when_the_worker_stays(self):
        output = MonitorOutput(25, Mock())
        timeouts = []
        real_join = output._worker.join

        def join(timeout=None):
            timeouts.append(timeout)
            return real_join(0)

        output._worker.join = join
        try:
            with (
                patch.object(output._worker, "is_alive", return_value=True),
                self.assertLogs(_logger, level="WARNING") as caught,
            ):
                output.close()
        finally:
            output._worker.join = real_join
            if output._worker.is_alive():
                real_join(3)
        self.assertEqual(timeouts, [3.0])
        self.assertTrue(any("3" in line for line in caught.output))

    def test_resampling_keeps_phase_between_capture_blocks(self):
        converter = _PCMConverter(2, 4, 1, 2)
        blocks = (array("h", [0, 100]), array("h", [200, 300]))
        data = b"".join(converter.convert(block.tobytes()) for block in blocks)
        self.assertEqual(list(array("h", data)), [0, 0, 50, 50, 100, 100, 150, 150, 200, 200, 250, 250])

    def test_durable_settings_and_session_volume_round_trip_independently(self):
        settings = AppSettings(
            audio_output_device_id=BROADCAST.device_id,
            monitor_output_enabled=True,
            monitor_output_device_id=HEADPHONES.device_id,
            broadcast_volume=85,
        )
        self.assertEqual(AppSettings.from_dict(settings.to_dict()), settings)
        self.assertFalse(AppSettings.from_dict({}).monitor_output_enabled)
        self.assertEqual(AppSettings.from_dict({}).broadcast_volume, 100)
        self.assertNotIn("monitor_volume", settings.to_dict())
        self.assertEqual(session_monitor_volume({"volume": 75, "monitor_volume": 25}), 25)
        self.assertEqual(session_monitor_volume({"volume": 75}), DEFAULT_MONITOR_VOLUME)
        self.assertEqual(session_monitor_volume({"monitor_volume": 300}), 100)


if __name__ == "__main__":
    unittest.main()
