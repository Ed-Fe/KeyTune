import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from player.autodj import AnalysisCache, AudioAnalysis, AutoDJPlanner, TransitionProfile, WaveAnalyzer
from player.autodj.service import AutoDJService


class AutoDJTests(unittest.TestCase):
    def test_planner_aligns_beats_and_falls_back(self):
        outgoing = AudioAnalysis(120, tuple(range(0, 20000, 500)), .9, .5)
        incoming = AudioAnalysis(122, tuple(range(100, 20000, 492)), .8, .55)
        plan = AutoDJPlanner().plan(outgoing, incoming, beats=16)
        self.assertFalse(plan.fallback_crossfade); self.assertAlmostEqual(plan.tempo_ratio, 120 / 122, places=4)
        weak = AudioAnalysis(120, outgoing.beats_ms, .1, .5)
        self.assertTrue(AutoDJPlanner().plan(outgoing, weak).fallback_crossfade)

    def test_artist_rule_and_energy_profile(self):
        candidates = [{"artist":"Recente","energy":.5}, {"artist":"Nova","energy":.58}]
        chosen = AutoDJPlanner.choose_next(candidates, recent_artists=["recente"], current_energy=.5, profile=TransitionProfile.PARTY)
        self.assertEqual(chosen["artist"], "Nova")

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
            def fake_download(url, target, headers):
                downloads.append((url, headers)); target.write_bytes(b"audio"); return target
            service._download = fake_download
            first = service.analyze("https://music.example/track")
            second = service.analyze("https://music.example/track")
            self.assertEqual(first, second); self.assertEqual(analyzer.calls, 1)
            self.assertEqual(downloads[0][1]["Authorization"], "secret")
