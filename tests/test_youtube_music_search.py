from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.models import (
    YOUTUBE_SEARCH_SCOPE_MUSIC_PLAYLISTS,
    YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS,
    YOUTUBE_SEARCH_SCOPE_MUSIC_VIDEOS,
    YOUTUBE_SEARCH_SCOPE_YOUTUBE_VIDEOS,
    YouTubeMediaSearchResult,
    get_search_scope_option,
)
from player.youtube_music.playlists import (
    build_watch_url,
    build_youtube_watch_url,
    extract_video_id_from_text,
    is_music_youtube_url,
)
from player.youtube_music.search import normalize_music_search_results


class YouTubeMusicSearchHelperTests(unittest.TestCase):
    def test_extract_video_id_from_supported_urls(self):
        video_id = "abc123DEF45"

        self.assertEqual(
            extract_video_id_from_text(f"https://music.youtube.com/watch?v={video_id}"),
            video_id,
        )
        self.assertEqual(
            extract_video_id_from_text(f"https://www.youtube.com/watch?v={video_id}&list=RDAMVM{video_id}"),
            video_id,
        )
        self.assertEqual(
            extract_video_id_from_text(f"https://youtu.be/{video_id}"),
            video_id,
        )
        self.assertEqual(
            extract_video_id_from_text(video_id),
            video_id,
        )

    def test_is_music_youtube_url_only_matches_music_host(self):
        self.assertTrue(is_music_youtube_url("https://music.youtube.com/watch?v=abc123DEF45"))
        self.assertFalse(is_music_youtube_url("https://www.youtube.com/watch?v=abc123DEF45"))
        self.assertFalse(is_music_youtube_url("https://youtu.be/abc123DEF45"))

    def test_normalize_music_search_results_maps_song_and_playlist(self):
        raw_results = [
            {
                "resultType": "song",
                "videoId": "abc123DEF45",
                "title": "Faixa de teste",
                "artists": [{"name": "Artista 1"}, {"name": "Artista 2"}],
                "duration": "3:45",
                "album": {"name": "Álbum de teste"},
                "feedbackTokens": {"add": "token-add", "remove": "token-remove"},
                "inLibrary": False,
            },
            {
                "resultType": "playlist",
                "browseId": "VLPL1234567890",
                "title": "Playlist de teste",
                "author": "Conta de teste",
                "itemCount": 12,
            },
        ]

        results = normalize_music_search_results(raw_results)

        self.assertEqual(len(results), 2)
        song_result, playlist_result = results

        self.assertEqual(song_result.playback_url, build_watch_url("abc123DEF45"))
        self.assertEqual(song_result.subtitle, "Artista 1, Artista 2")
        self.assertEqual(song_result.feedback_add_token, "token-add")
        self.assertTrue(song_result.can_add_to_playlist)
        self.assertTrue(song_result.can_save)

        self.assertEqual(playlist_result.playlist_id, "PL1234567890")
        self.assertTrue(playlist_result.can_open)
        self.assertFalse(playlist_result.can_add_to_playlist)
        self.assertEqual(playlist_result.save_action_label, "Salvar playlist na biblioteca")

    def test_video_search_result_cannot_be_saved_from_search(self):
        result = YouTubeMediaSearchResult(
            source="youtube_music",
            result_type="video",
            title="Vídeo de teste",
            video_id="abc123DEF45",
            playback_url=build_watch_url("abc123DEF45"),
        )

        self.assertFalse(result.can_save)
        self.assertEqual(result.save_action_label, "")

    def test_get_search_scope_option_falls_back_to_music_songs(self):
        self.assertEqual(
            get_search_scope_option("scope-inexistente").scope_id,
            YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS,
        )

    def test_public_search_scopes_do_not_require_authentication(self):
        self.assertFalse(get_search_scope_option(YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS).requires_auth)
        self.assertFalse(get_search_scope_option(YOUTUBE_SEARCH_SCOPE_MUSIC_VIDEOS).requires_auth)
        self.assertFalse(get_search_scope_option(YOUTUBE_SEARCH_SCOPE_MUSIC_PLAYLISTS).requires_auth)
        self.assertFalse(get_search_scope_option(YOUTUBE_SEARCH_SCOPE_YOUTUBE_VIDEOS).requires_auth)

    def test_search_result_choice_label_mentions_source_and_kind(self):
        result = YouTubeMediaSearchResult(
            source="youtube",
            result_type="video",
            title="Vídeo de teste",
            subtitle="Canal de teste",
            detail_text="4:12",
            video_id="abc123DEF45",
            playback_url=build_youtube_watch_url("abc123DEF45"),
        )

        self.assertIn("YouTube", result.choice_label)
        self.assertIn("vídeo", result.choice_label)
        self.assertIn("Canal de teste", result.choice_label)


if __name__ == "__main__":
    unittest.main()
