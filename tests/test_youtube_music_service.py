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

from player.youtube_music.service import YouTubeMusicService
from player.youtube_music.streams import ResolvedStreamPlayback


class YouTubeMusicServiceTests(unittest.TestCase):
    def test_cache_ttl_respects_expiring_signed_urls(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=760&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
            display_title="Vídeo de teste",
            display_artist="Canal de teste",
        )

        with patch("player.youtube_music.service.time.time", return_value=600), patch(
            "player.youtube_music.service.time.monotonic", return_value=10
        ):
            service._cache_stream_playback(media_path, resolved_playback)

        cached_entry = service._stream_cache[media_path]
        self.assertEqual(cached_entry["expires_at"], 140)
        self.assertEqual(cached_entry["display_title"], "Vídeo de teste")
        self.assertEqual(cached_entry["display_artist"], "Canal de teste")

    def test_cache_skips_urls_that_are_already_too_close_to_expiring(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=620&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
            display_title="Vídeo de teste",
            display_artist="Canal de teste",
        )

        with patch("player.youtube_music.service.time.time", return_value=600), patch(
            "player.youtube_music.service.time.monotonic", return_value=10
        ):
            returned_playback = service._cache_stream_playback(media_path, resolved_playback)

        self.assertEqual(returned_playback.stream_url, resolved_playback.stream_url)
        self.assertEqual(returned_playback.display_title, "Vídeo de teste")
        self.assertEqual(returned_playback.display_artist, "Canal de teste")
        self.assertNotIn(media_path, service._stream_cache)


    def test_search_uses_public_client_for_youtube_music_catalog(self):
        public_client = Mock()
        public_client.search.return_value = [{"resultType": "song", "videoId": "abc123DEF45", "title": "Faixa"}]
        fake_ytmusic_cls = Mock(return_value=public_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.search("teste", search_scope="music_songs")

        self.assertEqual(len(results), 1)
        public_client.search.assert_called_once_with("teste", filter="songs", limit=15)
        fake_ytmusic_cls.assert_called_once_with()

    def test_get_playlist_content_uses_public_client_when_auth_is_not_required(self):
        public_client = Mock()
        public_client.get_playlist.return_value = {
            "title": "Playlist pÃºblica",
            "tracks": [{"videoId": "abc123DEF45", "title": "Faixa"}],
        }
        fake_ytmusic_cls = Mock(return_value=public_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            playlist = service.get_playlist_content("PL1234567890")

        self.assertEqual(playlist.playlist_id, "PL1234567890")
        self.assertEqual(playlist.title, "Playlist pÃºblica")
        public_client.get_playlist.assert_called_once_with("PL1234567890", limit=None)
        fake_ytmusic_cls.assert_called_once_with()

    def test_get_playlist_content_uses_authenticated_client_when_requested(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {
            "title": "Playlist autenticada",
            "tracks": [{"videoId": "abc123DEF45", "title": "Faixa"}],
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            playlist = service.get_playlist_content("PL1234567890", require_auth=True)

        self.assertEqual(playlist.title, "Playlist autenticada")
        authenticated_client.get_playlist.assert_called_once_with("PL1234567890", limit=None)
        fake_ytmusic_cls.assert_called_once_with(service.browser_auth_file_path)

if __name__ == "__main__":
    unittest.main()
