from dataclasses import asdict
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.autodj import AudioAnalysis
from player.frames.autodj import FrameAutoDJMixin
from player.playlists import PlaylistState


class AutoDJRecoveryTests(unittest.TestCase):
    def test_removed_candidate_cannot_supply_plan_for_another_track(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["a.mp3", "b.mp3"])
        frame = FrameAutoDJMixin()
        frame.settings = SimpleNamespace(autodj_enabled=True)
        frame._get_active_playlist_state = lambda: state
        frame._refresh_autodj_session_ui = Mock()
        pair = ("a.mp3", "b.mp3")
        frame._autodj_transition_requests = {pair: {"status": "pending"}}
        frame._finish_autodj_transition_analysis(
            pair, "removed.mp3", None, None, SimpleNamespace(fallback_crossfade=False), "",
        )
        self.assertNotIn(pair, frame._autodj_transition_requests)
        self.assertIsNone(frame._prepared_autodj_transition(state))

    def test_analysis_reaches_valid_candidate_after_six_failures(self):
        state = PlaylistState(title="AutoDJ")
        state.set_items(["current.mp3"])
        state.autodj_session = True
        state.autodj_remaining_items = [f"bad{i}.mp3" for i in range(6)] + ["good.mp3"]
        frame = FrameAutoDJMixin()
        frame.settings = SimpleNamespace()
        frame.playlists = [state]
        frame._autodj_session_requests = {}
        frame._autodj_session_results = {}
        frame._autodj_session_retry_at = {}
        frame._refresh_autodj_session_ui = Mock()
        attempted = []
        analysis = asdict(AudioAnalysis(120, tuple(range(0, 60000, 500)), .95, .5, "C"))

        def analyze(path):
            attempted.append(path)
            if path.startswith("bad"):
                raise RuntimeError("unreadable")
            return analysis

        frame.autodj_service = SimpleNamespace(analyze=analyze)
        done = threading.Event()
        results = []

        def finish(*args):
            results.append(args)
            done.set()

        frame._queue_autodj_session_fill = finish
        self.assertTrue(frame._maybe_fill_autodj_session(state))
        self.assertTrue(done.wait(3))
        self.assertIn("good.mp3", attempted)
        self.assertEqual([selection.path for selection in results[0][2]], ["good.mp3"])
