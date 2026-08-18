from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import threading
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.smart_library.metadata_cache import NAMESPACE_AUDIO_ANALYSIS
from player.smart_library.models import SEARCH_SCOPE_FAVORITES
from player.smart_library.service import SmartLibraryService


class SmartLibraryServiceTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

        self.service = SmartLibraryService(os.path.join(self._temp_dir.name, "library.db"))
        self.addCleanup(self.service.close)

    def media_path(self, *parts):
        return os.path.join(self._temp_dir.name, *parts)

    def drain(self):
        """Espera a fila da thread de trabalho esvaziar antes de conferir."""
        done = threading.Event()
        self.assertTrue(self.service._submit(done.set))
        self.assertTrue(done.wait(timeout=5), "smart library worker did not drain")

    def write_media(self, relative_path):
        full_path = self.media_path(*relative_path)
        pathlib.Path(os.path.dirname(full_path)).mkdir(parents=True, exist_ok=True)
        pathlib.Path(full_path).write_text("conteudo", encoding="utf-8")
        return full_path

    # ------------------------------------------------------------------
    def test_service_opens_its_database(self):
        self.assertTrue(self.service.is_available)

    def test_registering_media_makes_it_searchable(self):
        path = self.write_media(("Rock", "Estrada.mp3"))

        self.service.register_media(path, label="Estrada")
        self.drain()

        results = self.service.search("estrada")
        self.assertEqual([record.display_label for record in results], ["Estrada"])

    def test_indexing_a_folder_walks_subfolders(self):
        self.write_media(("Musica", "Rock", "Estrada.mp3"))
        self.write_media(("Musica", "Sertanejo", "Canção.mp3"))
        self.write_media(("Musica", "leiame.txt"))

        finished = threading.Event()
        summaries = []

        def on_finished(summary):
            summaries.append(summary)
            finished.set()

        self.service.index_folder(self.media_path("Musica"), on_finished=on_finished)
        self.assertTrue(finished.wait(timeout=5))

        self.assertFalse(summaries[0].failed)
        self.assertEqual(summaries[0].indexed_files, 2)
        self.assertEqual(len(self.service.search("musica")), 2)

    def test_indexing_a_missing_folder_reports_failure(self):
        finished = threading.Event()
        summaries = []

        self.service.index_folder(
            self.media_path("NaoExiste"),
            on_finished=lambda summary: (summaries.append(summary), finished.set()),
        )
        self.assertTrue(finished.wait(timeout=5))

        self.assertTrue(summaries[0].failed)

    def test_favorites_are_stored_and_listed(self):
        path = self.write_media(("Rock", "Estrada.mp3"))

        self.assertTrue(self.service.toggle_favorite(path, label="Estrada"))

        self.assertTrue(self.service.is_favorite(path))
        self.assertEqual(len(self.service.search("", scope=SEARCH_SCOPE_FAVORITES)), 1)
        self.assertEqual([record.display_label for record in self.service.favorites()], ["Estrada"])

    def test_ratings_are_stored_and_listed(self):
        path = self.write_media(("Rock", "Estrada.mp3"))

        self.assertTrue(self.service.set_rating(path, 4, label="Estrada"))

        self.assertEqual(self.service.get_rating(path), 4)
        self.assertEqual(len(self.service.top_rated(minimum_rating=4)), 1)
        self.assertEqual(len(self.service.top_rated(minimum_rating=5)), 0)

    def test_playback_is_recorded_in_the_history(self):
        path = self.write_media(("Rock", "Estrada.mp3"))

        self.service.record_playback(path, label="Estrada", position_ms=60000, duration_ms=240000)
        self.drain()

        entries = self.service.recent_history()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].display_label, "Estrada")

    def test_resume_position_round_trips(self):
        path = self.write_media(("Podcasts", "episodio.mp3"))

        self.service.remember_position(path, 1800000, duration_ms=3600000, label="Episódio")
        self.drain()

        self.assertEqual(self.service.resume_position_ms(path), 1800000)

        self.service.forget_position(path)
        self.drain()

        self.assertEqual(self.service.resume_position_ms(path), 0)

    def test_resume_rules_follow_the_configured_window(self):
        self.assertTrue(
            self.service.should_remember_position(
                1800000, 3600000, minimum_duration_ms=600000, ignore_edges_ms=30000
            )
        )
        self.assertFalse(
            self.service.should_remember_position(
                90000, 180000, minimum_duration_ms=600000, ignore_edges_ms=30000
            )
        )

    def test_cached_payload_round_trips(self):
        path = self.write_media(("Rock", "Estrada.mp3"))

        self.service.store_payload(NAMESPACE_AUDIO_ANALYSIS, path, {"bpm": 128})
        self.drain()

        self.assertEqual(self.service.cached_payload(NAMESPACE_AUDIO_ANALYSIS, path), {"bpm": 128})

    def test_statistics_summarize_the_library(self):
        first = self.write_media(("Rock", "Estrada.mp3"))
        self.write_media(("Sertanejo", "Canção.mp3"))
        self.service.register_media_batch(
            [(first, "Estrada"), (self.media_path("Sertanejo", "Canção.mp3"), "Canção")]
        )
        self.drain()
        self.service.toggle_favorite(first, label="Estrada")

        statistics = self.service.statistics()

        self.assertEqual(statistics["media"], 2)
        self.assertEqual(statistics["folders"], 2)
        self.assertEqual(statistics["favorites"], 1)

    def test_clearing_everything_empties_the_library(self):
        path = self.write_media(("Rock", "Estrada.mp3"))
        self.service.record_playback(path, label="Estrada")
        self.drain()

        self.assertTrue(self.service.clear_everything())

        self.assertEqual(self.service.statistics()["media"], 0)
        self.assertEqual(self.service.recent_history(), [])

    def test_forget_missing_media_drops_deleted_files(self):
        present = self.write_media(("Rock", "Estrada.mp3"))
        missing = self.media_path("Rock", "Sumiu.mp3")
        self.service.register_media_batch([(present, "Estrada"), (missing, "Sumiu")])
        self.drain()

        finished = threading.Event()
        removed_counts = []
        self.service.forget_missing_media(
            on_finished=lambda removed: (removed_counts.append(removed), finished.set())
        )
        self.assertTrue(finished.wait(timeout=5))

        self.assertEqual(removed_counts[0], 1)
        self.assertEqual(self.service.statistics()["media"], 1)

    def test_history_for_view_switches_between_the_three_modes(self):
        path = self.write_media(("Rock", "Estrada.mp3"))
        for _ in range(3):
            self.service.record_playback(path, label="Estrada")
        self.service.record_playback(self.write_media(("Pop", "Cancao.mp3")), label="Canção")
        self.drain()

        self.assertEqual(len(self.service.history_for_view("all")), 4)

        grouped = self.service.history_for_view("grouped")
        self.assertEqual(len(grouped), 2)

        most_played = self.service.history_for_view("most_played")
        self.assertEqual([entry.display_label for entry in most_played], ["Estrada", "Canção"])

    def test_an_unknown_history_view_returns_nothing(self):
        self.service.record_playback(self.write_media(("Rock", "Estrada.mp3")), label="Estrada")
        self.drain()

        self.assertEqual(self.service.history_for_view("inventado"), [])

    def test_removing_the_history_of_a_media_clears_its_group(self):
        path = self.write_media(("Rock", "Estrada.mp3"))
        for _ in range(3):
            self.service.record_playback(path, label="Estrada")
        self.drain()

        self.assertTrue(self.service.remove_history_for_media(path))

        self.assertEqual(self.service.history_for_view("grouped"), [])

    def test_pending_resumes_lists_what_is_half_finished(self):
        episode = self.write_media(("Podcasts", "episodio.mp3"))
        self.service.remember_position(episode, 1800000, duration_ms=3600000, label="Episódio")
        self.drain()

        pending = self.service.pending_resumes()

        self.assertEqual([record.display_label for record in pending], ["Episódio"])
        self.assertEqual(pending[0].resume_position_ms, 1800000)

    def test_smart_playlist_media_applies_the_rule(self):
        from player.smart_library.smart_playlists import SmartPlaylistRule

        favorite = self.write_media(("Rock", "Estrada.mp3"))
        self.write_media(("Pop", "Cancao.mp3"))
        self.service.register_media_batch(
            [(favorite, "Estrada"), (self.media_path("Pop", "Cancao.mp3"), "Canção")]
        )
        self.drain()
        self.service.toggle_favorite(favorite, label="Estrada")

        results = self.service.smart_playlist_media(
            SmartPlaylistRule(name="Favoritas", favorites_only=True)
        )

        self.assertEqual([record.display_label for record in results], ["Estrada"])

    def test_a_closed_service_is_inert(self):
        path = self.write_media(("Rock", "Estrada.mp3"))
        self.service.close()

        self.assertFalse(self.service.is_available)
        self.assertFalse(self.service.register_media(path))
        self.assertEqual(self.service.search("estrada"), [])
        self.assertEqual(self.service.recent_history(), [])
        self.assertEqual(self.service.resume_position_ms(path), 0)
        self.assertIsNone(self.service.toggle_favorite(path))
        self.assertEqual(self.service.statistics()["media"], 0)
        self.assertEqual(self.service.pending_resumes(), [])
        self.assertEqual(self.service.grouped_history(), [])
        self.assertEqual(self.service.history_for_view("grouped"), [])
        self.assertFalse(self.service.remove_history_for_media(path))
        self.assertEqual(self.service.smart_playlist_media(None), [])


if __name__ == "__main__":
    unittest.main()
