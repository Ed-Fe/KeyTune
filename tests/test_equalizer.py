from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.equalizer.backend import build_mpv_equalizer_filter, default_equalizer_filter, load_equalizer_catalog
from player.equalizer.models import DEFAULT_EQUALIZER_PRESET_ID, EqualizerPreset
from player.frames.equalizer import FrameEqualizerMixin
from player.playlists import PlaylistState
from player.preferences import AppSettings


class EqualizerPresetTests(unittest.TestCase):
    def test_builtin_presets_use_conservative_levels(self):
        catalog = load_equalizer_catalog()

        self.assertTrue(catalog.builtin_presets)
        for preset in catalog.builtin_presets:
            self.assertLessEqual(preset.preamp_db, 0.0, preset.name)
            self.assertLessEqual(max(abs(value) for value in preset.band_gains_db), 4.0, preset.name)

    def test_filter_builder_adds_headroom_for_boosted_curves(self):
        preset = EqualizerPreset(
            preset_id="custom:test",
            name="Teste",
            preamp_db=0.0,
            band_gains_db=[3.0, 1.5, 0.0],
        )

        filter_chain = build_mpv_equalizer_filter(
            preset,
            band_frequencies_hz=[60.0, 170.0, 1000.0],
        )

        self.assertIn("volume=volume=-1.5dB", filter_chain)
        self.assertIn("g=3.0", filter_chain)


ROCK = "builtin:rock"
POP = "builtin:pop"


class _EqualizerFrame(FrameEqualizerMixin):
    def __init__(self, *, playing, settings=None):
        self.settings = settings or AppSettings()
        self.playing = playing
        self.playlists = [playing]
        self.announcements = []
        self._announce = self.announcements.append
        self._save_settings = Mock()
        self._refresh_equalizer_screen = Mock()
        self._apply_equalizer_state_to_current_playback = Mock(return_value=True)
        self._initialize_equalizer_support()

    def _get_active_playlist_state(self):
        return self.playing

    def _get_playlist_state(self, _index=None):
        return self.playing


class DefaultEqualizerTests(unittest.TestCase):
    def test_a_playlist_follows_the_equalizer_of_the_preferences(self):
        frame = _EqualizerFrame(playing=PlaylistState(title="Rock"))
        self.assertEqual(frame._equalizer_filter_chain_for_state(frame.playing), "")

        frame.on_select_equalizer_preset(ROCK)

        self.assertEqual((frame.settings.equalizer_enabled, frame.settings.equalizer_preset_id), (True, ROCK))
        frame._save_settings.assert_called_once_with()
        self.assertFalse(frame.playing.equalizer_enabled)
        self.assertTrue(frame._equalizer_filter_chain_for_state(frame.playing))
        # Qualquer outra aba, inclusive uma nova, sai com o mesmo som.
        self.assertEqual(
            frame._equalizer_filter_chain_for_state(PlaylistState(title="Nova")),
            frame._equalizer_filter_chain_for_state(frame.playing),
        )
        self.assertTrue(frame.announcements[-1].startswith("Equalizador: "))

    def test_turning_it_off_silences_every_playlist_that_follows_it(self):
        frame = _EqualizerFrame(
            playing=PlaylistState(title="Rock"),
            settings=AppSettings(equalizer_enabled=True, equalizer_preset_id=ROCK),
        )

        frame.on_toggle_equalizer_enabled(False)

        self.assertFalse(frame.settings.equalizer_enabled)
        self.assertEqual(frame.settings.equalizer_preset_id, ROCK)
        self.assertEqual(frame._equalizer_filter_chain_for_state(frame.playing), "")
        self.assertEqual(frame.announcements, ["Equalizador desativado."])

    def test_what_an_old_session_saved_in_the_playlist_is_ignored(self):
        old = PlaylistState.from_dict(
            {"title": "Antiga", "items": [], "equalizer_enabled": True, "equalizer_preset_id": ROCK}
        )
        frame = _EqualizerFrame(playing=old)

        self.assertFalse(old.equalizer_custom)
        self.assertEqual(frame._equalizer_filter_chain_for_state(old), "")


class OwnEqualizerTests(unittest.TestCase):
    def _frame(self):
        return _EqualizerFrame(
            playing=PlaylistState(title="Livro"),
            settings=AppSettings(equalizer_enabled=True, equalizer_preset_id=ROCK),
        )

    def test_a_playlist_that_gets_its_own_starts_from_what_was_in_effect(self):
        frame = self._frame()
        before = frame._equalizer_filter_chain_for_state(frame.playing)

        frame.on_toggle_equalizer_own(True)

        self.assertTrue(frame.playing.equalizer_custom)
        self.assertEqual((frame.playing.equalizer_enabled, frame.playing.equalizer_preset_id), (True, ROCK))
        self.assertEqual(frame._equalizer_filter_chain_for_state(frame.playing), before)
        self.assertEqual(frame.announcements, ["A aba Livro agora tem um equalizador só dela."])

    def test_changes_then_stay_in_that_playlist(self):
        frame = self._frame()
        frame.on_toggle_equalizer_own(True)

        frame.on_select_equalizer_preset(POP)

        self.assertEqual(frame.playing.equalizer_preset_id, POP)
        self.assertEqual(frame.settings.equalizer_preset_id, ROCK)
        frame._save_settings.assert_not_called()
        self.assertNotEqual(
            frame._equalizer_filter_chain_for_state(frame.playing),
            frame._equalizer_filter_chain_for_state(PlaylistState(title="Outra")),
        )
        self.assertTrue(frame.announcements[-1].startswith("Equalizador na aba Livro: "))

    def test_giving_it_up_goes_back_to_the_equalizer_of_the_preferences(self):
        frame = self._frame()
        frame.on_toggle_equalizer_own(True)
        frame.on_toggle_equalizer_enabled(False)
        self.assertEqual(frame._equalizer_filter_chain_for_state(frame.playing), "")

        frame.on_toggle_equalizer_own(False)

        self.assertFalse(frame.playing.equalizer_custom)
        self.assertTrue(frame._equalizer_filter_chain_for_state(frame.playing))
        self.assertTrue(frame.settings.equalizer_enabled)

    def test_the_choice_survives_the_session(self):
        frame = self._frame()
        frame.on_toggle_equalizer_own(True)
        frame.on_select_equalizer_preset(POP)

        restored = PlaylistState.from_dict(frame.playing.to_dict())

        self.assertTrue(restored.equalizer_custom)
        self.assertEqual(restored.equalizer_preset_id, POP)


class QuickPlayerEqualizerTests(unittest.TestCase):
    def test_no_filter_while_the_equalizer_is_off(self):
        self.assertEqual(default_equalizer_filter(AppSettings()), "")

    def test_the_filter_is_the_one_the_main_window_gives_a_playlist(self):
        settings = AppSettings(equalizer_enabled=True, equalizer_preset_id=ROCK)
        frame = _EqualizerFrame(playing=PlaylistState(title="Rock"), settings=settings)

        self.assertEqual(default_equalizer_filter(settings), frame._equalizer_filter_chain_for_state(frame.playing))

    def test_a_preset_that_no_longer_exists_means_no_filter(self):
        settings = SimpleNamespace(equalizer_enabled=True, equalizer_preset_id="custom:gone", equalizer_custom_presets=[])

        self.assertEqual(default_equalizer_filter(settings), "")

    def test_settings_keep_the_equalizer(self):
        restored = AppSettings.from_dict(AppSettings(equalizer_enabled=True, equalizer_preset_id=ROCK).to_dict())

        self.assertEqual((restored.equalizer_enabled, restored.equalizer_preset_id), (True, ROCK))
        self.assertEqual(AppSettings.from_dict({}).equalizer_preset_id, DEFAULT_EQUALIZER_PRESET_ID)


if __name__ == "__main__":
    unittest.main()