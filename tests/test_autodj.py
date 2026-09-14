import json
import math
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.autodj import (
    AnalysisCache,
    AudioAnalysis,
    AutoDJPlanner,
    AutoDJQueuePlanner,
    QueueCandidate,
    TransitionProfile,
    WaveAnalyzer,
    build_mix_lavfi_filters,
    mix_values,
)
from player.autodj import dependencies as autodj_dependencies
from player.autodj.service import AutoDJService
from player.autodj.sound_effects import transition_sound_path
from player.autodj.librosa_analyzer import (
    AutoDJAnalysisCancelled,
    AutoDJAnalyzerProcessError,
    LibrosaAnalyzer,
)
from player.autodj import worker as autodj_worker
from player.frames.autodj import FrameAutoDJMixin
from player.frames.library_tabs.playback_control import PlaylistPlaybackMixin
from player.frames.playback.backend import PlayerBackendMixin
from player.frames.playback.crossfade import CrossfadeMixin
from player.playlists.models import PlaylistState


class AutoDJTests(unittest.TestCase):
    def test_source_environment_does_not_prefer_managed_autodj_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            resource_dir = Path(temporary) / "site-packages"
            resource_dir.mkdir()
            with patch.object(autodj_dependencies, "get_autodj_site_packages_dir", return_value=resource_dir), patch.object(
                autodj_dependencies.sys, "frozen", False, create=True
            ), patch.object(autodj_dependencies, "_autodj_modules_available", return_value=True), patch.object(
                autodj_dependencies.sys, "path", list(autodj_dependencies.sys.path)
            ):
                autodj_dependencies.activate_autodj_dependencies()
                self.assertNotIn(str(resource_dir), autodj_dependencies.sys.path)

    def test_source_environment_uses_managed_resources_when_dependencies_are_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            resource_dir = Path(temporary) / "site-packages"
            resource_dir.mkdir()
            with patch.object(autodj_dependencies, "get_autodj_site_packages_dir", return_value=resource_dir), patch.object(
                autodj_dependencies.sys, "frozen", False, create=True
            ), patch.object(autodj_dependencies, "_autodj_modules_available", return_value=False), patch.object(
                autodj_dependencies.sys, "path", list(autodj_dependencies.sys.path)
            ):
                autodj_dependencies.activate_autodj_dependencies()
                self.assertEqual(autodj_dependencies.sys.path[0], str(resource_dir))

    def test_librosa_analyzer_uses_optional_worker_and_restores_tuple_fields(self):
        payload = {
            "bpm": 120.0,
            "beats_ms": [0, 500],
            "confidence": 0.8,
            "energy": 0.6,
            "phrase_boundaries_ms": [0],
            "section_boundaries_ms": [500],
        }
        def run(command, **_kwargs):
            Path(command[-1]).write_text(json.dumps({"ok": True, "result": payload}), encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch(
            "player.autodj.dependencies.get_autodj_worker_command",
            return_value=["KeyTune.exe", "--autodj-analyzer"],
        ), patch("player.autodj.librosa_analyzer.subprocess.run", side_effect=run) as run_worker:
            result = LibrosaAnalyzer().analyze("track.mp3")

        self.assertEqual(result.beats_ms, (0, 500))
        self.assertEqual(result.phrase_boundaries_ms, (0,))
        self.assertEqual(result.section_boundaries_ms, (500,))
        run_worker.assert_called_once()
        self.assertEqual(run_worker.call_args.args[0][:2], ["KeyTune.exe", "--autodj-analyzer"])

    def test_librosa_analyzer_reports_native_worker_exit_code(self):
        def fail_worker(_command, **kwargs):
            kwargs["stdout"].write(b"native decoder crash")
            return SimpleNamespace(returncode=-1073741819)

        with patch(
            "player.autodj.dependencies.get_autodj_worker_command",
            return_value=["KeyTune.exe", "--autodj-analyzer"],
        ), patch(
            "player.autodj.librosa_analyzer.subprocess.run",
            side_effect=fail_worker,
        ):
            with self.assertRaisesRegex(
                AutoDJAnalyzerProcessError,
                "0xC0000005.*native decoder crash",
            ):
                LibrosaAnalyzer().analyze("track.mp3")

    def test_librosa_analyzer_reports_worker_timeout(self):
        with patch(
            "player.autodj.dependencies.get_autodj_worker_command",
            return_value=["KeyTune.exe", "--autodj-analyzer"],
        ), patch(
            "player.autodj.librosa_analyzer.subprocess.run",
            side_effect=subprocess.TimeoutExpired("KeyTune.exe", 900),
        ):
            with self.assertRaisesRegex(AutoDJAnalyzerProcessError, "tempo limite"):
                LibrosaAnalyzer().analyze("track.mp3")

    def test_librosa_analyzer_terminates_a_cancelled_worker(self):
        class Process:
            args = ["worker"]
            returncode = None

            def __init__(self):
                self.terminated = False

            def poll(self):
                return self.returncode

            def terminate(self):
                self.terminated = True
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.returncode = 1

        process = Process()
        cancel_event = threading.Event()
        cancel_event.set()

        with patch("player.autodj.librosa_analyzer.subprocess.Popen", return_value=process):
            with self.assertRaises(AutoDJAnalysisCancelled):
                LibrosaAnalyzer()._analyze_with_worker(
                    ["worker"], "track.mp3", cancel_event=cancel_event
                )

        self.assertTrue(process.terminated)

    def test_service_deadline_does_not_wait_for_a_busy_analysis(self):
        started = threading.Event()
        release = threading.Event()

        class Analyzer:
            analysis_version = 1

            def analyze(self, _path):
                started.set()
                release.wait(1)
                return AudioAnalysis(120, (0, 500), .9, .5)

        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "first.wav"
            second_path = Path(temporary) / "second.wav"
            first_path.touch()
            second_path.touch()
            service = AutoDJService(Path(temporary) / "cache.db", analyzer=Analyzer())
            first_thread = threading.Thread(target=service.analyze, args=(first_path,))
            first_thread.start()
            self.assertTrue(started.wait(1))
            try:
                with self.assertRaises(AutoDJAnalysisCancelled):
                    service.analyze(second_path, deadline=time.monotonic() + .02)
            finally:
                release.set()
                first_thread.join(1)

            self.assertFalse(first_thread.is_alive())

    def test_real_service_limits_parallel_scientific_analyses(self):
        self.assertEqual(AutoDJService.max_parallel_analyses, 1)

    def test_autodj_worker_writes_result_without_using_console_output(self):
        analysis = AudioAnalysis(120, (0, 500), .8, .6)
        with tempfile.TemporaryDirectory() as temporary:
            result_path = Path(temporary) / "result.json"
            with patch.object(LibrosaAnalyzer, "_analyze_in_process", return_value=analysis):
                exit_code = autodj_worker.main(["track.mp3", "22050", "900", str(result_path)])
            payload = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"]["bpm"], 120)

    def test_autodj_worker_exits_quietly_when_shutdown_removes_the_result_directory(self):
        analysis = AudioAnalysis(120, (0, 500), .8, .6)
        with patch.object(LibrosaAnalyzer, "_analyze_in_process", return_value=analysis), patch.object(
            Path, "write_text", side_effect=FileNotFoundError
        ):
            exit_code = autodj_worker.main(["track.mp3", "22050", "900", "missing/result.json"])

        self.assertEqual(exit_code, 1)

    def test_autodj_worker_limits_native_threads_and_restores_environment(self):
        analysis = AudioAnalysis(120, (0, 500), .8, .6)
        observed_environment = {}

        def analyze(_self, _path):
            observed_environment.update(
                {name: os.environ.get(name) for name in autodj_worker._WORKER_ENVIRONMENT_DEFAULTS}
            )
            return analysis

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {"OPENBLAS_NUM_THREADS": "8"},
            clear=True,
        ), patch.object(LibrosaAnalyzer, "_analyze_in_process", analyze):
            exit_code = autodj_worker.main(
                ["track.mp3", "22050", "900", str(Path(temporary) / "result.json")]
            )
            self.assertEqual(os.environ.get("OPENBLAS_NUM_THREADS"), "8")
            self.assertNotIn("NUMBA_THREADING_LAYER", os.environ)

        self.assertEqual(exit_code, 0)
        self.assertTrue(all(value == "1" or value == "workqueue" for value in observed_environment.values()))

    def test_transition_sound_uses_the_profile_effect(self):
        path = transition_sound_path("party")
        self.assertIsNotNone(path)
        self.assertEqual(path.name, "dj_record_swipe.wav")

    def test_planner_aligns_beats_and_falls_back(self):
        outgoing = AudioAnalysis(120, tuple(range(0, 20000, 500)), .9, .5)
        incoming = AudioAnalysis(122, tuple(range(100, 20000, 492)), .8, .55)
        plan = AutoDJPlanner().plan(outgoing, incoming, beats=16)
        self.assertFalse(plan.fallback_crossfade); self.assertAlmostEqual(plan.tempo_ratio, 120 / 122, places=4)
        weak = AudioAnalysis(120, outgoing.beats_ms, .1, .5)
        self.assertTrue(AutoDJPlanner().plan(outgoing, weak).fallback_crossfade)

    def test_planner_accepts_half_time_and_double_time_tempos(self):
        slow_beats = tuple(range(0, 60000, 857))
        fast_beats = tuple(range(0, 60000, 429))

        slow_to_fast = AutoDJPlanner().plan(
            AudioAnalysis(70, slow_beats, .9, .5),
            AudioAnalysis(140, fast_beats, .9, .5),
        )
        fast_to_slow = AutoDJPlanner().plan(
            AudioAnalysis(140, fast_beats, .9, .5),
            AudioAnalysis(70, slow_beats, .9, .5),
        )

        self.assertFalse(slow_to_fast.fallback_crossfade)
        self.assertFalse(fast_to_slow.fallback_crossfade)
        self.assertEqual(slow_to_fast.tempo_ratio, 1.0)
        self.assertEqual(fast_to_slow.tempo_ratio, 1.0)

    def test_planner_falls_back_when_outgoing_analysis_was_truncated(self):
        beats = tuple(range(0, 900000, 500))
        plan = AutoDJPlanner().plan(
            AudioAnalysis(120, beats, .9, .5, analysis_truncated=True),
            AudioAnalysis(120, tuple(range(0, 180000, 500)), .9, .5),
        )

        self.assertTrue(plan.fallback_crossfade)
        self.assertEqual(plan.reason, "análise limitada pela duração")

    def test_planner_accepts_realistic_librosa_confidence(self):
        outgoing = AudioAnalysis(136, tuple(range(673, 142455, 441)), .433, 1.0)
        incoming = AudioAnalysis(129.2, tuple(range(93, 117796, 464)), .319, 1.0)

        plan = AutoDJPlanner().plan(outgoing, incoming, beats=16)

        self.assertFalse(plan.fallback_crossfade)
        self.assertEqual(plan.incoming_start_ms, 93)
        self.assertAlmostEqual(plan.tempo_ratio, 1.05263, places=5)

    def test_planner_accepts_observed_youtube_music_confidence(self):
        outgoing = AudioAnalysis(129.2, tuple(range(3715, 186109, 464)), .31, 1.0)
        incoming = AudioAnalysis(123.05, tuple(range(139, 218756, 488)), .257, 1.0)

        plan = AutoDJPlanner().plan(outgoing, incoming, beats=16)

        self.assertFalse(plan.fallback_crossfade)
        self.assertIsNotNone(plan.outgoing_end_ms)

    def test_planner_accepts_the_lower_confidence_observed_in_the_real_cache(self):
        beats = tuple(range(0, 40000, 500))
        accepted = AutoDJPlanner().plan(
            AudioAnalysis(120, beats, .209, .5),
            AudioAnalysis(123, beats, .20, .5),
        )
        rejected = AutoDJPlanner().plan(
            AudioAnalysis(120, beats, .209, .5),
            AudioAnalysis(123, beats, .17, .5, entry_ms=4500),
        )

        self.assertFalse(accepted.fallback_crossfade)
        self.assertTrue(rejected.fallback_crossfade)
        self.assertEqual(rejected.reason, "confiança insuficiente")
        self.assertEqual(rejected.incoming_start_ms, 4500)

    def test_planner_keeps_analyzed_entry_when_tempos_require_fallback(self):
        outgoing = AudioAnalysis(129.2, tuple(range(302, 305000, 464)), .282, .7)
        incoming = AudioAnalysis(80.75, tuple(range(2786, 134000, 743)), .241, .7, entry_ms=26564)

        plan = AutoDJPlanner().plan(outgoing, incoming, beats=16)

        self.assertTrue(plan.fallback_crossfade)
        self.assertEqual(plan.reason, "ajuste de tempo excederia o limite")
        self.assertEqual(plan.incoming_start_ms, 26564)

    def test_artist_rule_and_energy_profile(self):
        candidates = [{"artist":"Recente","energy":.5}, {"artist":"Nova","energy":.58}]
        chosen = AutoDJPlanner.choose_next(candidates, recent_artists=["recente"], current_energy=.5, profile=TransitionProfile.PARTY)
        self.assertEqual(chosen["artist"], "Nova")

    def test_planner_uses_four_beat_phrase_boundary(self):
        beats = tuple(range(0, 20500, 500))
        plan = AutoDJPlanner().plan(
            AudioAnalysis(120, beats, .9, .5),
            AudioAnalysis(120, beats, .9, .5),
            beats=16,
        )

        self.assertEqual(plan.outgoing_start_ms, beats[24])
        self.assertEqual(plan.outgoing_end_ms, beats[40])

    def test_planner_uses_active_phrase_entry_and_exit_points(self):
        beats = tuple(range(0, 40500, 500))
        plan = AutoDJPlanner().plan(
            AudioAnalysis(120, beats, .9, .5, exit_ms=beats[72]),
            AudioAnalysis(120, beats, .9, .5, entry_ms=beats[9]),
            beats=16,
        )

        self.assertFalse(plan.fallback_crossfade)
        self.assertEqual(plan.outgoing_start_ms, beats[56])
        self.assertEqual(plan.outgoing_end_ms, beats[72])
        self.assertEqual(plan.incoming_start_ms, beats[12])

    def test_planner_uses_detected_four_bar_phrase_boundaries(self):
        beats = tuple(range(0, 50500, 500))
        plan = AutoDJPlanner().plan(
            AudioAnalysis(
                120,
                beats,
                .9,
                .5,
                exit_ms=beats[75],
                phrase_boundaries_ms=tuple(beats[index] for index in range(8, len(beats), 16)),
            ),
            AudioAnalysis(
                120,
                beats,
                .9,
                .5,
                entry_ms=beats[9],
                phrase_boundaries_ms=tuple(beats[index] for index in range(4, len(beats), 16)),
            ),
            beats=16,
        )

        self.assertEqual(plan.outgoing_start_ms, beats[56])
        self.assertEqual(plan.outgoing_end_ms, beats[72])
        self.assertEqual(plan.incoming_start_ms, beats[20])

    def test_librosa_mix_points_skip_weak_intro_and_outro(self):
        import numpy as np

        beats_ms = tuple(range(0, 20000, 500))
        beat_frames = np.arange(len(beats_ms))
        levels = np.asarray(([.01] * 8) + ([.8] * 24) + ([.01] * 8))

        entry_ms, exit_ms = LibrosaAnalyzer._mix_points(
            beats_ms,
            beat_frames,
            levels.reshape(1, -1),
            np,
        )

        self.assertEqual(entry_ms, beats_ms[8])
        self.assertEqual(exit_ms, beats_ms[32])

    def test_librosa_entry_uses_a_safe_beat_when_the_next_phrase_is_too_late(self):
        entry_ms = LibrosaAnalyzer._select_entry_point(
            302,
            (302, 7733, 15164),
            tuple(range(302, 16000, 465)),
        )

        self.assertEqual(entry_ms, 4022)

    def test_librosa_entry_preserves_the_cue_when_minimum_intro_is_too_late(self):
        entry_ms = LibrosaAnalyzer._select_entry_point(
            500,
            (500, 3500),
            (500, 1500, 2500, 3500, 4500, 5500),
        )

        self.assertEqual(entry_ms, 500)

    def test_librosa_entry_keeps_very_short_cue_playable(self):
        entry_ms = LibrosaAnalyzer._select_entry_point(
            0,
            (0, 1000),
            (0, 1000, 2000, 3000),
        )

        self.assertEqual(entry_ms, 0)

    def test_librosa_entry_does_not_skip_most_of_a_short_track(self):
        beats = tuple(range(0, 10000, 500))

        entry_ms = LibrosaAnalyzer._select_entry_point(0, (0, 8000), beats)

        self.assertLessEqual(entry_ms, beats[-1] * 0.4)

    def test_librosa_entry_caps_a_late_energy_cue(self):
        beats = tuple(range(0, 180000, 500))

        entry_ms = LibrosaAnalyzer._select_entry_point(
            120000, (0, 80000, 160000), beats
        )

        self.assertEqual(entry_ms, 71500)

    def test_librosa_loader_falls_back_after_a_pyav_decode_error(self):
        import numpy as np

        librosa = SimpleNamespace(load=Mock(return_value=(np.ones(20), 10)))
        with patch("av.open", side_effect=OSError("unsupported container")):
            samples, sample_rate, truncated = LibrosaAnalyzer(
                sample_rate=10, maximum_duration_seconds=3
            )._load_audio("track.bin", librosa, np)

        self.assertEqual(sample_rate, 10)
        self.assertEqual(len(samples), 20)
        self.assertFalse(truncated)
        librosa.load.assert_called_once()

    def test_librosa_loader_marks_the_analysis_duration_limit(self):
        import numpy as np

        librosa = SimpleNamespace(load=Mock(return_value=(np.ones(30), 10)))
        with patch.dict(sys.modules, {"av": None}):
            _samples, _sample_rate, truncated = LibrosaAnalyzer(
                sample_rate=10, maximum_duration_seconds=3
            )._load_audio("track.wav", librosa, np)

        self.assertTrue(truncated)

    def test_librosa_beat_estimator_avoids_numba_tracker(self):
        import numpy as np

        onset = np.zeros(440)
        onset[3::22] = 1.0

        bpm, beat_frames, confidence = LibrosaAnalyzer._estimate_beats_from_onsets(
            onset,
            22050,
            np,
        )

        self.assertAlmostEqual(bpm, 117.45, places=2)
        self.assertEqual(tuple(beat_frames[:4]), (3, 25, 47, 69))
        self.assertGreater(confidence, 0.5)

    def test_beat_grid_confidence_is_not_destroyed_by_one_onset_outlier(self):
        import numpy as np

        onset = np.zeros(440)
        beat_frames = np.arange(3, 440, 22)
        onset[beat_frames] = 1.0
        onset[201] = 30.0

        confidence = LibrosaAnalyzer._beat_grid_confidence(onset, beat_frames, 0.7, np)

        self.assertGreaterEqual(confidence, 0.6)

    def test_beat_grid_confidence_rejects_non_finite_input(self):
        import numpy as np

        confidence = LibrosaAnalyzer._beat_grid_confidence(
            np.asarray([np.nan, np.inf, 1.0]),
            np.asarray([2]),
            np.nan,
            np,
        )

        self.assertEqual(confidence, 0.0)

    def test_librosa_estimates_mode_and_downbeat_phase(self):
        import numpy as np
        from player.autodj.librosa_analyzer import MAJOR_PROFILE

        musical_key, musical_mode, confidence = LibrosaAnalyzer._estimate_key(
            np.asarray(MAJOR_PROFILE).reshape(12, 1),
            np,
        )
        onset = np.asarray([.1, .2, 1.0, .1] * 3)
        downbeat_offset = LibrosaAnalyzer._downbeat_offset(
            np.arange(12),
            onset,
            np.zeros((1, 12)),
            np,
        )

        self.assertEqual((musical_key, musical_mode), ("C", "major"))
        self.assertGreater(confidence, 0)
        self.assertEqual(downbeat_offset, 2)

    def test_librosa_beat_estimator_resolves_half_tempo_harmonics(self):
        import numpy as np

        for expected_bpm in (120, 140):
            frames_per_beat = 60.0 * 22050 / (512 * expected_bpm)
            onset = np.zeros(900)
            beat_frames = np.rint(3 + np.arange(40) * frames_per_beat).astype(int)
            onset[beat_frames] = 1.0

            bpm, _estimated_frames, confidence = LibrosaAnalyzer._estimate_beats_from_onsets(
                onset, 22050, np
            )

            self.assertAlmostEqual(bpm, expected_bpm, delta=1.5)
            self.assertGreater(confidence, 0.2)

    def test_librosa_beat_estimator_keeps_confidence_for_a_weaker_harmonic(self):
        import numpy as np

        random = np.random.default_rng(4951)
        onset = np.convolve(
            random.random(900),
            np.ones(random.integers(4, 15)),
            mode="same",
        )
        period = random.integers(28, 52)
        onset += 0.25 * np.sin(2 * np.pi * np.arange(900) / period)

        _bpm, _estimated_frames, confidence = (
            LibrosaAnalyzer._estimate_beats_from_onsets(onset, 22050, np)
        )

        self.assertGreater(confidence, 0.0)

    def test_librosa_beat_estimator_uses_the_tempo_hint_within_safe_limits(self):
        import numpy as np

        onset = np.zeros(900)
        onset[np.arange(3, 900, 20)] = 1.0

        bpm, _estimated_frames, confidence = (
            LibrosaAnalyzer._estimate_beats_from_onsets(
                onset,
                22050,
                np,
                tempo_hint=129.2,
            )
        )
        upper_bpm, _frames, _confidence = (
            LibrosaAnalyzer._estimate_beats_from_onsets(
                onset,
                22050,
                np,
                tempo_hint=500,
            )
        )

        self.assertAlmostEqual(bpm, 129.2, delta=1.0)
        self.assertGreater(confidence, 0.5)
        self.assertLessEqual(upper_bpm, 200.0)

    def test_librosa_beat_estimator_resolves_a_half_tempo_hint(self):
        import numpy as np

        frames_per_beat = 60.0 * 22050 / (512 * 140)
        onset = np.zeros(1200)
        positions = np.rint(3 + np.arange(100) * frames_per_beat).astype(int)
        onset[positions[positions < onset.size]] = 1.0

        bpm, _estimated_frames, confidence = (
            LibrosaAnalyzer._estimate_beats_from_onsets(
                onset,
                22050,
                np,
                tempo_hint=70,
            )
        )

        self.assertAlmostEqual(bpm, 140, delta=1.5)
        self.assertGreater(confidence, 0.2)

    def test_librosa_beat_estimator_rejects_random_onsets(self):
        import numpy as np

        onset = np.random.default_rng(2026).random(1200)

        _bpm, _estimated_frames, confidence = (
            LibrosaAnalyzer._estimate_beats_from_onsets(
                onset,
                22050,
                np,
                tempo_hint=129.2,
            )
        )

        self.assertLess(confidence, 0.18)

    def test_librosa_measures_transition_loudness_without_energy_clipping(self):
        import numpy as np

        samples = np.full(22050 * 4, 0.5, dtype=float)

        entry_db = LibrosaAnalyzer._loudness_around(
            0, samples, 22050, 120, np, forward=True
        )
        exit_db = LibrosaAnalyzer._loudness_around(
            4000, samples, 22050, 120, np, forward=False
        )

        self.assertAlmostEqual(entry_db, -6.02, places=2)
        self.assertAlmostEqual(exit_db, -6.02, places=2)

    def test_librosa_finds_phrase_aligned_structural_boundary(self):
        import numpy as np

        beats_ms = tuple(range(0, 40000, 500))
        beat_frames = np.arange(len(beats_ms))
        chroma = np.zeros((12, len(beats_ms)))
        chroma[0, :40] = 1.0
        chroma[7, 40:] = 1.0
        boundaries = LibrosaAnalyzer._structural_boundaries(
            beats_ms,
            beat_frames,
            0,
            chroma,
            np.ones(len(beats_ms)),
            np.ones((1, len(beats_ms))),
            np,
        )

        self.assertIn(beats_ms[32], boundaries)
        self.assertTrue(all(value in beats_ms[::16] for value in boundaries))

    def test_next_track_selection_prefers_compatible_key(self):
        candidates = [
            {"path": "d", "artist": "A", "energy": .5, "musical_key": "D", "current_key": "C"},
            {"path": "g", "artist": "B", "energy": .5, "musical_key": "G", "current_key": "C"},
        ]

        chosen = AutoDJPlanner.choose_next(candidates, current_energy=.5)

        self.assertEqual(chosen["path"], "g")

    def test_planner_shortens_vocal_overlap_and_attenuates_louder_incoming(self):
        beats = tuple(range(0, 40500, 500))
        outgoing = AudioAnalysis(
            120, beats, .9, .5, "C", exit_ms=beats[72], musical_mode="major",
            loudness_db=-14, exit_vocal_probability=.8,
        )
        incoming = AudioAnalysis(
            120, beats, .9, .5, "G", entry_ms=beats[4], musical_mode="major",
            loudness_db=-8, entry_vocal_probability=.7,
        )

        plan = AutoDJPlanner().plan(outgoing, incoming, beats=32)

        self.assertEqual(plan.beat_count, 8)
        self.assertEqual(plan.incoming_gain_db, -1)
        self.assertEqual(plan.vocal_overlap, .7)

    def test_planner_matches_loudness_at_the_transition_points(self):
        beats = tuple(range(0, 40500, 500))
        outgoing = AudioAnalysis(
            120, beats, .9, .5, loudness_db=-14, exit_loudness_db=-11.0,
        )
        incoming = AudioAnalysis(
            120, beats, .9, .5, loudness_db=-6, entry_loudness_db=-8.2,
        )

        plan = AutoDJPlanner().plan(outgoing, incoming)

        self.assertEqual(plan.incoming_gain_db, -0.8)

    def test_planner_uses_deadband_and_caps_transition_attenuation(self):
        beats = tuple(range(0, 40500, 500))
        outgoing = AudioAnalysis(
            120, beats, .9, .5, exit_loudness_db=-12.0,
        )
        within_deadband = AudioAnalysis(
            120, beats, .9, .5, entry_loudness_db=-10.1,
        )
        much_louder = AudioAnalysis(
            120, beats, .9, .5, entry_loudness_db=-6.0,
        )

        self.assertEqual(AutoDJPlanner().plan(outgoing, within_deadband).incoming_gain_db, 0.0)
        self.assertEqual(AutoDJPlanner().plan(outgoing, much_louder).incoming_gain_db, -1.0)

    def test_queue_planner_builds_multiple_compatible_steps(self):
        beats = tuple(range(0, 40500, 500))
        current = AudioAnalysis(120, beats, .9, .5, "C", musical_mode="major", exit_energy=.5)
        candidates = [
            QueueCandidate("f-sharp.mp3", "A", AudioAnalysis(120, beats, .9, .8, "F♯", musical_mode="major", entry_energy=.8), 0),
            QueueCandidate("g.mp3", "B", AudioAnalysis(120, beats, .9, .5, "G", musical_mode="major", entry_energy=.5), 1),
            QueueCandidate("d.mp3", "C", AudioAnalysis(120, beats, .9, .52, "D", musical_mode="major", entry_energy=.52), 2),
        ]

        selections = AutoDJQueuePlanner().plan(current, candidates, count=2)

        self.assertEqual([item.path for item in selections], ["g.mp3", "d.mp3"])

    def test_mix_profiles_have_distinct_curves_without_tonal_adjustments(self):
        smooth = mix_values(.1, TransitionProfile.SMOOTH)
        party = mix_values(.1, TransitionProfile.PARTY)
        electronic = mix_values(.1, TransitionProfile.ELECTRONIC)

        self.assertNotEqual(smooth.incoming_volume, party.incoming_volume)
        self.assertNotEqual(party.incoming_volume, electronic.incoming_volume)
        for profile in TransitionProfile:
            for progress in (0.0, 0.5, 1.0):
                values = mix_values(progress, profile)
                self.assertEqual(values.incoming_bass_db, 0.0)
                self.assertEqual(values.outgoing_bass_db, 0.0)
                self.assertEqual(values.incoming_mid_db, 0.0)
                self.assertEqual(values.outgoing_mid_db, 0.0)
        self.assertAlmostEqual(mix_values(.5, TransitionProfile.PARTY).incoming_volume, 2 ** -0.5)
        self.assertAlmostEqual(mix_values(.5, TransitionProfile.PARTY).outgoing_volume, 2 ** -0.5)

    def test_neutral_mix_does_not_add_audio_filters(self):
        self.assertEqual(build_mix_lavfi_filters(0, 0), ())

    def test_mix_filters_use_named_lavfi_chain_for_live_commands(self):
        filters = build_mix_lavfi_filters(-12, -3)
        self.assertTrue(any("f=80" in item for item in filters))
        self.assertTrue(any("equalizer@autodj_bass_80" in item for item in filters))

        class Player:
            def set_audio_filters(self, value): self.filters = value

        class Frame(PlayerBackendMixin):
            current_pitch_semitones = 0

        player = Player()
        Frame()._apply_audio_filter_chain_to_player(
            player,
            "lavfi=[volume=volume=0.0dB,alimiter=limit=0.97:attack=5:release=50:level=disabled]",
            filters,
        )
        self.assertEqual(player.filters.count("lavfi=["), 2)
        self.assertEqual(player.filters.count("alimiter="), 1)
        self.assertIn("@autodj_mix:lavfi=[", player.filters)
        self.assertIn("equalizer@autodj_bass_80=f=80", player.filters)

    def test_mix_gain_updates_do_not_rebuild_audio_filter_chain(self):
        class Player:
            def __init__(self): self.commands = []
            def command_audio_filter(self, *args):
                self.commands.append(args)
                return True

        player = Player()
        from player.frames.equalizer import FrameEqualizerMixin

        self.assertTrue(FrameEqualizerMixin._update_autodj_mix_filter_on_player(player, -12, -3))
        self.assertEqual(len(player.commands), 3)
        self.assertEqual(
            player.commands[0],
            ("autodj_mix", "gain", "-12.00", "equalizer@autodj_bass_80"),
        )

        player.commands.clear()
        self.assertTrue(FrameEqualizerMixin._update_autodj_mix_filter_on_player(player, 0, 0))
        self.assertEqual(player.commands, [])

    def test_autodj_next_is_transient_and_manual_queue_has_priority(self):
        state = PlaylistState(title="Teste")
        state.set_items(["a.mp3", "b.mp3", "c.mp3"])
        self.assertTrue(state.set_autodj_next("c.mp3"))
        self.assertEqual(state.peek_in_playback_order(1), "c.mp3")
        self.assertEqual(state.move_in_playback_order(1), "c.mp3")
        self.assertIsNone(state.autodj_next_path)

        state.select_index(0)
        state.enqueue_item("b.mp3")
        self.assertFalse(state.set_autodj_next("c.mp3"))
        self.assertEqual(state.peek_in_playback_order(1), "b.mp3")

    def test_finished_analysis_promotes_selected_candidate(self):
        outgoing = AudioAnalysis(120, tuple(range(0, 20000, 500)), .9, .5, "C")
        incoming = AudioAnalysis(120, tuple(range(0, 20000, 500)), .9, .55, "G")
        plan = AutoDJPlanner().plan(outgoing, incoming)

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.settings = SimpleNamespace(
                    autodj_enabled=True,
                    autodj_profile="party",
                )
                self.state = PlaylistState(title="Teste")
                self.state.set_items(["a.mp3", "b.mp3", "c.mp3"])
                self._autodj_transition_requests = {
                    ("a.mp3", "b.mp3"): {"status": "pending"},
                }

            def _get_active_playlist_state(self): return self.state

        frame = Frame()
        frame._finish_autodj_transition_analysis(
            ("a.mp3", "b.mp3"),
            "c.mp3",
            outgoing,
            incoming,
            plan,
            "",
        )

        self.assertEqual(frame.state.peek_in_playback_order(1), "c.mp3")
        prepared = frame._prepared_autodj_transition(frame.state)
        self.assertEqual(prepared["pair"], ("a.mp3", "c.mp3"))
        self.assertEqual(prepared["profile"], "party")

    def test_new_playlist_analyzes_all_candidates_before_selecting(self):
        beats = tuple(range(0, 40500, 500))
        analyzed_paths = []
        finished = threading.Event()

        def analysis_for(path):
            values = {
                "bpm": 120,
                "beats_ms": beats,
                "confidence": .9,
                "energy": .5,
                "musical_key": "G" if path == "c.mp3" else "F♯",
                "musical_mode": "major",
                "key_confidence": .9,
                "entry_ms": beats[4],
                "exit_ms": beats[72],
                "phrase_boundaries_ms": tuple(beats[index] for index in range(4, len(beats), 16)),
                "entry_energy": .5 if path == "c.mp3" else .8,
                "exit_energy": .5,
                "loudness_db": -14.0 if path == "c.mp3" else -7.0,
            }
            if path == "a.mp3":
                values["musical_key"] = "C"
                values["phrase_boundaries_ms"] = tuple(beats[index] for index in range(8, len(beats), 16))
            return values

        class Service:
            def analyze(self, path):
                analyzed_paths.append(path)
                return analysis_for(path)

        class Player:
            def get_media(self): return object()
            def is_playing(self): return True

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.settings = SimpleNamespace(autodj_enabled=True, autodj_profile="smooth", autodj_beats=16)
                self.state = PlaylistState(title="Nova")
                self.state.set_items(["a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3", "f.mp3", "g.mp3"])
                self.autodj_service = Service()
                self.player = Player()
                self._autodj_transition_requests = {}

            def _get_active_playlist_state(self): return self.state
            def _refresh_playlist_browser(self): pass
            def _set_status_message(self, *_args, **_kwargs): pass
            def _finish_autodj_transition_analysis(self, *args):
                super()._finish_autodj_transition_analysis(*args)
                finished.set()

        frame = Frame()
        with patch("player.frames.autodj.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)):
            self.assertTrue(frame._maybe_prepare_autodj_transition())
            self.assertTrue(finished.wait(5))

        self.assertEqual(set(analyzed_paths), {"a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3", "f.mp3", "g.mp3"})
        self.assertEqual(frame.state.peek_in_playback_order(1), "c.mp3")

    def test_transition_candidate_timeout_falls_back_without_accepting_late_result(self):
        beats = tuple(range(0, 40500, 500))
        release_candidate = threading.Event()
        finished = threading.Event()

        class Service:
            max_parallel_analyses = 1

            def analyze(self, path):
                if path == "b.mp3":
                    release_candidate.wait(1)
                return {
                    "bpm": 120,
                    "beats_ms": beats,
                    "confidence": .9,
                    "energy": .5,
                }

        class Player:
            def get_media(self): return object()
            def is_playing(self): return True

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.settings = SimpleNamespace(autodj_enabled=True, autodj_profile="smooth", autodj_beats=16)
                self.state = PlaylistState(title="AutoDJ")
                self.state.set_items(["a.mp3", "b.mp3"])
                self.state.autodj_session = True
                self.playlists = [self.state]
                self.autodj_service = Service()
                self.player = Player()
                self._autodj_transition_requests = {}
                self._autodj_session_requests = {}
                self._autodj_session_results = {}
                self._autodj_session_retry_at = {}
                self._autodj_transition_candidate_wait_seconds = .01

            def _get_active_playlist_state(self): return self.state
            def _refresh_autodj_session_ui(self, _state=None): pass
            def _set_status_message(self, *_args, **_kwargs): pass
            def _finish_autodj_transition_analysis(self, *args):
                super()._finish_autodj_transition_analysis(*args)
                finished.set()

        frame = Frame()
        with patch("player.frames.autodj.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)):
            self.assertTrue(frame._maybe_prepare_autodj_transition())
            self.assertTrue(finished.wait(1))

        release_candidate.set()
        request = frame._autodj_transition_requests[("a.mp3", "b.mp3")]
        self.assertEqual(request["status"], "failed")
        self.assertIsNone(frame._prepared_autodj_transition(frame.state))

    def test_autodj_session_fills_a_five_track_rolling_queue(self):
        beats = tuple(range(0, 40500, 500))
        finished = threading.Event()
        analyzed_paths = []

        class Service:
            def analyze(self, path):
                analyzed_paths.append(path)
                return {
                    "bpm": 120,
                    "beats_ms": beats,
                    "confidence": .9,
                    "energy": .5,
                    "musical_key": "C",
                    "musical_mode": "major",
                    "entry_energy": .5,
                    "exit_energy": .5,
                }

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.settings = SimpleNamespace(autodj_profile="smooth", autodj_beats=16)
                self.state = PlaylistState(title="AutoDJ — Nova")
                self.state.set_items(["a.mp3"])
                self.state.autodj_session = True
                self.state.autodj_source_items = ["a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3", "f.mp3", "g.mp3"]
                self.state.autodj_source_labels = list(self.state.autodj_source_items)
                self.state.autodj_remaining_items = list(self.state.autodj_source_items[1:])
                self.playlists = [self.state]
                self.autodj_service = Service()
                self._autodj_session_requests = {}
                self._autodj_session_retry_at = {}

            def _get_active_playlist_state(self): return self.state
            def _get_playlist_state(self, _index=None): return self.state
            def _refresh_playlist_browser(self): pass
            def _set_status_message(self, *_args, **_kwargs): pass
            def _finish_autodj_session_fill(self, *args):
                super()._finish_autodj_session_fill(*args)
                finished.set()

        frame = Frame()
        with patch("player.frames.autodj.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)):
            self.assertTrue(frame._maybe_fill_autodj_session())
            self.assertTrue(finished.wait(5))

        self.assertEqual(len(frame.state.items), 6)
        self.assertEqual(len(frame.state.autodj_remaining_items), 1)
        self.assertEqual(
            set(analyzed_paths),
            {"a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3", "f.mp3", "g.mp3"},
        )

    def test_autodj_session_uses_completed_candidates_when_another_analysis_stalls(self):
        beats = tuple(range(0, 40500, 500))
        finished = threading.Event()
        stalled = threading.Event()

        class Service:
            def analyze(self, path):
                if path == "b.mp3":
                    stalled.wait(1)
                return {
                    "bpm": 120,
                    "beats_ms": beats,
                    "confidence": .9,
                    "energy": .5,
                }

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.settings = SimpleNamespace(autodj_profile="smooth", autodj_beats=16)
                self.state = PlaylistState(title="AutoDJ")
                self.state.set_items(["a.mp3"])
                self.state.autodj_session = True
                self.state.autodj_source_items = ["a.mp3", "b.mp3", "c.mp3"]
                self.state.autodj_source_labels = list(self.state.autodj_source_items)
                self.state.autodj_remaining_items = ["b.mp3", "c.mp3"]
                self.playlists = [self.state]
                self.autodj_service = Service()
                self._autodj_session_requests = {}
                self._autodj_session_retry_at = {}
                self._autodj_session_candidate_wait_seconds = .05

            def _get_active_playlist_state(self): return self.state
            def _get_playlist_state(self, _index=None): return self.state
            def _refresh_playlist_browser(self): pass
            def _set_status_message(self, *_args, **_kwargs): pass
            def _finish_autodj_session_fill(self, *args):
                super()._finish_autodj_session_fill(*args)
                finished.set()

        frame = Frame()
        with patch("player.frames.autodj.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)):
            self.assertTrue(frame._maybe_fill_autodj_session())
            self.assertTrue(finished.wait(1))

        self.assertEqual(frame.state.items, ["a.mp3", "c.mp3"])
        stalled.set()

    def test_autodj_session_drains_completed_analysis_when_callafter_is_missed(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["a.mp3"])
        state.autodj_session = True
        state.autodj_source_items = ["a.mp3", "b.mp3"]
        state.autodj_source_labels = list(state.autodj_source_items)
        state.autodj_remaining_items = ["b.mp3"]
        cancel_event = threading.Event()

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.state = state
                self.playlists = [state]
                self.autodj_service = object()
                self._autodj_session_requests = {id(state): cancel_event}
                self._autodj_session_results = {}
                self._autodj_session_retry_at = {}

            def _get_active_playlist_state(self): return self.state
            def _refresh_playlist_browser(self): pass
            def _set_status_message(self, *_args, **_kwargs): pass

        frame = Frame()
        with patch("player.frames.autodj.wx.CallAfter"):
            frame._queue_autodj_session_fill(
                state,
                "a.mp3",
                [SimpleNamespace(path="b.mp3")],
                "",
                cancel_event,
            )
        self.assertFalse(frame._maybe_fill_autodj_session())
        self.assertEqual(state.items, ["a.mp3", "b.mp3"])
        self.assertNotIn(id(state), frame._autodj_session_requests)

    def test_autodj_resumes_after_waiting_for_the_next_prepared_track(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["a.mp3"])
        state.autodj_session = True
        state.autodj_source_items = ["a.mp3", "b.mp3"]
        state.autodj_source_labels = list(state.autodj_source_items)
        state.autodj_remaining_items = ["b.mp3"]
        state.autodj_waiting_for_next = True
        cancel_event = threading.Event()

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.state = state
                self.playlists = [state]
                self._autodj_session_requests = {id(state): cancel_event}
                self._autodj_session_retry_at = {}
                self.play_requests = []

            def _get_active_playlist_state(self): return self.state
            def _get_active_playlist_index(self): return 0
            def _refresh_playlist_browser(self): pass
            def _play_media(self, **kwargs): self.play_requests.append(kwargs)

        frame = Frame()
        frame._finish_autodj_session_fill(
            state,
            "a.mp3",
            [SimpleNamespace(path="b.mp3")],
            "",
            cancel_event,
        )
        self.assertEqual(state.current_media_path, "b.mp3")
        self.assertEqual(frame.play_requests, [{"index": 0}])

    def test_start_autodj_session_creates_separate_dynamic_playlist(self):
        source = PlaylistState(title="Origem")
        source.set_items(["a.mp3", "b.mp3", "c.mp3"])
        source.browser_item_labels = ["A — Faixa", "B — Faixa", "C — Faixa"]

        class Notebook:
            def SetPageText(self, *_args): pass

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.settings = SimpleNamespace()
                self.playlists = [source]
                self.active_index = 0
                self.notebook = Notebook()
                self.played = []

            def _get_playlist_state(self, index=None):
                return self.playlists[self.active_index if index is None else index]
            def _create_empty_playlist_tab(self, select=False):
                self.playlists.append(PlaylistState(title="Nova"))
                return len(self.playlists) - 1
            def _select_tab(self, index, announce=False): self.active_index = index
            def _refresh_playlist_browser(self): pass
            def _play_media(self, **kwargs): self.played.append(kwargs)
            def _maybe_fill_autodj_session(self, _state=None): return True
            def _refresh_autodj_menu_state(self): pass
            def _announce(self, _message): pass

        frame = Frame()
        self.assertTrue(frame.on_start_autodj_session(None))

        session = frame.playlists[1]
        self.assertEqual(source.items, ["a.mp3", "b.mp3", "c.mp3"])
        self.assertTrue(session.autodj_session)
        self.assertEqual(session.items, ["a.mp3"])
        self.assertEqual(session.autodj_remaining_items, ["b.mp3", "c.mp3"])
        self.assertEqual(frame.played[0]["index"], 1)

    def test_autodj_session_can_replace_next_without_changing_current_track(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["A", "B", "C"])
        state.autodj_session = True
        state.autodj_remaining_items = ["D", "E"]

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.state = state
                self.playlists = [state]
                self._autodj_session_requests = {}
                self._autodj_session_retry_at = {}
                self._autodj_transition_requests = {("A", "B"): {"status": "ready"}}
                self.fill_calls = []
                self.announcements = []

            def _get_playlist_state(self, _index=None): return self.state
            def _refresh_playlist_browser(self): pass
            def _maybe_fill_autodj_session(self, session=None): self.fill_calls.append(session); return True
            def _announce(self, message): self.announcements.append(message)

        frame = Frame()
        self.assertTrue(frame.on_replace_autodj_next(None))
        self.assertEqual(state.current_media_path, "A")
        self.assertEqual(state.items, ["A", "C"])
        self.assertEqual(state.autodj_remaining_items, ["D", "E", "B"])
        self.assertEqual(frame._autodj_transition_requests, {})
        self.assertEqual(frame.fill_calls, [state])

    def test_autodj_session_recalculates_only_future_tracks(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["A", "B", "C", "D"], start_index=1)
        state.autodj_session = True
        state.autodj_remaining_items = ["E", "F"]
        state.autodj_history = ["A"]

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.state = state
                self.playlists = [state]
                self._autodj_session_requests = {}
                self._autodj_session_retry_at = {}
                self._autodj_transition_requests = {}

            def _get_playlist_state(self, _index=None): return self.state
            def _refresh_playlist_browser(self): pass
            def _maybe_fill_autodj_session(self, _state=None): return True
            def _announce(self, _message): pass

        frame = Frame()
        self.assertTrue(frame.on_recalculate_autodj_session(None))
        self.assertEqual(state.items, ["A", "B"])
        self.assertEqual(state.current_media_path, "B")
        self.assertEqual(state.autodj_history, ["A"])
        self.assertEqual(state.autodj_remaining_items, ["E", "F", "C", "D"])

    def test_autodj_preparation_pause_cancels_fill_and_is_resumable(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["A", "B"])
        state.autodj_session = True

        class Request:
            def __init__(self): self.cancelled = False
            def set(self): self.cancelled = True

        request = Request()

        class Frame(FrameAutoDJMixin):
            def __init__(self):
                self.state = state
                self.playlists = [state]
                self._autodj_session_requests = {id(state): request}
                self._autodj_session_retry_at = {}
                self.fill_count = 0

            def _get_playlist_state(self, _index=None): return self.state
            def _refresh_playlist_browser(self): pass
            def _maybe_fill_autodj_session(self, _state=None): self.fill_count += 1; return True
            def _announce(self, _message): pass

        frame = Frame()
        self.assertTrue(frame.on_toggle_autodj_preparation(None))
        self.assertTrue(state.autodj_preparation_paused)
        self.assertTrue(request.cancelled)
        self.assertTrue(frame.on_toggle_autodj_preparation(None))
        self.assertFalse(state.autodj_preparation_paused)
        self.assertEqual(frame.fill_count, 1)

    def test_autodj_transition_description_exposes_mix_decisions(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["A.mp3", "B.mp3"])
        state.autodj_session = True
        plan = SimpleNamespace(
            beat_count=8,
            fallback_crossfade=False,
            vocal_overlap=True,
            incoming_gain_db=-2.5,
            tempo_ratio=1.02,
        )

        class Frame(FrameAutoDJMixin):
            settings = SimpleNamespace(autodj_enabled=False)
            _autodj_transition_requests = {
                ("A.mp3", "B.mp3"): {
                    "status": "ready",
                    "plan": plan,
                    "outgoing": AudioAnalysis(120, (), .31, .5),
                    "incoming": AudioAnalysis(123, (), .21, .5),
                }
            }

        details, status = Frame()._autodj_transition_description(state)
        self.assertIn("8 batidas", details)
        self.assertIn("Vocais protegidos", details)
        self.assertIn("-2.5 dB", details)
        self.assertIn("120.0 BPM", details)
        self.assertIn("confiança 31%", details)
        self.assertIn("8 batidas", status)

    def test_autodj_fallback_description_exposes_the_actual_reason(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["A.mp3", "B.mp3"])
        state.autodj_session = True
        plan = AutoDJPlanner().plan(
            AudioAnalysis(120, tuple(range(0, 40000, 500)), .17, .5),
            AudioAnalysis(122, tuple(range(0, 40000, 492)), .30, .5),
        )

        class Frame(FrameAutoDJMixin):
            settings = SimpleNamespace(autodj_enabled=False)
            _autodj_transition_requests = {
                ("A.mp3", "B.mp3"): {
                    "status": "ready",
                    "plan": plan,
                    "outgoing": AudioAnalysis(120, (), .17, .5),
                    "incoming": AudioAnalysis(122, (), .30, .5),
                }
            }

        details, status = Frame()._autodj_transition_description(state)

        self.assertIn("confiança rítmica insuficiente", details)
        self.assertIn("confiança 17%", details)
        self.assertEqual(status, "Próxima, transição comum")

    def test_autodj_session_ui_reports_queue_and_item_states(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["A.mp3", "B.mp3", "C.mp3"], start_index=1)
        state.autodj_session = True
        state.autodj_source_title = "Origem"
        state.autodj_remaining_items = ["D.mp3", "E.mp3"]

        class Panel:
            def update_session(self, **values): self.values = values

        class Browser:
            def set_item_statuses(self, statuses): self.statuses = statuses

        page = SimpleNamespace(autodj_panel=Panel(), browser_panel=Browser())

        class Notebook:
            def GetSelection(self): return 0
            def GetPageCount(self): return 1
            def GetPage(self, _index): return page

        class Frame(FrameAutoDJMixin):
            settings = SimpleNamespace(autodj_enabled=False)
            notebook = Notebook()
            _autodj_session_requests = {}
            _autodj_transition_requests = {}

            def _get_playlist_state(self, _index=None): return state

        frame = Frame()
        frame._refresh_autodj_session_ui(state)

        self.assertIn("Origem", page.autodj_panel.values["summary"])
        self.assertIn("Na fila: 1", page.autodj_panel.values["summary"])
        self.assertIn("Analisadas na fila: 0", page.autodj_panel.values["summary"])
        self.assertIn("análise não confirmada", page.browser_panel.statuses["C.mp3"])
        self.assertEqual(page.browser_panel.statuses["A.mp3"], "Tocada")
        self.assertEqual(page.browser_panel.statuses["B.mp3"], "Tocando")
        self.assertIn("Próxima", page.browser_panel.statuses["C.mp3"])

        frame.autodj_service = SimpleNamespace(get_analysis_status=lambda path: "failed")
        frame._refresh_autodj_session_ui(state)
        self.assertIn("A análise da faixa atual falhou", page.autodj_panel.values["summary"])
        self.assertIn("Com falha na fila: 1", page.autodj_panel.values["summary"])
        self.assertIn("Falha na análise", page.browser_panel.statuses["C.mp3"])
        self.assertNotIn("Preparada", page.browser_panel.statuses["C.mp3"])

        frame.autodj_service = SimpleNamespace(get_analysis_status=lambda path: "ready")
        frame._refresh_autodj_session_ui(state)
        self.assertIn("Analisadas na fila: 1", page.autodj_panel.values["summary"])
        self.assertIn("Com falha na fila: 0", page.autodj_panel.values["summary"])
        self.assertNotIn("falhou", page.autodj_panel.values["summary"])

    def test_frame_converts_cached_analysis_and_derives_beat_duration(self):
        analysis = FrameAutoDJMixin._audio_analysis_from_result(
            {"bpm": 120, "beats_ms": [100, 600], "confidence": .8, "energy": .5}
        )
        transition = {
            "outgoing": analysis,
            "plan": AutoDJPlanner().plan(
                AudioAnalysis(120, tuple(range(0, 20000, 500)), .9, .5),
                AudioAnalysis(121, tuple(range(0, 20000, 496)), .9, .5),
                beats=16,
            ),
        }

        self.assertEqual(analysis.beats_ms, (100, 600))
        self.assertEqual(FrameAutoDJMixin._autodj_transition_duration_ms(transition), 8000)

    def test_prepared_transition_starts_at_planned_outgoing_beat(self):
        transition = {
            "pair": ("outgoing.mp3", "incoming.mp3"),
            "plan": SimpleNamespace(outgoing_start_ms=12000),
        }

        class State(PlaylistState):
            def __init__(self):
                super().__init__(title="AutoDJ")
                self.set_items(["outgoing.mp3", "incoming.mp3"])

        class Player:
            def __init__(self, current_time):
                self.current_time = current_time

            def get_media(self): return object()
            def is_playing(self): return True
            def get_time(self): return self.current_time
            def get_length(self): return 20000

        class Frame(PlaylistPlaybackMixin):
            def __init__(self, current_time):
                self._crossfade_state = None
                self.state = State()
                self.player = Player(current_time)
                self.play_request = None

            def _get_playlist_state(self, _index=None): return self.state
            def _prepared_autodj_transition(self, _state): return transition
            def _autodj_transition_duration_ms(self, _transition): return 8000
            def _autodj_preload_lead_ms(self, _media_path): return 1000
            def _can_crossfade_to_media(self, media_path, *, duration_override_ms=None):
                return media_path == "incoming.mp3" and duration_override_ms == 8000
            def _get_active_playlist_index(self): return 0
            def _describe_playlist_position(self, _state): return "Próxima faixa."
            def _play_media(self, **kwargs): self.play_request = kwargs

        early_frame = Frame(10999)
        self.assertFalse(early_frame._maybe_start_automatic_crossfade())
        self.assertIsNone(early_frame.play_request)

        frame = Frame(11000)
        self.assertTrue(frame._maybe_start_automatic_crossfade())
        self.assertIs(frame.play_request["autodj_transition"], transition)
        self.assertTrue(frame.play_request["allow_crossfade"])

    def test_fallback_autodj_transition_starts_before_the_end(self):
        plan = AutoDJPlanner().plan(
            AudioAnalysis(120, tuple(range(0, 20000, 500)), .1, .5),
            AudioAnalysis(122, tuple(range(0, 20000, 492)), .8, .5),
            beats=8,
        )
        transition = {"pair": ("outgoing.mp3", "incoming.mp3"), "plan": plan, "outgoing": AudioAnalysis(120, (), .1, .5)}

        class State(PlaylistState):
            def __init__(self):
                super().__init__(title="AutoDJ")
                self.set_items(["outgoing.mp3", "incoming.mp3"])

        class Player:
            def get_media(self): return object()
            def is_playing(self): return True
            def get_time(self): return 15000
            def get_length(self): return 20000

        class Frame(PlaylistPlaybackMixin):
            def __init__(self):
                self._crossfade_state = None
                self.state = State()
                self.player = Player()
                self.play_request = None

            def _get_playlist_state(self, _index=None): return self.state
            def _prepared_autodj_transition(self, _state): return transition
            def _autodj_transition_duration_ms(self, _transition): return 4000
            def _autodj_preload_lead_ms(self, _media_path): return 1000
            def _can_crossfade_to_media(self, _path, *, duration_override_ms=None): return duration_override_ms == 4000
            def _get_active_playlist_index(self): return 0
            def _describe_playlist_position(self, _state): return "Próxima faixa."
            def _play_media(self, **kwargs): self.play_request = kwargs

        frame = Frame()
        self.assertTrue(frame._maybe_start_automatic_crossfade())
        scheduled_plan = frame.play_request["autodj_transition"]["plan"]
        self.assertEqual(scheduled_plan.outgoing_start_ms, 16000)
        self.assertEqual(scheduled_plan.outgoing_end_ms, 20000)
        self.assertTrue(frame.play_request["allow_crossfade"])

    def test_crossfade_receives_autodj_entry_and_tempo(self):
        plan = SimpleNamespace(
            incoming_start_ms=750,
            outgoing_start_ms=12000,
            outgoing_end_ms=20000,
            tempo_ratio=1.025,
        )
        transition = {"plan": plan}

        class Frame(CrossfadeMixin):
            current_volume = 80
            _active_player_key = "primary"
            _crossfade_state = None

            def _autodj_transition_duration_ms(self, _transition): return 8000
            def _inactive_player_key(self): return "secondary"
            def _stop_player(self, *_args, **_kwargs): pass
            def _apply_volume_to_player(self, *_args, **_kwargs): pass
            def _queue_media_start(self, _media_path, **kwargs):
                self.queued = kwargs
                return {"serial": 42}
            def _crossfade_pending_timeout_seconds(self, _media_path): return 15
            def _ensure_crossfade_timer_running(self): pass

        frame = Frame()
        self.assertTrue(
            frame._start_crossfade(
                "incoming.mp3",
                tab_index=0,
                autodj_transition=transition,
            )
        )
        self.assertEqual(frame.queued["start_position_ms"], 750)
        self.assertTrue(frame.queued["pause_after_start"])
        self.assertEqual(frame._crossfade_state["duration_ms"], 8000)
        self.assertAlmostEqual(frame._crossfade_state["tempo_ratio"], 1.025)
        self.assertEqual(frame._crossfade_state["scheduled_outgoing_start_ms"], 12000)
        self.assertEqual(frame._crossfade_state["scheduled_outgoing_end_ms"], 20000)
        self.assertEqual(frame._crossfade_state["autodj_profile"], "smooth")

    def test_autodj_progress_follows_outgoing_beat_grid(self):
        class Player:
            def __init__(self, current_time): self.current_time = current_time
            def get_time(self): return self.current_time

        class Frame(CrossfadeMixin):
            current_volume = 80

            def __init__(self):
                self.outgoing = Player(16000)
                self.volumes = {}
                self.finished = False
                self._crossfade_state = {
                    "phase": "running",
                    "started_at": 0,
                    "duration_ms": 8000,
                    "autodj": True,
                    "autodj_profile": "party",
                    "autodj_filter_step": None,
                    "outgoing_key": "outgoing",
                    "incoming_key": "incoming",
                    "scheduled_outgoing_start_ms": 12000,
                    "scheduled_outgoing_end_ms": 20000,
                    "outgoing_ended": False,
                    "incoming_gain_db": -2.0,
                }

            def _managed_player(self, key): return self.outgoing if key == "outgoing" else None
            def _apply_autodj_mix_filters(self, *_args): pass
            def _apply_volume_to_player(self, key, volume): self.volumes[key] = volume
            def _finish_crossfade(self): self.finished = True

        frame = Frame()
        with patch("player.frames.playback.crossfade.time.monotonic", return_value=100):
            frame._apply_crossfade_volumes()

        self.assertEqual(frame.volumes["incoming"], 45)
        self.assertEqual(frame.volumes["outgoing"], 57)

        frame.outgoing.current_time = 20000
        with patch("player.frames.playback.crossfade.time.monotonic", return_value=100):
            frame._apply_crossfade_volumes()
        self.assertEqual(frame.volumes["incoming"], 80)
        self.assertTrue(frame.finished)

    def test_autodj_phase_correction_gently_accelerates_late_incoming_track(self):
        class Player:
            def get_time(self): return 2400

        class Frame(CrossfadeMixin):
            current_playback_rate = 1.0

            def __init__(self): self.rates = []
            def _managed_player(self, _key): return Player()
            def _apply_playback_rate_to_player(self, key, rate): self.rates.append((key, rate))

        state = {
            "incoming_key": "in",
            "incoming_start_ms": 500,
            "incoming_beat_ms": 500,
            "scheduled_outgoing_start_ms": 10000,
            "tempo_ratio": 1.0,
            "next_phase_correction_at": 0.0,
            "phase_rate": None,
        }
        frame = Frame()
        frame._correct_autodj_phase(state, 12000)

        self.assertGreater(frame.rates[0][1], 1.0)
        self.assertLessEqual(frame.rates[0][1], 1.012)

    def test_autodj_preload_waits_for_exact_outgoing_position(self):
        class Player:
            def __init__(self, current_time=0):
                self.current_time = current_time
                self.play_calls = 0

            def get_time(self): return self.current_time
            def play(self): self.play_calls += 1
            def is_playing(self): return True

        class Frame(CrossfadeMixin):
            def __init__(self):
                self.outgoing = Player(11999)
                self.incoming = Player()
                self.began = False
                self._crossfade_state = {
                    "phase": "pending",
                    "autodj": True,
                    "incoming_ready": True,
                    "incoming_key": "incoming",
                    "outgoing_key": "outgoing",
                    "scheduled_outgoing_start_ms": 12000,
                    "created_at": None,
                    "outgoing_ended": False,
                    "media_path": "incoming.mp3",
                    "pending_timeout_seconds": 15,
                }

            def _managed_player(self, key):
                return self.incoming if key == "incoming" else self.outgoing

            def _begin_pending_crossfade(self):
                self.began = True

        frame = Frame()
        frame._tick_crossfade()
        self.assertEqual(frame.incoming.play_calls, 0)
        self.assertFalse(frame.began)

        frame.outgoing.current_time = 12000
        frame._tick_crossfade()
        self.assertEqual(frame.incoming.play_calls, 1)
        self.assertTrue(frame.began)

    def test_wave_analysis_and_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "click.wav"; rate = 8000; samples = []
            for index in range(rate * 8):
                phase = index % (rate // 2)
                samples.append(25000 if phase < 40 else int(600 * math.sin(index / 8)))
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
                output.writeframes(b"".join(struct.pack("<h", value) for value in samples))
            analysis = WaveAnalyzer().analyze(path)
            self.assertGreater(analysis.confidence, 0); self.assertGreater(len(analysis.beats_ms), 5)
            cache = AnalysisCache(Path(temporary) / "cache.db"); cache.put(path, analysis)
            self.assertEqual(cache.get(path), analysis)

    def test_remote_analysis_downloads_once_and_uses_cache(self):
        class Analyzer:
            analysis_version = 99
            def __init__(self): self.calls = 0
            def analyze(self, path):
                self.calls += 1
                self.asserted_bytes = Path(path).read_bytes()
                return AudioAnalysis(100, (0, 600), .8, .4, "C")
        class Playback:
            stream_url = "https://example.invalid/audio"
            http_headers = {"Authorization": "secret"}
        with tempfile.TemporaryDirectory() as temporary:
            analyzer = Analyzer()
            service = AutoDJService(Path(temporary) / "cache.db", remote_resolver=lambda _path: Playback(), analyzer=analyzer)
            downloads = []
            def fake_download(url, target, headers, *, resume=False):
                downloads.append((url, headers)); target.write_bytes(b"audio"); return target
            service._download = fake_download
            first = service.analyze("https://music.example/track")
            second = service.analyze("https://music.example/track")
            self.assertEqual(first, second); self.assertEqual(analyzer.calls, 1)
            self.assertEqual(downloads[0][1]["Authorization"], "secret")

    def test_remote_download_reresolves_and_resumes_after_connection_reset(self):
        class Playback:
            stream_url = "https://example.invalid/audio"
            http_headers = {}

        with tempfile.TemporaryDirectory() as temporary:
            service = AutoDJService(Path(temporary) / "cache.db")
            target = Path(temporary) / "audio"
            resolver_calls = []
            retries = []
            download_calls = []

            def resolver(media_path):
                resolver_calls.append(media_path)
                return Playback()

            def fake_download(_url, target_path, _headers, *, resume=False):
                download_calls.append(resume)
                if not resume:
                    target_path.with_suffix(".webm").write_bytes(b"partial")
                    raise ConnectionResetError("interrompido")
                target_path.with_suffix(".webm").write_bytes(b"complete")
                return target_path.with_suffix(".webm")

            service._download = fake_download
            with patch("player.autodj.service.time.sleep"):
                downloaded_path = service._download_remote(
                    "media",
                    resolver,
                    target,
                    retry_handler=lambda media_path, error: retries.append((media_path, error)),
                )

            self.assertEqual(resolver_calls, ["media", "media"])
            self.assertEqual(len(retries), 1)
            self.assertEqual(retries[0][0], "media")
            self.assertIsInstance(retries[0][1], ConnectionResetError)
            self.assertEqual(download_calls, [False, True])
            self.assertEqual(downloaded_path.read_bytes(), b"complete")

    def test_resumed_http_download_appends_to_partial_file(self):
        class Response:
            status = 206
            headers = {"Content-Type": "audio/webm", "Content-Range": "bytes 7-11/12"}

            def __init__(self):
                self.chunks = iter((b"-rest", b""))

            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def read(self, _size): return next(self.chunks)

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "audio"
            output_path = target.with_suffix(".webm")
            output_path.write_bytes(b"partial")
            captured_requests = []

            def fake_urlopen(request, timeout):
                captured_requests.append((request, timeout))
                return Response()

            with patch("player.autodj.service.urlopen", fake_urlopen):
                downloaded_path = AutoDJService._download(
                    "https://example.invalid/audio",
                    target,
                    {},
                    resume=True,
                )

            self.assertEqual(downloaded_path.read_bytes(), b"partial-rest")
            self.assertEqual(captured_requests[0][0].get_header("Range"), "bytes=7-")

    def test_remote_download_rejects_oversized_content_before_writing(self):
        class Response:
            status = 200
            headers = {
                "Content-Type": "audio/webm",
                "Content-Length": str(121 * 1024 * 1024),
            }

            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def read(self, _size): raise AssertionError("oversized response must not be read")

        with tempfile.TemporaryDirectory() as temporary, patch(
            "player.autodj.service.urlopen", return_value=Response()
        ):
            with self.assertRaisesRegex(ValueError, "120 MB"):
                AutoDJService._download(
                    "https://example.invalid/audio",
                    Path(temporary) / "audio",
                    {},
                )

    def test_remote_download_rejects_non_http_urls(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "player.autodj.service.urlopen"
        ) as open_url:
            with self.assertRaisesRegex(ValueError, "URL de mídia inválida"):
                AutoDJService._download(
                    "file:///C:/Windows/win.ini",
                    Path(temporary) / "audio",
                    {},
                )

        open_url.assert_not_called()
