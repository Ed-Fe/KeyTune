"""A lista única da aba do YouTube Music: início, busca e o que se abre dentro deles.

A lista é uma pilha: o início fica embaixo e a busca, a biblioteca e cada canal,
artista, álbum ou playlist aberto entram por cima. Chegar ao fim da lista traz
a página seguinte.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import wx


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.youtube_music.browse import BrowseMixin
from player.frames.youtube_music.navigation import (
    VIEW_KIND_HOME,
    VIEW_KIND_LIBRARY,
    ResultsNavigationMixin,
    YouTubeResultsView,
    container_title,
    results_view_summary,
)
from player.frames.youtube_music.search import SearchMixin
from player.frames.youtube_music.state import LibraryStateMixin
from player.youtube_music import catalog
from player.youtube_music.browse import YouTubeMoodCategory
from player.youtube_music.folders import (
    FOLDER_CHART_COUNTRY,
    FOLDER_CHART_GROUP,
    FOLDER_MOOD_CATEGORY,
    FOLDER_MOOD_SECTION,
    chart_folder_items,
    home_folder_items,
    mood_folder_items,
)
from player.youtube_music.library_manager import YouTubeMusicLibraryManager
from player.youtube_music.models import (
    YOUTUBE_ARTIST_SECTIONS,
    YOUTUBE_CHANNEL_SECTIONS,
    YOUTUBE_KIND_CHANNELS,
    YOUTUBE_KIND_VIDEOS,
    YOUTUBE_RESULTS_PAGE_SIZE,
    YOUTUBE_SEARCH_SCOPE_OPTIONS,
    YOUTUBE_SEARCH_SOURCE_MUSIC,
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
    YouTubeMusicPlaylistSummary,
    YouTubeResultPage,
)
from player.youtube_music.panel import YouTubeMusicTabPanel
from player.youtube_music.playlists import looks_like_link
from player.youtube_music.search import normalize_music_search_results, normalize_youtube_entry

CHANNEL_ID = "UCabcdefghijklmnopqrstuv"


def _video(index, source=YOUTUBE_SEARCH_SOURCE_YOUTUBE):
    return YouTubeMediaSearchResult(
        source=source,
        result_type="video",
        title=f"Vídeo {index}",
        video_id=f"video{index:06d}",
        playback_url=f"https://www.youtube.com/watch?v=video{index:06d}",
    )


def _channel():
    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        result_type="channel",
        title="Canal de teste",
        browse_id=CHANNEL_ID,
    )


def _artist():
    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type="artist",
        title="Artista de teste",
        browse_id=CHANNEL_ID,
    )


class ScopeTests(unittest.TestCase):
    def test_the_search_offers_albums_artists_channels_and_youtube_playlists(self):
        scope_ids = [option.scope_id for option in YOUTUBE_SEARCH_SCOPE_OPTIONS]

        for scope_id in ("music_albums", "music_artists", "youtube_channels", "youtube_playlists"):
            self.assertIn(scope_id, scope_ids)


class NormalizationTests(unittest.TestCase):
    def test_a_youtube_channel_entry_becomes_a_channel_that_can_be_opened(self):
        result = normalize_youtube_entry(
            {
                "id": CHANNEL_ID,
                "url": f"https://www.youtube.com/channel/{CHANNEL_ID}",
                "title": "Canal de teste",
                "channel_id": CHANNEL_ID,
                "channel_follower_count": 1500,
            }
        )

        self.assertEqual(result.result_type, "channel")
        self.assertEqual(result.browse_id, CHANNEL_ID)
        self.assertTrue(result.can_browse)
        self.assertTrue(result.opens_on_enter)
        self.assertFalse(result.can_add_to_playlist)
        self.assertIn("1.500", result.detail_text)

    def test_a_youtube_playlist_entry_becomes_a_playlist_of_youtube(self):
        result = normalize_youtube_entry(
            {
                "id": "PL123",
                "url": "https://www.youtube.com/playlist?list=PL123",
                "title": "Playlist de teste",
                "channel": "Dono",
            }
        )

        self.assertEqual(result.result_type, "playlist")
        self.assertEqual(result.source, YOUTUBE_SEARCH_SOURCE_YOUTUBE)
        self.assertEqual(result.playlist_id, "PL123")
        self.assertEqual(result.subtitle, "Dono")
        self.assertTrue(result.can_browse)
        self.assertFalse(result.opens_on_enter)

    def test_a_live_video_is_announced_as_live(self):
        result = normalize_youtube_entry(
            {"id": "abc123DEF45", "url": "https://www.youtube.com/watch?v=abc123DEF45", "title": "Ao vivo", "live_status": "is_live"}
        )

        self.assertEqual(result.result_type, "video")
        self.assertIn("ao vivo", result.detail_text)

    def test_music_albums_and_artists_are_kept_in_the_results(self):
        album, artist = normalize_music_search_results(
            [
                {
                    "resultType": "album",
                    "title": "Dois",
                    "type": "Album",
                    "year": "1986",
                    "playlistId": "OLAK5uy_abc",
                    "browseId": "MPREb_abc",
                    "artists": [{"name": "Legião Urbana"}],
                },
                {"resultType": "artist", "artist": "Legião Urbana", "browseId": CHANNEL_ID},
            ]
        )

        self.assertEqual(album.result_type, "album")
        self.assertEqual(album.playlist_id, "OLAK5uy_abc")
        self.assertEqual(album.subtitle, "Legião Urbana")
        self.assertTrue(album.can_browse)
        self.assertFalse(album.opens_on_enter)
        self.assertEqual(artist.result_type, "artist")
        self.assertEqual(artist.title, "Legião Urbana")
        self.assertTrue(artist.opens_on_enter)


@patch("player.youtube_music.catalog.ensure_yt_dlp_executable_available", Mock())
class YouTubePageTests(unittest.TestCase):
    def _entries(self, count):
        return [
            {"id": f"video{index:06d}", "url": f"https://www.youtube.com/watch?v=video{index:06d}", "title": f"Vídeo {index}"}
            for index in range(count)
        ]

    def setUp(self):
        # Cada teste diz se o YouTube.js está ligado; desligado, a listagem é do yt-dlp.
        self._youtubejs_enabled = self._patch("player.youtube_music.catalog.youtubejs_resolver_enabled", False)

    def _patch(self, target, return_value):
        patcher = patch(target, return_value=return_value)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_with_youtubejs_on_the_search_does_not_go_through_yt_dlp(self):
        self._youtubejs_enabled.return_value = True
        entries = [{"id": "video000001", "title": "Vídeo", "channel": "Canal", "view_count_text": "2 mi de visualizações"}]
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract, patch(
            "player.youtube_music.catalog.youtubejs_runtime.search_page", return_value=(entries, True)
        ) as search_page:
            page = catalog.youtube_search_page("rock", YOUTUBE_KIND_VIDEOS, 20, 20)

        search_page.assert_called_once_with("rock", YOUTUBE_KIND_VIDEOS, start=20, count=20)
        extract.assert_not_called()
        self.assertEqual([result.detail_text for result in page.results], ["2 mi de visualizações"])
        self.assertTrue(page.has_more)

    def test_when_youtubejs_fails_the_search_falls_back_to_yt_dlp(self):
        self._youtubejs_enabled.return_value = True
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract, patch(
            "player.youtube_music.catalog.youtubejs_runtime.search_page", side_effect=RuntimeError("sem Node")
        ):
            extract.return_value = SimpleNamespace(data={"entries": self._entries(3)})

            page = catalog.youtube_search_page("rock", YOUTUBE_KIND_VIDEOS, 0, 20)

        self.assertEqual(extract.call_args.args[0], "ytsearch20:rock")
        self.assertEqual(len(page.results), 3)

    def test_the_second_page_of_a_video_search_asks_only_for_its_own_items(self):
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract:
            extract.return_value = SimpleNamespace(data={"entries": self._entries(20)})

            page = catalog.youtube_search_page("rock", YOUTUBE_KIND_VIDEOS, 20, 20)

        self.assertEqual(extract.call_args.args[0], "ytsearch40:rock")
        self.assertEqual(extract.call_args.kwargs["playlist_items"], "21-40")
        self.assertEqual(len(page.results), 20)
        self.assertTrue(page.has_more)

    def test_a_channel_search_uses_the_channel_filter_of_youtube(self):
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract:
            extract.return_value = SimpleNamespace(
                data={"entries": [{"id": CHANNEL_ID, "url": f"https://www.youtube.com/channel/{CHANNEL_ID}", "title": "Canal"}]}
            )

            page = catalog.youtube_search_page("felipe neto", YOUTUBE_KIND_CHANNELS, 0, 20)

        target = extract.call_args.args[0]
        self.assertIn("search_query=felipe+neto", target)
        self.assertIn("sp=EgIQAg", target)
        self.assertEqual([result.result_type for result in page.results], ["channel"])
        self.assertFalse(page.has_more)

    def test_each_filter_of_a_channel_lists_its_own_tab(self):
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract:
            extract.return_value = SimpleNamespace(data={"entries": self._entries(3)})

            for section in YOUTUBE_CHANNEL_SECTIONS:
                catalog.youtube_channel_page(CHANNEL_ID, section.section_id, 0, 20)

        targets = [call.args[0] for call in extract.call_args_list]
        self.assertEqual(
            targets,
            [f"https://www.youtube.com/channel/{CHANNEL_ID}/{name}" for name in ("videos", "shorts", "streams", "playlists")],
        )

    def test_a_channel_without_the_tab_is_just_an_empty_list(self):
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract:
            extract.side_effect = RuntimeError("ERROR: [youtube:tab] This channel does not have a shorts tab")

            page = catalog.youtube_channel_page(CHANNEL_ID, "shorts", 0, 20)

        self.assertEqual(page.results, ())
        self.assertFalse(page.has_more)

    def test_other_failures_are_reported(self):
        with patch("player.youtube_music.catalog.extract_yt_dlp_info") as extract:
            extract.side_effect = RuntimeError("ERROR: sem conexão")

            with self.assertRaises(RuntimeError):
                catalog.youtube_channel_page(CHANNEL_ID, "videos", 0, 20)


class MusicPageTests(unittest.TestCase):
    def _songs(self, count):
        return [{"resultType": "song", "videoId": f"song{index:07d}", "title": f"Faixa {index}"} for index in range(count)]

    def test_the_next_page_of_a_music_search_is_cut_from_a_longer_request(self):
        client = Mock()
        client.search.return_value = self._songs(40)

        page = catalog.music_search_page(client, "rock", "songs", 20, 20)

        client.search.assert_called_once_with("rock", filter="songs", limit=40)
        self.assertEqual([result.title for result in page.results][:2], ["Faixa 20", "Faixa 21"])
        self.assertEqual(len(page.results), 20)
        self.assertTrue(page.has_more)

    def test_a_short_answer_means_there_is_nothing_more(self):
        client = Mock()
        client.search.return_value = self._songs(7)

        page = catalog.music_search_page(client, "rock", "songs", 0, 20)

        self.assertEqual(len(page.results), 7)
        self.assertFalse(page.has_more)

    def test_the_albums_of_an_artist_come_from_the_full_listing_when_there_is_one(self):
        client = Mock()
        client.get_artist_albums.return_value = [
            {"title": "Dois", "browseId": "MPREb_1", "playlistId": "OLAK5uy_1"},
            {"title": "Que País É Este", "browseId": "MPREb_2", "playlistId": "OLAK5uy_2"},
        ]
        artist = {
            "name": "Legião Urbana",
            "albums": {"browseId": "MPAD1", "params": "abc", "results": [{"title": "Dois", "browseId": "MPREb_1"}]},
        }

        page = catalog.music_artist_page(client, artist, "albums", 0, 20)

        client.get_artist_albums.assert_called_once_with("MPAD1", "abc", limit=None)
        self.assertEqual([result.title for result in page.results], ["Dois", "Que País É Este"])
        self.assertEqual({result.result_type for result in page.results}, {"album"})
        self.assertEqual(page.results[0].subtitle, "Legião Urbana")

    def test_related_artists_can_be_opened_too(self):
        artist = {"related": {"results": [{"title": "Capital Inicial", "browseId": "UC2", "subscribers": "1M"}]}}

        page = catalog.music_artist_page(Mock(), artist, "related", 0, 20)

        self.assertEqual(page.results[0].result_type, "artist")
        self.assertTrue(page.results[0].can_browse)

    def test_an_artist_without_the_section_has_an_empty_list(self):
        page = catalog.music_artist_page(Mock(), {"name": "X"}, "singles", 0, 20)

        self.assertEqual(page.results, ())


class LibraryManagerBrowseTests(unittest.TestCase):
    def _manager(self, client):
        return YouTubeMusicLibraryManager(lambda **_kwargs: client, lambda video_id, playlist_id=None: video_id)

    def test_the_artist_page_is_fetched_once_for_all_its_filters(self):
        client = Mock()
        client.get_artist.return_value = {"name": "X", "related": {"results": []}, "albums": {"results": []}}
        manager = self._manager(client)

        manager.fetch_browse_page(_artist(), section_id="related")
        manager.fetch_browse_page(_artist(), section_id="albums")

        client.get_artist.assert_called_once_with(CHANNEL_ID)

    def test_a_channel_is_listed_by_youtube_and_not_by_youtube_music(self):
        client = Mock()
        manager = self._manager(client)

        with patch("player.youtube_music.catalog.youtube_channel_page", return_value=YouTubeResultPage()) as channel_page:
            manager.fetch_browse_page(_channel(), section_id="playlists", start=20, count=20)

        channel_page.assert_called_once_with(CHANNEL_ID, "playlists", 20, 20)
        client.get_artist.assert_not_called()


class _Frame(ResultsNavigationMixin, SearchMixin, BrowseMixin, LibraryStateMixin):
    def __init__(self, service):
        self.announcements = []
        self._service = service
        self.panel = Mock()
        self.panel.get_selected_search_result_ids.return_value = []
        self._refresh_youtube_music_screen_later = Mock()
        self._ensure_youtube_music_authenticated = Mock(return_value=True)
        self._auto_load_youtube_music_library_if_needed = Mock()
        self._load_more_youtube_music_playlists = Mock(return_value=True)
        self._load_youtube_music_playlist_by_id = Mock(return_value=True)
        self._open_youtube_music_link = Mock(return_value=True)
        self.background_tasks = 0

    def _announce(self, message):
        self.announcements.append(message)

    def _get_youtube_music_service(self):
        return self._service

    def _get_youtube_music_panel(self):
        return self.panel

    def _is_youtube_music_operation_in_progress(self):
        return False

    def _format_youtube_music_error_detail(self, error):
        return str(error)

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None, timeout_ms=None):
        self.background_tasks += 1
        try:
            result = worker()
        except Exception as exc:
            on_error(exc)
            return True
        on_success(result)
        return True


def _page(start, count, *, has_more=True):
    return YouTubeResultPage(results=tuple(_video(index) for index in range(start, start + count)), has_more=has_more)


def _open_channel(frame, section="Vídeos"):
    frame.on_browse_youtube_music_search_result(_channel())
    frame.on_browse_youtube_music_search_result(_folder(frame, section))


class ResultsNavigationTests(unittest.TestCase):
    def _frame(self):
        service = Mock()
        service.fetch_search_page.side_effect = lambda query, search_scope, start, count: YouTubeResultPage(
            results=(_channel(),), has_more=False
        )
        service.fetch_browse_page.side_effect = lambda result, section_id, start, count: _page(start, count)
        frame = _Frame(service)
        frame.panel.get_search_query.return_value = "canal"
        frame.panel.get_search_scope_id.return_value = "youtube_channels"
        return frame, service

    def test_a_search_starts_the_navigation_over(self):
        frame, _service = self._frame()
        frame._youtube_music_results_view_stack = [YouTubeResultsView(title="antiga"), YouTubeResultsView(title="aberta")]

        frame.on_search_youtube_music()

        views = frame._youtube_music_results_views()
        self.assertEqual([view.kind for view in views], [VIEW_KIND_HOME, ""])
        self.assertTrue(frame._youtube_music_can_go_back_in_results())
        self.assertEqual(frame._youtube_music_search_results(), [_channel()])
        self.assertIn("1 item", frame.announcements[-1])
        self.assertTrue(frame._youtube_music_pending_results_focus)

    def test_a_search_with_no_results_leaves_the_focus_in_the_search_field(self):
        frame, service = self._frame()
        service.fetch_search_page.side_effect = lambda query, search_scope, start, count: YouTubeResultPage()

        frame.on_search_youtube_music()

        self.assertFalse(frame._youtube_music_pending_results_focus)

    def test_the_focus_goes_to_the_results_once_when_the_screen_is_refreshed(self):
        frame, _service = self._frame()
        frame.on_search_youtube_music()
        frame._youtube_music_service = None

        with patch("player.frames.youtube_music.state._youtube_music_has_saved_auth", return_value=False):
            LibraryStateMixin._refresh_youtube_music_screen(frame)
            LibraryStateMixin._refresh_youtube_music_screen(frame)

        frame.panel.focus_search_results.assert_called_once_with()

    def test_opening_a_channel_lists_what_there_is_to_see_in_it(self):
        frame, service = self._frame()
        frame.on_search_youtube_music()
        frame._youtube_music_pending_results_focus = False
        frame.panel.get_selected_search_result_ids.return_value = [_channel().stable_id]

        frame.on_browse_youtube_music_search_result(_channel())

        self.assertEqual(
            [item.title for item in frame._youtube_music_search_results()],
            [section.label for section in YOUTUBE_CHANNEL_SECTIONS],
        )
        self.assertEqual(frame.announcements[-1], "Canal Canal de teste: 4 itens.")
        self.assertFalse(frame._youtube_music_pending_results_focus)
        service.fetch_browse_page.assert_not_called()

    def test_choosing_what_to_see_in_a_channel_brings_its_list(self):
        frame, service = self._frame()
        frame.on_search_youtube_music()

        _open_channel(frame, "Playlists")

        view = frame._youtube_music_current_results_view()
        self.assertEqual(len(view.results), YOUTUBE_RESULTS_PAGE_SIZE)
        self.assertEqual(service.fetch_browse_page.call_args.kwargs["section_id"], "playlists")
        self.assertIn("Canal Canal de teste — Playlists", frame.announcements[-1])
        self.assertEqual(len(frame._youtube_music_results_views()), 4)

    def test_an_artist_lists_its_own_sections(self):
        frame, _service = self._frame()

        frame.on_browse_youtube_music_search_result(_artist())

        self.assertEqual(
            [item.title for item in frame._youtube_music_search_results()],
            [section.label for section in YOUTUBE_ARTIST_SECTIONS],
        )

    def test_back_returns_to_the_search_on_the_item_that_was_opened(self):
        frame, _service = self._frame()
        frame.on_search_youtube_music()
        frame.panel.get_selected_search_result_ids.return_value = [_channel().stable_id]
        frame.on_browse_youtube_music_search_result(_channel())

        self.assertTrue(frame.on_youtube_music_results_back())

        self.assertEqual(frame._youtube_music_search_results(), [_channel()])
        self.assertEqual(frame._youtube_music_pending_result_selection, _channel().stable_id)
        self.assertEqual(len(frame._youtube_music_results_views()), 2)

    def test_back_from_the_search_returns_to_the_home_list(self):
        frame, _service = self._frame()
        frame.on_search_youtube_music()

        self.assertTrue(frame.on_youtube_music_results_back())

        self.assertEqual(frame._youtube_music_search_results(), home_folder_items())
        self.assertFalse(frame._youtube_music_can_go_back_in_results())

    def test_back_at_the_home_list_only_says_so(self):
        frame, _service = self._frame()

        self.assertFalse(frame.on_youtube_music_results_back())

        self.assertEqual(frame.announcements[-1], "Não há lista anterior para voltar.")

    def test_the_end_of_the_list_brings_the_next_page(self):
        frame, service = self._frame()
        frame.on_search_youtube_music()
        _open_channel(frame)

        self.assertTrue(frame.on_load_more_youtube_music_results())

        view = frame._youtube_music_current_results_view()
        self.assertEqual(len(view.results), 2 * YOUTUBE_RESULTS_PAGE_SIZE)
        self.assertEqual(service.fetch_browse_page.call_args.kwargs["start"], YOUTUBE_RESULTS_PAGE_SIZE)
        self.assertEqual(frame.announcements[-1], "Mais 20 itens. Total: 40.")

    def test_repeated_items_are_not_added_twice_and_end_the_list(self):
        frame, service = self._frame()
        frame.on_search_youtube_music()
        _open_channel(frame)
        service.fetch_browse_page.side_effect = lambda result, section_id, start, count: _page(0, count)

        frame.on_load_more_youtube_music_results()

        view = frame._youtube_music_current_results_view()
        self.assertEqual(len(view.results), YOUTUBE_RESULTS_PAGE_SIZE)
        self.assertFalse(view.has_more)
        self.assertEqual(frame.announcements[-1], "Fim da lista: não há mais itens.")
        self.assertFalse(frame.on_load_more_youtube_music_results())

    def test_a_loose_list_goes_right_above_the_home_list_and_has_nothing_to_load(self):
        frame, _service = self._frame()
        frame.on_search_youtube_music()
        frame.on_browse_youtube_music_search_result(_channel())

        frame._set_youtube_music_search_results([_video(1)], search_summary="Curtidas: 1 faixa.")

        self.assertEqual(len(frame._youtube_music_results_views()), 2)
        self.assertFalse(frame.on_load_more_youtube_music_results())
        self.assertEqual(frame._youtube_music_search_summary(), "Curtidas: 1 faixa.")

    def test_a_link_typed_in_the_search_field_is_opened_instead_of_searched(self):
        frame, service = self._frame()
        frame.panel.get_search_query.return_value = "https://music.youtube.com/playlist?list=PL1234567890"

        self.assertTrue(frame.on_search_youtube_music())

        frame._open_youtube_music_link.assert_called_once_with("https://music.youtube.com/playlist?list=PL1234567890")
        service.fetch_search_page.assert_not_called()

    def test_what_looks_like_a_link(self):
        for text in ("https://youtu.be/abcdefghijk", "www.youtube.com/watch?v=abcdefghijk", "music.youtube.com/playlist?list=PL1"):
            self.assertTrue(looks_like_link(text), text)
        for text in ("legião urbana", "abcdefghijk", "rock https://youtu.be/abcdefghijk", ""):
            self.assertFalse(looks_like_link(text), text)

    def test_a_result_with_nothing_inside_is_not_opened(self):
        frame, service = self._frame()

        self.assertFalse(frame.on_browse_youtube_music_search_result(_video(1)))

        service.fetch_browse_page.assert_not_called()

    def test_titles_say_what_is_open(self):
        self.assertEqual(container_title(_artist(), "albums"), "Artista Artista de teste — Álbuns")
        self.assertEqual(YOUTUBE_ARTIST_SECTIONS[0].section_id, "songs")

    def test_a_youtube_playlist_is_expanded_by_youtube(self):
        frame, service = self._frame()
        service.get_youtube_playlist_content.return_value = SimpleNamespace(
            item_urls=["https://www.youtube.com/watch?v=a"], item_labels=["A"]
        )
        playlist = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="playlist", title="Lista", playlist_id="PL123"
        )

        items, labels, playlist_count, skipped = frame._prepare_youtube_music_search_results_for_playlist([playlist])

        service.get_youtube_playlist_content.assert_called_once_with("PL123", "Lista")
        service.get_playlist_content.assert_not_called()
        self.assertEqual((items, labels, playlist_count, skipped), (["https://www.youtube.com/watch?v=a"], ["A"], 1, 0))


def _folder(frame, title):
    return next(item for item in frame._youtube_music_search_results() if item.title == title)


class HomeListTests(unittest.TestCase):
    def _frame(self):
        service = Mock()
        service.get_charts.return_value = [_video(1), _video(2)]
        service.get_liked_songs.return_value = [_video(3)]
        service.get_mood_categories.return_value = [
            ("Momentos", [YouTubeMoodCategory("Foco", "p1"), YouTubeMoodCategory("Treino", "p2")]),
            ("Gêneros", [YouTubeMoodCategory("Rock", "p3")]),
        ]
        service.get_mood_playlists.return_value = [_video(4)]
        frame = _Frame(service)
        frame._youtube_music_library_playlists = [
            YouTubeMusicPlaylistSummary("PLminha0001", "Academia", "12 faixas"),
            YouTubeMusicPlaylistSummary("RDmix000001", "Mix 1", "", "Mix"),
        ]
        return frame, service

    def test_the_tab_starts_at_the_home_list(self):
        frame, _service = self._frame()

        self.assertEqual(
            [item.title for item in frame._youtube_music_search_results()],
            ["Suas playlists e mixes", "Curtidas", "Histórico", "Em alta", "Moods e gêneros"],
        )
        self.assertTrue(all(item.opens_on_enter for item in frame._youtube_music_search_results()))
        self.assertTrue(frame._youtube_music_search_summary().startswith("Início"))
        self.assertFalse(frame._youtube_music_can_go_back_in_results())

    def test_trending_goes_from_continents_to_countries_to_the_charts(self):
        frame, service = self._frame()

        frame.on_browse_youtube_music_search_result(_folder(frame, "Em alta"))
        self.assertEqual(frame.background_tasks, 0)
        self.assertEqual(frame._youtube_music_search_results(), chart_folder_items())
        self.assertEqual(frame._youtube_music_search_results()[0].title, "Global")

        frame.on_browse_youtube_music_search_result(_folder(frame, "América do Sul"))
        self.assertEqual(frame.background_tasks, 0)
        self.assertEqual(frame.announcements[-1].split(":")[0], "Em alta — América do Sul")

        frame.on_browse_youtube_music_search_result(_folder(frame, "Brasil"))
        service.get_charts.assert_called_once_with("BR")
        self.assertEqual(frame._youtube_music_search_results(), [_video(1), _video(2)])
        self.assertEqual(frame.announcements[-1], "Em alta em Brasil: 2 itens.")
        self.assertEqual(len(frame._youtube_music_results_views()), 4)

    def test_moods_go_from_sections_to_categories_to_playlists(self):
        frame, service = self._frame()

        frame.on_browse_youtube_music_search_result(_folder(frame, "Moods e gêneros"))
        self.assertEqual([item.title for item in frame._youtube_music_search_results()], ["Momentos", "Gêneros"])

        frame.on_browse_youtube_music_search_result(_folder(frame, "Momentos"))
        self.assertEqual([item.title for item in frame._youtube_music_search_results()], ["Foco", "Treino"])

        frame.on_browse_youtube_music_search_result(_folder(frame, "Treino"))
        service.get_mood_playlists.assert_called_once_with("p2", badge="Treino")
        self.assertEqual(frame._youtube_music_search_results(), [_video(4)])

    def test_a_single_section_of_moods_shows_its_categories_right_away(self):
        items = mood_folder_items([("Tudo", [YouTubeMoodCategory("Foco", "p1")]), ("Vazia", [])])

        self.assertEqual([(item.kind, item.title) for item in items], [(FOLDER_MOOD_CATEGORY, "Foco")])
        self.assertEqual(mood_folder_items([("", [object()]), ("B", [object()])])[0].kind, FOLDER_MOOD_SECTION)

    def test_trending_folders_are_global_and_then_the_continents(self):
        items = chart_folder_items()

        self.assertEqual((items[0].kind, items[0].payload), (FOLDER_CHART_COUNTRY, "ZZ"))
        self.assertTrue(all(item.kind == FOLDER_CHART_GROUP for item in items[1:]))
        self.assertIn(("BR", "Brasil"), items[1].payload)

    def test_liked_songs_need_the_account(self):
        frame, service = self._frame()
        frame._ensure_youtube_music_authenticated.return_value = False

        self.assertFalse(frame.on_browse_youtube_music_search_result(_folder(frame, "Curtidas")))
        service.get_liked_songs.assert_not_called()
        self.assertFalse(frame._youtube_music_can_go_back_in_results())

        frame._ensure_youtube_music_authenticated.return_value = True
        self.assertTrue(frame.on_browse_youtube_music_search_result(_folder(frame, "Curtidas")))
        self.assertEqual(frame._youtube_music_search_results(), [_video(3)])

    def test_the_library_is_a_list_that_follows_the_account(self):
        frame, _service = self._frame()

        frame.on_browse_youtube_music_search_result(_folder(frame, "Suas playlists e mixes"))

        results = frame._youtube_music_search_results()
        self.assertEqual(frame._youtube_music_current_results_view().kind, VIEW_KIND_LIBRARY)
        self.assertEqual([result.playlist_id for result in results], ["PLminha0001", "RDmix000001"])
        self.assertTrue(all(result.library_playlist and result.can_browse and not result.can_save for result in results))
        self.assertEqual(results[0].choice_label, "Academia — YouTube Music · playlist · 12 faixas")
        frame._auto_load_youtube_music_library_if_needed.assert_called_once_with()

        frame._set_youtube_music_library_cache(
            [YouTubeMusicPlaylistSummary("PLnova00001", "Nova")], has_more_playlists=True
        )

        self.assertEqual([result.playlist_id for result in frame._youtube_music_search_results()], ["PLnova00001"])
        self.assertTrue(frame._youtube_music_current_results_view().has_more)
        self.assertTrue(frame.on_load_more_youtube_music_results())
        frame._load_more_youtube_music_playlists.assert_called_once_with()

    def test_enter_on_a_library_playlist_opens_it_in_its_own_tab(self):
        frame, _service = self._frame()
        frame.on_browse_youtube_music_search_result(_folder(frame, "Suas playlists e mixes"))
        playlist = frame._youtube_music_search_results()[0]
        frame.panel.get_selected_search_results.return_value = [playlist]

        self.assertTrue(frame._add_youtube_music_search_results_to_current_playlist(play=True))

        frame._load_youtube_music_playlist_by_id.assert_called_once_with(
            "PLminha0001", fallback_title="Academia", require_auth=True
        )

    def test_a_library_playlist_is_read_with_the_account(self):
        frame, service = self._frame()
        service.get_playlist_content.return_value = SimpleNamespace(item_urls=["u"], item_labels=["l"])
        playlist = YouTubeMusicPlaylistSummary("PLminha0001", "Academia").as_result()

        frame._prepare_youtube_music_search_results_for_playlist([playlist])

        service.get_playlist_content.assert_called_once_with("PLminha0001", fallback_title="Academia", require_auth=True)


class DownloadFromTheListTests(unittest.TestCase):
    def _frame(self, selected):
        service = Mock()
        service.get_playlist_content.return_value = SimpleNamespace(
            item_urls=["https://music.youtube.com/watch?v=a", "https://music.youtube.com/watch?v=b"],
            item_labels=["A", "B"],
        )
        frame = _Frame(service)
        frame.panel.get_selected_search_results.return_value = list(selected)
        frame.download_media_entries = Mock()
        frame._download_in_progress = Mock(return_value=False)
        frame._offer_to_cancel_download = Mock()
        return frame, service

    def _playlist(self, title="Rock: anos 80"):
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_MUSIC, result_type="playlist", title=title, playlist_id="PL1234567890"
        )

    def test_videos_are_downloaded_by_their_own_address(self):
        frame, service = self._frame([_video(1), _video(2)])

        frame.download_youtube_music_search_selection()

        frame.download_media_entries.assert_called_once_with(
            [(_video(1).playback_url, "Vídeo 1"), (_video(2).playback_url, "Vídeo 2")]
        )
        self.assertEqual(frame.background_tasks, 0)

    def test_a_playlist_is_downloaded_whole_into_a_folder_with_its_name(self):
        frame, _service = self._frame([self._playlist()])

        frame.download_youtube_music_search_selection()

        frame.download_media_entries.assert_called_once_with(
            [
                ("https://music.youtube.com/watch?v=a", "A", "Rock_ anos 80"),
                ("https://music.youtube.com/watch?v=b", "B", "Rock_ anos 80"),
            ]
        )
        self.assertEqual(frame.announcements[-1], "Carregando as faixas de Rock: anos 80 para baixar.")

    def test_in_a_mixed_selection_the_playlist_keeps_its_folder_and_the_video_stays_loose(self):
        frame, _service = self._frame([self._playlist(), _video(1)])

        frame.download_youtube_music_search_selection()

        entries = frame.download_media_entries.call_args.args[0]
        self.assertEqual([folder for _url, _title, folder in entries], ["Rock_ anos 80", "Rock_ anos 80", ""])
        self.assertEqual(entries[-1][:2], (_video(1).playback_url, "Vídeo 1"))

    def test_two_playlists_with_the_same_name_get_separate_folders(self):
        frame, _service = self._frame([self._playlist("Mix"), self._playlist("mix")])

        frame.download_youtube_music_search_selection()

        folders = [folder for _url, _title, folder in frame.download_media_entries.call_args.args[0]]
        self.assertEqual(folders, ["Mix", "Mix", "mix (2)", "mix (2)"])

    def test_an_empty_playlist_does_not_stop_the_others(self):
        frame, service = self._frame([self._playlist("Vazia"), _video(1)])
        service.get_playlist_content.return_value = SimpleNamespace(item_urls=[], item_labels=[])

        frame.download_youtube_music_search_selection()

        frame.download_media_entries.assert_called_once_with([(_video(1).playback_url, "Vídeo 1", "")])

    def test_a_download_already_running_is_not_started_again(self):
        frame, service = self._frame([self._playlist()])
        frame._download_in_progress.return_value = True

        self.assertFalse(frame.download_youtube_music_search_selection())

        frame._offer_to_cancel_download.assert_called_once_with()
        service.get_playlist_content.assert_not_called()

    def test_the_menu_offers_download_for_lists_and_videos_but_not_for_folders(self):
        frame, _service = self._frame([])

        self.assertTrue(frame._youtube_music_search_results_can_download([self._playlist()]))
        self.assertTrue(frame._youtube_music_search_results_can_download([_video(1)]))
        self.assertFalse(frame._youtube_music_search_results_can_download([_channel(), home_folder_items()[0]]))


class ResultsListKeysTests(unittest.TestCase):
    def _panel(self, selected, *, can_go_back=False, has_more=False, focused=0, count=1):
        panel = YouTubeMusicTabPanel.__new__(YouTubeMusicTabPanel)
        panel.get_selected_search_results = Mock(return_value=list(selected))
        panel._on_add_search_results_to_current_playlist = Mock()
        panel._on_browse_search_result = Mock()
        panel._on_results_back = Mock()
        panel._on_load_more_results = Mock()
        panel._can_go_back = can_go_back
        panel._has_more_results = has_more
        panel._operation_in_progress = False
        panel.search_results_list = Mock()
        panel.search_results_list.GetItemCount.return_value = count
        panel.search_results_list.GetFocusedItem.return_value = focused
        return panel

    def _press(self, panel, key_code, *, shift=False, alt=False):
        event = Mock()
        event.GetKeyCode.return_value = key_code
        event.ShiftDown.return_value = shift
        event.ControlDown.return_value = False
        event.AltDown.return_value = alt
        panel._on_search_list_key_down(event)
        return event

    def test_enter_on_a_channel_opens_it_instead_of_playing(self):
        panel = self._panel([_channel()])

        self._press(panel, wx.WXK_RETURN)

        panel._on_browse_search_result.assert_called_once_with()
        panel._on_add_search_results_to_current_playlist.assert_not_called()

    def test_enter_on_a_folder_opens_it(self):
        panel = self._panel([home_folder_items()[3]])

        self._press(panel, wx.WXK_RETURN)

        panel._on_browse_search_result.assert_called_once_with()
        panel._on_add_search_results_to_current_playlist.assert_not_called()

    def test_enter_on_a_video_still_plays(self):
        panel = self._panel([_video(1)])

        self._press(panel, wx.WXK_RETURN)

        panel._on_add_search_results_to_current_playlist.assert_called_once_with(play=True)
        panel._on_browse_search_result.assert_not_called()

    def test_right_arrow_opens_what_has_content_and_is_ignored_otherwise(self):
        playlist = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_MUSIC, result_type="playlist", title="Lista", playlist_id="PL1"
        )
        panel = self._panel([playlist])
        self._press(panel, wx.WXK_RIGHT)
        panel._on_browse_search_result.assert_called_once_with()

        panel = self._panel([_video(1)])
        event = self._press(panel, wx.WXK_RIGHT)
        panel._on_browse_search_result.assert_not_called()
        event.Skip.assert_called_once_with()

    def test_backspace_goes_back(self):
        panel = self._panel([_video(1)], can_go_back=True)

        self._press(panel, wx.WXK_BACK)

        panel._on_results_back.assert_called_once_with()

    def test_left_arrow_goes_back_only_when_there_is_a_list_behind(self):
        panel = self._panel([_video(1)], can_go_back=True)
        self._press(panel, wx.WXK_LEFT)
        panel._on_results_back.assert_called_once_with()

        panel = self._panel([_video(1)], can_go_back=False)
        event = self._press(panel, wx.WXK_LEFT)
        panel._on_results_back.assert_not_called()
        event.Skip.assert_called_once_with()

    def test_down_on_the_last_item_loads_more(self):
        panel = self._panel([_video(1)], has_more=True, focused=19, count=20)

        self._press(panel, wx.WXK_DOWN)

        panel._on_load_more_results.assert_called_once_with()

    def test_down_in_the_middle_of_the_list_just_moves(self):
        panel = self._panel([_video(1)], has_more=True, focused=5, count=20)

        event = self._press(panel, wx.WXK_DOWN)

        panel._on_load_more_results.assert_not_called()
        event.Skip.assert_called_once_with()

    def test_down_on_the_last_item_does_nothing_special_when_the_list_is_complete(self):
        panel = self._panel([_video(1)], has_more=False, focused=19, count=20)

        event = self._press(panel, wx.WXK_DOWN)

        panel._on_load_more_results.assert_not_called()
        event.Skip.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
