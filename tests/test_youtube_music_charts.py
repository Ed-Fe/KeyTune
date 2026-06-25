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

from player.youtube_music.charts import normalize_chart_results
from player.youtube_music.models import (
    YOUTUBE_CHART_COUNTRIES,
    YOUTUBE_CHART_DEFAULT_COUNTRY_CODE,
    get_chart_country_groups,
    get_chart_country_label,
)
from player.youtube_music.service import YouTubeMusicService


class YouTubeMusicChartsNormalizationTests(unittest.TestCase):
    def test_normalize_maps_playlist_sections_and_skips_artists(self):
        raw_charts = {
            "countries": {"selected": {"text": "Brasil"}, "options": []},
            "videos": [
                {"title": "Top Vídeos - Brasil", "playlistId": "PLvideos", "thumbnails": []},
            ],
            "artists": [
                {"title": "Artista X", "browseId": "UCabc", "rank": "1", "trend": "neutral"},
            ],
        }

        results = normalize_chart_results(raw_charts)

        self.assertEqual(len(results), 1)
        chart_result = results[0]
        self.assertEqual(chart_result.result_type, "playlist")
        self.assertEqual(chart_result.playlist_id, "PLvideos")
        self.assertEqual(chart_result.source_badge, "Em alta · vídeos")
        self.assertTrue(chart_result.can_open)
        self.assertTrue(chart_result.can_save)

    def test_normalize_orders_premium_daily_and_weekly_sections(self):
        raw_charts = {
            "daily": [{"title": "Diário", "playlistId": "PLdaily"}],
            "weekly": [{"title": "Semanal", "playlistId": "PLweekly"}],
            "genres": [{"title": "Pop", "playlistId": "PLgenre"}],
        }

        results = normalize_chart_results(raw_charts)

        self.assertEqual(
            [result.playlist_id for result in results],
            ["PLdaily", "PLweekly", "PLgenre"],
        )
        self.assertEqual(results[0].source_badge, "Em alta · diário")
        self.assertEqual(results[1].source_badge, "Em alta · semanal")

    def test_normalize_deduplicates_and_skips_incomplete_entries(self):
        raw_charts = {
            "videos": [
                {"title": "Top", "playlistId": "PLdup"},
                {"title": "Sem id", "playlistId": ""},
                {"playlistId": "PLnotitle"},
                {"title": "Top", "playlistId": "PLdup"},
            ],
        }

        results = normalize_chart_results(raw_charts)

        self.assertEqual([result.playlist_id for result in results], ["PLdup"])

    def test_normalize_handles_non_dict_payload(self):
        self.assertEqual(normalize_chart_results(None), [])
        self.assertEqual(normalize_chart_results([]), [])


class YouTubeMusicChartsServiceTests(unittest.TestCase):
    def test_get_charts_uses_public_client_and_passes_country(self):
        public_client = Mock()
        public_client.get_charts.return_value = {
            "videos": [{"title": "Top Vídeos - Brasil", "playlistId": "PLvideos"}],
        }
        fake_ytmusic_cls = Mock(return_value=public_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.get_charts("br")

        self.assertEqual(len(results), 1)
        public_client.get_charts.assert_called_once_with("BR")
        fake_ytmusic_cls.assert_called_once_with()

    def test_get_charts_defaults_blank_country_to_global(self):
        public_client = Mock()
        public_client.get_charts.return_value = {}
        fake_module = SimpleNamespace(YTMusic=Mock(return_value=public_client))
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            service.get_charts("")

        public_client.get_charts.assert_called_once_with("ZZ")


class YouTubeMusicChartCountryTests(unittest.TestCase):
    def test_default_country_is_present_in_options(self):
        codes = {code for code, _label in YOUTUBE_CHART_COUNTRIES}
        self.assertIn(YOUTUBE_CHART_DEFAULT_COUNTRY_CODE, codes)
        self.assertIn("BR", codes)

    def test_get_chart_country_label_resolves_known_and_unknown_codes(self):
        self.assertEqual(get_chart_country_label("br"), "Brasil")
        self.assertEqual(get_chart_country_label("ZZ"), "Global")
        self.assertEqual(get_chart_country_label("xx"), "XX")


class YouTubeMusicChartGroupsTests(unittest.TestCase):
    def test_global_is_first_top_level_section(self):
        sections = get_chart_country_groups()
        self.assertEqual(sections[0][0], "")
        self.assertEqual(sections[0][1], [(YOUTUBE_CHART_DEFAULT_COUNTRY_CODE, "Global")])

    def test_every_country_appears_exactly_once(self):
        grouped_codes = [
            code for _title, countries in get_chart_country_groups() for code, _label in countries
        ]
        self.assertEqual(sorted(grouped_codes), sorted(code for code, _label in YOUTUBE_CHART_COUNTRIES))
        self.assertEqual(len(grouped_codes), len(set(grouped_codes)))

    def test_continent_sections_have_non_empty_titles_and_members(self):
        for title, countries in get_chart_country_groups()[1:]:
            self.assertTrue(title)
            self.assertTrue(countries)


if __name__ == "__main__":
    unittest.main()
