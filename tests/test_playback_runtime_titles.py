from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.playback import (
    _looks_like_stream_artifact_title,
    _should_apply_runtime_stream_title,
)


class PlaybackRuntimeTitleTests(unittest.TestCase):
    def test_detects_stream_artifact_file_names(self):
        self.assertTrue(_looks_like_stream_artifact_title("hls-1080p-a0540.m3u8"))
        self.assertTrue(_looks_like_stream_artifact_title("https://cdn.example.invalid/path/audio.m4s"))

    def test_ignores_regular_human_titles(self):
        self.assertFalse(_looks_like_stream_artifact_title("Stepson and Stepmom in a Hotel Room After a Delayed Flight"))
        self.assertFalse(_looks_like_stream_artifact_title("Rádio Cultura FM"))

    def test_runtime_title_does_not_override_resolved_generic_remote_label(self):
        self.assertFalse(
            _should_apply_runtime_stream_title(
                "https://example.com/watch?v=123",
                "Stepson and Stepmom in a Hotel Room After a Delayed Flight",
                "hls-1080p-a0540.m3u8",
            )
        )
        self.assertFalse(
            _should_apply_runtime_stream_title(
                "https://example.com/watch?v=123",
                "Stepson and Stepmom in a Hotel Room After a Delayed Flight",
                "stepson_and_stepmom_in_a_hotel_room_after_a_delayed_flight",
            )
        )

    def test_runtime_title_still_can_replace_raw_url_fallback_label(self):
        self.assertTrue(
            _should_apply_runtime_stream_title(
                "https://example.com/live/master.m3u8",
                "master.m3u8",
                "Rádio Cultura FM",
            )
        )


if __name__ == "__main__":
    unittest.main()
