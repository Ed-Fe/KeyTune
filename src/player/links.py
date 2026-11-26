"""Abrir no navegador um link que o próprio KeyTune mostra (manual, guias).

Só abre endereços ``http``/``https`` e arquivos que ficam dentro das pastas de
documentação indicadas; qualquer outra coisa é recusada. Um arquivo ``.md`` abre
na versão ``.html`` que a release gera, quando ela existe.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

_WEB_SCHEMES = ("http", "https")


def resolve_link(target: str, base_directories=()) -> str | None:
    """O endereço que o navegador deve abrir para *target*, ou ``None`` se não der."""
    target = str(target or "").strip()
    if not target or target.startswith("#"):
        return None
    parts = urlsplit(target)
    if parts.scheme:
        return target if parts.scheme.lower() in _WEB_SCHEMES and parts.netloc else None
    relative = Path(parts.path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidates = []
    if relative.suffix.lower() == ".md":
        candidates.append(relative.with_suffix(".html"))
    candidates.append(relative)
    for directory in base_directories:
        for candidate in candidates:
            path = Path(directory) / candidate
            if path.is_file():
                return path.resolve().as_uri()
    return None


def open_link(target: str, base_directories=()) -> bool:
    """Abre *target* no navegador padrão; ``False`` se o link não vale ou não abriu."""
    address = resolve_link(target, base_directories)
    if address is None:
        return False
    try:
        import wx

        return bool(wx.LaunchDefaultBrowser(address))
    except Exception:
        return False
