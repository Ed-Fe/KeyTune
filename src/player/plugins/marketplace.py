"""GitHub-friendly marketplace catalog parsing and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .manifest import PLUGIN_ID_RE, VERSION_RE

DEFAULT_CATALOG_URL = "https://raw.githubusercontent.com/ed-fe/keytune-plugins/main/catalog.json"
MAX_CATALOG_BYTES = 2 * 1024 * 1024


class MarketplaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketplaceEntry:
    id: str
    name: str
    version: str
    description: str
    author: str
    download_url: str
    sha256: str
    homepage: str = ""
    verified: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MarketplaceEntry":
        required = ("id", "name", "version", "author", "download_url", "sha256")
        if not isinstance(value, dict) or any(not value.get(key) for key in required):
            raise MarketplaceError("Entrada incompleta no catálogo.")
        if not PLUGIN_ID_RE.fullmatch(str(value["id"])) or not VERSION_RE.fullmatch(str(value["version"])):
            raise MarketplaceError("Identificador ou versão inválida no catálogo.")
        parsed = urlparse(str(value["download_url"]))
        if parsed.scheme != "https" or not parsed.netloc:
            raise MarketplaceError("Downloads do marketplace devem usar HTTPS.")
        checksum = str(value["sha256"]).lower()
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
            raise MarketplaceError("Checksum SHA-256 inválido no catálogo.")
        return cls(
            id=str(value["id"]), name=str(value["name"]), version=str(value["version"]),
            description=str(value.get("description", "")), author=str(value["author"]),
            download_url=str(value["download_url"]), sha256=checksum,
            homepage=str(value.get("homepage", "")), verified=bool(value.get("verified", False)),
        )


def parse_catalog(payload: bytes | str) -> list[MarketplaceEntry]:
    try:
        document = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MarketplaceError("O catálogo não contém JSON válido.") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise MarketplaceError("Versão de catálogo incompatível.")
    plugins = document.get("plugins")
    if not isinstance(plugins, list):
        raise MarketplaceError("A lista de plugins do catálogo é inválida.")
    entries = [MarketplaceEntry.from_dict(item) for item in plugins]
    if len({item.id for item in entries}) != len(entries):
        raise MarketplaceError("O catálogo contém ids duplicados.")
    return entries


def fetch_catalog(url: str = DEFAULT_CATALOG_URL, *, timeout: int = 15) -> list[MarketplaceEntry]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KeyTune/2 plugin-marketplace"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_CATALOG_BYTES + 1)
    except OSError as exc:
        raise MarketplaceError(f"Não foi possível acessar o marketplace: {exc}") from exc
    if len(payload) > MAX_CATALOG_BYTES:
        raise MarketplaceError("O catálogo excede o limite de tamanho.")
    return parse_catalog(payload)
