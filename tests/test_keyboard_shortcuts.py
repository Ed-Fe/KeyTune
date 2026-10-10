from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.keyboard.shortcuts import (
    RESERVED_SHORTCUTS,
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    Keymap,
    action_by_id,
    actions,
    effective_bindings,
    find_conflicts,
    format_shortcut,
    is_bare_shortcut,
    normalize_overrides,
    normalize_shortcut,
    overrides_from_bindings,
    shortcut_problem,
)


class NormalizeShortcutTests(unittest.TestCase):
    def test_orders_modifiers_and_capitalizes_keys(self):
        self.assertEqual(normalize_shortcut("shift+ctrl+p"), "Ctrl+Shift+P")
        self.assertEqual(normalize_shortcut("alt+shift+ctrl+left"), "Ctrl+Alt+Shift+Left")
        self.assertEqual(normalize_shortcut("Control+PgDn"), "Ctrl+PageDown")
        self.assertEqual(normalize_shortcut("windows+alt+f5"), "Alt+Win+F5")

    def test_punctuation_and_plus_keys(self):
        self.assertEqual(normalize_shortcut("Ctrl+."), "Ctrl+.")
        self.assertEqual(normalize_shortcut("Shift+]"), "Shift+]")
        self.assertEqual(normalize_shortcut("Ctrl++"), "Ctrl++")
        self.assertEqual(normalize_shortcut("\\"), "\\")

    def test_rejects_invalid_text(self):
        for text in ("", "Ctrl", "Ctrl+Shift", "Ctrl+P+Q", "Ctrl+Banana", None, 5):
            self.assertEqual(normalize_shortcut(text), "", text)


class ShortcutRulesTests(unittest.TestCase):
    def test_bare_shortcuts_need_the_player_surface(self):
        self.assertTrue(is_bare_shortcut("Space"))
        self.assertTrue(is_bare_shortcut("Shift+Left"))
        self.assertFalse(is_bare_shortcut("Ctrl+O"))
        self.assertFalse(is_bare_shortcut("Alt+Left"))
        self.assertFalse(is_bare_shortcut("F3"))
        self.assertFalse(is_bare_shortcut("Shift+F3"))

    def test_reserved_and_scope_problems(self):
        self.assertTrue(shortcut_problem("Tab", SCOPE_LOCAL))
        self.assertTrue(shortcut_problem("Ctrl+C", SCOPE_LOCAL))
        self.assertTrue(shortcut_problem("Win+P", SCOPE_LOCAL))
        self.assertEqual(shortcut_problem("Win+Alt+P", SCOPE_GLOBAL), "")
        self.assertTrue(shortcut_problem("Shift+P", SCOPE_GLOBAL))
        self.assertTrue(shortcut_problem("P", SCOPE_GLOBAL))
        self.assertEqual(shortcut_problem("F9", SCOPE_GLOBAL), "")
        self.assertEqual(shortcut_problem("P", SCOPE_LOCAL), "")

    def test_shortcuts_windows_keeps_for_itself_are_refused(self):
        for shortcut in ("Alt+Tab", "Alt+Shift+Tab", "Ctrl+Escape", "Ctrl+Shift+Escape", "Ctrl+Alt+Delete", "Alt+F4", "F10"):
            for scope in (SCOPE_LOCAL, SCOPE_GLOBAL):
                self.assertTrue(shortcut_problem(shortcut, scope), f"{shortcut} ({scope})")
        self.assertEqual(shortcut_problem("Ctrl+Alt+P", SCOPE_GLOBAL), "")

    def test_format_uses_readable_key_names(self):
        self.assertEqual(format_shortcut("Space"), "Espaço")
        self.assertEqual(format_shortcut("ctrl+pageup"), "Ctrl+Page Up")
        self.assertEqual(format_shortcut(""), "")


class CatalogTests(unittest.TestCase):
    def test_defaults_are_valid_unique_and_not_reserved(self):
        for scope in (SCOPE_LOCAL, SCOPE_GLOBAL):
            seen_ids = set()
            seen_shortcuts = {}
            for action in actions(scope):
                self.assertNotIn(action.action_id, seen_ids)
                seen_ids.add(action.action_id)
                if not action.default:
                    continue
                normalized = normalize_shortcut(action.default)
                self.assertEqual(normalized, action.default, action.action_id)
                self.assertEqual(shortcut_problem(normalized, scope), "", action.action_id)
                self.assertNotIn(normalized, RESERVED_SHORTCUTS)
                self.assertNotIn(normalized, seen_shortcuts, f"{action.action_id} x {seen_shortcuts.get(normalized)}")
                seen_shortcuts[normalized] = action.action_id

    def test_playlist_item_shortcuts_are_in_the_catalog(self):
        # Fora do catálogo, outro atalho os tomaria sem a tela perguntar.
        bindings = effective_bindings({}, SCOPE_LOCAL)
        expected = {"Alt+Up": "move_item_up", "Alt+Down": "move_item_down", "Alt+Home": "first_item", "Alt+End": "last_item"}
        for shortcut, action_id in expected.items():
            self.assertEqual(find_conflicts(bindings, shortcut), [action_id])

    def test_frame_handlers_exist(self):
        try:
            from player.frames.base import MediaPlayerFrame
        except ImportError as exc:  # pragma: no cover - wx ausente
            self.skipTest(f"wx indisponível: {exc}")
        for scope in (SCOPE_LOCAL, SCOPE_GLOBAL):
            for action in actions(scope):
                self.assertTrue(hasattr(MediaPlayerFrame, action.handler), action.handler)


class OverridesTests(unittest.TestCase):
    def test_normalize_drops_unknown_invalid_and_default_values(self):
        overrides = normalize_overrides(
            {
                "play_pause": "ctrl+alt+p",
                "stop": "",
                "next_track": "Ctrl+PageDown",
                "unknown": "Ctrl+J",
                "seek_forward": "Ctrl+Banana",
                "open_file": "Tab",
                "volume_up": 3,
            }
        )
        self.assertEqual(overrides, {"play_pause": "Ctrl+Alt+P", "stop": ""})
        self.assertEqual(normalize_overrides(["x"]), {})

    def test_global_overrides_require_a_modifier(self):
        self.assertEqual(normalize_overrides({"play_pause": "P"}, SCOPE_GLOBAL), {})
        self.assertEqual(normalize_overrides({"play_pause": "Win+P"}, SCOPE_GLOBAL), {"play_pause": "Win+P"})

    def test_round_trip_through_bindings(self):
        bindings = effective_bindings({"play_pause": "P"})
        self.assertEqual(bindings["play_pause"], "P")
        self.assertEqual(bindings["stop"], "Ctrl+.")
        bindings["stop"] = ""
        self.assertEqual(overrides_from_bindings(bindings), {"play_pause": "P", "stop": ""})

    def test_find_conflicts(self):
        bindings = effective_bindings({})
        self.assertEqual(find_conflicts(bindings, "ctrl+o"), ["open_file"])
        self.assertEqual(find_conflicts(bindings, "Ctrl+O", exclude="open_file"), [])
        self.assertEqual(find_conflicts(bindings, ""), [])


class KeymapTests(unittest.TestCase):
    def test_without_overrides_nothing_is_consumed(self):
        keymap = Keymap({})
        self.assertFalse(keymap.has_overrides)
        self.assertEqual(keymap.resolve("Space"), (None, False))

    def test_remapped_action_and_freed_default(self):
        keymap = Keymap({"play_pause": "P"})
        action, consumed = keymap.resolve("P")
        self.assertTrue(consumed)
        self.assertEqual(action.action_id, "play_pause")
        # O Espaço deixou de tocar ou pausar e não faz mais nada.
        self.assertEqual(keymap.resolve("Space"), (None, True))
        # Os demais atalhos padrão seguem com o tratamento fixo.
        self.assertEqual(keymap.resolve("Ctrl+O"), (None, False))

    def test_taken_default_goes_to_the_new_owner(self):
        keymap = Keymap({"play_pause": "Ctrl+T", "new_playlist": ""})
        action, consumed = keymap.resolve("Ctrl+T")
        self.assertTrue(consumed)
        self.assertEqual(action.action_id, "play_pause")
        self.assertEqual(keymap.shortcut_for("new_playlist"), "")
        self.assertEqual(keymap.shortcut_for("open_file"), "Ctrl+O")

    def test_action_lookup(self):
        self.assertEqual(action_by_id("toggle_tray", SCOPE_GLOBAL).default, "Ctrl+Alt+Shift+K")
        self.assertIsNone(action_by_id("toggle_tray", SCOPE_LOCAL))


if __name__ == "__main__":
    unittest.main()
