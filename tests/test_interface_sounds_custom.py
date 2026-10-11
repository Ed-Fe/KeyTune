from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import interface_sounds
from player.interface_sounds import custom
from player.interface_sounds.labels import sound_labels
from player.preferences.models import AppSettings


def _write_wav(path, *, seconds=0.1, sample_width=2):
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(sample_width)
        sound.setframerate(8000)
        sound.writeframes(b"\x10" * int(8000 * seconds) * sample_width)
    return path


class CustomSoundTests(unittest.TestCase):
    def setUp(self):
        interface_sounds._last_played.clear()
        self.folder = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(custom, "custom_sounds_dir", return_value=self.folder / "guardados"))
        self.ffmpeg = self.enterContext(patch.object(custom, "find_ffmpeg_directory", return_value=None))

    def test_a_plain_wav_is_copied_without_ffmpeg(self):
        source = _write_wav(self.folder / "meu.wav")

        stored = pathlib.Path(custom.import_custom_sound(interface_sounds.SOUND_LIKE, source))

        self.assertEqual(stored.parent, self.folder / "guardados")
        self.assertEqual(stored.read_bytes(), source.read_bytes())

    def test_without_ffmpeg_other_files_are_refused(self):
        long_sound = _write_wav(self.folder / "longo.wav", seconds=6)
        eight_bits = _write_wav(self.folder / "oito.wav", sample_width=1)
        not_audio = self.folder / "som.mp3"
        not_audio.write_bytes(b"nada")

        for source in (long_sound, eight_bits, not_audio, self.folder / "sumiu.wav"):
            with self.assertRaises(custom.CustomSoundError):
                custom.import_custom_sound(interface_sounds.SOUND_LIKE, source)
        self.assertEqual(list((self.folder / "guardados").glob("*")), [])

    def test_with_ffmpeg_the_file_is_converted_and_cut(self):
        self.ffmpeg.return_value = self.folder
        source = self.folder / "som.mp3"
        source.write_bytes(b"mp3")

        def run(command, **_kwargs):
            _write_wav(command[-1])
            return SimpleNamespace(returncode=0)

        with patch.object(custom.subprocess, "run", side_effect=run) as ffmpeg:
            stored = custom.import_custom_sound(interface_sounds.SOUND_LIKE, source)

        command = ffmpeg.call_args.args[0]
        self.assertEqual(command[command.index("-t") + 1], "5")
        self.assertTrue(pathlib.Path(stored).is_file())

    def test_a_failed_conversion_leaves_nothing_behind(self):
        self.ffmpeg.return_value = self.folder
        source = self.folder / "som.mp3"
        source.write_bytes(b"mp3")
        with patch.object(custom.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(custom.CustomSoundError):
                custom.import_custom_sound(interface_sounds.SOUND_LIKE, source)

        self.assertEqual(list((self.folder / "guardados").glob("*")), [])

    def test_files_no_event_uses_are_removed(self):
        kept = pathlib.Path(custom.import_custom_sound(interface_sounds.SOUND_LIKE, _write_wav(self.folder / "a.wav")))
        dropped = pathlib.Path(
            custom.import_custom_sound(interface_sounds.SOUND_UNLIKE, _write_wav(self.folder / "b.wav"))
        )

        custom.remove_unused_custom_sounds({interface_sounds.SOUND_LIKE: str(kept)})

        self.assertTrue(kept.is_file())
        self.assertFalse(dropped.exists())

    def test_the_chosen_file_plays_in_place_of_the_packaged_one(self):
        chosen = _write_wav(self.folder / "meu.wav")

        data = interface_sounds.sound_data(interface_sounds.SOUND_LIKE, 100, str(chosen))

        self.assertEqual(len(data), len(chosen.read_bytes()))
        self.assertNotEqual(data, interface_sounds.sound_data(interface_sounds.SOUND_LIKE, 100))

    @unittest.skipUnless(sys.platform.startswith("win"), "os sons tocam pelo Windows")
    def test_a_missing_chosen_file_falls_back_to_the_packaged_sound(self):
        with patch.object(interface_sounds._output, "submit") as thread:
            self.assertTrue(interface_sounds.play(interface_sounds.SOUND_LIKE, 50, str(self.folder / "sumiu.wav")))

        self.assertEqual(thread.call_args.args, (interface_sounds.sound_data(interface_sounds.SOUND_LIKE, 50),))


class SoundChoiceTests(unittest.TestCase):
    def setUp(self):
        interface_sounds._last_played.clear()

    def test_every_sound_has_a_name_in_the_preferences(self):
        self.assertEqual(sorted(name for name, _label in sound_labels()), sorted(interface_sounds.SOUND_NAMES))

    @unittest.skipUnless(sys.platform.startswith("win"), "os sons tocam pelo Windows")
    def test_a_sound_turned_off_alone_stays_silent(self):
        frame = SimpleNamespace(
            settings=SimpleNamespace(
                interface_sounds_enabled=True,
                interface_sounds_volume=40,
                interface_sounds_disabled=[interface_sounds.SOUND_LIST_EDGE],
                interface_sounds_custom={},
            )
        )
        with patch.object(interface_sounds._output, "submit") as thread:
            self.assertFalse(interface_sounds.play_for(frame, interface_sounds.SOUND_LIST_EDGE))
            self.assertTrue(interface_sounds.play_for(frame, interface_sounds.SOUND_OPEN))

        thread.assert_called_once()

    def test_the_preferences_keep_only_known_sounds(self):
        settings = AppSettings.from_dict(
            {
                "interface_sounds_disabled": ["open", "inventado", "back"],
                "interface_sounds_custom": {"like": "C:/sons/a.wav", "inventado": "C:/x.wav", "open": 3},
            }
        )

        self.assertEqual(settings.interface_sounds_disabled, ["open", "back"])
        self.assertEqual(settings.interface_sounds_custom, {"like": "C:/sons/a.wav"})
        self.assertEqual(settings.to_dict()["interface_sounds_custom"], {"like": "C:/sons/a.wav"})


if __name__ == "__main__":
    unittest.main()
