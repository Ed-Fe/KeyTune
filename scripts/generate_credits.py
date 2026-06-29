from __future__ import annotations

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


def read_previous_contributors_section(credits_text: str) -> list[str]:
    match = re.search(r"^## Contribuidores\s*\n(.*?)(?:\n## |\Z)", credits_text, re.DOTALL | re.MULTILINE)
    if not match:
        return []
    return [line for line in match.group(1).splitlines() if line.strip()]


def render_credits(libraries: list[tuple[str, str, str]], contributors: list[str]) -> str:
    library_lines = "\n".join(
        f"- [{name}]({url}){f' ({version})' if version else ''}" for name, version, url in libraries
    )
    contributors_section = (
        "\n".join(contributors)
        if contributors
        else "Ainda não há contribuidores externos registrados além do(s) mantenedor(es) original(is)."
    )

    return f"""# Créditos

## Bibliotecas de terceiros

{library_lines}

## Contribuidores

{contributors_section}
"""


def main() -> int:
    requirements_text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    libraries = parse_requirements(requirements_text)

    contributors = fetch_contributors()
    if contributors is None:
        previous_text = CREDITS_PATH.read_text(encoding="utf-8") if CREDITS_PATH.is_file() else ""
        contributors = read_previous_contributors_section(previous_text)

    credits_text = render_credits(libraries, contributors)
    CREDITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDITS_PATH.write_text(credits_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
