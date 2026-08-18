from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.smart_library.database import SmartLibraryDatabase
from player.smart_library.history import HistoryStore
from player.smart_library.metadata_cache import (
    NAMESPACE_AUDIO_ANALYSIS,
    NAMESPACE_MEDIA_METADATA,
    MetadataCache,
    file_fingerprint,
)
from player.smart_library.models import (
    SEARCH_SCOPE_FAVORITES,
    SEARCH_SCOPE_HISTORY,
    build_search_text,
    clamp_rating,
    media_path_key,
)
from player.smart_library.ratings import RatingStore
from player.smart_library.records import MediaRecordStore
from player.smart_library.resume import ResumeStore
from player.smart_library.search import (
    MediaSearchStore,
    build_full_text_query,
    escape_like,
    search_terms,
)


class SmartLibraryStoreTestCase(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

        self.database = SmartLibraryDatabase(os.path.join(self._temp_dir.name, "library.db"))
        self.assertTrue(self.database.open())
        self.addCleanup(self.database.close)

        self.records = MediaRecordStore(self.database)
        self.search = MediaSearchStore(self.database)
        self.ratings = RatingStore(self.database, self.records)
        self.resume = ResumeStore(self.database, self.records)
        self.history = HistoryStore(self.database, self.records)
        self.cache = MetadataCache(self.database)

    def media_path(self, *parts):
        return os.path.join(self._temp_dir.name, *parts)


class SmartLibraryDatabaseTests(SmartLibraryStoreTestCase):
    def test_transaction_rolls_back_every_statement_when_one_fails(self):
        path = self.media_path("faixa.mp3")

        succeeded = self.database.execute_transaction(
            (
                (
                    "INSERT INTO media (path_key, media_path) VALUES (?, ?)",
                    (media_path_key(path), path),
                ),
                ("INSERT INTO table_that_does_not_exist VALUES (?)", (1,)),
            )
        )

        self.assertFalse(succeeded)
        self.assertEqual(self.database.query_one("SELECT id FROM media WHERE path_key = ?", (media_path_key(path),)), None)


class MediaPathKeyTests(unittest.TestCase):
    def test_local_paths_normalize_case_and_separators(self):
        first = media_path_key("C:\\Musica\\Canção.mp3")
        second = media_path_key("c:/musica/./Canção.mp3")

        self.assertEqual(first, second)

    def test_remote_paths_keep_their_shape(self):
        key = media_path_key("https://www.youtube.com/watch?v=Abc123")

        self.assertEqual(key, "https://www.youtube.com/watch?v=abc123")

    def test_blank_path_has_no_key(self):
        self.assertEqual(media_path_key("   "), "")

    def test_search_text_folds_accents_and_includes_folder(self):
        search_text = build_search_text("Canção Bonita", os.path.join("C:", "Sertanejo", "faixa.mp3"))

        self.assertIn("cancao bonita", search_text)
        self.assertIn("sertanejo", search_text)

    def test_search_terms_drop_duplicates_and_accents(self):
        self.assertEqual(search_terms("Ção  ção  bonita"), ["cao", "bonita"])

    def test_the_full_text_query_requires_every_term_as_a_prefix(self):
        self.assertEqual(build_full_text_query(["estrada", "rock"]), '"estrada"* AND "rock"*')

    def test_the_full_text_query_strips_operator_characters(self):
        self.assertEqual(build_full_text_query(["-estrada*"]), '"estrada"*')
        self.assertEqual(build_full_text_query(['"', "^:"]), "")

    def test_like_escaping_neutralizes_wildcards(self):
        self.assertEqual(escape_like("100%_a\\b"), "100\\%\\_a\\\\b")

    def test_rating_is_clamped_to_the_supported_range(self):
        self.assertEqual(clamp_rating(9), 5)
        self.assertEqual(clamp_rating(-3), 0)
        self.assertEqual(clamp_rating("bolacha"), 0)


class MediaRecordStoreTests(SmartLibraryStoreTestCase):
    def test_registering_twice_keeps_a_single_row(self):
        path = self.media_path("faixa.mp3")

        first_id = self.records.register(path, label="Faixa")
        second_id = self.records.register(path, label="Faixa renomeada")

        self.assertIsNotNone(first_id)
        self.assertEqual(first_id, second_id)
        self.assertEqual(self.records.count(), 1)
        self.assertEqual(self.records.get(path).label, "Faixa renomeada")

    def test_reregistering_without_duration_keeps_the_measured_one(self):
        path = self.media_path("podcast.mp3")
        self.records.register(path, label="Podcast", duration_ms=3600000)

        self.records.register(path, label="Podcast")

        self.assertEqual(self.records.get(path).duration_ms, 3600000)

    def test_registering_preserves_favorite_and_rating(self):
        path = self.media_path("favorita.mp3")
        self.records.register(path, label="Favorita")
        self.ratings.set_favorite(path, True)
        self.ratings.set_rating(path, 4)

        self.records.register(path, label="Favorita")

        record = self.records.get(path)
        self.assertTrue(record.favorite)
        self.assertEqual(record.rating, 4)

    def test_register_many_indexes_a_batch(self):
        entries = [(self.media_path(f"faixa{index}.mp3"), f"Faixa {index}") for index in range(5)]

        indexed = self.records.register_many(entries)

        self.assertEqual(indexed, 5)
        self.assertEqual(self.records.count(), 5)

    def test_blank_paths_are_ignored(self):
        self.assertIsNone(self.records.register("   "))
        self.assertEqual(self.records.count(), 0)

    def test_get_many_returns_a_map_keyed_by_normalized_path(self):
        first = self.media_path("uma.mp3")
        second = self.media_path("outra.mp3")
        self.records.register_many([(first, "Uma"), (second, "Outra")])

        records = self.records.get_many([first, second, self.media_path("ausente.mp3")])

        self.assertEqual(len(records), 2)
        self.assertIn(media_path_key(first), records)

    def test_remote_media_does_not_count_as_a_folder(self):
        self.records.register("https://www.youtube.com/watch?v=abc123", label="Remota")
        self.records.register(self.media_path("Rock", "Estrada.mp3"), label="Estrada")

        self.assertEqual(self.records.count(), 2)
        self.assertEqual(self.records.folder_count(), 1)

    def test_forget_missing_drops_files_that_are_gone(self):
        present = self.media_path("presente.mp3")
        pathlib.Path(present).write_text("x", encoding="utf-8")
        missing = self.media_path("sumiu.mp3")
        self.records.register_many([(present, "Presente"), (missing, "Sumiu")])

        removed = self.records.forget_missing(os.path.isfile)

        self.assertEqual(removed, 1)
        self.assertEqual(self.records.count(), 1)


class RatingStoreTests(SmartLibraryStoreTestCase):
    def test_toggling_a_favorite_registers_an_unknown_media(self):
        path = self.media_path("nova.mp3")

        self.assertTrue(self.ratings.toggle_favorite(path, label="Nova"))

        self.assertTrue(self.ratings.is_favorite(path))
        self.assertEqual(self.records.count(), 1)

    def test_toggling_twice_returns_to_the_original_state(self):
        path = self.media_path("nova.mp3")
        self.ratings.toggle_favorite(path)

        self.assertFalse(self.ratings.toggle_favorite(path))
        self.assertFalse(self.ratings.is_favorite(path))

    def test_ratings_are_clamped_when_stored(self):
        path = self.media_path("avaliada.mp3")

        self.ratings.set_rating(path, 42)

        self.assertEqual(self.ratings.get_rating(path), 5)

    def test_favorite_count_reflects_marked_media(self):
        for index in range(3):
            self.ratings.set_favorite(self.media_path(f"f{index}.mp3"), True)

        self.assertEqual(self.ratings.favorite_count(), 3)

    def test_a_write_failure_is_reported(self):
        path = self.media_path("faixa.mp3")
        self.records.register(path)
        self.database.close()

        self.assertFalse(self.ratings.set_favorite(path, True))
        self.assertFalse(self.ratings.set_rating(path, 4))


class MediaSearchStoreTests(SmartLibraryStoreTestCase):
    def setUp(self):
        super().setUp()
        self.records.register(self.media_path("Sertanejo", "Canção Bonita.mp3"), label="Canção Bonita")
        self.records.register(self.media_path("Rock", "Estrada.mp3"), label="Estrada")
        self.records.register(self.media_path("Rock", "Outra Estrada.mp3"), label="Outra Estrada")

    def test_search_ignores_accents_and_case(self):
        results = self.search.search("cancao")

        self.assertEqual([record.label for record in results], ["Canção Bonita"])

    def test_search_matches_the_containing_folder(self):
        results = self.search.search("rock")

        self.assertEqual(len(results), 2)

    def test_every_term_must_match(self):
        self.assertEqual(len(self.search.search("outra estrada")), 1)
        self.assertEqual(len(self.search.search("outra sertanejo")), 0)

    def test_an_empty_query_without_a_filter_returns_nothing(self):
        self.assertEqual(self.search.search("   "), [])

    def test_favorites_filter_works_without_a_query(self):
        favorite_path = self.media_path("Rock", "Estrada.mp3")
        self.ratings.set_favorite(favorite_path, True)

        results = self.search.search("", scope=SEARCH_SCOPE_FAVORITES)

        self.assertEqual([record.label for record in results], ["Estrada"])

    def test_history_filter_only_lists_played_media(self):
        played_path = self.media_path("Rock", "Estrada.mp3")
        self.history.record(played_path, label="Estrada")

        results = self.search.search("", scope=SEARCH_SCOPE_HISTORY)

        self.assertEqual([record.label for record in results], ["Estrada"])

    def test_wildcards_in_the_query_are_treated_literally(self):
        self.assertEqual(self.search.search("%"), [])

    def test_a_word_prefix_matches(self):
        self.assertEqual([record.label for record in self.search.search("estrad")], ["Estrada", "Outra Estrada"])

    def test_a_fragment_inside_a_word_still_matches(self):
        # O índice FTS5 só cobre prefixos; achar "onita" no meio de "Bonita"
        # é o que a varredura de reserva garante.
        self.assertEqual([record.label for record in self.search.search("onita")], ["Canção Bonita"])

    def test_full_text_operators_are_not_interpreted(self):
        # "OR" precisa ser tratado como mais um termo obrigatório, não como o
        # operador do FTS5 — caso contrário a busca devolveria itens demais.
        self.assertEqual(self.search.search("estrada OR cancao"), [])

    def test_a_lone_quote_finds_nothing_instead_of_failing(self):
        self.assertEqual(self.search.search('"'), [])

    def test_the_index_is_rebuilt_for_a_database_created_without_it(self):
        # Simula um banco da versão anterior: o índice some, mas as linhas de
        # `media` continuam lá e precisam voltar a ser encontráveis.
        self.database.execute("DROP TABLE media_fts")
        self.assertTrue(self.database._prepare_full_text_search())

        self.assertEqual([record.label for record in self.search.search("estrad")], ["Estrada", "Outra Estrada"])

    def test_limit_caps_the_result_list(self):
        self.assertEqual(len(self.search.search("mp3")), 3)
        self.assertEqual(len(self.search.search("mp3", limit=2)), 2)


class HistoryStoreTests(SmartLibraryStoreTestCase):
    def test_recording_creates_an_entry_and_counts_the_play(self):
        path = self.media_path("faixa.mp3")

        self.assertTrue(self.history.record(path, label="Faixa", position_ms=45000, duration_ms=180000))

        entries = self.history.recent()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].display_label, "Faixa")
        self.assertEqual(entries[0].position_ms, 45000)
        self.assertEqual(self.records.get(path).play_count, 1)

    def test_history_is_trimmed_to_the_configured_limit(self):
        for index in range(8):
            self.history.record(self.media_path(f"faixa{index}.mp3"), label=f"Faixa {index}", limit=3)

        self.assertEqual(self.history.count(), 3)

    def test_recent_can_be_filtered_by_text(self):
        self.history.record(self.media_path("Canção.mp3"), label="Canção")
        self.history.record(self.media_path("Estrada.mp3"), label="Estrada")

        entries = self.history.recent(query="cancao")

        self.assertEqual([entry.display_label for entry in entries], ["Canção"])

    def test_the_history_filter_treats_wildcards_literally(self):
        self.history.record(self.media_path("faixa.mp3"), label="Faixa")

        self.assertEqual(self.history.recent(query="%"), [])

    def test_removing_an_entry_leaves_the_media_indexed(self):
        self.history.record(self.media_path("faixa.mp3"), label="Faixa")
        entry_id = self.history.recent()[0].entry_id

        self.assertTrue(self.history.remove(entry_id))

        self.assertEqual(self.history.count(), 0)
        self.assertEqual(self.records.count(), 1)

    def test_grouped_history_collapses_repeated_plays(self):
        path = self.media_path("faixa.mp3")
        for _ in range(4):
            self.history.record(path, label="Faixa")
        self.history.record(self.media_path("outra.mp3"), label="Outra")

        grouped = self.history.grouped()

        self.assertEqual(len(grouped), 2)
        by_label = {entry.display_label: entry.play_count for entry in grouped}
        self.assertEqual(by_label["Faixa"], 4)
        self.assertEqual(by_label["Outra"], 1)

    def test_most_played_orders_by_play_count(self):
        rarely = self.media_path("rara.mp3")
        often = self.media_path("comum.mp3")
        self.history.record(rarely, label="Rara")
        for _ in range(3):
            self.history.record(often, label="Comum")

        most_played = self.history.most_played()

        self.assertEqual([entry.display_label for entry in most_played], ["Comum", "Rara"])

    def test_grouped_history_respects_the_text_filter(self):
        self.history.record(self.media_path("Canção.mp3"), label="Canção")
        self.history.record(self.media_path("Estrada.mp3"), label="Estrada")

        self.assertEqual([entry.display_label for entry in self.history.grouped(query="cancao")], ["Canção"])

    def test_removing_every_play_of_a_media_empties_its_group(self):
        path = self.media_path("faixa.mp3")
        for _ in range(3):
            self.history.record(path, label="Faixa")

        self.assertTrue(self.history.remove_media_entries(path))

        self.assertEqual(self.history.count(), 0)
        self.assertEqual(self.records.count(), 1)

    def test_media_count_reports_distinct_media(self):
        path = self.media_path("faixa.mp3")
        for _ in range(3):
            self.history.record(path, label="Faixa")

        self.assertEqual(self.history.count(), 3)
        self.assertEqual(self.history.media_count(), 1)

    def test_clearing_history_resets_the_play_counters(self):
        path = self.media_path("faixa.mp3")
        self.history.record(path, label="Faixa")

        self.history.clear()

        self.assertEqual(self.history.count(), 0)
        self.assertEqual(self.records.get(path).play_count, 0)
        self.assertEqual(self.records.get(path).last_played_epoch, 0)


class ResumeStoreTests(SmartLibraryStoreTestCase):
    RESUME_RULES = {"minimum_duration_ms": 600000, "ignore_edges_ms": 30000}

    def test_short_media_never_gets_a_resume_point(self):
        self.assertFalse(
            self.resume.should_remember(120000, 180000, **self.RESUME_RULES)
        )

    def test_the_opening_margin_is_ignored(self):
        self.assertFalse(
            self.resume.should_remember(15000, 3600000, **self.RESUME_RULES)
        )

    def test_the_closing_margin_is_ignored(self):
        self.assertFalse(
            self.resume.should_remember(3595000, 3600000, **self.RESUME_RULES)
        )

    def test_the_middle_of_a_long_media_is_remembered(self):
        self.assertTrue(
            self.resume.should_remember(1800000, 3600000, **self.RESUME_RULES)
        )

    def test_an_unknown_duration_is_not_remembered(self):
        self.assertFalse(self.resume.should_remember(1800000, 0, **self.RESUME_RULES))

    def test_remembering_stores_and_reads_the_position(self):
        path = self.media_path("audiolivro.m4b")

        self.assertTrue(self.resume.remember(path, 1800000, duration_ms=3600000, label="Audiolivro"))

        self.assertEqual(self.resume.get_position_ms(path), 1800000)
        self.assertEqual(self.records.get(path).duration_ms, 3600000)

    def test_forgetting_clears_the_position(self):
        path = self.media_path("audiolivro.m4b")
        self.resume.remember(path, 1800000, duration_ms=3600000)

        self.resume.forget(path)

        self.assertEqual(self.resume.get_position_ms(path), 0)

    def test_unknown_media_has_no_saved_position(self):
        self.assertEqual(self.resume.get_position_ms(self.media_path("nunca.mp3")), 0)

    def test_pending_lists_only_what_is_half_finished(self):
        started = self.media_path("episodio.mp3")
        finished = self.media_path("terminado.mp3")
        self.resume.remember(started, 1800000, duration_ms=3600000, label="Episódio")
        self.records.register(finished, label="Terminado")

        pending = self.resume.pending()

        self.assertEqual([record.display_label for record in pending], ["Episódio"])

    def test_pending_puts_the_most_recent_first(self):
        first = self.media_path("primeiro.mp3")
        second = self.media_path("segundo.mp3")
        self.resume.remember(first, 60000, duration_ms=3600000, label="Primeiro")
        self.database.execute(
            "UPDATE media SET resume_updated_epoch = 1000 WHERE label = 'Primeiro'"
        )
        self.resume.remember(second, 60000, duration_ms=3600000, label="Segundo")

        self.assertEqual(
            [record.display_label for record in self.resume.pending()],
            ["Segundo", "Primeiro"],
        )

    def test_forgetting_removes_it_from_pending(self):
        path = self.media_path("episodio.mp3")
        self.resume.remember(path, 1800000, duration_ms=3600000, label="Episódio")

        self.resume.forget(path)

        self.assertEqual(self.resume.pending(), [])


class MetadataCacheTests(SmartLibraryStoreTestCase):
    def _existing_file(self, name="faixa.mp3"):
        path = self.media_path(name)
        pathlib.Path(path).write_text("conteudo", encoding="utf-8")
        return path

    def test_payload_round_trips(self):
        path = self._existing_file()

        self.assertTrue(self.cache.store(NAMESPACE_MEDIA_METADATA, path, {"title": "Canção"}))

        self.assertEqual(self.cache.get(NAMESPACE_MEDIA_METADATA, path), {"title": "Canção"})

    def test_namespaces_do_not_collide(self):
        path = self._existing_file()
        self.cache.store(NAMESPACE_MEDIA_METADATA, path, {"title": "Canção"})
        self.cache.store(NAMESPACE_AUDIO_ANALYSIS, path, {"bpm": 128})

        self.assertEqual(self.cache.get(NAMESPACE_AUDIO_ANALYSIS, path), {"bpm": 128})
        self.assertEqual(self.cache.count(), 2)

    def test_a_changed_file_invalidates_the_entry(self):
        path = self._existing_file()
        self.cache.store(NAMESPACE_AUDIO_ANALYSIS, path, {"bpm": 128})

        pathlib.Path(path).write_text("outro conteudo bem maior", encoding="utf-8")

        self.assertIsNone(self.cache.get(NAMESPACE_AUDIO_ANALYSIS, path))

    def test_an_explicit_fingerprint_is_honored(self):
        path = self._existing_file()
        self.cache.store(NAMESPACE_AUDIO_ANALYSIS, path, {"bpm": 128}, fingerprint="v1")

        self.assertEqual(self.cache.get(NAMESPACE_AUDIO_ANALYSIS, path, fingerprint="v1"), {"bpm": 128})
        self.assertIsNone(self.cache.get(NAMESPACE_AUDIO_ANALYSIS, path, fingerprint="v2"))

    def test_remote_media_uses_a_stable_fingerprint(self):
        self.assertEqual(file_fingerprint("https://example.com/stream"), "remote")

    def test_a_missing_file_has_no_fingerprint(self):
        self.assertEqual(file_fingerprint(self.media_path("ausente.mp3")), "")

    def test_trimming_keeps_only_the_newest_entries(self):
        for index in range(6):
            path = self._existing_file(f"faixa{index}.mp3")
            self.cache.store(NAMESPACE_AUDIO_ANALYSIS, path, {"bpm": index}, limit=3)

        self.assertEqual(self.cache.count(), 3)

    def test_non_serializable_payloads_are_refused(self):
        path = self._existing_file()

        self.assertFalse(self.cache.store(NAMESPACE_AUDIO_ANALYSIS, path, {"handle": object()}))

    def test_clearing_a_namespace_leaves_the_others(self):
        path = self._existing_file()
        self.cache.store(NAMESPACE_MEDIA_METADATA, path, {"title": "Canção"})
        self.cache.store(NAMESPACE_AUDIO_ANALYSIS, path, {"bpm": 128})

        self.cache.clear(NAMESPACE_AUDIO_ANALYSIS)

        self.assertEqual(self.cache.count(NAMESPACE_MEDIA_METADATA), 1)
        self.assertEqual(self.cache.count(NAMESPACE_AUDIO_ANALYSIS), 0)


class ClosedDatabaseTests(unittest.TestCase):
    """Um banco fechado nunca deve estourar: só devolve resultados vazios."""

    def setUp(self):
        self.database = SmartLibraryDatabase(os.path.join(tempfile.gettempdir(), "unused.db"))
        self.records = MediaRecordStore(self.database)
        self.search = MediaSearchStore(self.database)

    def test_writes_are_inert(self):
        self.assertIsNone(self.records.register("C:\\faixa.mp3"))

    def test_reads_return_empty_results(self):
        self.assertEqual(self.records.count(), 0)
        self.assertEqual(self.search.search("faixa"), [])
        self.assertIsNone(self.records.get("C:\\faixa.mp3"))


if __name__ == "__main__":
    unittest.main()
