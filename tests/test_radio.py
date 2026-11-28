from email.message import EmailMessage
from pathlib import Path
import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import Mock, patch

import wx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.announcements import ANNOUNCE_CONFIRMATIONS, ANNOUNCE_ERRORS, ANNOUNCE_PROGRESS
from player.frames.playback.media_metadata import MediaMetadataMixin
from player.frames.radio.directory import RadioDirectoryMixin
from player.frames.radio.now_playing import RadioNowPlayingMixin, clean_radio_stream_title
from player.library import is_audio_playback_media
from player.radio.client import (
    FALLBACK_SERVERS,
    _REQUEST_TIMEOUT_SECONDS,
    _USER_AGENT,
    RadioBrowserClient,
    RadioBrowserError,
)
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
from player.radio.service import (
    DIRECTORY_ADDED,
    DIRECTORY_CHECK_FAILED,
    DIRECTORY_DUPLICATE,
    DIRECTORY_REJECTED,
    DIRECTORY_UNCERTAIN,
    DirectoryAddResult,
    RadioService,
)
from player.radio.submission import (
    DIRECTORY_NAME_LIMIT,
    RadioDirectorySubmission,
    directory_submission_preview,
    initial_directory_submission,
    validate_directory_submission,
)
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


class _UrlopenDirectory:
    """Substitui o urlopen do cliente. A descoberta dos espelhos não sai da máquina."""

    def __init__(self, servers, on_request):
        self.servers = list(servers)
        self.on_request = on_request
        self.add_urls = []

    def __call__(self, request, timeout=None):
        if request.full_url.endswith("/json/servers"):
            body = json.dumps([{"name": name} for name in self.servers]).encode("utf-8")
            return _JsonResponse(body)
        if request.full_url.endswith("/json/add"):
            self.add_urls.append(request.full_url)
        return self.on_request(request, timeout)


class _JsonResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


class RadioDirectoryClientTests(unittest.TestCase):
    def _client(self, on_request, servers=("aa.example", "bb.example")):
        transport = _UrlopenDirectory(servers, on_request)
        patcher = patch("player.radio.client.urllib.request.urlopen", transport)
        patcher.start()
        self.addCleanup(patcher.stop)
        return RadioBrowserClient(), transport

    def test_add_posts_the_filled_fields_once_with_the_app_user_agent(self):
        captured = {}

        def on_request(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _JsonResponse(b'{"ok": true, "message": "added", "uuid": "new-uuid"}')

        client, transport = self._client(on_request)
        result = client.add_station(
            name="Rádio Exemplo",
            url="https://stream.example/a",
            homepage="  ",
            favicon="https://example.com/icon.png",
            countrycode="BR",
            languagecodes="pt,en",
            tags="rock,jazz",
        )

        self.assertEqual(result, (True, "added", "new-uuid"))
        self.assertEqual(len(transport.add_urls), 1)
        self.assertTrue(transport.add_urls[0].endswith("/json/add"))
        self.assertTrue(
            transport.add_urls[0].startswith("https://aa.example/")
            or transport.add_urls[0].startswith("https://bb.example/")
        )
        request = captured["request"]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(captured["timeout"], _REQUEST_TIMEOUT_SECONDS)
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["user-agent"], _USER_AGENT)
        self.assertIn("application/x-www-form-urlencoded", headers["content-type"])
        body = urllib.parse.parse_qs(request.data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "name": ["Rádio Exemplo"],
                "url": ["https://stream.example/a"],
                "favicon": ["https://example.com/icon.png"],
                "countrycode": ["BR"],
                "languagecodes": ["pt,en"],
                "tags": ["rock,jazz"],
            },
        )

    def test_add_is_not_repeated_on_another_mirror(self):
        def on_request(_request, _timeout):
            raise urllib.error.URLError("timed out")

        client, transport = self._client(on_request)

        with self.assertRaises(RadioBrowserError):
            client.add_station(name="Rádio", url="https://stream.example/a")

        self.assertEqual(len(transport.add_urls), 1)

    def test_http_error_is_a_communication_failure_and_is_not_retried(self):
        def on_request(request, _timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                500,
                "server error",
                EmailMessage(),
                io.BytesIO(b'{"ok": true, "message": "added", "uuid": "should-not-count"}'),
            )

        client, transport = self._client(on_request)

        with self.assertRaises(RadioBrowserError):
            client.add_station(name="Rádio", url="https://stream.example/a")

        self.assertEqual(len(transport.add_urls), 1)

    def test_add_reads_ok_as_text_or_boolean(self):
        payloads = [
            {"ok": True, "message": "added", "uuid": "abc"},
            {"ok": "true", "uuid": "abc"},
            {"ok": False, "message": "no"},
            {"ok": "false", "message": "no"},
            {"message": "no"},
            ["not a result"],
        ]
        answers = iter(payloads)

        def on_request(_request, _timeout):
            return _JsonResponse(json.dumps(next(answers)).encode("utf-8"))

        client, _transport = self._client(on_request)

        self.assertEqual(client.add_station(name="Rádio", url="https://stream.example/a"), (True, "added", "abc"))
        self.assertEqual(client.add_station(name="Rádio", url="https://stream.example/a"), (True, "", "abc"))
        self.assertEqual(client.add_station(name="Rádio", url="https://stream.example/a"), (False, "no", ""))
        self.assertEqual(client.add_station(name="Rádio", url="https://stream.example/a"), (False, "no", ""))
        self.assertEqual(client.add_station(name="Rádio", url="https://stream.example/a"), (False, "no", ""))
        self.assertEqual(client.add_station(name="Rádio", url="https://stream.example/a"), (False, "", ""))

    def test_byurl_retries_the_next_mirror(self):
        calls = []

        def on_request(request, _timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.URLError("down")
            return _JsonResponse(json.dumps([API_STATION]).encode("utf-8"))

        client, _transport = self._client(on_request)
        stream_url = "https://stream.example/a"

        self.assertEqual(client.stations_by_url(stream_url), [API_STATION])
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0], calls[1])
        encoded = urllib.parse.quote_plus(stream_url)
        self.assertIn(f"/json/stations/byurl?url={encoded}", calls[0])
        self.assertIn(f"/json/stations/byurl?url={encoded}", calls[1])

    def test_byurl_keeps_an_unreadable_payload(self):
        def on_request(_request, _timeout):
            return _JsonResponse(b'{"ok": false}')

        client, _transport = self._client(on_request)

        self.assertEqual(client.stations_by_url("https://stream.example/a"), {"ok": False})


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

    def test_duplicate_station_is_not_sent(self):
        self.client.stations_by_url.return_value = [
            {"name": "", "url": STREAM_URL},
            {"name": "Já existe", "url": STREAM_URL},
        ]

        result = self.service.add_to_directory(RadioDirectorySubmission(name="Nova", url=STREAM_URL))

        self.assertEqual(result.status, DIRECTORY_DUPLICATE)
        self.assertEqual(result.existing_name, "Já existe")
        self.client.add_station.assert_not_called()

    def test_failed_duplicate_check_does_not_send(self):
        self.client.stations_by_url.side_effect = RadioBrowserError("offline")

        result = self.service.add_to_directory(RadioDirectorySubmission(name="Nova", url=STREAM_URL))

        self.assertEqual(result.status, DIRECTORY_CHECK_FAILED)
        self.client.add_station.assert_not_called()

    def test_unreadable_duplicate_check_does_not_send(self):
        self.client.stations_by_url.return_value = {"ok": False}

        result = self.service.add_to_directory(RadioDirectorySubmission(name="Nova", url=STREAM_URL))

        self.assertEqual(result.status, DIRECTORY_CHECK_FAILED)
        self.client.add_station.assert_not_called()

    def test_new_address_is_sent_once_and_accepted(self):
        self.client.stations_by_url.return_value = []
        self.client.add_station.return_value = (True, "added", "uuid-1")
        submission = RadioDirectorySubmission(
            name="Nova",
            url=STREAM_URL,
            country_code="BR",
            language_codes="pt",
            tags="rock",
            homepage="https://example.com",
            favicon="",
        )

        result = self.service.add_to_directory(submission)

        self.assertEqual((result.status, result.uuid, result.message), (DIRECTORY_ADDED, "uuid-1", "added"))
        self.client.stations_by_url.assert_called_once_with(STREAM_URL)
        self.client.add_station.assert_called_once_with(
            name="Nova",
            url=STREAM_URL,
            homepage="https://example.com",
            favicon="",
            countrycode="BR",
            languagecodes="pt",
            tags="rock",
        )

    def test_rejected_add_keeps_the_directory_message(self):
        self.client.stations_by_url.return_value = []
        self.client.add_station.return_value = (False, "invalid url", "")

        result = self.service.add_to_directory(RadioDirectorySubmission(name="Nova", url=STREAM_URL))

        self.assertEqual((result.status, result.message), (DIRECTORY_REJECTED, "invalid url"))
        self.assertEqual(self.client.add_station.call_count, 1)

    def test_add_failure_is_uncertain_and_is_not_retried(self):
        self.client.stations_by_url.return_value = []
        self.client.add_station.side_effect = RadioBrowserError("timed out")

        result = self.service.add_to_directory(RadioDirectorySubmission(name="Nova", url=STREAM_URL))

        self.assertEqual(result.status, DIRECTORY_UNCERTAIN)
        self.assertEqual(self.client.add_station.call_count, 1)


class RadioDirectorySubmissionTests(unittest.TestCase):
    def _validate(self, **fields):
        values = {
            "name": "Rádio Nova",
            "url": "https://stream.example/a",
            "country_code": "BR",
            "language_codes": "",
            "tags": "",
            "homepage": "",
            "favicon": "",
        }
        values.update(fields)
        return validate_directory_submission(**values)

    def test_accepts_a_complete_station_and_drops_blank_optional_parts(self):
        submission, field, message = self._validate(
            name="  Rádio Nova  ",
            url=" https://stream.example/a ",
            country_code=" br ",
            language_codes=" pt, ,en ",
            tags=" rock, jazz ",
            homepage="",
            favicon=" https://example.com/icon.png ",
        )

        self.assertEqual((field, message), ("", ""))
        self.assertEqual(submission.name, "Rádio Nova")
        self.assertEqual(submission.url, "https://stream.example/a")
        self.assertEqual(submission.country_code, "BR")
        self.assertEqual(submission.language_codes, "pt,en")
        self.assertEqual(submission.tags, "rock,jazz")
        self.assertEqual(submission.homepage, "")
        self.assertEqual(submission.favicon, "https://example.com/icon.png")

    def test_name_is_required_and_limited_to_400_characters(self):
        _submission, field, message = self._validate(name="   ")
        self.assertEqual(field, "name")
        self.assertIn("nome", message.casefold())

        submission, field, _message = self._validate(name="a" * DIRECTORY_NAME_LIMIT)
        self.assertEqual(field, "")
        self.assertEqual(len(submission.name), DIRECTORY_NAME_LIMIT)

        _submission, field, message = self._validate(name="a" * (DIRECTORY_NAME_LIMIT + 1))
        self.assertEqual(field, "name")
        self.assertIn("400", message)

    def test_stream_address_must_be_http_or_https(self):
        for url in ("", "   ", "ftp://example.com/a", "notaurl", "http://", "https://"):
            _submission, field, _message = self._validate(url=url)
            self.assertEqual(field, "url", url)

        submission, field, _message = self._validate(url="HTTP://Example.com/Live")
        self.assertEqual(field, "")
        self.assertEqual(submission.url, "HTTP://Example.com/Live")

    def test_country_is_blank_or_two_letters(self):
        for country_code in ("", "BR", "br", "bR"):
            submission, field, _message = self._validate(country_code=country_code)
            self.assertEqual(field, "", country_code)
            self.assertEqual(submission.country_code, country_code.strip().upper())

        for country_code in ("B", "BRA", "B1", "12"):
            _submission, field, _message = self._validate(country_code=country_code)
            self.assertEqual(field, "country_code", country_code)

    def test_optional_pages_must_be_http_when_filled(self):
        for field_name in ("homepage", "favicon"):
            submission, field, _message = self._validate(**{field_name: ""})
            self.assertEqual(field, "")
            self.assertEqual(getattr(submission, field_name), "")

            _submission, field, _message = self._validate(**{field_name: "ftp://example.com/a"})
            self.assertEqual(field, field_name)

            submission, field, _message = self._validate(**{field_name: "https://example.com/a"})
            self.assertEqual(field, "")
            self.assertEqual(getattr(submission, field_name), "https://example.com/a")

            _submission, field, _message = self._validate(**{field_name: "http://[x"})
            self.assertEqual(field, field_name)

    def test_malformed_stream_address_stays_on_the_stream_field(self):
        _submission, field, message = self._validate(url="http://[x")
        self.assertEqual(field, "url")
        self.assertIn("http://", message)

    def test_the_first_invalid_field_is_the_one_reported(self):
        _submission, field, _message = self._validate(name="", url="notaurl", country_code="BRASIL")
        self.assertEqual(field, "name")

    def test_preview_lists_each_filled_field_and_the_public_warning(self):
        submission = RadioDirectorySubmission(
            name="Rádio Nova",
            url="https://stream.example/a",
            country_code="BR",
            language_codes="pt,en",
            tags="rock,jazz",
            homepage="https://example.com",
            favicon="https://example.com/icon.png",
        )

        self.assertEqual(
            directory_submission_preview(submission).splitlines(),
            [
                "Nome: Rádio Nova",
                "Endereço do stream: https://stream.example/a",
                "Código do país: BR",
                "Códigos de idioma: pt,en",
                "Gêneros: rock,jazz",
                "Site: https://example.com",
                "Endereço do ícone: https://example.com/icon.png",
                "",
                "O cadastro é público e o KeyTune não pode desfazê-lo.",
            ],
        )

    def test_preview_skips_blank_optional_fields(self):
        submission = RadioDirectorySubmission(name="Rádio Nova", url="https://stream.example/a")

        self.assertEqual(
            directory_submission_preview(submission).splitlines(),
            [
                "Nome: Rádio Nova",
                "Endereço do stream: https://stream.example/a",
                "",
                "O cadastro é público e o KeyTune não pode desfazê-lo.",
            ],
        )

    def test_only_one_unlisted_station_is_prefilled(self):
        custom = RadioStation(name="Minha FM", stream_url="https://mine.example/live", station_uuid="")
        listed = _station()
        folder = RadioFolderItem("country", "Brasil")

        prefilled = initial_directory_submission("br", [custom])
        self.assertEqual((prefilled.name, prefilled.url, prefilled.country_code), ("Minha FM", "https://mine.example/live", "BR"))

        empty = initial_directory_submission("BR", [listed])
        self.assertEqual((empty.name, empty.url, empty.country_code), ("", "", "BR"))
        self.assertEqual(initial_directory_submission("BR", [custom, custom]).name, "")
        self.assertEqual(initial_directory_submission("", [folder]).country_code, "")
        self.assertEqual(initial_directory_submission("BR", []).name, "")


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, name=None):
        self._target = target

    def start(self):
        self._target()


class _DirectoryQuestion:
    def __init__(self, parent, message, title, style):
        self.parent = parent
        self.message = message
        self.title = title
        self.style = style
        self.labels = None
        self.destroyed = False

    def SetYesNoLabels(self, yes_label, no_label):
        self.labels = (yes_label, no_label)

    def ShowModal(self):
        return self.parent.answer

    def Destroy(self):
        self.destroyed = True

    def IsBeingDeleted(self):
        return self.destroyed


class DirectorySubmitFlowTests(unittest.TestCase):
    def _host(self, result):
        host = RadioDirectoryMixin.__new__(RadioDirectoryMixin)
        host.result = result
        host.answer = wx.ID_NO
        host._deleted = False
        host.announcements = []
        host.reopened = []
        host.questions = []
        host._radio_directory_submit_running = False

        def announce(message, category):
            host.announcements.append((message, category))

        def service():
            double = Mock()
            double.add_to_directory.side_effect = lambda submission: host.result
            return double

        host._announce = announce
        host._get_radio_service = service
        host._get_radio_panel = lambda: None
        host._show_radio_directory_dialog = lambda initial: host.reopened.append(initial) or False
        host.IsBeingDeleted = lambda: host._deleted
        return host

    def _submit(self, host, submission):
        def question(*args, **kwargs):
            dialog = _DirectoryQuestion(*args, **kwargs)
            host.questions.append(dialog)
            return dialog

        with (
            patch("player.frames.radio.directory.threading.Thread", _ImmediateThread),
            patch("player.frames.radio.directory.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)),
            patch("player.frames.radio.directory.wx.MessageDialog", question),
        ):
            started = host._submit_radio_to_directory(submission)
        return started

    def test_rejection_asks_once_and_reopens_only_on_yes(self):
        submission = RadioDirectorySubmission(name="Nova", url=STREAM_URL)
        host = self._host(DirectoryAddResult(DIRECTORY_REJECTED, message="url inválida"))
        host.answer = wx.ID_YES

        self.assertTrue(self._submit(host, submission))

        self.assertEqual(
            host.announcements,
            [("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS)],
        )
        self.assertNotIn("url inválida", host.announcements[0][0])
        self.assertEqual(host.reopened, [submission])
        self.assertFalse(host._radio_directory_submit_running)
        question = host.questions[0]
        self.assertEqual(len(host.questions), 1)
        self.assertIn("url inválida", question.message)
        self.assertIn("Voltar ao formulário?", question.message)
        self.assertEqual(question.message.count("Voltar ao formulário?"), 1)
        self.assertEqual(question.title, "Cadastro no diretório")
        self.assertEqual(question.labels, ("&Sim", "&Não"))
        self.assertTrue(question.style & wx.NO_DEFAULT)
        self.assertTrue(question.style & wx.YES_NO)
        self.assertTrue(question.destroyed)

        host.answer = wx.ID_NO
        host.reopened.clear()
        host.questions.clear()
        host.announcements.clear()
        self._submit(host, submission)
        self.assertEqual(host.reopened, [])
        self.assertEqual(host.announcements, [("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS)])
        self.assertEqual(len(host.questions), 1)

    def test_success_and_duplicate_are_only_announced(self):
        submission = RadioDirectorySubmission(name="Nova", url=STREAM_URL)
        added = self._host(DirectoryAddResult(DIRECTORY_ADDED, uuid="abc"))
        self._submit(added, submission)
        self.assertEqual(added.questions, [])
        self.assertEqual(added.reopened, [])
        self.assertEqual(
            added.announcements,
            [
                ("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS),
                ("Nova foi adicionada ao diretório.", ANNOUNCE_CONFIRMATIONS),
            ],
        )

        duplicate = self._host(DirectoryAddResult(DIRECTORY_DUPLICATE, existing_name="Já existe"))
        self._submit(duplicate, submission)
        self.assertEqual(duplicate.questions, [])
        self.assertEqual(
            duplicate.announcements,
            [
                ("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS),
                ("Este endereço já está no diretório, na rádio Já existe.", ANNOUNCE_ERRORS),
            ],
        )

    def test_check_failure_and_uncertain_result_ask_without_announcing(self):
        submission = RadioDirectorySubmission(name="Nova", url=STREAM_URL)
        failed = self._host(DirectoryAddResult(DIRECTORY_CHECK_FAILED))
        self._submit(failed, submission)
        self.assertEqual(failed.announcements, [("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS)])
        self.assertIn("Nada foi enviado.", failed.questions[0].message)
        self.assertNotIn("Nada foi enviado.", failed.announcements[0][0])
        self.assertEqual(failed.reopened, [])

        host = self._host(DirectoryAddResult(DIRECTORY_ADDED))

        def explode(_submission):
            raise RuntimeError("timed out")

        host._get_radio_service = lambda: Mock(add_to_directory=explode)
        self._submit(host, submission)
        self.assertEqual(host.announcements, [("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS)])
        self.assertIn("Não dá para saber", host.questions[0].message)
        self.assertIn("Nova", host.questions[0].message)
        self.assertNotIn("Não dá para saber", host.announcements[0][0])

    def test_destroyed_window_skips_the_question_and_the_reopen(self):
        submission = RadioDirectorySubmission(name="Nova", url=STREAM_URL)
        host = self._host(DirectoryAddResult(DIRECTORY_REJECTED, message="não"))

        def mark_deleted(_submission):
            host._deleted = True
            return host.result

        host._get_radio_service = lambda: Mock(add_to_directory=mark_deleted)
        self._submit(host, submission)
        self.assertEqual(host.questions, [])
        self.assertEqual(host.announcements, [("Enviando Nova ao diretório.", ANNOUNCE_PROGRESS)])
        self.assertEqual(host.reopened, [])
        self.assertFalse(host._radio_directory_submit_running)


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
