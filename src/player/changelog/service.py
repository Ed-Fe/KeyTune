"""Leitura do histórico de mudanças, um arquivo por versão em ``docs/changelog``.

``2.1.0.md`` é o texto em português (idioma de origem); ``2.1.0.en.md`` e
``2.1.0.es.md`` são as traduções. ``unreleased.md`` guarda o que ainda não foi
lançado e não vai para o pacote.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ..i18n import SOURCE_LANGUAGE, get_active_language
from ..update.service import release_notes_to_plain_text

UNRELEASED = "unreleased"

_FILE_PATTERN = re.compile(r"^(?P<version>\d+(?:\.\d+)*|unreleased)(?:\.(?P<language>[A-Za-z]+(?:_[A-Za-z]+)?))?\.md$")
_HEADING_PATTERN = re.compile(r"^##\s*\[[^\]]+\](?:\s*-\s*(?P<date>\S+))?")


@dataclass(frozen=True)
class ChangelogEntry:
    version: str
    date: str
    path: Path

    @property
    def is_unreleased(self) -> bool:
        return self.version == UNRELEASED

    def read_text(self) -> str:
        return release_notes_to_plain_text(self.path.read_text(encoding="utf-8"))


def changelog_directories() -> list[Path]:
    directories = []
    if getattr(sys, "frozen", False):
        directories.append(Path(sys.executable).resolve().parent / "docs" / "changelog")
    directories.append(Path(__file__).resolve().parents[3] / "docs" / "changelog")
    directories.append(Path.cwd() / "docs" / "changelog")

    unique = []
    for directory in directories:
        if directory not in unique:
            unique.append(directory)
    return unique


def list_changelog_entries(language: str | None = None, directories: list[Path] | None = None) -> list[ChangelogEntry]:
    """Versões disponíveis, da mais nova para a mais antiga, no idioma pedido.

    Cada versão usa o arquivo do idioma ativo e, se ele não existir, o texto
    em português. O que ainda não foi lançado vem primeiro.
    """
    if language is None:
        language = get_active_language()
    for directory in directories if directories is not None else changelog_directories():
        entries = _entries_in_directory(directory, language)
        if entries:
            return entries
    return []


def _entries_in_directory(directory: Path, language: str) -> list[ChangelogEntry]:
    if not directory.is_dir():
        return []

    by_version: dict[str, dict[str, Path]] = {}
    for path in directory.glob("*.md"):
        match = _FILE_PATTERN.match(path.name)
        if match is None:
            continue
        file_language = match.group("language") or SOURCE_LANGUAGE
        by_version.setdefault(match.group("version"), {})[file_language] = path

    entries = []
    for version, files in by_version.items():
        path = files.get(language) or files.get(SOURCE_LANGUAGE)
        if path is None:
            continue
        entries.append(ChangelogEntry(version=version, date=_read_date(path), path=path))

    entries.sort(key=lambda entry: (entry.is_unreleased, _version_key(entry.version)), reverse=True)
    return entries


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _read_date(path: Path) -> str:
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                match = _HEADING_PATTERN.match(line)
                if match:
                    return match.group("date") or ""
    except OSError:
        return ""
    return ""
