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
    def test_switches_stream_resolution_to_anonymous_mode_for_the_session(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/audio.webm",
        )

        with patch.object(service, "has_saved_browser_auth", return_value=True), patch(
            "player.youtube_music.service.resolve_music_stream_playback",
            return_value=resolved_playback,
        ) as resolve_stream:
            service.resolve_stream_playback(media_path)
            next_mode = service.advance_stream_playback_after_http_403()
            service.resolve_stream_playback(media_path)

        self.assertEqual(next_mode, "visionos")
        self.assertEqual(
            [
                (
                    call.kwargs["use_account_cookies"],
                    call.kwargs["anonymous_player_client"],
                )
                for call in resolve_stream.call_args_list
            ],
            [(True, ""), (False, "")],
        )

    def test_http_403_advances_stream_profiles_once_per_session(self):
        service = YouTubeMusicService()

        with patch.object(service, "has_saved_browser_auth", return_value=True):
            self.assertEqual(service.advance_stream_playback_after_http_403(), "visionos")
            self.assertEqual(service.advance_stream_playback_after_http_403(), "tv_simply")
            self.assertEqual(service.advance_stream_playback_after_http_403(), "")

        with patch(
            "player.youtube_music.service.resolve_music_stream_playback",
            return_value=ResolvedStreamPlayback(stream_url="https://media.example.invalid/audio.mp4"),
        ) as resolve_stream:
            service.resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertFalse(resolve_stream.call_args.kwargs["use_account_cookies"])
        self.assertEqual(resolve_stream.call_args.kwargs["anonymous_player_client"], "tv_simply")

    def test_cache_ttl_respects_expiring_signed_urls(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=760&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
            display_title="Vídeo de teste",
            display_artist="Canal de teste",
        )

        with patch("player.youtube_music.stream_cache.time.time", return_value=600), patch(
            "player.youtube_music.stream_cache.time.monotonic", return_value=10
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

        with patch("player.youtube_music.stream_cache.time.time", return_value=600), patch(
            "player.youtube_music.stream_cache.time.monotonic", return_value=10
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

    def test_add_tracks_to_playlist_returns_added_count_on_success(self):
        authenticated_client = Mock()
        authenticated_client.add_playlist_items.return_value = {
            "status": "STATUS_SUCCEEDED",
            "playlistEditResults": [{"videoId": "abc123DEF45"}, {"videoId": "xyz987WVU54"}],
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            added = service.add_tracks_to_playlist("PL1234567890", ["abc123DEF45", "abc123DEF45", "xyz987WVU54"])

        self.assertEqual(added, 2)
        # Duplicates in the request are collapsed before hitting the API.
        authenticated_client.add_playlist_items.assert_called_once_with(
            "PL1234567890", ["abc123DEF45", "xyz987WVU54"]
        )

    def test_add_tracks_to_playlist_raises_when_server_rejects(self):
        authenticated_client = Mock()
        authenticated_client.add_playlist_items.return_value = "STATUS_FAILED"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.add_tracks_to_playlist("PL1234567890", ["abc123DEF45"])

    def test_remove_tracks_from_playlist_maps_set_video_ids(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {
            "owned": True,
            "tracks": [
                {"videoId": "abc123DEF45", "setVideoId": "SET_ABC"},
                {"videoId": "xyz987WVU54", "setVideoId": "SET_XYZ"},
            ],
        }
        authenticated_client.remove_playlist_items.return_value = "STATUS_SUCCEEDED"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            removed = service.remove_tracks_from_playlist("PL1234567890", ["abc123DEF45"])

        self.assertEqual(removed, 1)
        authenticated_client.remove_playlist_items.assert_called_once_with(
            "PL1234567890", [{"videoId": "abc123DEF45", "setVideoId": "SET_ABC"}]
        )

    def test_remove_tracks_from_playlist_raises_when_track_absent(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {
            "owned": True,
            "tracks": [{"videoId": "other00ID000", "setVideoId": "SET_OTHER"}],
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.remove_tracks_from_playlist("PL1234567890", ["abc123DEF45"])
        authenticated_client.remove_playlist_items.assert_not_called()

    def test_remove_tracks_from_playlist_rejects_non_owned_playlist(self):
        authenticated_client = Mock()
        # A saved/public playlist the account does not own: no ``owned`` flag
        # and no ``collaborators`` entry.
        authenticated_client.get_playlist.return_value = {
            "tracks": [{"videoId": "abc123DEF45", "setVideoId": "SET_ABC"}]
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.remove_tracks_from_playlist("PL1234567890", ["abc123DEF45"])
        authenticated_client.remove_playlist_items.assert_not_called()

    def test_create_playlist_returns_new_id_for_empty_playlist(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            new_id = service.create_playlist("Minha playlist")

        self.assertEqual(new_id, "PLNEW1234567")
        authenticated_client.create_playlist.assert_called_once_with(
            "Minha playlist", "", privacy_status="PRIVATE", video_ids=None
        )

    def test_create_playlist_seeds_and_dedupes_video_ids(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            new_id = service.create_playlist(
                "Seleção",
                video_ids=["abc123DEF45", "abc123DEF45", "xyz987WVU54"],
            )

        self.assertEqual(new_id, "PLNEW1234567")
        authenticated_client.create_playlist.assert_called_once_with(
            "Seleção", "", privacy_status="PRIVATE", video_ids=["abc123DEF45", "xyz987WVU54"]
        )

    def test_create_playlist_forwards_chosen_privacy_status(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            service.create_playlist("Pública", privacy_status="PUBLIC")

        authenticated_client.create_playlist.assert_called_once_with(
            "Pública", "", privacy_status="PUBLIC", video_ids=None
        )

    def test_create_playlist_falls_back_to_private_for_invalid_privacy(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            service.create_playlist("Qualquer", privacy_status="BOGUS")

        authenticated_client.create_playlist.assert_called_once_with(
            "Qualquer", "", privacy_status="PRIVATE", video_ids=None
        )

    def test_create_playlist_raises_when_no_id_returned(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = {"error": "boom"}
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.create_playlist("Sem id")

    def test_delete_playlist_deletes_owned_playlist(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {"owned": True, "tracks": []}
        authenticated_client.delete_playlist.return_value = "STATUS_SUCCEEDED"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            deleted_id = service.delete_playlist("PL1234567890")

        self.assertEqual(deleted_id, "PL1234567890")
        authenticated_client.delete_playlist.assert_called_once_with("PL1234567890")

    def test_delete_playlist_rejects_non_owned_playlist(self):
        authenticated_client = Mock()
        # Saved/collaborator playlist: editable but not owned, so not deletable.
        authenticated_client.get_playlist.return_value = {"collaborators": [], "tracks": []}
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.delete_playlist("PL1234567890")
        authenticated_client.delete_playlist.assert_not_called()

    def test_delete_playlist_rejects_watch_mix_without_api_calls(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.delete_playlist("RDAMVM1234567")
        authenticated_client.get_playlist.assert_not_called()
        authenticated_client.delete_playlist.assert_not_called()

    def test_get_media_feedback_status_reads_like_status_from_song(self):
        authenticated_client = Mock()
        authenticated_client.get_song.return_value = {"likeStatus": "LIKE"}
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            status = service.get_media_feedback_status("https://music.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(status, "LIKE")
        authenticated_client.get_song.assert_called_once_with("abc123DEF45")
        fake_ytmusic_cls.assert_called_once_with(service.browser_auth_file_path)

    def test_rate_media_feedback_calls_rate_song_for_like(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            message = service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "LIKE")

        self.assertEqual(message, "Mídia atual curtida no YouTube Music.")
        authenticated_client.rate_song.assert_called_once_with("abc123DEF45", "LIKE")
        authenticated_client.get_song.assert_not_called()


    def test_rate_media_feedback_calls_rate_song_for_dislike(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            message = service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "DISLIKE")

        self.assertEqual(message, "Mídia atual marcada como não gostei no YouTube Music.")
        authenticated_client.rate_song.assert_called_once_with("abc123DEF45", "DISLIKE")
        authenticated_client.get_song.assert_not_called()


    def test_rate_media_feedback_rejects_invalid_rating_without_calling_api(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            with self.assertRaises(RuntimeError):
                service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "FAVORITE")

        authenticated_client.rate_song.assert_not_called()

    def test_rate_media_feedback_returns_success_regardless_of_server_propagation_delay(self):
        # O YouTube Music propaga avaliações de forma assíncrona: o get_song()
        # imediatamente após rate_song() pode retornar o status anterior.
        # O player não deve fazer get_song() nem reportar falso alarme.
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            message = service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "LIKE")

        # Mesmo que o servidor ainda não reflita o novo status, a mensagem
        # deve ser a de sucesso (a avaliação foi enviada sem exceção).
        self.assertEqual(message, "Mídia atual curtida no YouTube Music.")
        authenticated_client.rate_song.assert_called_once_with("abc123DEF45", "LIKE")
        authenticated_client.get_song.assert_not_called()


if __name__ == "__main__":
    unittest.main()
