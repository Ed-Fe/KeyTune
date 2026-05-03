from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.equalizer.backend import build_mpv_equalizer_filter, load_equalizer_catalog
from player.equalizer.models import EqualizerPreset


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


if __name__ == "__main__":
    unittest.main()