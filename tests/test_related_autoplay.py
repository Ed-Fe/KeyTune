from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.constants import YOUTUBE_MUSIC_RADIO_MAX_SEED_ATTEMPTS
from player.frames.library_tabs.related_autoplay import RelatedAutoplayMixin
from player.playlists import PlaylistState


def _watch_url(video_id, playlist_id=None):
    url = f"https://music.youtube.com/watch?v={video_id}"
    if playlist_id:
        url = f"{url}&list={playlist_id}"
    return url


class _RadioContent:
    def __init__(self, item_urls, playlist_id="RDAMVMnew", item_labels=None):
        self.item_urls = list(item_urls)
        self.item_labels = list(item_labels or [])
        self.playlist_id = playlist_id


class _RelatedAutoplayFrame(RelatedAutoplayMixin):
    """Exercises the mixin without wx, recording what it would have fetched."""

    def __init__(self, state):
        self._state = state
        self.dispatched = []
        self.announcements = []
        self.status_messages = []
        self.played = 0
        self._related_autoplay = None

    # -- collaborators the mixin reaches for --------------------------------

    def _get_active_playlist_state(self):
        return self._state

    def _get_active_playlist_index(self):
        return 0

    def _youtube_music_service_for_playback(self):
        return object()

    def _dispatch_related_youtube_music_fetch(self, seed_media_path, radio_video_id):
        self.dispatched.append((seed_media_path, radio_video_id))

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, auto_clear_ms=6000):
        self.status_messages.append(message)

    def _refresh_playlist_browser(self):
        return

    def _play_media(self, index=None, announce_message=None):
        self.played += 1

    def _describe_playlist_position(self, state):
        return "1 de 1"


def _playlist(video_ids, title="Playlist"):
    state = PlaylistState(title=title)
    state.append_items([_watch_url(video_id) for video_id in video_ids])
    state.current_media_path = state.items[-1] if state.items else None
    return state


class KnownVideoIdsTests(unittest.TestCase):
    def test_every_video_id_in_the_playlist_is_collected(self):
        frame = _RelatedAutoplayFrame(_playlist(["aaa", "bbb", "ccc"]))

        known = frame._related_autoplay_known_video_ids(frame._state)

        self.assertEqual(known, ["aaa", "bbb", "ccc"])

    def test_items_without_a_video_id_are_skipped(self):
        state = PlaylistState(title="Mista")
        state.append_items([_watch_url("aaa"), r"C:\musica\local.mp3"])
        frame = _RelatedAutoplayFrame(state)

        self.assertEqual(frame._related_autoplay_known_video_ids(state), ["aaa"])

    def test_missing_state_yields_no_ids(self):
        frame = _RelatedAutoplayFrame(None)

        self.assertEqual(frame._related_autoplay_known_video_ids(None), [])


class SeedRetryTests(unittest.TestCase):
    def test_retry_uses_the_latest_untried_track_as_the_new_seed(self):
        state = _playlist(["aaa", "bbb", "ccc"])
        frame = _RelatedAutoplayFrame(state)
        request = {"seed": state.items[-1], "status": "pending", "tried_video_ids": ["ccc"]}

        retried = frame._retry_related_youtube_music_with_new_seed(request, state, state.items[-1])

        self.assertTrue(retried)
        self.assertEqual(frame.dispatched, [(state.items[-1], "bbb")])
        self.assertEqual(request["tried_video_ids"], ["ccc", "bbb"])
        self.assertEqual(request["status"], "pending")

    def test_retry_drops_the_exhausted_queue_so_a_fresh_radio_is_opened(self):
        state = _playlist(["aaa", "bbb"])
        state.radio_queue_playlist_id = "RDAMVMold"
        frame = _RelatedAutoplayFrame(state)
        request = {"seed": state.items[-1], "status": "pending", "tried_video_ids": ["bbb"]}

        frame._retry_related_youtube_music_with_new_seed(request, state, state.items[-1])

        self.assertIsNone(state.radio_queue_playlist_id)

    def test_retry_stops_after_the_configured_number_of_seeds(self):
        state = _playlist(["aaa", "bbb", "ccc", "ddd"])
        frame = _RelatedAutoplayFrame(state)
        tried = ["ddd", "ccc", "bbb"][:YOUTUBE_MUSIC_RADIO_MAX_SEED_ATTEMPTS]
        request = {"seed": state.items[-1], "status": "pending", "tried_video_ids": tried}

        retried = frame._retry_related_youtube_music_with_new_seed(request, state, state.items[-1])

        self.assertFalse(retried)
        self.assertEqual(frame.dispatched, [])

    def test_retry_stops_when_every_track_was_already_tried(self):
        state = _playlist(["aaa"])
        frame = _RelatedAutoplayFrame(state)
        request = {"seed": state.items[-1], "status": "pending", "tried_video_ids": ["aaa"]}

        self.assertFalse(frame._retry_related_youtube_music_with_new_seed(request, state, state.items[-1]))
        self.assertEqual(frame.dispatched, [])


class FinishFetchTests(unittest.TestCase):
    def test_an_empty_result_retries_with_an_earlier_seed_instead_of_ending(self):
        state = _playlist(["aaa", "bbb"])
        frame = _RelatedAutoplayFrame(state)
        frame._related_autoplay = {
            "seed": state.items[-1],
            "status": "pending",
            "advance_when_ready": True,
            "tried_video_ids": ["bbb"],
        }

        frame._finish_related_youtube_music_fetch(state.items[-1], _RadioContent([]))

        self.assertEqual(frame.dispatched, [(state.items[-1], "aaa")])
        self.assertEqual(frame.announcements, [])
        self.assertEqual(len(state.items), 2)

    def test_an_empty_result_ends_the_playlist_once_no_seed_is_left(self):
        state = _playlist(["aaa"])
        frame = _RelatedAutoplayFrame(state)
        frame._related_autoplay = {
            "seed": state.items[-1],
            "status": "pending",
            "advance_when_ready": True,
            "tried_video_ids": ["aaa"],
        }

        frame._finish_related_youtube_music_fetch(state.items[-1], _RadioContent([]))

        self.assertEqual(frame.dispatched, [])
        self.assertIn("Nenhum conteúdo relacionado", frame.announcements[-1])

    def test_the_radio_queue_is_remembered_for_the_next_fetch(self):
        state = _playlist(["aaa"])
        frame = _RelatedAutoplayFrame(state)
        frame._related_autoplay = {
            "seed": state.items[-1],
            "status": "pending",
            "advance_when_ready": False,
            "tried_video_ids": ["aaa"],
        }

        frame._finish_related_youtube_music_fetch(
            state.items[-1], _RadioContent([_watch_url("bbb", "RDAMVMnew")], playlist_id="RDAMVMnew")
        )

        self.assertEqual(state.radio_queue_playlist_id, "RDAMVMnew")
        self.assertEqual(len(state.items), 2)


if __name__ == "__main__":
    unittest.main()
