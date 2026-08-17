from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.browse import (
    extract_browse_playlists_from_response,
    tolerant_library_playlist_parsing,
)
from player.youtube_music.library_manager import YouTubeMusicLibraryManager


HAS_YTMUSICAPI = importlib.util.find_spec("ytmusicapi") is not None


def make_playlist_tile(playlist_id, title, *, thumbnail):
    """Build a library grid tile shaped like YouTube Music's own response.

    *thumbnail* is the ``musicThumbnailRenderer.thumbnail`` payload; passing
    ``{}`` reproduces the tile that makes ytmusicapi raise ``KeyError``.
    """
    return {
        "title": {
            "runs": [
                {
                    "text": title,
                    "navigationEndpoint": {"browseEndpoint": {"browseId": f"VL{playlist_id}"}},
                }
            ]
        },
        "subtitle": {"runs": [{"text": "Playlist"}, {"text": " • "}, {"text": "12 músicas"}]},
        "thumbnailRenderer": {"musicThumbnailRenderer": {"thumbnail": thumbnail}},
        "navigationEndpoint": {"browseEndpoint": {"browseId": f"VL{playlist_id}"}},
    }


COVER = {"thumbnails": [{"url": "https://example.invalid/cover.jpg", "width": 60, "height": 60}]}


def make_library_response(tiles):
    """Wrap tiles in the ``FEmusic_liked_playlists`` browse response shape."""
    return {
        "contents": {
            "singleColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "content": {
                                "sectionListRenderer": {
                                    "contents": [
                                        {
                                            "itemSectionRenderer": {
                                                "contents": [
                                                    {
                                                        "gridRenderer": {
                                                            "items": [
                                                                {"musicTwoRowItemRenderer": {}},
                                                                *(
                                                                    {"musicTwoRowItemRenderer": tile}
                                                                    for tile in tiles
                                                                ),
                                                            ]
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }


class FakeYTMusicClient:
    """Client that parses tiles the way ytmusicapi's library mixin does.

    Going through the real ``parse_playlist`` (resolved from the mixin's own
    namespace, exactly like ytmusicapi does) is what lets these tests prove the
    tolerant patch lands where it matters.
    """

    def __init__(self, tiles):
        self._tiles = tiles
        self.parse_calls = 0

    def get_library_playlists(self, limit=None):
        from ytmusicapi.mixins import library as library_mixin

        self.parse_calls += 1
        return [library_mixin.parse_playlist(tile) for tile in self._tiles]

    def _send_request(self, endpoint, body, *args, **kwargs):
        return make_library_response(self._tiles)


@unittest.skipUnless(HAS_YTMUSICAPI, "ytmusicapi is not installed")
class TolerantLibraryPlaylistParsingTests(unittest.TestCase):
    def test_untouched_parser_still_raises_on_a_tile_without_cover_art(self):
        from ytmusicapi.mixins import library as library_mixin

        with self.assertRaises(KeyError):
            library_mixin.parse_playlist(make_playlist_tile("PLempty", "Playlist vazia", thumbnail={}))

    def test_tolerant_parser_rebuilds_the_tile_without_cover_art(self):
        from ytmusicapi.mixins import library as library_mixin

        with tolerant_library_playlist_parsing():
            playlist = library_mixin.parse_playlist(
                make_playlist_tile("PLempty", "Playlist vazia", thumbnail={})
            )

        self.assertEqual(playlist["playlistId"], "PLempty")
        self.assertEqual(playlist["title"], "Playlist vazia")
        self.assertEqual(playlist["count"], "12")

    def test_original_parser_is_restored_afterwards(self):
        from ytmusicapi.mixins import library as library_mixin

        original = library_mixin.parse_playlist
        with tolerant_library_playlist_parsing():
            self.assertIsNot(library_mixin.parse_playlist, original)
        self.assertIs(library_mixin.parse_playlist, original)

    def test_original_parser_is_restored_even_when_the_body_raises(self):
        from ytmusicapi.mixins import library as library_mixin

        original = library_mixin.parse_playlist
        with self.assertRaises(RuntimeError):
            with tolerant_library_playlist_parsing():
                raise RuntimeError("boom")
        self.assertIs(library_mixin.parse_playlist, original)


@unittest.skipUnless(HAS_YTMUSICAPI, "ytmusicapi is not installed")
class LibraryPlaylistFetchTests(unittest.TestCase):
    def make_manager(self, client):
        return YouTubeMusicLibraryManager(
            get_client_fn=lambda require_auth=False: client,
            build_watch_url_fn=lambda video_id, playlist_id=None: "",
        )

    def test_a_tile_without_cover_art_no_longer_drops_the_whole_listing(self):
        client = FakeYTMusicClient(
            [
                make_playlist_tile("PLgood", "Favoritas", thumbnail=COVER),
                make_playlist_tile("PLempty", "Playlist vazia", thumbnail={}),
                make_playlist_tile("PLother", "Rock", thumbnail=COVER),
            ]
        )

        playlists, has_more = self.make_manager(client).get_user_library_playlists()

        self.assertEqual(
            [playlist.title for playlist in playlists], ["Favoritas", "Playlist vazia", "Rock"]
        )
        self.assertEqual([playlist.playlist_id for playlist in playlists][1], "PLempty")
        self.assertFalse(has_more)
        # The first attempt crashed, the tolerant retry succeeded: no need for
        # the raw-response fallback.
        self.assertEqual(client.parse_calls, 2)

    def test_healthy_libraries_are_fetched_in_a_single_attempt(self):
        client = FakeYTMusicClient([make_playlist_tile("PLgood", "Favoritas", thumbnail=COVER)])

        playlists, _has_more = self.make_manager(client).get_user_library_playlists()

        self.assertEqual([playlist.title for playlist in playlists], ["Favoritas"])
        self.assertEqual(client.parse_calls, 1)

    def test_falls_back_to_the_raw_browse_response_when_parsing_keeps_failing(self):
        class AlwaysFailingClient(FakeYTMusicClient):
            def get_library_playlists(self, limit=None):
                self.parse_calls += 1
                raise KeyError("Unable to find 'thumbnails'")

        client = AlwaysFailingClient(
            [
                make_playlist_tile("PLgood", "Favoritas", thumbnail=COVER),
                make_playlist_tile("PLempty", "Playlist vazia", thumbnail={}),
            ]
        )

        playlists, _has_more = self.make_manager(client).get_user_library_playlists()

        self.assertEqual(
            [playlist.title for playlist in playlists], ["Favoritas", "Playlist vazia"]
        )
        self.assertEqual(client.parse_calls, 2)

    def test_returns_empty_when_even_the_raw_request_is_unavailable(self):
        class UnusableClient:
            def get_library_playlists(self, limit=None):
                raise KeyError("Unable to find 'thumbnails'")

        playlists, has_more = self.make_manager(UnusableClient()).get_user_library_playlists()

        self.assertEqual(playlists, [])
        self.assertFalse(has_more)


class RawBrowseResponseWalkerTests(unittest.TestCase):
    def test_reads_playlists_from_a_library_grid_and_skips_the_new_playlist_button(self):
        response = make_library_response(
            [make_playlist_tile("PLgood", "Favoritas", thumbnail=COVER)]
        )

        playlists = extract_browse_playlists_from_response(response)

        self.assertEqual(playlists, [
            {
                "playlistId": "PLgood",
                "title": "Favoritas",
                "description": "Playlist • 12 músicas",
                "count": "12",
            }
        ])

    def test_reads_the_browse_id_from_the_title_run_when_the_tile_has_none(self):
        tile = make_playlist_tile("PLtitleonly", "Só no título", thumbnail=COVER)
        del tile["navigationEndpoint"]

        playlists = extract_browse_playlists_from_response(make_library_response([tile]))

        self.assertEqual([playlist["playlistId"] for playlist in playlists], ["PLtitleonly"])


if __name__ == "__main__":
    unittest.main()
