from __future__ import annotations

import io
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music import youtubejs_runtime


class YouTubeJSRuntimeTests(unittest.TestCase):
    def test_managed_node_is_refreshed_only_when_resource_is_outdated(self):
        node_dir = pathlib.Path("C:/keytune/resources/node")
        for installed in (True, False):
            with self.subTest(installed=installed), patch.object(
                youtubejs_runtime, "get_optional_resource_dir", return_value=node_dir,
            ), patch.object(
                youtubejs_runtime, "find_all_available_javascript_runtimes", return_value={"node": str(node_dir / "node.exe")},
            ), patch.object(
                youtubejs_runtime, "optional_resource_installed", return_value=installed,
            ), patch.object(youtubejs_runtime, "youtubejs_dependency_versions", return_value={}), patch.object(
                youtubejs_runtime, "install_optional_resource",
            ) as install:
                youtubejs_runtime.install_nodejs_dependency(force=True)
                self.assertEqual(install.call_count, 0 if installed else 1)

    def setUp(self):
        youtubejs_runtime._stop_worker()
        self.addCleanup(youtubejs_runtime._stop_worker)

    @patch("player.youtube_music.youtubejs_runtime._request_worker")
    def test_resolve_stream_parses_direct_audio_result(self, request_worker):
        request_worker.return_value = {
            "stream_url": "https://example.googlevideo.com/audio.m4a",
            "title": "Faixa",
            "artist": "Artista",
        }

        result = youtubejs_runtime.resolve_stream(
            "https://www.youtube.com/watch?v=abc123DEF45",
            cookie_header="SID=abc",
            user_agent="Teste/1.0",
        )

        self.assertEqual(result.stream_url, "https://example.googlevideo.com/audio.m4a")
        self.assertEqual(result.display_title, "Faixa")
        self.assertEqual(result.display_artist, "Artista")
        request = request_worker.call_args.args[0]
        self.assertEqual(request["cookie"], "SID=abc")

    @patch("player.youtube_music.youtubejs_runtime.os.path.isdir", return_value=True)
    @patch("player.youtube_music.youtubejs_runtime.os.path.isfile", return_value=True)
    @patch(
        "player.youtube_music.youtubejs_runtime.find_all_available_javascript_runtimes",
        return_value={"node": "C:/Program Files/nodejs/node.exe"},
    )
    @patch("player.youtube_music.youtubejs_runtime.subprocess.Popen")
    def test_worker_process_is_reused(self, start_process, _find_runtimes, _is_file, _is_dir):
        response_line = 'KEYTUNE_YOUTUBEJS_RESULT={"stream_url":"https://example.com/audio"}\n'
        worker = SimpleNamespace(
            stdin=io.StringIO(),
            stdout=io.StringIO(response_line + response_line),
            poll=Mock(return_value=None),
            kill=Mock(),
            wait=Mock(),
        )
        start_process.return_value = worker

        first = youtubejs_runtime._request_worker({"media_url": "primeira"})
        second = youtubejs_runtime._request_worker({"media_url": "segunda"})

        self.assertEqual(first["stream_url"], "https://example.com/audio")
        self.assertEqual(second["stream_url"], "https://example.com/audio")
        start_process.assert_called_once()

    @patch("player.youtube_music.youtubejs_runtime.os.path.isfile", return_value=True)
    @patch("player.youtube_music.youtubejs_runtime.os.path.isdir", return_value=False)
    @patch("player.youtube_music.youtubejs_runtime._youtubejs_cache_dir", return_value="C:/tmp/youtubejs")
    @patch(
        "player.youtube_music.youtubejs_runtime.find_all_available_javascript_runtimes",
        return_value={"node": "C:/Program Files/nodejs/node.exe"},
    )
    def test_resolve_stream_reports_missing_package(self, _find_runtimes, _cache_dir, _is_dir, _is_file):
        with self.assertRaisesRegex(RuntimeError, "não está instalado"):
            youtubejs_runtime.resolve_stream("https://www.youtube.com/watch?v=abc123DEF45")

    def test_node_resource_is_downloaded_only_when_no_compatible_node_exists(self):
        with patch.object(
            youtubejs_runtime,
            "find_all_available_javascript_runtimes",
            return_value={},
        ), patch.object(youtubejs_runtime, "install_optional_resource") as install_resource:
            youtubejs_runtime.install_nodejs_dependency()

        install_resource.assert_called_once_with("node", progress_callback=None)

    def test_system_node_is_reused_without_downloading_portable_node(self):
        with patch.object(
            youtubejs_runtime,
            "find_all_available_javascript_runtimes",
            return_value={"node": "C:/Program Files/nodejs/node.exe"},
        ), patch.object(youtubejs_runtime, "install_optional_resource") as install_resource:
            youtubejs_runtime.install_nodejs_dependency()

        install_resource.assert_not_called()


if __name__ == "__main__":
    unittest.main()
