from __future__ import annotations

import pathlib
import re
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.manual import service
from player.links import resolve_link
from player.manual.service import (
    ManualLink,
    find_anchor,
    first_match_line_start,
    fold,
    link_in_line,
    load_manual,
    manual_candidate_paths,
    parse_manual,
    search_manual,
)

DOCS = PROJECT_ROOT / "docs"

SAMPLE = """# Manual de teste

Abertura do manual.

## Reproduzir

Texto da seção, **antes** dos tópicos.

### Atalhos

| Tecla | O que faz |
| --- | --- |
| `Espaço` | Reproduzir ou pausar |
| `Ctrl+.` | Parar |

Depois da tabela, veja [Atualizações](#atualizacoes) e o [site](https://exemplo.org).

### Modos

1. Primeiro passo com `código`.
2. Segundo passo com *ênfase*.

#### Detalhe fundo

Linha do detalhe.

## Vazia

### Só um título sem texto
"""


class ParseManualTests(unittest.TestCase):
    def setUp(self):
        self.sections = parse_manual(SAMPLE)

    def test_sections_come_from_the_headings_in_order(self):
        self.assertEqual([s.title for s in self.sections], ["Manual de teste", "Reproduzir"])

    def test_text_before_the_first_subheading_is_the_opening_topic(self):
        topics = self.sections[1].topics
        self.assertEqual([t.title for t in topics][1:], ["Atalhos", "Modos"])
        self.assertEqual(topics[0].text, "Texto da seção, antes dos tópicos.")

    def test_sections_and_topics_without_text_are_dropped(self):
        self.assertNotIn("Vazia", [s.title for s in self.sections])

    def test_tables_become_item_colon_description_lines(self):
        shortcuts = self.sections[1].topics[1].text
        self.assertIn("Espaço: Reproduzir ou pausar", shortcuts)
        self.assertIn("Ctrl+.: Parar", shortcuts)
        self.assertNotIn("|", shortcuts)
        self.assertNotIn("---", shortcuts)

    def test_internal_links_keep_only_the_text_and_external_ones_the_address(self):
        text = self.sections[1].topics[1].text
        self.assertIn("veja Atualizações e o site (https://exemplo.org).", text)
        self.assertNotIn("#atualizacoes", text)

    def test_inline_marks_disappear_and_lists_keep_their_numbers(self):
        text = self.sections[1].topics[2].text
        self.assertIn("1. Primeiro passo com código.", text)
        self.assertIn("2. Segundo passo com ênfase.", text)
        self.assertIn("Linha do detalhe.", text)
        self.assertNotIn("#", text)

    def test_a_three_column_table_names_the_columns(self):
        sections = parse_manual("## S\n\n### T\n\n| Para | A | B |\n| --- | --- | --- |\n| x | 1 | 2 |\n")
        self.assertEqual(sections[0].topics[0].text, "x. A: 1; B: 2.")


class ManualLinkTests(unittest.TestCase):
    def setUp(self):
        self.sections = parse_manual(SAMPLE)

    def test_a_topic_keeps_its_links_in_order(self):
        self.assertEqual(
            self.sections[1].topics[1].links,
            [ManualLink("Atualizações", "#atualizacoes"), ManualLink("site", "https://exemplo.org")],
        )

    def test_headings_become_anchors_of_their_topics(self):
        self.assertEqual(find_anchor(self.sections, "manual-de-teste"), (0, 0))
        self.assertEqual(find_anchor(self.sections, "#reproduzir"), (1, 0))
        self.assertEqual(find_anchor(self.sections, "atalhos"), (1, 1))
        self.assertEqual(find_anchor(self.sections, "detalhe-fundo"), (1, 2))
        self.assertIsNone(find_anchor(self.sections, "vazia"))

    def test_an_empty_opening_hands_its_anchor_to_the_next_topic(self):
        sections = parse_manual("## Seção\n\n### Primeiro\n\nTexto.\n")
        self.assertEqual(find_anchor(sections, "secao"), (0, 0))

    def test_repeated_headings_are_numbered_like_the_html(self):
        sections = parse_manual("## A\n\n### Dicas\n\nUm.\n\n## B\n\n### Dicas\n\nDois.\n")
        self.assertEqual(find_anchor(sections, "dicas"), (0, 0))
        self.assertEqual(find_anchor(sections, "dicas-2"), (1, 0))

    def test_the_link_in_a_line_is_the_one_under_the_cursor(self):
        links = self.sections[1].topics[1].links
        line = "Depois da tabela, veja Atualizações e o site (https://exemplo.org)."
        self.assertEqual(link_in_line(links, line, line.index("site") + 1).target, "https://exemplo.org")
        self.assertEqual(link_in_line(links, line, 0).target, "#atualizacoes")
        self.assertIsNone(link_in_line(links, "Sem link aqui.", 0))

    def test_every_internal_link_of_the_real_manuals_has_a_destination(self):
        for name in ("manual.md", "manual.en.md", "manual.es.md"):
            sections = parse_manual((DOCS / name).read_text(encoding="utf-8"))
            for section in sections:
                for topic in section.topics:
                    for link in topic.links:
                        if link.is_internal:
                            with self.subTest(name=name, link=link.target):
                                self.assertIsNotNone(find_anchor(sections, link.anchor))


class ResolveLinkTests(unittest.TestCase):
    def test_web_addresses_pass_and_other_schemes_do_not(self):
        self.assertEqual(resolve_link("https://exemplo.org/a"), "https://exemplo.org/a")
        self.assertIsNone(resolve_link("javascript:alert(1)"))
        self.assertIsNone(resolve_link("file:///C:/Windows"))
        self.assertIsNone(resolve_link("#ancora"))

    def test_a_markdown_file_opens_as_its_html_inside_the_docs_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder) / "plugins.md").write_text("x", encoding="utf-8")
            (pathlib.Path(folder) / "plugins.html").write_text("x", encoding="utf-8")
            self.assertTrue(resolve_link("plugins.md", [folder]).endswith("plugins.html"))
            self.assertIsNone(resolve_link("../plugins.md", [folder]))
            self.assertIsNone(resolve_link("ausente.md", [folder]))


class RealManualTests(unittest.TestCase):
    def _load(self, name):
        return parse_manual((DOCS / name).read_text(encoding="utf-8"))

    def test_the_portuguese_manual_has_no_markdown_marks_left(self):
        sections = self._load("manual.md")
        self.assertGreater(len(sections), 10)
        for section in sections:
            for topic in section.topics:
                with self.subTest(section=section.title, topic=topic.title):
                    self.assertFalse(re.search(r"\*\*|`|\]\(|^\s*\|", topic.text, re.M))

    def test_translations_have_the_same_sections_and_topic_count(self):
        reference = [len(s.topics) for s in self._load("manual.md")]
        for name in ("manual.en.md", "manual.es.md"):
            with self.subTest(name=name):
                self.assertEqual([len(s.topics) for s in self._load(name)], reference)


class SearchManualTests(unittest.TestCase):
    def setUp(self):
        self.sections = parse_manual(SAMPLE)

    def test_fold_ignores_case_and_accents_without_changing_the_length(self):
        text = "Seção ÁÉÍ Ação ß"
        self.assertEqual(len(fold(text)), len(text))
        self.assertEqual(fold("Ação"), "acao")
        self.assertEqual(fold("ÁÉÍÓÚ ç"), "aeiou c")

    def test_a_search_ignores_accents_and_case(self):
        found = search_manual(self.sections, "ATUALIZACOES")
        self.assertEqual([t.title for s in found for t in s.topics], ["Atalhos"])

    def test_all_the_words_must_appear_in_the_same_topic(self):
        self.assertEqual(len(search_manual(self.sections, "parar espaço")), 1)
        self.assertEqual(search_manual(self.sections, "parar ênfase"), [])

    def test_the_section_title_counts_for_every_topic_in_it(self):
        found = search_manual(self.sections, "reproduzir")
        self.assertEqual([len(s.topics) for s in found], [3])

    def test_an_empty_search_gives_back_the_whole_manual(self):
        self.assertEqual([s.title for s in search_manual(self.sections, "   ")], [s.title for s in self.sections])

    def test_the_search_does_not_change_the_original_sections(self):
        before = [len(s.topics) for s in self.sections]
        search_manual(self.sections, "parar")
        self.assertEqual([len(s.topics) for s in self.sections], before)

    def test_the_text_opens_on_the_line_with_the_first_match(self):
        text = "\n".join(["Primeira linha.", "Segunda linha com Atenção aqui.", "Terceira."])
        start = first_match_line_start(text, "atencao")
        self.assertEqual(text[start:].splitlines()[0], "Segunda linha com Atenção aqui.")
        self.assertEqual(first_match_line_start(text, "nada disso"), 0)
        self.assertEqual(first_match_line_start(text, ""), 0)

    def test_the_real_manual_finds_cookies(self):
        sections = parse_manual((DOCS / "manual.md").read_text(encoding="utf-8"))
        found = search_manual(sections, "cookies exportar")
        self.assertTrue(found)
        self.assertTrue(all("cookies" in fold(t.text + t.title + s.title) for s in found for t in s.topics))


class LoadManualTests(unittest.TestCase):
    def test_the_active_language_comes_first_then_portuguese(self):
        paths = manual_candidate_paths("en", [pathlib.Path("d")])
        self.assertEqual([p.name for p in paths], ["manual.en.md", "manual.md"])
        self.assertEqual([p.name for p in manual_candidate_paths("pt_BR", [pathlib.Path("d")])], ["manual.md"])

    def test_falls_back_to_portuguese_when_the_translation_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder) / "manual.md").write_text("## A\n\nTexto.\n", encoding="utf-8")
            sections = load_manual("es", [pathlib.Path(folder)])
        self.assertEqual([s.title for s in sections], ["A"])

    def test_no_file_means_no_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_manual("pt_BR", [pathlib.Path(folder)]), [])

    def test_module_exposes_the_directories_helper(self):
        self.assertTrue(service.manual_directories())


if __name__ == "__main__":
    unittest.main()
