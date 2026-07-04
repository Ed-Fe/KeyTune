import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from player.autodj import planner


class NormalizeBpmTests(unittest.TestCase):
    def test_already_in_octave_is_unchanged(self):
        self.assertAlmostEqual(planner.normalize_bpm_to_reference(128.0, 130.0), 128.0)

    def test_double_time_is_folded_down(self):
        # 140 vs 70 are rhythmically compatible; fold 140 near 70.
        self.assertAlmostEqual(planner.normalize_bpm_to_reference(140.0, 70.0), 70.0)

    def test_half_time_is_folded_up(self):
        self.assertAlmostEqual(planner.normalize_bpm_to_reference(70.0, 140.0), 140.0)

    def test_zero_is_returned_as_is(self):
        self.assertEqual(planner.normalize_bpm_to_reference(0.0, 120.0), 0.0)


class ComputeIncomingRateTests(unittest.TestCase):
    def test_close_tempos_match_cleanly(self):
        rate, matched = planner.compute_incoming_rate(126.0, 124.0)
        self.assertTrue(matched)
        # Incoming should speed up slightly so 124 * rate == 126.
        self.assertAlmostEqual(124.0 * rate, 126.0, places=1)

    def test_double_time_matches_via_octave_fold(self):
        rate, matched = planner.compute_incoming_rate(140.0, 70.0)
        self.assertTrue(matched)
        self.assertAlmostEqual(rate, 1.0, places=2)

    def test_far_tempos_are_clamped_and_flagged_loose(self):
        rate, matched = planner.compute_incoming_rate(128.0, 100.0)
        self.assertFalse(matched)
        # Clamped to +/- max stretch instead of a huge 1.28x stretch.
        self.assertLessEqual(rate, 1.0 + planner.DEFAULT_MAX_STRETCH + 1e-9)
        self.assertGreaterEqual(rate, 1.0 - planner.DEFAULT_MAX_STRETCH - 1e-9)

    def test_invalid_bpm_is_safe(self):
        self.assertEqual(planner.compute_incoming_rate(0.0, 120.0), (1.0, False))
        self.assertEqual(planner.compute_incoming_rate(120.0, 0.0), (1.0, False))


class NextBeatTimeTests(unittest.TestCase):
    def test_returns_first_beat_after(self):
        beats = [0.5, 1.0, 1.5, 2.0]
        self.assertEqual(planner.next_beat_time(beats, 1.0), 1.5)

    def test_strictly_greater(self):
        beats = [0.5, 1.0, 1.5]
        # 0.9 -> 1.0 is the first strictly greater.
        self.assertEqual(planner.next_beat_time(beats, 0.9), 1.0)

    def test_none_when_past_last_beat(self):
        beats = [0.5, 1.0, 1.5]
        self.assertIsNone(planner.next_beat_time(beats, 1.5))

    def test_empty_beats(self):
        self.assertIsNone(planner.next_beat_time([], 1.0))


class BassSwapGainsTests(unittest.TestCase):
    def test_incoming_starts_cut_outgoing_full(self):
        incoming_db, outgoing_db = planner.bass_swap_gains(0.0)
        self.assertEqual(incoming_db, planner.BASS_SWAP_CUT_DB)
        self.assertEqual(outgoing_db, 0.0)

    def test_roles_reversed_after_swap(self):
        incoming_db, outgoing_db = planner.bass_swap_gains(1.0)
        self.assertEqual(incoming_db, 0.0)
        self.assertEqual(outgoing_db, planner.BASS_SWAP_CUT_DB)

    def test_midpoint_splits_the_handover(self):
        midpoint = (planner.BASS_SWAP_START + planner.BASS_SWAP_END) / 2.0
        incoming_db, outgoing_db = planner.bass_swap_gains(midpoint)
        self.assertAlmostEqual(incoming_db, planner.BASS_SWAP_CUT_DB / 2.0)
        self.assertAlmostEqual(outgoing_db, planner.BASS_SWAP_CUT_DB / 2.0)

    def test_progress_is_clamped(self):
        self.assertEqual(planner.bass_swap_gains(-1.0), planner.bass_swap_gains(0.0))
        self.assertEqual(planner.bass_swap_gains(2.0), planner.bass_swap_gains(1.0))

    def test_invalid_progress_is_safe(self):
        incoming_db, outgoing_db = planner.bass_swap_gains(None)
        self.assertEqual(incoming_db, planner.BASS_SWAP_CUT_DB)
        self.assertEqual(outgoing_db, 0.0)


class TransitionDurationTests(unittest.TestCase):
    def test_duration_scales_with_beats_and_tempo(self):
        # 16 beats at 128 BPM == 16 * (60000/128) == 7500 ms, within range.
        self.assertEqual(planner.transition_duration_ms(128.0, beats=16), 7500)

    def test_duration_is_clamped_to_min(self):
        self.assertEqual(planner.transition_duration_ms(240.0, beats=4, min_ms=3000), 3000)

    def test_duration_is_clamped_to_max(self):
        self.assertEqual(planner.transition_duration_ms(30.0, beats=16, max_ms=20000), 20000)

    def test_invalid_bpm_falls_back_to_default(self):
        self.assertEqual(planner.transition_duration_ms(0.0), 8000)


if __name__ == "__main__":
    unittest.main()
