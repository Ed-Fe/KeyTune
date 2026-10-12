from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music import account_lists, chapters, transcript
from player.youtube_music.search import normalize_music_home_item


class ChaptersTests(unittest.TestCase):
    def test_description_timestamps_become_chapters(self):
        description = "Intro\n0:00 Começo\n1:30 - Meio\n1:02:03 Fim\nrodapé"
        found = chapters.chapters_from_description(description)
        self.assertEqual([(c.title, c.start_seconds) for c in found], [("Começo", 0), ("Meio", 90), ("Fim", 3723)])

    def test_the_description_needs_three_chapters_starting_at_zero(self):
        self.assertEqual(chapters.chapters_from_description("0:00 A\n1:00 B"), [])
        self.assertEqual(chapters.chapters_from_description("0:10 A\n1:00 B\n2:00 C"), [])

    def test_youtubejs_chapters_win_over_the_description(self):
        entries = [{"title": "Um", "start_seconds": 0}, {"title": "Dois", "start_seconds": 40}]
        with patch("player.youtube_music.chapters.youtubejs_resolver_enabled", return_value=True), patch(
            "player.youtube_music.chapters.youtubejs_runtime.media_chapters", return_value=(entries, False)
        ):
            found = chapters.media_chapters("https://www.youtube.com/watch?v=dQw4w9WgXcQ", lambda _url: "")
        self.assertEqual([c.title for c in found], ["Um", "Dois"])


class TranscriptTests(unittest.TestCase):
    def test_json3_events_become_timed_lines(self):
        payload = {
            "events": [
                {"tStartMs": 0},
                {"tStartMs": 1500, "segs": [{"utf8": "Olá"}, {"utf8": " mundo\n"}]},
                {"tStartMs": 61000, "segs": [{"utf8": "  "}]},
                {"tStartMs": 65000, "segs": [{"utf8": "Fim"}]},
            ]
        }
        lines = transcript.parse_json3(payload)
        self.assertEqual([(l.start_seconds, l.text) for l in lines], [(1, "Olá mundo"), (65, "Fim")])

    def test_the_authors_subtitle_beats_the_automatic_one(self):
        info = {
            "language": "en",
            "subtitles": {"pt-BR": [{"ext": "json3", "url": "manual"}]},
            "automatic_captions": {"en-orig": [{"ext": "json3", "url": "auto"}]},
        }
        with patch("player.youtube_music.transcript.content_language", return_value="pt"):
            self.assertEqual(transcript._pick_track(info), ("pt-BR", "manual", False))

    def test_the_original_automatic_caption_is_preferred_over_a_translation(self):
        info = {
            "language": "en",
            "automatic_captions": {
                "pt": [{"ext": "json3", "url": "translated"}],
                "en-orig": [{"ext": "json3", "url": "original"}],
            },
        }
        with patch("player.youtube_music.transcript.content_language", return_value="pt"):
            self.assertEqual(transcript._pick_track(info), ("en-orig", "original", True))

    def test_no_subtitle_means_no_track(self):
        with patch("player.youtube_music.transcript.content_language", return_value="pt"):
            self.assertIsNone(transcript._pick_track({"language": "en"}))

    def test_clock_formats_hours_only_when_needed(self):
        self.assertEqual(transcript.format_clock(65), "1:05")
        self.assertEqual(transcript.format_clock(3723), "1:02:03")


class MusicHomeTests(unittest.TestCase):
    def test_home_items_become_tracks_playlists_albums_and_artists(self):
        track = normalize_music_home_item(
            {"title": "Faixa", "videoId": "dQw4w9WgXcQ", "videoType": "MUSIC_VIDEO_TYPE_ATV", "artists": [{"name": "A"}]}
        )
        self.assertEqual((track.result_type, track.video_id), ("song", "dQw4w9WgXcQ"))

        playlist = normalize_music_home_item({"title": "Mix", "playlistId": "RDCLAK5uy_x", "description": "A, B"})
        self.assertEqual((playlist.result_type, playlist.playlist_id, playlist.detail_text), ("playlist", "RDCLAK5uy_x", "A, B"))

        album = normalize_music_home_item({"title": "Disco", "browseId": "MPREb_abc", "audioPlaylistId": "OLAK5uy_x"})
        self.assertEqual(album.result_type, "album")

        artist = normalize_music_home_item({"title": "Banda", "browseId": "UCabcdefghijklmnopqrstuv"})
        self.assertEqual(artist.result_type, "artist")

    def test_unknown_items_are_dropped(self):
        self.assertIsNone(normalize_music_home_item({"title": "?"}))
        self.assertIsNone(normalize_music_home_item("texto"))


class AccountListTests(unittest.TestCase):
    def test_watch_later_page_keeps_only_videos(self):
        entries = [{"id": "dQw4w9WgXcQ", "title": "Vídeo", "channel": "Canal", "duration": 61}]
        with patch("player.youtube_music.account_lists.require_account_session", return_value=("c", 0)), patch(
            "player.youtube_music.account_lists.youtubejs_runtime.account_playlist_page", return_value=(entries, True)
        ) as page:
            result = account_lists.playlist_page(account_lists.WATCH_LATER_PLAYLIST_ID)(0, 20)
        self.assertTrue(result.has_more)
        self.assertEqual([r.video_id for r in result.results], ["dQw4w9WgXcQ"])
        self.assertEqual(page.call_args.args[1], "WL")

    def test_saving_needs_a_video_url(self):
        self.assertFalse(account_lists.add_to_playlist("WL", "isto não é um vídeo"))


if __name__ == "__main__":
    unittest.main()
