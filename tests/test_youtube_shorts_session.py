from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.youtube_music import shorts
from player.frames.youtube_music.shorts import ShortsMixin, short_label
from player.playlists import PlaylistState
from player.youtube_music.models import YOUTUBE_SEARCH_SOURCE_YOUTUBE, YouTubeMediaSearchResult


def _short(video_id, title="Corte", channel="Canal"):
    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        result_type="video",
        title=title,
        subtitle=channel,
        video_id=video_id,
        playback_url=f"https://www.youtube.com/watch?v={video_id}",
    )


class _Frame(ShortsMixin):
    def __init__(self, state):
        self.state = state
        self.announced = []
        self.played = []

    def _announce(self, message):
        self.announced.append(message)

    def _resolve_playlist_state_index(self, state):
        return 0

    def _refresh_playlist_browser(self):
        pass

    def _get_active_playlist_state(self):
        return self.state

    def _get_active_playlist_index(self):
        return 0

    def _play_media(self, **kwargs):
        self.played.append(kwargs)


def _state(count, current=0):
    state = PlaylistState(title="Shorts")
    urls = [f"https://www.youtube.com/watch?v=vid{index:08d}" for index in range(count)]
    state.set_items_prepared(urls, {url: i for i, url in enumerate(urls)}, [f"s{i}" for i in range(count)], start_index=current)
    state.shorts_session = True
    return state


class ShortsSessionTests(unittest.TestCase):
    def test_the_label_is_title_and_channel(self):
        self.assertEqual(short_label(_short("aaaaaaaaaaa", "Piada", "Fulano")), "Piada — Fulano")
        self.assertEqual(short_label(_short("aaaaaaaaaaa", "Piada", "")), "Piada")

    def test_no_refill_while_many_shorts_remain(self):
        frame = _Frame(_state(10, current=0))
        with patch.object(shorts.threading, "Thread") as thread:
            self.assertFalse(frame._shorts_session_refill(frame.state))
        thread.assert_not_called()

    def test_refill_starts_near_the_end_and_only_once(self):
        frame = _Frame(_state(10, current=8))
        with patch.object(shorts.threading, "Thread") as thread:
            self.assertTrue(frame._shorts_session_refill(frame.state))
            self.assertFalse(frame._shorts_session_refill(frame.state))
        thread.return_value.start.assert_called_once()

    def test_a_refill_keeps_only_new_shorts(self):
        state = _state(3, current=2)
        frame = _Frame(state)
        results = [_short("vid00000001"), _short("newnewnew01"), _short("newnewnew02")]
        frame._finish_shorts_refill(state, results, False)
        self.assertEqual(len(state.items), 5)
        self.assertFalse(state.shorts_loading)
        self.assertEqual(frame.played, [])

    def test_when_next_was_pressed_at_the_end_the_first_new_short_plays(self):
        state = _state(2, current=1)
        frame = _Frame(state)
        frame._finish_shorts_refill(state, [_short("newnewnew01")], True)
        self.assertEqual(state.current_index, 2)
        self.assertEqual(len(frame.played), 1)

    def test_nothing_new_is_announced_when_next_was_pressed(self):
        state = _state(2, current=1)
        frame = _Frame(state)
        frame._finish_shorts_refill(state, [], True)
        self.assertTrue(frame.announced)


if __name__ == "__main__":
    unittest.main()
