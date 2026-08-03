from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.item_search import FrameItemSearchMixin
from player.library.browser import normalize_search_text


NOT_FOUND = -1


class _FakeBrowser:
    def __init__(self, labels, selected=NOT_FOUND):
        self._labels = list(labels)
        self._selected = selected
        self.focused = []

    def has_searchable_items(self):
        return bool(self._labels)

    def search_labels(self):
        return list(self._labels)

    def get_selected_index(self):
        return self._selected

    def focus_search_result(self, index):
        if not 0 <= index < len(self._labels):
            return False
        self._selected = index
        self.focused.append(index)
        return True


class _SearchFrame(FrameItemSearchMixin):
    def __init__(self, browser):
        self._browser = browser
        self._item_search_query = ""
        self.announcements = []
        self.status_messages = []

    def _get_browser_panel(self):
        return self._browser

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, auto_clear_ms=6000):
        self.status_messages.append(message)


class NormalizeSearchTextTests(unittest.TestCase):
    def test_folds_accents_and_case(self):
        self.assertEqual(normalize_search_text("  Coração  "), "coracao")
        self.assertEqual(normalize_search_text("ÁGUA"), "agua")

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(normalize_search_text(""), "")
        self.assertEqual(normalize_search_text(None), "")


class ItemSearchTests(unittest.TestCase):
    def _frame(self, labels, selected=NOT_FOUND, query=""):
        frame = _SearchFrame(_FakeBrowser(labels, selected=selected))
        frame._item_search_query = query
        return frame

    def test_search_matches_substring_ignoring_accents(self):
        frame = self._frame(["Primeira faixa", "Coração valente", "Outra"], query="coracao")

        self.assertTrue(frame._run_item_search(1, include_current=True))

        self.assertEqual(frame._browser.focused, [1])
        self.assertIn("resultado 1 de 1", frame.status_messages[-1])

    def test_result_is_not_announced_because_focus_moves_to_the_item(self):
        frame = self._frame(["Rock 1", "Outro"], selected=0, query="rock")

        frame._run_item_search(1, include_current=True)

        self.assertEqual(frame.announcements, [])

    def test_first_search_keeps_current_item_when_it_matches(self):
        frame = self._frame(["Rock 1", "Rock 2", "Rock 3"], selected=1, query="rock")

        frame._run_item_search(1, include_current=True)

        self.assertEqual(frame._browser.focused, [1])
        self.assertIn("resultado 2 de 3", frame.status_messages[-1])

    def test_find_next_moves_forward_from_selection(self):
        frame = self._frame(["Rock 1", "Outro", "Rock 2"], selected=0, query="rock")

        frame._repeat_item_search(1)

        self.assertEqual(frame._browser.focused, [2])
        self.assertIn("resultado 2 de 2", frame.status_messages[-1])

    def test_find_next_wraps_and_reports_the_wrap_in_the_status_bar(self):
        frame = self._frame(["Rock 1", "Outro", "Rock 2"], selected=2, query="rock")

        frame._repeat_item_search(1)

        self.assertEqual(frame._browser.focused, [0])
        self.assertIn("voltando ao início da lista", frame.status_messages[-1])
        self.assertIn("resultado 1 de 2", frame.status_messages[-1])

    def test_find_previous_moves_backward_and_wraps(self):
        frame = self._frame(["Rock 1", "Outro", "Rock 2"], selected=0, query="rock")

        frame._repeat_item_search(-1)

        self.assertEqual(frame._browser.focused, [2])
        self.assertIn("voltando ao fim da lista", frame.status_messages[-1])

    def test_search_without_matches_announces_and_keeps_selection(self):
        frame = self._frame(["Rock 1", "Rock 2"], selected=0, query="jazz")

        self.assertFalse(frame._run_item_search(1, include_current=True))

        self.assertEqual(frame._browser.focused, [])
        self.assertIn("jazz", frame.announcements[-1])

    def test_search_without_items_announces_missing_target(self):
        frame = self._frame([], query="rock")

        self.assertFalse(frame._run_item_search(1))

        self.assertIn("Não há itens para localizar", frame.announcements[-1])

    def test_search_starts_at_list_edges_when_nothing_is_selected(self):
        frame = self._frame(["Rock 1", "Outro", "Rock 2"], selected=NOT_FOUND, query="rock")

        frame._repeat_item_search(-1)

        self.assertEqual(frame._browser.focused, [2])


if __name__ == "__main__":
    unittest.main()
