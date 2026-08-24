"""Strict, dependency-free parsing for ``keytune-plugin.json`` manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from ..i18n import _


PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class ManifestError(ValueError):
    pass


class PluginPermission(str, Enum):
    PLAYBACK_READ = "playback.read"
    PLAYBACK_CONTROL = "playback.control"
    LIBRARY_READ = "library.read"
    LIBRARY_WRITE = "library.write"
    NETWORK = "network"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    CLIPBOARD = "clipboard"
    NOTIFICATIONS = "notifications"
    UI_MENU = "ui.menu"
    UI_TAB = "ui.tab"
    UI_VIEW = "ui.view"
    SETTINGS = "settings"
    YOUTUBE_MUSIC_READ = "youtube_music.read"
    YOUTUBE_MUSIC_WRITE = "youtube_music.write"
    YT_DLP = "yt_dlp"
    AUTODJ_ANALYZE = "autodj.analyze"


PERMISSION_DESCRIPTIONS = {
    PluginPermission.PLAYBACK_READ: _("Ler a faixa, a posição e o estado de reprodução"),
    PluginPermission.PLAYBACK_CONTROL: _("Controlar reprodução, volume, fila e troca de faixa"),
    PluginPermission.LIBRARY_READ: _("Consultar a biblioteca carregada, playlists e metadados"),
    PluginPermission.LIBRARY_WRITE: _("Alterar biblioteca, playlists, favoritos e avaliações"),
    PluginPermission.NETWORK: _("Acessar a internet e outros serviços de rede"),
    PluginPermission.FILESYSTEM_READ: _("Ler arquivos escolhidos ou autorizados"),
    PluginPermission.FILESYSTEM_WRITE: _("Criar ou alterar arquivos autorizados"),
    PluginPermission.CLIPBOARD: _("Ler ou alterar a área de transferência"),
    PluginPermission.NOTIFICATIONS: _("Mostrar avisos e fazer anúncios pelo leitor de telas"),
    PluginPermission.UI_MENU: _("Adicionar ações e submenus"),
    PluginPermission.UI_TAB: _("Adicionar abas ao player"),
    PluginPermission.UI_VIEW: _("Adicionar telas ou painéis"),
    PluginPermission.SETTINGS: _("Armazenar configurações próprias"),
    PluginPermission.YOUTUBE_MUSIC_READ: _("Consultar a conta e a biblioteca do YouTube Music"),
    PluginPermission.YOUTUBE_MUSIC_WRITE: _("Alterar playlists e avaliações do YouTube Music"),
    PluginPermission.YT_DLP: _("Usar o resolvedor de mídia yt-dlp"),
    PluginPermission.AUTODJ_ANALYZE: _("Analisar BPM, batidas, energia e tonalidade de faixas"),
}


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    api_version: str
    entrypoint: str
    author: str
    description: str = ""
    homepage: str = ""
    license: str = ""
    permissions: frozenset[PluginPermission] = field(default_factory=frozenset)
    isolation: str = "process"
    minimum_keytune_version: str = "2.0.0"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PluginManifest":
        if not isinstance(value, dict):
            raise ManifestError("O manifesto deve ser um objeto JSON.")
        required = ("id", "name", "version", "api_version", "entrypoint", "author")
        missing = [key for key in required if not str(value.get(key, "")).strip()]
        if missing:
            raise ManifestError("Campos obrigatórios ausentes: " + ", ".join(missing))
        plugin_id = str(value["id"]).strip()
        if not PLUGIN_ID_RE.fullmatch(plugin_id):
            raise ManifestError("O id deve ter de 3 a 64 caracteres minúsculos seguros.")
        version = str(value["version"]).strip()
        if not VERSION_RE.fullmatch(version):
            raise ManifestError("A versão deve seguir o versionamento semântico.")
        entrypoint = str(value["entrypoint"]).strip()
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", entrypoint):
            raise ManifestError("O entrypoint deve usar o formato modulo:objeto.")
        try:
            permissions = frozenset(PluginPermission(item) for item in value.get("permissions", []))
        except (TypeError, ValueError) as exc:
            raise ManifestError(f"Permissão desconhecida: {exc}") from exc
        isolation = str(value.get("isolation", "process"))
        if isolation not in {"process", "in_process"}:
            raise ManifestError("isolation deve ser process ou in_process.")
        return cls(
            id=plugin_id,
            name=str(value["name"]).strip(),
            version=version,
            api_version=str(value["api_version"]).strip(),
            entrypoint=entrypoint,
            author=str(value["author"]).strip(),
            description=str(value.get("description", "")).strip(),
            homepage=str(value.get("homepage", "")).strip(),
            license=str(value.get("license", "")).strip(),
            permissions=permissions,
            isolation=isolation,
            minimum_keytune_version=str(value.get("minimum_keytune_version", "2.0.0")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "api_version": self.api_version, "entrypoint": self.entrypoint,
            "author": self.author, "description": self.description,
            "homepage": self.homepage, "license": self.license,
            "permissions": sorted(item.value for item in self.permissions),
            "isolation": self.isolation,
            "minimum_keytune_version": self.minimum_keytune_version,
        }
