from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.library_manager import YouTubeMusicLibraryManager


def _track(video_id, title=None):
    return {"videoId": video_id, "title": title or f"Faixa {video_id}", "artists": []}


def _build_watch_url(video_id, playlist_id=None):
    url = f"https://music.youtube.com/watch?v={video_id}"
    if playlist_id:
        url = f"{url}&list={playlist_id}"
    return url


class _FakeClient:
    """Records every get_watch_playlist call and replays queued responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get_watch_playlist(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            return {"playlistId": "", "tracks": []}
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _LegacyFakeClient(_FakeClient):
    """Older ytmusicapi builds that do not accept the ``radio`` keyword."""

    def get_watch_playlist(self, **kwargs):
        if "radio" in kwargs:
            raise TypeError("get_watch_playlist() got an unexpected keyword argument 'radio'")
        return super().get_watch_playlist(**kwargs)


def _manager(client):
    return YouTubeMusicLibraryManager(lambda require_auth=False: client, _build_watch_url)


class RadioContentTests(unittest.TestCase):
    def test_seed_track_is_never_returned(self):
        client = _FakeClient([{"playlistId": "RDAMVMseed", "tracks": [_track("seed"), _track("aaa")]}])

        content = _manager(client).get_radio_content("seed")

        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=aaa&list=RDAMVMseed"])

    def test_duplicates_inside_the_same_batch_are_dropped(self):
        client = _FakeClient(
            [{"playlistId": "RDAMVMseed", "tracks": [_track("aaa"), _track("bbb"), _track("aaa")]}]
        )

        content = _manager(client).get_radio_content("seed")

        self.assertEqual(len(content.item_urls), 2)
        self.assertEqual(len(content.item_labels), 2)

    def test_excluded_video_ids_are_dropped(self):
        client = _FakeClient(
            [{"playlistId": "RDAMVMseed", "tracks": [_track("aaa"), _track("bbb"), _track("ccc")]}]
        )

        content = _manager(client).get_radio_content("seed", exclude_video_ids=["aaa", "ccc"])

        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=bbb&list=RDAMVMseed"])

    def test_tracks_disliked_on_the_account_are_dropped(self):
        disliked = _track("aaa")
        disliked["likeStatus"] = "DISLIKE"
        client = _FakeClient(
            [{"playlistId": "RDAMVMseed", "tracks": [disliked, _track("bbb")]}]
        )

        content = _manager(client).get_radio_content("seed", require_auth=True)

        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=bbb&list=RDAMVMseed"])

    def test_blank_and_missing_video_ids_are_ignored(self):
        client = _FakeClient(
            [{"playlistId": "RDAMVMseed", "tracks": [{"title": "sem id"}, _track("  "), _track("aaa")]}]
        )

        content = _manager(client).get_radio_content("seed", exclude_video_ids=["", None, "  "])

        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=aaa&list=RDAMVMseed"])

    def test_empty_seed_returns_empty_content_without_calling_the_api(self):
        client = _FakeClient([])

        content = _manager(client).get_radio_content("   ")

        self.assertEqual(content.item_urls, [])
        self.assertEqual(client.calls, [])

    def test_existing_queue_is_continued_before_starting_a_new_radio(self):
        client = _FakeClient([{"playlistId": "RDAMVMold", "tracks": [_track("aaa")]}])

        content = _manager(client).get_radio_content("seed", continue_playlist_id="RDAMVMold")

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0].get("playlistId"), "RDAMVMold")
        self.assertNotIn("radio", client.calls[0])
        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=aaa&list=RDAMVMold"])

    def test_new_radio_is_requested_when_the_continued_queue_has_only_known_tracks(self):
        client = _FakeClient(
            [
                {"playlistId": "RDAMVMold", "tracks": [_track("aaa")]},
                {"playlistId": "RDAMVMnew", "tracks": [_track("bbb")]},
            ]
        )

        content = _manager(client).get_radio_content(
            "seed", exclude_video_ids=["aaa"], continue_playlist_id="RDAMVMold"
        )

        self.assertEqual(len(client.calls), 2)
        self.assertTrue(client.calls[1].get("radio"))
        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=bbb&list=RDAMVMnew"])

    def test_new_radio_is_requested_when_continuing_the_queue_fails(self):
        client = _FakeClient(
            [RuntimeError("queue is gone"), {"playlistId": "RDAMVMnew", "tracks": [_track("bbb")]}]
        )

        content = _manager(client).get_radio_content("seed", continue_playlist_id="RDAMVMold")

        self.assertEqual(len(client.calls), 2)
        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=bbb&list=RDAMVMnew"])

    def test_a_failing_radio_still_raises(self):
        client = _FakeClient([RuntimeError("network down")])

        with self.assertRaises(RuntimeError):
            _manager(client).get_radio_content("seed")

    def test_content_is_empty_when_every_track_is_already_known(self):
        client = _FakeClient([{"playlistId": "RDAMVMseed", "tracks": [_track("aaa"), _track("bbb")]}])

        content = _manager(client).get_radio_content("seed", exclude_video_ids=["aaa", "bbb"])

        self.assertEqual(content.item_urls, [])

    def test_legacy_ytmusicapi_without_the_radio_keyword_is_supported(self):
        client = _LegacyFakeClient([{"playlistId": "RDAMVMseed", "tracks": [_track("aaa")]}])

        content = _manager(client).get_radio_content("seed")

        self.assertEqual(content.item_urls, ["https://music.youtube.com/watch?v=aaa&list=RDAMVMseed"])


if __name__ == "__main__":
    unittest.main()
