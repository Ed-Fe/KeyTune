from __future__ import annotations

import argparse
import datetime
import re
import unicodedata
from pathlib import Path
from html import escape

import markdown


BASE_STYLE = """
:root {
  color-scheme: light;
  --bg: #f4f1ea;
  --paper: #fffdf8;
  --text: #1f2328;
  --muted: #5c6470;
  --accent: #205375;
  --accent-soft: #d9e7f0;
  --border: #d7d0c4;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", "Noto Sans", Arial, sans-serif;
  line-height: 1.65;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(32, 83, 117, 0.12), transparent 35%),
    linear-gradient(180deg, #faf7f2 0%, var(--bg) 100%);
}
main {
  max-width: 920px;
  margin: 0 auto;
  padding: 48px 24px 72px;
}
.card {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: 0 18px 48px rgba(31, 35, 40, 0.08);
  padding: 36px;
}
h1, h2, h3 { line-height: 1.2; }
h1 { margin-top: 0; font-size: clamp(2rem, 4vw, 3rem); }
h2 { margin-top: 2.25rem; border-top: 1px solid var(--border); padding-top: 1.25rem; }
h3 { margin-top: 1.5rem; }
p, li { font-size: 1rem; }
a { color: var(--accent); }
code {
  background: var(--accent-soft);
  padding: 0.12rem 0.35rem;
  border-radius: 6px;
}
pre {
  overflow-x: auto;
  padding: 1rem;
  border-radius: 14px;
  background: #111827;
  color: #f9fafb;
}
pre code { background: transparent; padding: 0; }
blockquote {
  margin: 1.25rem 0;
  padding: 0.25rem 1rem;
  border-left: 4px solid var(--accent);
  color: var(--muted);
  background: rgba(32, 83, 117, 0.04);
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
}
th, td {
  border: 1px solid var(--border);
  padding: 0.7rem;
  text-align: left;
  vertical-align: top;
}
th { background: rgba(32, 83, 117, 0.08); }
footer {
  margin-top: 2rem;
  color: var(--muted);
  font-size: 0.92rem;
}
.toc {
  margin: 1.5rem 0 2rem;
  padding: 1rem 1.2rem;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(32, 83, 117, 0.04);
}
.toc h2 {
  margin: 0 0 0.75rem;
  padding: 0;
  border: 0;
  font-size: 1.15rem;
}
.toc ol {
  margin: 0;
  padding-left: 1.25rem;
}
.toc li { margin: 0.25rem 0; }
.toc a { text-decoration: none; }
.toc a:hover { text-decoration: underline; }
"""


def slugify_heading(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug or "section"


def collect_headings(source_text: str) -> list[tuple[int, str, str]]:
    headings: list[tuple[int, str, str]] = []
    used_slugs: dict[str, int] = {}

    for raw_line in source_text.splitlines():
        if not raw_line.startswith("#"):
            continue

        match = re.match(r"^(#{1,6})\s+(.*)$", raw_line)
        if not match:
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        slug_base = slugify_heading(title)
        occurrence = used_slugs.get(slug_base, 0)
        used_slugs[slug_base] = occurrence + 1
        slug = slug_base if occurrence == 0 else f"{slug_base}-{occurrence + 1}"
        headings.append((level, title, slug))

    return headings


def inject_heading_ids(html_text: str, headings: list[tuple[int, str, str]]) -> str:
    heading_pattern = re.compile(r"<h([1-6])>(.*?)</h\1>")
    heading_iter = iter(headings)

    def replace(match: re.Match[str]) -> str:
        try:
          level, title, slug = next(heading_iter)
        except StopIteration:
          return match.group(0)

        html_level = int(match.group(1))
        if html_level != level:
            return match.group(0)

        return f'<h{html_level} id="{slug}">{match.group(2)}</h{html_level}>'

    return heading_pattern.sub(replace, html_text, count=len(headings))


def build_toc_html(headings: list[tuple[int, str, str]]) -> str:
    toc_items = []
    for level, title, slug in headings:
        if level == 1:
            continue
        indent_class = f"toc-level-{level}"
        toc_items.append(
            f'<li class="{indent_class}"><a href="#{slug}">{escape(title)}</a></li>'
        )

    if not toc_items:
        return ""

    return """
    <nav class="toc" aria-label="Índice do manual">
      <ol>
        {items}
      </ol>
    </nav>
    """.format(items="\n        ".join(toc_items))


def render_markdown(source_text: str, title: str, source_url: str = "https://github.com/ed-fe/KeyTune/blob/main/docs/manual.md") -> str:
    headings = collect_headings(source_text)
    body = markdown.markdown(
        source_text,
        extensions=["extra", "sane_lists", "tables", "fenced_code"],
        output_format="html5",
    )
    body = inject_heading_ids(body, headings)
    toc_html = build_toc_html(headings)
    generated_date = datetime.date.today().strftime("%d/%m/%Y")

    if toc_html:
        first_section_match = re.search(r"<h2\b", body)
        if first_section_match:
            body = f"{body[:first_section_match.start()]}{toc_html}{body[first_section_match.start():]}"
        else:
            body = f"{body}{toc_html}"

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{BASE_STYLE}</style>
</head>
<body>
  <main>
    <section class="card">
      <h1>{escape(title)}</h1>
      {body}
      <footer>
        Gerado em {generated_date} &mdash; <a href="{source_url}">ver fonte no GitHub</a>
      </footer>
    </section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Renderiza o manual em Markdown para HTML.")
    parser.add_argument("source", type=Path, help="Arquivo Markdown de origem")
    parser.add_argument("target", type=Path, help="Arquivo HTML de destino")
    args = parser.parse_args()

    source_text = args.source.read_text(encoding="utf-8")
    title = next(
        (line.lstrip("# ").strip() for line in source_text.splitlines() if line.startswith("# ")),
        args.source.stem,
    )
    lines = source_text.splitlines()
    title_index = next((index for index, line in enumerate(lines) if line.startswith("# ")), None)
    if title_index is None:
        body_source = source_text
    else:
        body_source = "\n".join(lines[:title_index] + lines[title_index + 1 :])

    html_text = render_markdown(body_source, title)
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(html_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
