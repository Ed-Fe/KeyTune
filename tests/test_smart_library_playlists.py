from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import time
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.preferences.models import AppSettings
from player.smart_library.database import SmartLibraryDatabase
from player.smart_library.history import HistoryStore
from player.smart_library.ratings import RatingStore
from player.smart_library.records import MediaRecordStore
from player.smart_library.smart_playlists import (
    DEFAULT_SMART_PLAYLIST_LIMIT,
    MIN_SMART_PLAYLIST_LIMIT,
    SORT_HIGHEST_RATED,
    SORT_LEAST_RECENTLY_PLAYED,
    SORT_MOST_PLAYED,
    SORT_TITLE,
    SmartPlaylistCollection,
    SmartPlaylistRule,
    SmartPlaylistStore,
)


DAY_SECONDS = 86400


class SmartPlaylistRuleTests(unittest.TestCase):
    def test_rule_round_trips(self):
        rule = SmartPlaylistRule(
            name="Preferidas esquecidas",
            favorites_only=True,
            minimum_rating=4,
            folder_path="C:\\Musica",
            not_played_for_days=30,
            minimum_play_count=2,
            include_never_played=False,
            exclude_remote=False,
            sort_order=SORT_MOST_PLAYED,
            limit=250,
        )

        restored = SmartPlaylistRule.from_dict(rule.to_dict())

        self.assertEqual(restored, rule)

    def test_out_of_range_values_are_clamped(self):
        restored = SmartPlaylistRule.from_dict(
            {
                "name": "Estranha",
                "minimum_rating": 99,
                "not_played_for_days": -5,
                "limit": 0,
                "sort_order": "inventado",
            }
        )

        self.assertEqual(restored.minimum_rating, 5)
        self.assertEqual(restored.not_played_for_days, 0)
        # Números fora de faixa são presos ao limite, como nas demais
        # preferências; só um valor não numérico cai no padrão.
        self.assertEqual(restored.limit, MIN_SMART_PLAYLIST_LIMIT)
        self.assertEqual(restored.sort_order, "recently_played")

    def test_a_non_numeric_limit_falls_back_to_the_default(self):
        restored = SmartPlaylistRule.from_dict({"name": "Estranha", "limit": "muitas"})

        self.assertEqual(restored.limit, DEFAULT_SMART_PLAYLIST_LIMIT)

    def test_collection_drops_rules_without_a_name(self):
        collection = SmartPlaylistCollection.from_list(
            [{"name": "Boa"}, {"name": "   "}, "lixo", {"favorites_only": True}]
        )

        self.assertEqual([rule.name for rule in collection.rules], ["Boa"])

    def test_collection_round_trips_through_settings(self):
        settings = AppSettings(
            smart_library_smart_playlists=[
                {"name": "Favoritas", "favorites_only": True, "limit": 40},
                {"name": "", "favorites_only": True},
            ]
        )

        restored = AppSettings.from_dict(settings.to_dict())

        self.assertEqual(len(restored.smart_library_smart_playlists), 1)
        self.assertEqual(restored.smart_library_smart_playlists[0]["name"], "Favoritas")
        self.assertEqual(restored.smart_library_smart_playlists[0]["limit"], 40)


class SmartPlaylistStoreTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

        self.database = SmartLibraryDatabase(os.path.join(self._temp_dir.name, "library.db"))
        self.assertTrue(self.database.open())
        self.addCleanup(self.database.close)

        self.records = MediaRecordStore(self.database)
        self.ratings = RatingStore(self.database, self.records)
        self.history = HistoryStore(self.database, self.records)
        self.playlists = SmartPlaylistStore(self.database)

        self.now = int(time.time())
        self.rock = self.media_path("Rock", "Estrada.mp3")
        self.pop = self.media_path("Pop", "Cancao.mp3")
        self.forgotten = self.media_path("Rock", "Antiga.mp3")
        self.remote = "https://www.youtube.com/watch?v=abc123"

        self.records.register_many(
            [
                (self.rock, "Estrada"),
                (self.pop, "Canção"),
                (self.forgotten, "Antiga"),
                (self.remote, "Remota"),
            ]
        )

    def media_path(self, *parts):
        return os.path.join(self._temp_dir.name, *parts)

    def set_play_state(self, media_path, play_count, days_ago):
        self.database.execute(
            "UPDATE media SET play_count = ?, last_played_epoch = ? WHERE path_key = ?",
            (play_count, self.now - days_ago * DAY_SECONDS, _key(media_path)),
        )

    # ------------------------------------------------------------------
    def test_an_empty_rule_returns_local_media(self):
        results = self.playlists.query(SmartPlaylistRule(name="Tudo"))

        self.assertEqual(len(results), 3)

    def test_remote_media_can_be_included(self):
        results = self.playlists.query(SmartPlaylistRule(name="Tudo", exclude_remote=False))

        self.assertEqual(len(results), 4)

    def test_favorites_only_filters_the_list(self):
        self.ratings.set_favorite(self.rock, True)

        results = self.playlists.query(SmartPlaylistRule(name="Favs", favorites_only=True))

        self.assertEqual([record.display_label for record in results], ["Estrada"])

    def test_minimum_rating_filters_the_list(self):
        self.ratings.set_rating(self.rock, 5)
        self.ratings.set_rating(self.pop, 3)

        results = self.playlists.query(SmartPlaylistRule(name="Top", minimum_rating=4))

        self.assertEqual([record.display_label for record in results], ["Estrada"])

    def test_folder_filter_includes_subfolders(self):
        nested = self.media_path("Rock", "Ao Vivo", "Show.mp3")
        self.records.register(nested, label="Show")

        results = self.playlists.query(
            SmartPlaylistRule(name="Rock", folder_path=self.media_path("Rock"))
        )

        self.assertEqual(
            sorted(record.display_label for record in results),
            ["Antiga", "Estrada", "Show"],
        )

    def test_folder_filter_ignores_case(self):
        results = self.playlists.query(
            SmartPlaylistRule(name="Rock", folder_path=self.media_path("ROCK"))
        )

        self.assertEqual(len(results), 2)

    def test_folder_filter_does_not_include_a_sibling_with_the_same_prefix(self):
        sibling = self.media_path("Rock antigo", "Demo.mp3")
        self.records.register(sibling, label="Demo")

        results = self.playlists.query(
            SmartPlaylistRule(name="Rock", folder_path=self.media_path("Rock"))
        )

        self.assertNotIn("Demo", [record.display_label for record in results])

    def test_not_played_for_days_includes_never_played_by_default(self):
        self.set_play_state(self.rock, play_count=4, days_ago=1)
        self.set_play_state(self.pop, play_count=2, days_ago=90)

        results = self.playlists.query(
            SmartPlaylistRule(name="Esquecidas", not_played_for_days=30),
            now_epoch=self.now,
        )

        self.assertEqual(
            sorted(record.display_label for record in results),
            ["Antiga", "Canção"],
        )

    def test_never_played_media_can_be_excluded(self):
        self.set_play_state(self.pop, play_count=2, days_ago=90)

        results = self.playlists.query(
            SmartPlaylistRule(name="Esquecidas", not_played_for_days=30, include_never_played=False),
            now_epoch=self.now,
        )

        self.assertEqual([record.display_label for record in results], ["Canção"])

    def test_excluding_never_played_works_without_a_day_filter(self):
        self.set_play_state(self.rock, play_count=1, days_ago=2)

        results = self.playlists.query(
            SmartPlaylistRule(name="Já tocadas", include_never_played=False)
        )

        self.assertEqual([record.display_label for record in results], ["Estrada"])

    def test_minimum_play_count_filters_the_list(self):
        self.set_play_state(self.rock, play_count=9, days_ago=1)
        self.set_play_state(self.pop, play_count=2, days_ago=1)

        results = self.playlists.query(SmartPlaylistRule(name="Batidas", minimum_play_count=5))

        self.assertEqual([record.display_label for record in results], ["Estrada"])

    def test_sort_orders_change_the_result_order(self):
        self.set_play_state(self.rock, play_count=9, days_ago=10)
        self.set_play_state(self.pop, play_count=2, days_ago=1)
        self.set_play_state(self.forgotten, play_count=1, days_ago=40)
        self.ratings.set_rating(self.forgotten, 5)

        by_plays = self.playlists.query(SmartPlaylistRule(name="x", sort_order=SORT_MOST_PLAYED))
        by_oldest = self.playlists.query(
            SmartPlaylistRule(name="x", sort_order=SORT_LEAST_RECENTLY_PLAYED)
        )
        by_rating = self.playlists.query(SmartPlaylistRule(name="x", sort_order=SORT_HIGHEST_RATED))
        by_title = self.playlists.query(SmartPlaylistRule(name="x", sort_order=SORT_TITLE))

        self.assertEqual(by_plays[0].display_label, "Estrada")
        self.assertEqual(by_oldest[0].display_label, "Antiga")
        self.assertEqual(by_rating[0].display_label, "Antiga")
        self.assertEqual([record.display_label for record in by_title], ["Antiga", "Canção", "Estrada"])

    def test_limit_caps_the_result_list(self):
        results = self.playlists.query(SmartPlaylistRule(name="x", limit=2))

        self.assertEqual(len(results), 2)

    def test_a_missing_rule_returns_nothing(self):
        self.assertEqual(self.playlists.query(None), [])


def _key(media_path):
    from player.smart_library.models import media_path_key

    return media_path_key(media_path)


if __name__ == "__main__":
    unittest.main()
