import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.changelog.service import list_changelog_entries
from player.update import service as update_service

CHANGELOG_DIR = PROJECT_ROOT / "docs" / "changelog"
TRANSLATED_LANGUAGES = ("en", "es")


def _write(directory: pathlib.Path, name: str, text: str) -> None:
    (directory / name).write_text(text, encoding="utf-8")


class ChangelogEntriesTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.directory = pathlib.Path(self._temp.name)
        _write(self.directory, "1.9.0.md", "## [1.9.0] - 2026-01-02\n\n### Adicionado\n\n- **Um**: texto.\n")
        _write(self.directory, "1.10.0.md", "## [1.10.0] - 2026-02-03\n\n### Corrigido\n\n- **Dois**: texto.\n")
        _write(self.directory, "1.10.0.en.md", "## [1.10.0] - 2026-02-03\n\n### Fixed\n\n- **Two**: text.\n")
        _write(self.directory, "unreleased.md", "## [Não lançado]\n\n### Adicionado\n\n- **Três**: texto.\n")

    def test_orders_newest_first_with_unreleased_on_top(self):
        entries = list_changelog_entries("pt_BR", [self.directory])

        self.assertEqual([entry.version for entry in entries], ["unreleased", "1.10.0", "1.9.0"])
        self.assertTrue(entries[0].is_unreleased)
        self.assertEqual(entries[1].date, "2026-02-03")
        self.assertEqual(entries[0].date, "")

    def test_uses_the_translation_when_it_exists_and_falls_back_to_portuguese(self):
        entries = {entry.version: entry for entry in list_changelog_entries("en", [self.directory])}

        self.assertIn("Fixed", entries["1.10.0"].read_text())
        self.assertIn("Adicionado", entries["1.9.0"].read_text())

    def test_missing_directory_gives_no_entries(self):
        self.assertEqual(list_changelog_entries("pt_BR", [self.directory / "nope"]), [])

    def test_ignores_files_that_are_not_versions(self):
        _write(self.directory, "README.md", "# Notas\n")

        versions = [entry.version for entry in list_changelog_entries("pt_BR", [self.directory])]

        self.assertNotIn("README", versions)


class LocalizedReleaseNotesTests(unittest.TestCase):
    ASSETS = [
        {"name": "KeyTune-Setup.exe", "browser_download_url": "https://example.invalid/setup"},
        {"name": "release-notes.en.md", "browser_download_url": "https://example.invalid/notes.en"},
    ]

    def _notes(self, language, assets=None, download=None):
        with mock.patch.object(update_service, "get_active_language", return_value=language), mock.patch.object(
            update_service, "_download_text", download or (lambda url, **_kwargs: "## [2.2.0]\nEnglish notes\n")
        ):
            return update_service._localized_release_notes(self.ASSETS if assets is None else assets, "Notas em português")

    def test_source_language_keeps_the_release_body(self):
        self.assertEqual(self._notes("pt_BR"), "Notas em português")

    def test_uses_the_asset_of_the_active_language(self):
        self.assertIn("English notes", self._notes("en"))

    def test_language_without_asset_keeps_the_release_body(self):
        self.assertEqual(self._notes("es"), "Notas em português")

    def test_failed_download_keeps_the_release_body(self):
        def failing_download(url, **_kwargs):
            raise update_service.UpdateError("offline")

        self.assertEqual(self._notes("en", download=failing_download), "Notas em português")

    def test_empty_asset_keeps_the_release_body(self):
        self.assertEqual(self._notes("en", download=lambda url, **_kwargs: "  \n"), "Notas em português")


def _structure(text: str) -> list[str]:
    """Headings and bullets with their depth, ignoring the wording."""
    shape = []
    for line in text.splitlines():
        heading = re.match(r"^(#{2,3}) ", line)
        bullet = re.match(r"^(\s*)- ", line)
        if heading:
            shape.append(heading.group(1))
        elif bullet:
            shape.append(f"{len(bullet.group(1))}-")
    return shape


class ChangelogFilesTests(unittest.TestCase):
    def released_versions(self):
        names = sorted(path.name for path in CHANGELOG_DIR.glob("*.md"))
        return [name[: -len(".md")] for name in names if re.fullmatch(r"\d+(?:\.\d+)*\.md", name)]

    def test_every_released_version_has_all_translations_with_the_same_shape(self):
        versions = self.released_versions()
        self.assertTrue(versions)
        for version in versions:
            source = (CHANGELOG_DIR / f"{version}.md").read_text(encoding="utf-8")
            for language in TRANSLATED_LANGUAGES:
                with self.subTest(version=version, language=language):
                    path = CHANGELOG_DIR / f"{version}.{language}.md"
                    self.assertTrue(path.is_file(), f"falta {path.name}")
                    translated = path.read_text(encoding="utf-8")
                    self.assertEqual(_structure(translated), _structure(source))
                    self.assertEqual(translated.splitlines()[0], source.splitlines()[0])
                    # Key names are translated ("Espaço" -> "Space"), so only the count of code spans is compared.
                    self.assertEqual(len(re.findall(r"`[^`\n]+`", translated)), len(re.findall(r"`[^`\n]+`", source)))

    def test_each_file_starts_with_its_own_version_heading(self):
        for path in CHANGELOG_DIR.glob("*.md"):
            match = re.match(r"^(\d+(?:\.\d+)*)", path.name)
            if match is None:
                continue
            with self.subTest(file=path.name):
                first_line = path.read_text(encoding="utf-8").splitlines()[0]
                self.assertTrue(first_line.startswith(f"## [{match.group(1)}] - "), first_line)


if __name__ == "__main__":
    unittest.main()
