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


@dataclass(frozen=True)
class ManualLink:
    """Um link do manual: o texto dele e para onde ele leva.

    *target* é uma âncora (``#recursos-de-acessibilidade``), que leva a outro
    trecho do próprio manual, ou um endereço, que abre no navegador.
    """

    text: str
    target: str

    @property
    def is_internal(self) -> bool:
        return self.target.startswith("#")

    @property
    def anchor(self) -> str:
        return self.target[1:] if self.is_internal else ""

    def rendered_text(self) -> str:
        """Como o link aparece no texto do tópico (ver ``_plain_inline``)."""
        return self.text if self.is_internal else f"{self.text} ({self.target})"


@dataclass
class ManualTopic:
    title: str
    text: str = ""
    # Os links do tópico, na ordem em que aparecem, sem repetir.
    links: list[ManualLink] = field(default_factory=list)
    # As âncoras que levam a este tópico: a do título dele, as dos ``####`` de
    # dentro e, na abertura de uma seção, a do título da seção.
    anchors: list[str] = field(default_factory=list)
    # A abertura da seção (o texto entre o ``##`` e o primeiro ``###``).
    is_overview: bool = False


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


def manual_html_path(language: str | None = None, directories: list[Path] | None = None) -> Path | None:
    """O ``manual.html`` gerado na release (o do idioma ativo primeiro), ou ``None``."""
    for path in manual_candidate_paths(language, directories):
        html_path = path.with_suffix(".html")
        if html_path.is_file():
            return html_path
    return None


def load_manual(language: str | None = None, directories: list[Path] | None = None) -> list[ManualSection]:
    """As seções do manual, ou uma lista vazia se nenhum arquivo for encontrado."""
    for path in manual_candidate_paths(language, directories):
        if path.is_file():
            try:
                return parse_manual(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
    return []


def parse_manual(markdown: str) -> list[ManualSection]:
    sections: list[ManualSection] = []
    # Linhas do tópico em montagem, sem o título dele.
    current_topic: ManualTopic | None = None
    current_lines: list[str] = []
    used_slugs: dict[str, int] = {}

    def close_topic():
        nonlocal current_topic, current_lines
        if current_topic is not None:
            current_topic.text = _lines_to_text(current_lines)
            current_topic.links = _links_in(current_lines)
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
        anchor = _heading_anchor(line, used_slugs) if heading else ""
        if level == 1:
            close_topic()
            section = open_section(_plain_inline(heading.group(2)))
            current_topic = ManualTopic(title=_("Apresentação"), anchors=[anchor], is_overview=True)
            section.topics.append(current_topic)
        elif level == 2:
            close_topic()
            section = open_section(_plain_inline(heading.group(2)))
            current_topic = ManualTopic(title=_("Visão geral da seção"), anchors=[anchor], is_overview=True)
            section.topics.append(current_topic)
        elif level == 3 and section is not None:
            close_topic()
            current_topic = ManualTopic(title=_plain_inline(heading.group(2)), anchors=[anchor])
            section.topics.append(current_topic)
        else:
            # Títulos mais fundos (####) ficam como uma linha de texto do tópico.
            if heading and level > 3:
                line = heading.group(2)
                if current_topic is not None:
                    current_topic.anchors.append(anchor)
            current_lines.append(line)
    close_topic()

    # A abertura que ficou sem texto (título seguido direto de outro título) some;
    # as âncoras dela passam para o tópico seguinte, para o link continuar levando
    # ao começo da seção.
    for section in sections:
        kept: list[ManualTopic] = []
        orphan_anchors: list[str] = []
        for topic in section.topics:
            if topic.text:
                topic.anchors = orphan_anchors + topic.anchors
                orphan_anchors = []
                kept.append(topic)
            else:
                orphan_anchors.extend(topic.anchors)
        if orphan_anchors and kept:
            kept[-1].anchors.extend(orphan_anchors)
        section.topics = kept
    return [section for section in sections if section.topics]


_RAW_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def slugify_heading(title: str) -> str:
    """A âncora de um título, igual à que ``scripts/render_manual.py`` gera no HTML."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug or "section"


def _heading_anchor(line: str, used_slugs: dict[str, int]) -> str:
    # Mesma conta do HTML: o título cru, e um número a partir do segundo repetido.
    match = _RAW_HEADING.match(line)
    if not match:
        return ""
    base = slugify_heading(match.group(2).strip())
    occurrence = used_slugs.get(base, 0)
    used_slugs[base] = occurrence + 1
    return base if occurrence == 0 else f"{base}-{occurrence + 1}"


def _links_in(lines: list[str]) -> list[ManualLink]:
    links: list[ManualLink] = []
    for line in lines:
        for match in _LINK.finditer(line):
            link = ManualLink(text=_plain_inline(match.group(1)), target=match.group(2))
            if link not in links:
                links.append(link)
    return links


def find_anchor(sections: list[ManualSection], anchor: str) -> tuple[int, int] | None:
    """``(seção, tópico)`` do tópico que tem a âncora *anchor*, ou ``None``."""
    anchor = anchor.lstrip("#")
    for section_index, section in enumerate(sections):
        for topic_index, topic in enumerate(section.topics):
            if anchor in topic.anchors:
                return section_index, topic_index
    return None


def link_in_line(links: list[ManualLink], line: str, column: int = 0) -> ManualLink | None:
    """O link que aparece na linha *line* do texto, o mais perto da coluna *column*.

    Um link cujo texto contém a coluna ganha; sem nenhum, vale o primeiro da linha.
    """
    found: list[tuple[int, int, ManualLink]] = []
    for link in links:
        rendered = link.rendered_text()
        if not rendered:
            continue
        start = line.find(rendered)
        while start >= 0:
            found.append((start, start + len(rendered), link))
            start = line.find(rendered, start + 1)
    if not found:
        return None
    for start, end, link in found:
        if start <= column <= end:
            return link
    return min(found, key=lambda item: item[0])[2]


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
