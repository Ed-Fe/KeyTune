import importlib.util
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from player import i18n  # noqa: E402


def _load_tool():
    spec = importlib.util.spec_from_file_location("keytune_i18n_tool", REPO_ROOT / "scripts" / "i18n.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NormalizeLanguageTests(unittest.TestCase):
    def test_exact_and_case_insensitive_match(self):
        self.assertEqual(i18n.normalize_language("pt_BR"), "pt_BR")
        self.assertEqual(i18n.normalize_language("pt-br"), "pt_BR")
        self.assertEqual(i18n.normalize_language("en"), "en")

    def test_prefix_match(self):
        self.assertEqual(i18n.normalize_language("en_US"), "en")
        self.assertEqual(i18n.normalize_language("pt_PT"), "pt_BR")

    def test_unknown_falls_back_to_source(self):
        self.assertEqual(i18n.normalize_language("xx_YY"), i18n.SOURCE_LANGUAGE)
        self.assertEqual(i18n.normalize_language(""), i18n.SOURCE_LANGUAGE)
        self.assertEqual(i18n.normalize_language(None), i18n.SOURCE_LANGUAGE)


class DetectSystemLanguageTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {
            key: os.environ.get(key) for key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
        }
        for key in self._saved_env:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_env_variable_drives_detection(self):
        os.environ["LANG"] = "en_US.UTF-8"
        self.assertEqual(i18n.detect_system_language(), "en")

    def test_language_priority_list(self):
        os.environ["LANGUAGE"] = "en_GB:pt_BR"
        self.assertEqual(i18n.detect_system_language(), "en")


class SetupTranslationTests(unittest.TestCase):
    def tearDown(self):
        # Restore the source language so other test modules are unaffected.
        i18n.setup_translation("pt_BR")

    def test_source_language_returns_msgid(self):
        i18n.setup_translation("pt_BR")
        self.assertEqual(i18n.get_active_language(), "pt_BR")
        self.assertEqual(i18n._("Preferências"), "Preferências")

    def test_english_catalog_translates(self):
        self.assertIn("en", i18n.available_languages())
        active = i18n.setup_translation("en")
        self.assertEqual(active, "en")
        self.assertEqual(i18n._("Preferências"), "Preferences")
        self.assertEqual(i18n._("&Arquivo"), "&File")

    def test_unknown_language_falls_back_to_source(self):
        active = i18n.setup_translation("xx")
        self.assertEqual(active, "pt_BR")
        self.assertEqual(i18n._("Preferências"), "Preferências")


class PoMoRoundTripTests(unittest.TestCase):
    def test_parse_and_compile_roundtrip(self):
        tool = _load_tool()
        po_text = (
            'msgid ""\n'
            'msgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n'
            "\n"
            'msgid "Olá"\n'
            'msgstr "Hello"\n'
        )
        entries = tool._parse_po(po_text)
        self.assertEqual(entries["Olá"], "Hello")

        mo_bytes = tool._compile_mo(entries)
        # Valid little-endian .mo magic number.
        self.assertEqual(mo_bytes[:4], b"\xde\x12\x04\x95")

    def test_fuzzy_entries_are_skipped(self):
        tool = _load_tool()
        po_text = 'msgid "x"\nmsgstr "y"\n\n#, fuzzy\nmsgid "a"\nmsgstr "b"\n'
        entries = tool._parse_po(po_text)
        self.assertEqual(entries.get("x"), "y")
        self.assertNotIn("a", entries)


class ExtractionTests(unittest.TestCase):
    def test_extract_finds_translatable_calls(self):
        tool = _load_tool()
        source = 'x = _("Olá")\ny = ngettext("um", "muitos", n)\nz = other("nope")\n'
        found = tool.extract_from_source(source)
        singulars = [singular for singular, _plural in found]
        self.assertIn("Olá", singulars)
        self.assertIn("um", singulars)
        self.assertNotIn("nope", singulars)


if __name__ == "__main__":
    unittest.main()
