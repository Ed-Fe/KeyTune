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

from player.constants import YOUTUBE_MUSIC_RADIO_RECENT_LIMIT
from player.frames.library_tabs.station_radio import StationRadioMixin
from player.playlists import PlaylistState


def _url(video_id, playlist_id=None):
    url = f"https://music.youtube.com/watch?v={video_id}"
    if playlist_id:
        url += f"&list={playlist_id}"
    return url


class _ImmediateThread:
    def __init__(self, target, daemon=True):
        self.target = target

    def start(self):
        self.target()


class _StationFrame(StationRadioMixin):
    def __init__(self, source_state, service=None):
        self.source_state = source_state
        self.target_state = PlaylistState(title="Nova")
        self.service = service or Mock()
        self.notebook = Mock()
        self.announcements = []
        self.status_messages = []
        self.fetches = []
        self._related_autoplay = {"status": "pending"}

    def _get_active_playlist_state(self):
        return self.source_state

    def _youtube_music_service_for_playback(self):
        return self.service

    def _capture_active_playlist_state(self):
        return None

    def _media_label(self, _media_path):
        return "Faixa semente — Artista"

    def _create_empty_playlist_tab(self, select=False):
        return 1

    def _get_playlist_state(self, index=None):
        return self.target_state if index == 1 else self.source_state

    def _select_tab(self, index, announce=True):
        self.selected_tab = index

    def _refresh_playlist_browser(self):
        self.refreshed = True

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message):
        self.status_messages.append(message)

    def _fetch_new_station_tracks(self, target_state, seed_media_path, seed_video_id, excluded_video_ids):
        self.fetches.append((target_state, seed_media_path, seed_video_id, set(excluded_video_ids)))
        return True


class StationCreationTests(unittest.TestCase):
    def test_current_track_becomes_item_one_of_a_fresh_radio(self):
        source = PlaylistState(title="Mix antigo")
        source.set_items([_url("played1"), _url("played2"), _url("seed")])
        source.select_index(2)
        source.last_position_ms = 42000
        source.was_playing = True
        frame = _StationFrame(source)
        frame._youtube_music_radio_recent = ["older"]

        created = frame.on_start_radio_from_current()

        self.assertTrue(created)
        self.assertEqual(frame.target_state.items, [_url("seed")])
        self.assertEqual(frame.target_state.current_index, 0)
        self.assertEqual(frame.target_state.last_position_ms, 42000)
        self.assertTrue(frame.target_state.was_playing)
        self.assertIsNone(frame.target_state.radio_queue_playlist_id)
        self.assertEqual(frame.target_state.title, "Rádio: Faixa semente — Artista")
        self.assertEqual(frame.selected_tab, 1)
        self.assertEqual(frame.fetches[0][3], {"older", "played1", "played2"})
        self.assertIsNone(frame._related_autoplay)

    def test_local_media_does_not_create_a_radio(self):
        source = PlaylistState(title="Local")
        source.set_items([r"C:\Músicas\faixa.mp3"])
        frame = _StationFrame(source)

        self.assertFalse(frame.on_start_radio_from_current())
        self.assertIn("não é uma faixa compatível", frame.announcements[-1])
        self.assertEqual(frame.fetches, [])

    def test_recent_history_is_unique_bounded_and_keeps_the_latest_play(self):
        frame = _StationFrame(PlaylistState(title="Teste"))
        for index in range(YOUTUBE_MUSIC_RADIO_RECENT_LIMIT + 5):
            frame._remember_youtube_music_radio_playback(_url(f"track{index}"))
        frame._remember_youtube_music_radio_playback(_url("track10"))

        recent = frame._youtube_music_radio_recent_for_session()

        self.assertEqual(len(recent), YOUTUBE_MUSIC_RADIO_RECENT_LIMIT)
        self.assertEqual(recent[-1], "track10")
        self.assertEqual(recent.count("track10"), 1)

    def test_recent_history_ignores_local_names_that_look_like_video_ids(self):
        frame = _StationFrame(PlaylistState(title="Teste"))

        remembered = frame._remember_youtube_music_radio_playback("abcdefghijk")

        self.assertFalse(remembered)
        self.assertEqual(frame._youtube_music_radio_recent_for_session(), [])

    def test_recent_history_ignores_an_invalid_session_value(self):
        frame = _StationFrame(PlaylistState(title="Teste"))

        frame._restore_youtube_music_radio_recent("not-a-list")

        self.assertEqual(frame._youtube_music_radio_recent_for_session(), [])


class StationFetchTests(unittest.TestCase):
    def test_multiple_fresh_fetches_merge_only_new_video_ids(self):
        source = PlaylistState(title="Origem")
        source.set_items([_url("seed")])
        responses = [
            SimpleNamespace(
                playlist_id="RD1",
                item_urls=[_url("one", "RD1"), _url("same", "RD1")],
                item_labels=["Um", "Repetida"],
            ),
            SimpleNamespace(
                playlist_id="RD2",
                item_urls=[_url("same", "RD2"), _url("two", "RD2")],
                item_labels=["Repetida", "Dois"],
            ),
            SimpleNamespace(playlist_id="RD3", item_urls=[], item_labels=[]),
        ]
        service = Mock()
        service.get_radio_content.side_effect = responses
        frame = _StationFrame(source, service=service)
        target = frame.target_state
        target.set_items([_url("seed")])
        frame._fetch_new_station_tracks = StationRadioMixin._fetch_new_station_tracks.__get__(frame)
        frame._finish_new_station_tracks = StationRadioMixin._finish_new_station_tracks.__get__(frame)
        frame._resolve_playlist_state_index = Mock(return_value=1)
        frame._is_current_playlist_state = Mock(return_value=True)

        with patch("player.frames.library_tabs.station_radio.threading.Thread", _ImmediateThread), patch(
            "player.frames.library_tabs.station_radio.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)
        ):
            frame._fetch_new_station_tracks(target, _url("seed"), "seed", {"old"})

        self.assertEqual(
            target.items,
            [_url("seed"), _url("one", "RD1"), _url("same", "RD1"), _url("two", "RD2")],
        )
        self.assertEqual(target.radio_queue_playlist_id, "RD2")
        self.assertEqual(service.get_radio_content.call_count, 3)
        second_exclusions = service.get_radio_content.call_args_list[1].kwargs["exclude_video_ids"]
        self.assertTrue({"old", "seed", "one", "same"}.issubset(second_exclusions))


if __name__ == "__main__":
    unittest.main()
