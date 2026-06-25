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

from player.youtube_music.browse import (
    YouTubeMoodCategory,
    extract_browse_playlists_from_response,
    normalize_mood_categories,
    normalize_mood_playlists,
    normalize_track_items,
)
from player.youtube_music.service import YouTubeMusicService


class MoodCategoriesNormalizationTests(unittest.TestCase):
    def test_groups_sections_and_skips_incomplete_entries(self):
        raw = {
            "For you": [
                {"title": "1980s", "params": "ggMP1980"},
                {"title": "Sem params", "params": ""},
                {"params": "ggMPnope"},
            ],
            "Genres": [
                {"title": "Pop", "params": "ggMPpop"},
            ],
            "Vazio": [],
        }

        sections = normalize_mood_categories(raw)

        self.assertEqual([title for title, _categories in sections], ["For you", "Genres"])
        for_you = sections[0][1]
        self.assertEqual(len(for_you), 1)
        self.assertIsInstance(for_you[0], YouTubeMoodCategory)
        self.assertEqual(for_you[0].title, "1980s")
        self.assertEqual(for_you[0].params, "ggMP1980")
        self.assertEqual(for_you[0].section, "For you")

    def test_handles_non_dict_payload(self):
        self.assertEqual(normalize_mood_categories(None), [])
        self.assertEqual(normalize_mood_categories([]), [])


class MoodPlaylistsNormalizationTests(unittest.TestCase):
    def test_normalizes_and_dedupes_playlists(self):
        raw = [
            {"title": "Foco", "playlistId": "PLfoco", "description": "Para concentrar"},
            {"title": "Sem id", "playlistId": ""},
            {"title": "Foco", "playlistId": "PLfoco"},
        ]

        results = normalize_mood_playlists(raw, badge="Decadas")

        self.assertEqual([result.playlist_id for result in results], ["PLfoco"])
        result = results[0]
        self.assertEqual(result.result_type, "playlist")
        self.assertEqual(result.source_badge, "Decadas")
        self.assertTrue(result.can_open)
        self.assertTrue(result.can_save)
        self.assertIn("Para concentrar", result.detail_text)


class TrackItemsNormalizationTests(unittest.TestCase):
    def test_normalizes_liked_and_history_tracks_with_badge(self):
        raw = [
            {
                "videoId": "abc123",
                "title": "Faixa A",
                "artists": [{"name": "Artista A"}],
                "feedbackTokens": {"add": "ADD", "remove": "REMOVE"},
                "likeStatus": "LIKE",
            },
            {"videoId": "", "title": "Sem id"},
            {"videoId": "abc123", "title": "Duplicada"},
        ]

        results = normalize_track_items(raw, badge="Curtida")

        self.assertEqual([result.video_id for result in results], ["abc123"])
        result = results[0]
        self.assertEqual(result.result_type, "song")
        self.assertEqual(result.source_badge, "Curtida")
        self.assertEqual(result.subtitle, "Artista A")
        self.assertTrue(result.playback_url)
        self.assertTrue(result.can_add_to_playlist)

    def test_handles_empty_payload(self):
        self.assertEqual(normalize_track_items(None, badge="Histórico"), [])


class BrowsePlaylistFallbackTests(unittest.TestCase):
    def _two_row_tile(self, *, browse_id, title, page_type="MUSIC_PAGE_TYPE_PLAYLIST"):
        return {
            "musicTwoRowItemRenderer": {
                "title": {"runs": [{"text": title}]},
                "subtitle": {"runs": [{"text": "Uma "}, {"text": "playlist"}]},
                "navigationEndpoint": {
                    "browseEndpoint": {
                        "browseId": browse_id,
                        "browseEndpointContextSupportedConfigs": {
                            "browseEndpointContextMusicConfig": {"pageType": page_type}
                        },
                    }
                },
            }
        }

    def test_extracts_playlists_and_skips_non_playlist_tiles(self):
        response = {
            "sections": [
                {"contents": [self._two_row_tile(browse_id="VLPL123", title="Top Pop")]},
                {
                    "contents": [
                        self._two_row_tile(
                            browse_id="UCartist",
                            title="Algum Artista",
                            page_type="MUSIC_PAGE_TYPE_ARTIST",
                        ),
                        # song carousel item that breaks ytmusicapi is ignored
                        {"musicResponsiveListItemRenderer": {"foo": "bar"}},
                        self._two_row_tile(browse_id="VLPL123", title="Top Pop"),
                    ]
                },
            ]
        }

        playlists = extract_browse_playlists_from_response(response)

        self.assertEqual(playlists, [{"playlistId": "PL123", "title": "Top Pop", "description": "Uma playlist"}])

    def test_handles_non_dict_response(self):
        self.assertEqual(extract_browse_playlists_from_response(None), [])

    def test_get_mood_playlists_falls_back_when_parser_raises(self):
        client = Mock()
        client.get_mood_playlists.side_effect = KeyError("musicTwoRowItemRenderer")
        client._send_request.return_value = {
            "contents": [self._two_row_tile(browse_id="VLPLgenre", title="Rock Clássico")]
        }
        fake_module = SimpleNamespace(YTMusic=Mock(return_value=client))
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.get_mood_playlists("ggMProck", badge="Rock")

        client._send_request.assert_called_once()
        self.assertEqual([result.playlist_id for result in results], ["PLgenre"])
        self.assertEqual(results[0].source_badge, "Rock")


class BrowseServiceTests(unittest.TestCase):
    def _service_with_client(self, client):
        fake_module = SimpleNamespace(YTMusic=Mock(return_value=client))
        service = YouTubeMusicService()
        return service, fake_module

    def test_get_mood_categories_uses_public_client(self):
        client = Mock()
        client.get_mood_categories.return_value = {"Genres": [{"title": "Pop", "params": "ggMPpop"}]}
        service, fake_module = self._service_with_client(client)

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            sections = service.get_mood_categories()

        self.assertEqual(sections[0][1][0].title, "Pop")
        fake_module.YTMusic.assert_called_once_with()  # public (no auth path)

    def test_get_mood_playlists_passes_params(self):
        client = Mock()
        client.get_mood_playlists.return_value = [{"title": "Foco", "playlistId": "PLfoco"}]
        service, fake_module = self._service_with_client(client)

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.get_mood_playlists("ggMPpop", badge="Pop")

        client.get_mood_playlists.assert_called_once_with("ggMPpop")
        self.assertEqual(results[0].source_badge, "Pop")

    def test_get_liked_songs_extracts_tracks(self):
        client = Mock()
        client.get_liked_songs.return_value = {
            "tracks": [{"videoId": "abc123", "title": "Faixa", "artists": [{"name": "A"}]}]
        }
        service, fake_module = self._service_with_client(client)
        service.has_saved_browser_auth = lambda: True

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.get_liked_songs(limit=50)

        client.get_liked_songs.assert_called_once_with(limit=50)
        self.assertEqual(results[0].source_badge, "Curtida")

    def test_get_history_normalizes_items(self):
        client = Mock()
        client.get_history.return_value = [
            {"videoId": "abc123", "title": "Faixa", "artists": [{"name": "A"}]}
        ]
        service, fake_module = self._service_with_client(client)
        service.has_saved_browser_auth = lambda: True

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.get_history()

        client.get_history.assert_called_once_with()
        self.assertEqual(results[0].source_badge, "Histórico")


if __name__ == "__main__":
    unittest.main()
