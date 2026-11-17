"""Leitura do manual do usuário, dividido em seções e tópicos para a janela de ajuda.

O manual é o ``docs/manual.md`` (ou ``manual.<idioma>.md``). Os títulos ``##``
são as seções; os ``###`` de cada uma são os tópicos. O texto que vem logo
depois do ``##``, antes do primeiro ``###``, é o tópico de abertura da seção.
O Markdown vira texto simples, pensado para o leitor de tela: sem símbolos de
formatação, tabelas em linhas "item: descrição" e cada parágrafo numa linha só.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import SOURCE_LANGUAGE, _, get_active_language

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t#]*$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


@dataclass
class ManualTopic:
    title: str
    text: str = ""


@dataclass
class ManualSection:
    title: str
    topics: list[ManualTopic] = field(default_factory=list)


def manual_directories() -> list[Path]:
    directories = []
    if getattr(sys, "frozen", False):
        directories.append(Path(sys.executable).resolve().parent / "docs")
    directories.append(Path(__file__).resolve().parents[3] / "docs")
    directories.append(Path.cwd() / "docs")

    unique = []
    for directory in directories:
        if directory not in unique:
            unique.append(directory)
    return unique


def manual_candidate_paths(language: str | None = None, directories: list[Path] | None = None) -> list[Path]:
    """Onde procurar o manual: o idioma ativo primeiro, depois o texto em português."""
    if language is None:
        language = get_active_language()
    names = []
    if language and language != SOURCE_LANGUAGE:
        names.append(f"manual.{language}.md")
    names.append("manual.md")
    return [directory / name for name in names for directory in (directories or manual_directories())]


def load_manual(language: str | None = None, directories: list[Path] | None = None) -> list[ManualSection]:
    """As seções do manual, ou uma lista vazia se nenhum arquivo for encontrado."""
    for path in manual_candidate_paths(language, directories):
        if path.is_file():
            try:
                return parse_manual(path.read_text(encoding="utf-8"))
            except OSError:
                continue
    return []


def parse_manual(markdown: str) -> list[ManualSection]:
    sections: list[ManualSection] = []
    # Linhas do tópico em montagem, sem o título dele.
    current_topic: ManualTopic | None = None
    current_lines: list[str] = []

    def close_topic():
        nonlocal current_topic, current_lines
        if current_topic is not None:
            current_topic.text = _lines_to_text(current_lines)
        current_topic = None
        current_lines = []

    def open_section(title):
        section = ManualSection(title=title)
        sections.append(section)
        return section

    section: ManualSection | None = None
    for line in markdown.splitlines():
        heading = _HEADING.match(line)
        level = len(heading.group(1)) if heading else 0
        if level == 1:
            close_topic()
            section = open_section(_plain_inline(heading.group(2)))
            current_topic = ManualTopic(title=_("Apresentação"))
            section.topics.append(current_topic)
        elif level == 2:
            close_topic()
            section = open_section(_plain_inline(heading.group(2)))
            current_topic = ManualTopic(title=_("Visão geral da seção"))
            section.topics.append(current_topic)
        elif level == 3 and section is not None:
            close_topic()
            current_topic = ManualTopic(title=_plain_inline(heading.group(2)))
            section.topics.append(current_topic)
        else:
            # Títulos mais fundos (####) ficam como uma linha de texto do tópico.
            if heading and level > 3:
                line = heading.group(2)
            current_lines.append(line)
    close_topic()

    # A abertura que ficou sem texto (título seguido direto de outro título) some.
    for section in sections:
        section.topics = [topic for topic in section.topics if topic.text]
    return [section for section in sections if section.topics]


def _lines_to_text(lines: list[str]) -> str:
    output: list[str] = []
    header: list[str] | None = None
    table_started = False
    for raw in lines:
        if _TABLE_ROW.match(raw):
            cells = [_plain_inline(cell) for cell in raw.strip().strip("|").split("|")]
            if not table_started:
                header = cells
                table_started = True
                continue
            if _TABLE_SEPARATOR.match(raw):
                continue
            output.append(_table_row_text(header or [], cells))
            continue
        table_started = False
        header = None
        text = re.sub(r"^\s*>\s?", "", raw)
        indent = re.match(r"\s*", text).group(0)
        output.append(indent + _plain_inline(text.strip()))
    return _squeeze_blank_lines(output)


def _table_row_text(header: list[str], cells: list[str]) -> str:
    cells = [cell for cell in cells]
    if not cells:
        return ""
    if len(cells) == 1:
        return cells[0]
    if len(cells) == 2:
        return f"{cells[0]}: {cells[1]}"
    pairs = []
    for index, cell in enumerate(cells[1:], start=1):
        label = header[index] if index < len(header) else ""
        pairs.append(f"{label}: {cell}" if label else cell)
    return f"{cells[0]}. " + "; ".join(pairs) + "."


def _squeeze_blank_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        line = line.rstrip()
        if not line and (not cleaned or not cleaned[-1]):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _plain_inline(text: str) -> str:
    # Link interno (#âncora): fica só o texto. Link externo: texto e endereço.
    text = _LINK.sub(lambda m: m.group(1) if m.group(2).startswith("#") else f"{m.group(1)} ({m.group(2)})", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", text)
    return text.strip()


def fold(text: str) -> str:
    """Minúsculas e sem acento, com o mesmo tamanho do original (posição por posição)."""
    folded = []
    for char in text:
        base = unicodedata.normalize("NFD", char)[0].lower()
        folded.append(base if len(base) == 1 else char)
    return "".join(folded)


def query_words(query: str) -> list[str]:
    return [word for word in fold(query).split() if word]


def topic_matches(section: ManualSection, topic: ManualTopic, words: list[str]) -> bool:
    """O tópico tem todas as palavras, somando o título da seção, o dele e o texto."""
    haystack = fold(f"{section.title}\n{topic.title}\n{topic.text}")
    return all(word in haystack for word in words)


def search_manual(sections: list[ManualSection], query: str) -> list[ManualSection]:
    """Cópias das seções só com os tópicos que casam; seção sem nenhum some."""
    words = query_words(query)
    if not words:
        return list(sections)
    found = []
    for section in sections:
        topics = [topic for topic in section.topics if topic_matches(section, topic, words)]
        if topics:
            found.append(ManualSection(title=section.title, topics=topics))
    return found


def first_match_line_start(text: str, query: str) -> int:
    """Posição, no texto, do começo da primeira linha com alguma das palavras (0 se não houver)."""
    words = query_words(query)
    if not words:
        return 0
    folded = fold(text)
    best = None
    for word in words:
        index = folded.find(word)
        if index >= 0 and (best is None or index < best):
            best = index
    if best is None:
        return 0
    return folded.rfind("\n", 0, best) + 1
