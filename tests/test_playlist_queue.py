from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.playlists.models import PlaylistState


def _state(paths):
    state = PlaylistState(title="Teste")
    state.set_items(list(paths), start_index=0)
    return state


class PlaylistQueueTests(unittest.TestCase):
    def test_enqueue_plays_before_sequential_next(self):
        state = _state(["A", "B", "C", "D"])
        # Tocando A; enfileira D.
        self.assertTrue(state.enqueue_item("D"))
        # Próxima deve ser a enfileirada (D), não a sequencial (B).
        self.assertEqual(state.move_next(), "D")
        # Fila esvaziada: volta ao fluxo sequencial a partir de D.
        self.assertEqual(state.peek_in_playback_order(1), None)

    def test_queue_survives_item_removal_by_resolving_path(self):
        state = _state(["A", "B", "C", "D", "E"])
        self.assertTrue(state.enqueue_item("D"))
        # Remove A: os índices deslocam, mas a fila guarda o caminho.
        state.items.pop(0)
        state.refresh_browser_item_labels()
        state.current_index = 0
        state.current_media_path = state.items[0]
        self.assertEqual(state.move_next(), "D")

    def test_queue_survives_reorder(self):
        state = _state(["A", "B", "C", "D"])
        self.assertTrue(state.enqueue_item("D"))
        # Move D para o topo (pop + insert), como faz _move_current_item.
        moved = state.items.pop(3)
        state.items.insert(0, moved)
        state.refresh_browser_item_labels()
        self.assertEqual(state.move_next(), "D")

    def test_enqueue_is_deduplicated(self):
        state = _state(["A", "B", "C"])
        self.assertTrue(state.enqueue_item("C"))
        self.assertFalse(state.enqueue_item("C"))
        self.assertEqual(state.custom_queue, ["C"])

    def test_enqueue_new_path_appends_to_playlist(self):
        state = _state(["A", "B"])
        self.assertTrue(state.enqueue_item("Z"))
        self.assertIn("Z", state.items)
        self.assertEqual(state.move_next(), "Z")

    def test_clear_queue_reports_state(self):
        state = _state(["A", "B", "C"])
        state.enqueue_item("C")
        self.assertTrue(state.clear_queue())
        self.assertEqual(state.custom_queue, [])
        self.assertFalse(state.clear_queue())

    def test_persistence_round_trip_keeps_paths_and_drops_stale(self):
        state = _state(["A", "B", "C"])
        state.enqueue_item("C")
        payload = state.to_dict()
        self.assertEqual(payload["custom_queue"], ["C"])
        # Simula uma sessão salva com um caminho que não existe mais.
        payload["custom_queue"] = ["C", "GHOST"]
        restored = PlaylistState.from_dict(payload)
        self.assertEqual(restored.custom_queue, ["C"])

    def test_queue_paths_prunes_stale_entries(self):
        state = _state(["A", "B", "C"])
        state.enqueue_item("B")
        state.enqueue_item("C")
        # B some da playlist sem passar pela API da fila.
        state.items.remove("B")
        state.refresh_browser_item_labels()
        self.assertEqual(state.queue_paths(), ["C"])
        self.assertEqual(state.custom_queue, ["C"])

    def test_remove_queue_entry(self):
        state = _state(["A", "B", "C"])
        state.enqueue_item("B")
        state.enqueue_item("C")
        self.assertEqual(state.remove_queue_entry(0), "B")
        self.assertEqual(state.custom_queue, ["C"])
        self.assertIsNone(state.remove_queue_entry(5))

    def test_dequeue_item_toggles_off(self):
        state = _state(["A", "B", "C"])
        state.enqueue_item("B")
        self.assertTrue(state.is_queued("B"))
        self.assertTrue(state.dequeue_item("B"))
        self.assertFalse(state.is_queued("B"))
        self.assertEqual(state.custom_queue, [])
        # Remover algo que não está na fila é no-op.
        self.assertFalse(state.dequeue_item("B"))

    def test_move_queue_entry(self):
        state = _state(["A", "B", "C", "D"])
        state.enqueue_item("B")
        state.enqueue_item("C")
        state.enqueue_item("D")
        # Desce o primeiro (B) para a posição 1.
        self.assertEqual(state.move_queue_entry(0, 1), 1)
        self.assertEqual(state.custom_queue, ["C", "B", "D"])
        # Sobe o último (D) para a posição 1.
        self.assertEqual(state.move_queue_entry(2, -1), 1)
        self.assertEqual(state.custom_queue, ["C", "D", "B"])
        # Fora dos limites não faz nada.
        self.assertIsNone(state.move_queue_entry(0, -1))
        self.assertIsNone(state.move_queue_entry(2, 1))

    def test_enqueue_does_not_reshuffle_remaining_order(self):
        state = _state(["A", "B", "C", "D"])
        state.shuffle_enabled = True
        state.reset_playback_order(preferred_index=0)
        order_before = list(state.playback_order)
        # Enfileira um item novo (força append) e confere que a ordem existente
        # é preservada, apenas estendida com o novo índice.
        state.enqueue_item("Z")
        self.assertEqual(state.playback_order[: len(order_before)], order_before)
        self.assertEqual(len(state.playback_order), len(state.items))


if __name__ == "__main__":
    unittest.main()
