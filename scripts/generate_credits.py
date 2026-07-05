from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from player.constants import GITHUB_REPOSITORY_NAME, GITHUB_REPOSITORY_OWNER  # noqa: E402

REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
CREDITS_PATH = REPO_ROOT / "docs" / "credits.md"
HTTP_TIMEOUT_SECONDS = 10

# Localized headings for the credits document. The actual library/contributor
# data is language-neutral, so only the surrounding text is translated. ``pt_BR``
# is the default and is written to ``docs/credits.md``; other languages are
# written to ``docs/credits.<language>.md``.
CREDITS_STRINGS = {
    "pt_BR": {
        "title": "Créditos",
        "libraries_heading": "Bibliotecas de terceiros",
        "contributors_heading": "Contribuidores",
        "contributors_section_pattern": r"^## Contribuidores\s*\n(.*?)(?:\n## |\Z)",
        "no_contributors": "Ainda não há contribuidores externos registrados além do(s) mantenedor(es) original(is).",
    },
    "en": {
        "title": "Credits",
        "libraries_heading": "Third-party libraries",
        "contributors_heading": "Contributors",
        "contributors_section_pattern": r"^## Contributors\s*\n(.*?)(?:\n## |\Z)",
        "no_contributors": "There are no external contributors registered yet beyond the original maintainer(s).",
    },
    "es": {
        "title": "Créditos",
        "libraries_heading": "Bibliotecas de terceros",
        "contributors_heading": "Colaboradores",
        "contributors_section_pattern": r"^## Colaboradores\s*\n(.*?)(?:\n## |\Z)",
        "no_contributors": "Todavía no hay colaboradores externos registrados además del o de los mantenedores originales.",
    },
}


def credits_path_for_language(language: str) -> Path:
    if language == "pt_BR":
        return CREDITS_PATH
    return REPO_ROOT / "docs" / f"credits.{language}.md"

REQUIREMENT_LINE_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)\s*([><=!~]=?\s*[\w.]+)?")


def parse_requirements(requirements_text: str) -> list[tuple[str, str, str]]:
    libraries = []
    for raw_line in requirements_text.splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line or line.startswith("#"):
            continue

        match = REQUIREMENT_LINE_PATTERN.match(line)
        if not match:
            continue

        name = match.group(1)
        version_spec = (match.group(2) or "").strip()
        libraries.append((name, version_spec, f"https://pypi.org/project/{name}/"))

    return libraries


def fetch_contributors() -> list[str] | None:
    api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY_OWNER}/{GITHUB_REPOSITORY_NAME}/contributors"
    http_request = request.Request(api_url, headers={"Accept": "application/vnd.github+json"})

    try:
        with request.urlopen(http_request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, ValueError):
        return None

    contributors = []
    for entry in payload:
        login = entry.get("login")
        profile_url = entry.get("html_url")
        if login and profile_url:
            contributors.append(f"- [{login}]({profile_url})")
    return contributors


def read_previous_contributors_section(credits_text: str, pattern: str) -> list[str]:
    match = re.search(pattern, credits_text, re.DOTALL | re.MULTILINE)
    if not match:
        return []
    return [line for line in match.group(1).splitlines() if line.strip()]


def render_credits(libraries: list[tuple[str, str, str]], contributors: list[str], language: str = "pt_BR") -> str:
    strings = CREDITS_STRINGS.get(language, CREDITS_STRINGS["pt_BR"])
    library_lines = "\n".join(
        f"- [{name}]({url}){f' ({version})' if version else ''}" for name, version, url in libraries
    )
    contributors_section = "\n".join(contributors) if contributors else strings["no_contributors"]

    return f"""# {strings["title"]}

## {strings["libraries_heading"]}

{library_lines}

## {strings["contributors_heading"]}

{contributors_section}
"""


def generate_for_language(libraries, contributors_by_login, language: str) -> Path:
    strings = CREDITS_STRINGS.get(language, CREDITS_STRINGS["pt_BR"])
    target_path = credits_path_for_language(language)

    contributors = contributors_by_login
    if contributors is None:
        previous_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        contributors = read_previous_contributors_section(previous_text, strings["contributors_section_pattern"])

    credits_text = render_credits(libraries, contributors, language)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(credits_text, encoding="utf-8")
    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o documento de créditos do KeyTune.")
    parser.add_argument(
        "--language",
        action="append",
        dest="languages",
        choices=sorted(CREDITS_STRINGS),
        help="Idioma(s) a gerar. Pode ser repetido. Padrão: pt_BR.",
    )
    args = parser.parse_args()
    languages = args.languages or ["pt_BR"]

    requirements_text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    libraries = parse_requirements(requirements_text)

    # Fetch contributors once (language-neutral); ``None`` means the network
    # lookup failed and each language reuses its previously written list.
    contributors = fetch_contributors()

    for language in languages:
        generate_for_language(libraries, contributors, language)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
