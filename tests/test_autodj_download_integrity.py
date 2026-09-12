from http.client import IncompleteRead
from io import BytesIO
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from player.autodj.service import AutoDJService
from player.autodj.analyzer import AudioAnalysis


class Response(BytesIO):
    def __init__(self, body, *, status=200, **headers):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Type": "audio/mp4", **headers}


class AutoDJDownloadIntegrityTests(unittest.TestCase):
    def test_explicit_range_requests_whole_track_even_on_first_request(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("player.autodj.service.urlopen", return_value=Response(b"audio")) as fetch:
                result = AutoDJService._download(
                    "https://example.invalid/audio", Path(directory) / "audio", {"range": "bytes=0-1"}
                )
            self.assertEqual(result.read_bytes(), b"audio")
            self.assertEqual(fetch.call_args.args[0].get_header("Range"), "bytes=0-")

    def test_partial_response_is_resumed_before_being_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            service = AutoDJService(Path(directory) / "cache.db")
            responses = [
                Response(b"first", status=206, **{"Content-Range": "bytes 0-4/9", "Content-Length": "5"}),
                Response(b"last", status=206, **{"Content-Range": "bytes 5-8/9", "Content-Length": "4"}),
            ]
            playback = SimpleNamespace(stream_url="https://example.invalid/audio", http_headers={})
            with patch("player.autodj.service.urlopen", side_effect=responses) as fetch, patch(
                "player.autodj.service.time.sleep"
            ):
                result = service._download_remote("media", lambda _: playback, Path(directory) / "audio")
            self.assertEqual(result.read_bytes(), b"firstlast")
            self.assertEqual([c.args[0].get_header("Range") for c in fetch.call_args_list], ["bytes=0-", "bytes=5-"])

    def test_truncated_body_is_not_accepted_as_complete_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("player.autodj.service.urlopen", return_value=Response(b"cut", **{"Content-Length": "100"})):
                with self.assertRaises(IncompleteRead):
                    AutoDJService._download("https://example.invalid/audio", Path(directory) / "audio", {})

    def test_progressing_ranges_do_not_exhaust_failure_retry_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            service = AutoDJService(Path(directory) / "cache.db")
            responses = [
                Response(bytes([index]), status=206, **{"Content-Range": f"bytes {index}-{index}/5"})
                for index in range(5)
            ]
            resolver = Mock(return_value=SimpleNamespace(stream_url="https://example.invalid/audio", http_headers={}))
            with patch("player.autodj.service.urlopen", side_effect=responses):
                result = service._download_remote("media", resolver, Path(directory) / "audio")
            self.assertEqual(result.read_bytes(), bytes(range(5)))
            resolver.assert_called_once_with("media")

    def test_alternate_stream_uses_a_separate_file_and_only_success_is_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            analyzer = Mock(analysis_version=7)
            analyzer.analyze.return_value = AudioAnalysis(120, (0, 500), .9, .5)
            primary = Mock()
            alternate = Mock()
            service = AutoDJService(Path(directory) / "cache.db", remote_resolver=primary,
                                    remote_fallback_resolver=alternate, analyzer=analyzer)
            targets = []

            def download(media, resolver, target, **kwargs):
                targets.append(target)
                if resolver is primary:
                    target.write_bytes(b"partial")
                    raise IncompleteRead(b"", 100)
                self.assertIs(resolver, alternate)
                self.assertFalse(target.exists())
                target.write_bytes(b"complete")
                return target

            with patch.object(service, "_download_remote", side_effect=download):
                result = service.analyze("media")
            self.assertNotEqual(targets[0], targets[1])
            analyzer.analyze.assert_called_once_with(targets[1])
            self.assertEqual(service.get_analysis_status("media"), "ready")
            self.assertEqual(service.get_cached("media")["bpm"], result["bpm"])

    def test_incomplete_alternate_stream_remains_failed_and_uncached(self):
        with tempfile.TemporaryDirectory() as directory:
            analyzer = Mock(analysis_version=7)
            service = AutoDJService(Path(directory) / "cache.db", remote_resolver=Mock(),
                                    remote_fallback_resolver=Mock(), analyzer=analyzer)
            with patch.object(service, "_download_remote", side_effect=IncompleteRead(b"", 100)):
                with self.assertRaisesRegex(RuntimeError, "incompleto"):
                    service.analyze("media")
            analyzer.analyze.assert_not_called()
            self.assertEqual(service.get_analysis_status("media"), "failed")
            self.assertIsNone(service.get_cached("media"))

    def test_wrong_range_is_rejected_without_modifying_partial_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "audio"
            partial = target.with_suffix(".m4a")
            partial.write_bytes(b"first")
            response = Response(b"bad", status=206, **{"Content-Range": "bytes 0-2/9"})
            with patch("player.autodj.service.urlopen", return_value=response):
                with self.assertRaises(ValueError):
                    AutoDJService._download("https://example.invalid/audio", target, {}, resume=True)
            self.assertEqual(partial.read_bytes(), b"first")

    def test_server_ignoring_range_replaces_partial_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "audio"
            target.with_suffix(".m4a").write_bytes(b"partial")
            with patch("player.autodj.service.urlopen", return_value=Response(b"complete")):
                result = AutoDJService._download("https://example.invalid/audio", target, {}, resume=True)
            self.assertEqual(result.read_bytes(), b"complete")

    def test_failure_is_visible_and_successful_retry_clears_it(self):
        with tempfile.TemporaryDirectory() as directory:
            service = AutoDJService(Path(directory) / "cache.db")
            self.assertEqual(service.get_analysis_status("media"), "unknown")

            def fail(*args, **kwargs):
                self.assertEqual(service.get_analysis_status("media"), "pending")
                raise ValueError("invalid audio")

            with patch.object(service, "_analyze_serialized", side_effect=fail):
                with self.assertRaises(ValueError):
                    service.analyze("media")
            self.assertEqual(service.get_analysis_status("media"), "failed")
            with patch.object(service, "_analyze_serialized", return_value={"bpm": 120}):
                service.analyze("media")
            self.assertEqual(service.get_analysis_status("media"), "ready")


if __name__ == "__main__":
    unittest.main()
