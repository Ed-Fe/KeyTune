from __future__ import annotations

import io
import pathlib
import sys
import time
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import interface_sounds
from player.preferences.models import AppSettings


def _peak(data):
    with wave.open(io.BytesIO(data), "rb") as sound:
        frames = sound.readframes(sound.getnframes())
    return max(abs(int.from_bytes(frames[index : index + 2], "little", signed=True)) for index in range(0, len(frames), 2))


class InterfaceSoundsTests(unittest.TestCase):
    def setUp(self):
        interface_sounds._last_played.clear()

    def test_every_sound_is_packaged_as_16_bit_wav(self):
        for name in interface_sounds.SOUND_NAMES:
            with wave.open(str(interface_sounds.sound_path(name)), "rb") as sound:
                self.assertEqual(sound.getsampwidth(), 2, name)
                self.assertGreater(sound.getnframes(), 0, name)

    def test_the_license_lists_every_sound(self):
        license_text = (interface_sounds.sound_path(interface_sounds.SOUND_SUCCESS).parent / "LICENSE.md").read_text(
            encoding="utf-8"
        )
        for name in interface_sounds.SOUND_NAMES:
            self.assertIn(f"`{name}.wav`", license_text)

    def test_an_unknown_sound_has_no_file_and_does_not_play(self):
        self.assertIsNone(interface_sounds.sound_path("../segredo"))
        with patch.object(interface_sounds._output, "submit") as thread:
            self.assertFalse(interface_sounds.play("nada"))
        thread.assert_not_called()

    def test_the_volume_scales_the_samples_as_the_ear_hears(self):
        full = _peak(interface_sounds.sound_data(interface_sounds.SOUND_SUCCESS, 100))
        half = _peak(interface_sounds.sound_data(interface_sounds.SOUND_SUCCESS, 50))

        self.assertAlmostEqual(half / full, 0.25, places=2)

    def test_every_sound_comes_out_at_the_same_level(self):
        levels = []
        for name in interface_sounds.SOUND_NAMES:
            with wave.open(io.BytesIO(interface_sounds.sound_data(name, 100)), "rb") as sound:
                frames = sound.readframes(sound.getnframes())
            samples = [int.from_bytes(frames[i : i + 2], "little", signed=True) for i in range(0, len(frames), 2)]
            gate = max(abs(sample) for sample in samples) * 0.05
            loud = [sample for sample in samples if abs(sample) >= gate]
            levels.append((sum(sample * sample for sample in loud) / len(loud)) ** 0.5 / 32768)

        self.assertLess(max(levels) / min(levels), 1.6)
        self.assertLess(max(levels), 0.11)

    def test_a_silent_file_is_left_alone(self):
        self.assertEqual(interface_sounds.level_gain([0, 0, 0]), 1.0)

    def test_nothing_is_heard_while_the_tests_run(self):
        output = interface_sounds._Output()
        with patch.object(interface_sounds, "_windows_play") as windows_play:
            output.submit(b"RIFF")
            output._thread.join(0.2)
        windows_play.assert_not_called()

    def test_the_same_sound_asked_again_at_once_is_ignored(self):
        with patch.object(interface_sounds._output, "submit") as submit:
            self.assertTrue(interface_sounds.play(interface_sounds.SOUND_BACK, 50))
            self.assertFalse(interface_sounds.play(interface_sounds.SOUND_BACK, 50))
            self.assertTrue(interface_sounds.play(interface_sounds.SOUND_OPEN, 50))
        self.assertEqual(submit.call_count, 2)

    def test_only_the_latest_requests_wait_to_play(self):
        output = interface_sounds._Output()
        with patch.object(interface_sounds.threading, "Thread"):
            for number in range(6):
                output.submit(b"%d" % number)
        self.assertEqual(list(output._pending), [b"2", b"3", b"4", b"5"])

    @unittest.skipUnless(sys.platform.startswith("win"), "os sons tocam pelo Windows")
    def test_sounds_play_over_each_other_and_their_outputs_close(self):
        from player.interface_sounds.wave_out import WaveOutPlayer

        # Volume 1: sai pela placa de som de verdade, mas não dá para ouvir.
        data = interface_sounds.sound_data(interface_sounds.SOUND_BACK, 1)
        player = WaveOutPlayer()
        try:
            player.play(data)
            player.play(data)
        except OSError as exc:
            self.skipTest(f"sem saída de som: {exc}")
        self.assertEqual(len(player._voices), 2)
        deadline = time.monotonic() + 3
        while player.active and time.monotonic() < deadline:
            time.sleep(0.05)
            player.reap()
        self.assertFalse(player.active)

    def test_the_closing_wait_lasts_as_long_as_the_last_sound(self):
        with patch.object(interface_sounds._output, "submit"):
            interface_sounds.play(interface_sounds.SOUND_APP_CLOSED, 50)
        seconds = interface_sounds.sound_seconds(interface_sounds.sound_data(interface_sounds.SOUND_APP_CLOSED, 50))
        with patch.object(interface_sounds, "_output_silenced", return_value=False), patch.object(
            interface_sounds.time, "sleep"
        ) as sleep:
            waited = interface_sounds.wait_until_played(limit_seconds=10)
            self.assertEqual(interface_sounds.wait_until_played(limit_seconds=0), 0.0)

        self.assertGreater(seconds, 0.5)
        self.assertAlmostEqual(waited, seconds, delta=0.3)
        sleep.assert_called_once_with(waited)

    def test_no_sound_starts_or_ends_with_silence(self):
        for name in interface_sounds.SOUND_NAMES:
            with wave.open(str(interface_sounds.sound_path(name)), "rb") as sound:
                rate, channels = sound.getframerate(), sound.getnchannels()
                frames = sound.readframes(sound.getnframes())
            samples = [abs(int.from_bytes(frames[i : i + 2], "little", signed=True)) for i in range(0, len(frames), 2)]
            threshold = max(samples) * 0.01
            window = int(rate * channels * 0.05)
            self.assertGreater(max(samples[:window]), threshold, name)
            self.assertGreater(max(samples[-window * 2 :]), max(samples) * 0.001, name)

    def test_volume_zero_is_silence(self):
        with patch.object(interface_sounds._output, "submit") as thread:
            self.assertFalse(interface_sounds.play(interface_sounds.SOUND_SUCCESS, 0))
        thread.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith("win"), "os sons tocam pelo Windows")
    def test_the_frame_preferences_decide_whether_it_plays(self):
        on = SimpleNamespace(settings=SimpleNamespace(interface_sounds_enabled=True, interface_sounds_volume=40))
        off = SimpleNamespace(settings=SimpleNamespace(interface_sounds_enabled=False, interface_sounds_volume=40))
        with patch.object(interface_sounds._output, "submit") as thread:
            self.assertTrue(interface_sounds.play_for(on, interface_sounds.SOUND_NOTIFICATION))
            self.assertFalse(interface_sounds.play_for(off, interface_sounds.SOUND_NOTIFICATION))
            self.assertFalse(interface_sounds.play_for(object(), interface_sounds.SOUND_NOTIFICATION))

        thread.assert_called_once()

    def test_the_preferences_keep_the_sounds_choice(self):
        settings = AppSettings.from_dict({"interface_sounds_enabled": False, "interface_sounds_volume": 250})

        self.assertFalse(settings.interface_sounds_enabled)
        self.assertEqual(settings.interface_sounds_volume, 100)
        self.assertEqual(settings.to_dict()["interface_sounds_volume"], 100)
        self.assertTrue(AppSettings().interface_sounds_enabled)


if __name__ == "__main__":
    unittest.main()
