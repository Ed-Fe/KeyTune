from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.frames.playback.media_metadata import MediaMetadataMixin
from player.frames.radio.now_playing import RadioNowPlayingMixin, clean_radio_stream_title
from player.library import is_audio_playback_media
from player.radio.client import FALLBACK_SERVERS, RadioBrowserClient, RadioBrowserError
from player.radio.folders import (
    FOLDER_COUNTRIES,
    FOLDER_COUNTRY,
    FOLDER_COUNTRY_STATES,
    FOLDER_FAVORITES,
    FOLDER_TAGS,
    home_folder_items,
    open_radio_folder,
)
from player.radio.media import (
    build_radio_media_path,
    is_radio_media,
    radio_station_uuid,
    radio_stream_url,
)
from player.radio.models import RadioFolderItem, RadioStation
from player.radio.service import RadioService
from player.radio.store import RadioLibraryStore
from player.smart_library import SmartLibraryService

STREAM_URL = "https://stream.example.com/radio;"
STATION_UUID = "570cc99a-9159-4d91-9a8f-96ddb5b30797"
API_STATION = {
    "stationuuid": STATION_UUID,
    "name": " Rádio Exemplo FM ",
    "url": "https://example.com/listen.pls",
    "url_resolved": STREAM_URL,
    "homepage": "https://example.com/",
    "tags": "pop,rock,,news,talk",
    "country": "Brazil",
    "countrycode": "br",
    "state": "Sao Paulo",
    "language": "portuguese",
    "codec": "MP3",
    "bitrate": 128,
    "votes": 10,
    "clickcount": 5,
}


def _station(name="Rádio Exemplo FM", uuid=STATION_UUID, stream_url=STREAM_URL):
    return RadioStation(name=name, stream_url=stream_url, station_uuid=uuid)


class RadioMediaPathTests(unittest.TestCase):
    def test_media_path_carries_the_station_and_strips_back_to_the_stream(self):
        media_path = build_radio_media_path(STREAM_URL, STATION_UUID)

        self.assertTrue(is_radio_media(media_path))
        self.assertEqual(radio_stream_url(media_path), STREAM_URL)
        self.assertEqual(radio_station_uuid(media_path), STATION_UUID)

    def test_existing_fragment_is_replaced(self):
        media_path = build_radio_media_path("http://example.com/live#old", "")

        self.assertEqual(radio_stream_url(media_path), "http://example.com/live")
        self.assertEqual(radio_station_uuid(media_path), "")
        self.assertTrue(is_radio_media(media_path))

    def test_only_stream_addresses_become_radio_items(self):
        self.assertEqual(build_radio_media_path("C:\\musicas\\faixa.mp3", STATION_UUID), "")
        self.assertEqual(build_radio_media_path("", STATION_UUID), "")
        self.assertFalse(is_radio_media("https://example.com/live.mp3"))
        self.assertFalse(is_radio_media("C:\\pasta\\arquivo#keytune-radio=x.mp3"))

    def test_radio_plays_as_audio(self):
        self.assertTrue(is_audio_playback_media(build_radio_media_path(STREAM_URL, STATION_UUID)))


class RadioStationTests(unittest.TestCase):
    def test_reads_a_station_from_the_directory(self):
        station = RadioStation.from_api(API_STATION)

        self.assertEqual(station.name, "Rádio Exemplo FM")
        self.assertEqual(station.stream_url, STREAM_URL)
        self.assertEqual(station.country_code, "BR")
        self.assertEqual(station.tags, ("pop", "rock", "news", "talk"))
        self.assertEqual(station.key, STATION_UUID)
        self.assertEqual(
            station.choice_label,
            "Rádio Exemplo FM — Sao Paulo, Brazil — pop, rock, news — MP3 128 kbps",
        )

    def test_station_without_a_playable_stream_is_dropped(self):
        self.assertIsNone(RadioStation.from_api({**API_STATION, "url": "", "url_resolved": ""}))
        self.assertIsNone(RadioStation.from_api({**API_STATION, "name": ""}))
        self.assertIsNone(RadioStation.from_api("not a station"))

    def test_falls_back_to_the_unresolved_address(self):
        station = RadioStation.from_api({**API_STATION, "url_resolved": ""})

        self.assertEqual(station.stream_url, "https://example.com/listen.pls")

    def test_round_trips_through_the_saved_form(self):
        station = RadioStation.from_api(API_STATION)

        self.assertEqual(RadioStation.from_dict(station.to_dict()), station)

    def test_station_without_uuid_is_identified_by_its_stream(self):
        station = RadioStation(name="Minha rádio", stream_url="HTTP://Example.com/Live")

        self.assertEqual(station.key, "http://example.com/live")


class RadioBrowserClientTests(unittest.TestCase):
    def test_uses_a_discovered_server_and_sends_the_search(self):
        requested_urls = []

        def fetch_json(url):
            requested_urls.append(url)
            if url.endswith("/json/servers"):
                return [{"name": "xx1.api.radio-browser.info"}, {"name": "xx1.api.radio-browser.info"}]
            return [API_STATION, "junk"]

        client = RadioBrowserClient(fetch_json=fetch_json)
        stations = client.search_stations(name="jovem pan", country_code="BR", offset=50, limit=50)

        self.assertEqual(stations, [API_STATION])
        search_url = requested_urls[-1]
        self.assertTrue(search_url.startswith("https://xx1.api.radio-browser.info/json/stations/search?"))
        self.assertIn("name=jovem+pan", search_url)
        self.assertIn("countrycode=BR", search_url)
        self.assertIn("offset=50", search_url)
        self.assertIn("hidebroken=true", search_url)
        self.assertNotIn("tag=", search_url)

    def test_falls_back_to_the_next_server_when_one_fails(self):
        attempts = []

        def fetch_json(url):
            if url.endswith("/json/servers"):
                raise urllib.error.URLError("offline")
            attempts.append(url)
            if len(attempts) == 1:
                raise urllib.error.URLError("down")
            return []

        client = RadioBrowserClient(fetch_json=fetch_json)

        self.assertEqual(client.tags(), [])
        self.assertEqual(len(attempts), 2)
        self.assertIn(FALLBACK_SERVERS[0], attempts[0])
        self.assertIn(FALLBACK_SERVERS[1], attempts[1])

    def test_raises_when_no_server_answers(self):
        def fetch_json(_url):
            raise urllib.error.URLError("offline")

        with self.assertRaises(RadioBrowserError):
            RadioBrowserClient(fetch_json=fetch_json).countries()

    def test_vote_reports_what_the_directory_said(self):
        client = RadioBrowserClient(
            fetch_json=lambda url: [] if url.endswith("/servers") else {"ok": False, "message": "too often"}
        )

        self.assertEqual(client.vote(STATION_UUID), (False, "too often"))


class _LibraryTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.database_path = str(Path(self._directory.name) / "library.db")
        self.library = SmartLibraryService(self.database_path)
        self.addCleanup(lambda: self.library.close())
        self.store = RadioLibraryStore(lambda: self.library)

    def reopen_library(self):
        """Fecha a biblioteca (esvaziando a fila de gravações) e abre de novo."""
        self.library.close()
        self.library = SmartLibraryService(self.database_path)


class RadioLibraryStoreTests(_LibraryTestCase):
    def test_favorite_is_the_library_favorite_and_keeps_the_station_details(self):
        station = RadioStation.from_api(API_STATION)

        self.assertTrue(self.store.toggle_favorite(station))

        self.assertTrue(self.library.is_favorite(station.media_path))
        self.assertEqual(self.library.favorites()[0].label, "Rádio Exemplo FM")
        self.reopen_library()
        self.assertEqual(self.store.favorites(), [station])
        self.assertEqual(self.store.favorite_keys(), {STATION_UUID})
        self.assertFalse(self.store.toggle_favorite(station))
        self.assertEqual(self.store.favorites(), [])
        self.assertEqual(self.store.find(station.media_path), station)

    def test_station_favorited_from_the_playlist_shows_up_once_its_details_are_known(self):
        station = _station()
        self.store.remember(station)

        self.library.toggle_favorite(station.media_path, label=station.name)

        self.assertEqual(self.store.favorites(), [station])
        self.assertTrue(self.store.is_favorite(station))

    def test_favorites_come_in_alphabetical_order_and_skip_other_media(self):
        self.store.toggle_favorite(_station("Zebra FM", "uuid-z", "https://z.example.com/live"))
        self.store.toggle_favorite(_station("alfa FM", "uuid-a", "https://a.example.com/live"))
        self.library.set_favorite("C:\\musicas\\faixa.mp3", True, label="faixa")

        self.assertEqual([station.name for station in self.store.favorites()], ["alfa FM", "Zebra FM"])

    def test_recents_come_from_the_playback_history_latest_first(self):
        first = _station("Primeira", "uuid-1", "https://one.example.com/live")
        second = _station("Segunda", "uuid-2", "https://two.example.com/live")
        never_played = _station("Nunca tocada", "uuid-3", "https://three.example.com/live")
        for station in (first, second, never_played):
            self.store.remember(station)
        self.library._history.record(first.media_path, label=first.name)
        self.library._database.execute("UPDATE media SET last_played_epoch = last_played_epoch - 60")
        self.library._history.record(second.media_path, label=second.name)

        self.assertEqual([station.name for station in self.store.recents()], ["Segunda", "Primeira"])

    def test_clearing_the_library_forgets_the_stations(self):
        station = _station()
        self.store.toggle_favorite(station)

        self.library.clear_everything()

        self.assertEqual(self.store.favorites(), [])
        self.assertIsNone(self.store.find(station.media_path))

    def test_without_the_library_nothing_is_kept_and_nothing_breaks(self):
        store = RadioLibraryStore(lambda: None)
        station = _station()

        self.assertIsNone(store.toggle_favorite(station))
        self.assertFalse(store.remember(station))
        self.assertFalse(store.is_favorite(station))
        self.assertEqual((store.favorites(), store.recents(), store.find(station.media_path)), ([], [], None))


class RadioServiceTests(_LibraryTestCase):
    def setUp(self):
        super().setUp()
        self.client = Mock()
        self.service = RadioService(self.store, client=self.client)

    def test_search_page_drops_bad_and_repeated_stations(self):
        self.client.search_stations.return_value = [API_STATION, dict(API_STATION), {"name": "sem stream"}]

        page = self.service.fetch_search_page(" exemplo ", country_code="BR", start=100, count=3)

        self.assertEqual([station.name for station in page.results], ["Rádio Exemplo FM"])
        self.assertTrue(page.has_more)
        self.client.search_stations.assert_called_once_with(limit=3, name="exemplo", country_code="BR", offset=100)

    def test_short_page_ends_the_list(self):
        self.client.search_stations.return_value = [API_STATION]

        self.assertFalse(self.service.fetch_top_page(count=50).has_more)

    def test_playing_item_is_recognized_from_the_session_then_from_the_library(self):
        media_path = build_radio_media_path(STREAM_URL, STATION_UUID)
        unknown = self.service.station_for_media_path(media_path, "Nome da playlist")
        self.assertEqual((unknown.name, unknown.station_uuid, unknown.homepage), ("Nome da playlist", STATION_UUID, ""))

        self.client.search_stations.return_value = [API_STATION]
        self.service.fetch_top_page()
        self.assertEqual(self.service.station_for_media_path(media_path).homepage, "https://example.com/")

        remembered = _station("Favorita", "uuid-fav", "https://fav.example.com/live")
        self.service.remember(remembered)
        self.assertEqual(self.service.station_for_media_path(remembered.media_path), remembered)
        self.assertIsNone(self.service.station_for_media_path("https://example.com/song.mp3"))

    def test_toggle_favorite(self):
        station = _station()

        self.assertTrue(self.service.toggle_favorite(station))
        self.assertTrue(self.service.is_favorite(station))
        self.assertFalse(self.service.toggle_favorite(station))
        self.assertEqual(self.service.favorites(), [])

    def test_states_are_requested_by_the_directory_country_name(self):
        self.client.countries.return_value = [{"name": "Brazil", "iso_3166_1": "BR", "stationcount": 900}]
        self.client.states.return_value = [{"name": "Bahia", "stationcount": 3}]

        self.assertEqual(self.service.list_states("br"), [{"name": "Bahia", "stationcount": 3}])
        self.client.states.assert_called_once_with("Brazil", limit=500)
        self.assertEqual(self.service.list_states("ZZ"), [])

    def test_pasted_stream_becomes_a_station(self):
        station = RadioService.custom_station(" https://example.com/live.aac ")

        self.assertEqual(station.stream_url, "https://example.com/live.aac")
        self.assertEqual(station.station_uuid, "")
        self.assertIsNone(RadioService.custom_station("jovem pan"))

    def test_click_is_only_counted_for_directory_stations_and_never_raises(self):
        self.client.count_click.side_effect = RadioBrowserError("offline")

        self.service.count_click(_station())
        self.service.count_click(_station(uuid=""))

        self.client.count_click.assert_called_once_with(STATION_UUID)


class RadioFolderTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.favorites.return_value = [_station()]
        self.service.recents.return_value = []

    def test_home_offers_the_user_country_only_when_known(self):
        with_country = home_folder_items(self.service, ("BR", "Brasil"))
        without_country = home_folder_items(self.service, ("", ""))

        country_items = [item for item in with_country if item.kind == FOLDER_COUNTRY]
        self.assertEqual([(item.detail_text, item.payload) for item in country_items], [("Brasil", ("BR", "Brasil"))])
        self.assertEqual(len(without_country), len(with_country) - 1)
        self.assertEqual(with_country[0].choice_label, "Rádios favoritas — 1 rádio")

    def test_favorites_open_without_asking_the_directory(self):
        content = open_radio_folder(RadioFolderItem(FOLDER_FAVORITES, "Rádios favoritas"), self.service)

        self.assertIsNone(content.fetch_page)
        self.assertEqual(content.results, [_station()])
        self.assertEqual(content.kind, FOLDER_FAVORITES)

    def test_countries_become_folders_with_code_and_name(self):
        self.service.list_countries.return_value = [
            {"name": "Brazil", "iso_3166_1": "br", "stationcount": 2},
            {"name": "", "iso_3166_1": "XX"},
        ]
        content = open_radio_folder(RadioFolderItem(FOLDER_COUNTRIES, "Países"), self.service)

        page = content.fetch_page(0, 50)

        self.assertEqual([(item.kind, item.payload, item.detail_text) for item in page.results],
                         [(FOLDER_COUNTRY, ("BR", "Brazil"), "2 rádios")])
        self.assertFalse(page.has_more)
        self.assertEqual(content.fetch_page(50, 50).results, [])

    def test_country_opens_its_sections_and_states_lead_to_stations(self):
        country = RadioFolderItem(FOLDER_COUNTRY, "Brazil", payload=("BR", "Brazil"))
        sections = open_radio_folder(country, self.service).results
        states_item = next(item for item in sections if item.kind == FOLDER_COUNTRY_STATES)
        self.service.list_states.return_value = [{"name": "Bahia", "stationcount": 3}]

        state_item = open_radio_folder(states_item, self.service).fetch_page(0, 50).results[0]
        open_radio_folder(state_item, self.service).fetch_page(50, 50)

        self.service.list_states.assert_called_once_with("BR")
        self.service.fetch_state_page.assert_called_once_with("BR", "Bahia", start=50, count=50)

    def test_genres_are_paged(self):
        self.service.list_tags.return_value = [{"name": "pop", "stationcount": 9}, {"name": "rock"}]

        page = open_radio_folder(RadioFolderItem(FOLDER_TAGS, "Gêneros"), self.service).fetch_page(0, 2)

        self.assertTrue(page.has_more)
        self.assertEqual([item.payload for item in page.results], ["pop", "rock"])

    def test_unknown_folder_has_no_content(self):
        self.assertIsNone(open_radio_folder(RadioFolderItem("???", "x"), self.service))


class RadioPlaybackIntegrationTests(unittest.TestCase):
    def test_radio_resolves_to_its_stream_as_a_live_without_yt_dlp(self):
        media_path = build_radio_media_path(STREAM_URL, STATION_UUID)

        details = MediaMetadataMixin()._resolve_media_for_playback_details(media_path)

        self.assertEqual(details, (STREAM_URL, {}, "", "", True))

    def test_stream_title_ignores_what_is_not_a_song(self):
        media_path = build_radio_media_path("https://example.com/live/stream.aac", STATION_UUID)

        self.assertEqual(clean_radio_stream_title(media_path, "Rádio X", " Artista - Música "), "Artista - Música")
        self.assertEqual(clean_radio_stream_title(media_path, "Rádio X", "stream.aac"), "")
        self.assertEqual(clean_radio_stream_title(media_path, "Rádio X", "rádio x"), "")
        self.assertEqual(clean_radio_stream_title(media_path, "Rádio X", " - "), "")

    def test_song_change_goes_to_the_status_bar_and_the_status_announcement(self):
        media_path = build_radio_media_path(STREAM_URL, STATION_UUID)

        class Frame(RadioNowPlayingMixin):
            def __init__(self):
                self.status_messages = []
                self.state = Mock(current_media_path=media_path)

            def _media_label(self, _media_path):
                return "Rádio X"

            def _set_status_message(self, message, *, auto_clear_ms=6000):
                self.status_messages.append(message)

            def _get_active_playlist_state(self):
                return self.state

        frame = Frame()
        frame._handle_radio_stream_title(media_path, "Artista - Música")
        frame._handle_radio_stream_title(media_path, "Artista - Música")

        self.assertEqual(frame.status_messages, ["Rádio X: Artista - Música"])
        self.assertEqual(frame._radio_now_playing_sentence(), "Tocando na rádio: Artista - Música.")
        frame.state.current_media_path = "C:\\musica.mp3"
        self.assertEqual(frame._radio_now_playing_sentence(), "")


if __name__ == "__main__":
    unittest.main()
