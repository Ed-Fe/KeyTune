"""Stable capability-oriented API presented to plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .manifest import PluginPermission

API_VERSION = "2.0"


class PermissionDeniedError(PermissionError):
    pass


class HostBridge(Protocol):
    def invoke(self, method: str, arguments: dict[str, Any]) -> Any: ...
    def register_contribution(self, kind: str, contribution: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    data_directory: Path
    permissions: frozenset[PluginPermission]


class PluginAPI:
    """Versioned facade; every operation checks its capability before dispatch."""

    version = API_VERSION

    def __init__(self, context: PluginContext, bridge: HostBridge):
        self.context = context
        self.data_directory = context.data_directory
        self._bridge = bridge

    def require(self, permission: PluginPermission) -> None:
        if permission not in self.context.permissions:
            raise PermissionDeniedError(
                f"O plugin {self.context.plugin_id} não recebeu a permissão {permission.value}."
            )

    def playback_state(self) -> dict[str, Any]:
        self.require(PluginPermission.PLAYBACK_READ)
        return self._bridge.invoke("playback.state", {})

    def playback(self, action: str, **arguments: Any) -> Any:
        self.require(PluginPermission.PLAYBACK_CONTROL)
        return self._bridge.invoke("playback.control", {"action": action, **arguments})

    def library_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        self.require(PluginPermission.LIBRARY_READ)
        return self._bridge.invoke("library.search", {"query": query, "limit": limit})

    def playlists(self) -> list[dict[str, Any]]:
        """Return every currently loaded playlist/folder tab and its items."""
        self.require(PluginPermission.LIBRARY_READ)
        return self._bridge.invoke("library.playlists", {})

    def active_playlist(self) -> dict[str, Any] | None:
        self.require(PluginPermission.LIBRARY_READ)
        return self._bridge.invoke("library.active_playlist", {})

    def add_to_playlist(self, media_paths: list[str], *, playlist_index: int | None = None) -> int:
        self.require(PluginPermission.LIBRARY_WRITE)
        return self._bridge.invoke(
            "library.add_to_playlist",
            {"media_paths": list(media_paths), "playlist_index": playlist_index},
        )

    def youtube_music_account(self) -> dict[str, Any]:
        self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke("youtube_music.account", {})

    def youtube_music_search(self, query: str, *, scope: str = "music_songs") -> list[dict[str, Any]]:
        self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke("youtube_music.search", {"query": query, "scope": scope})

    def youtube_music_playlists(self, *, limit: int = 100) -> list[dict[str, Any]]:
        self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke("youtube_music.playlists", {"limit": limit})

    def youtube_music_playlist(self, playlist_id: str) -> dict[str, Any]:
        self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke("youtube_music.playlist", {"playlist_id": playlist_id})

    def youtube_music_rate(self, media_path: str, rating: str) -> bool:
        self.require(PluginPermission.YOUTUBE_MUSIC_WRITE)
        return self._bridge.invoke("youtube_music.rate", {"media_path": media_path, "rating": rating})

    def youtube_music_create_playlist(self, title: str, *, description: str = "", video_ids=()) -> str:
        self.require(PluginPermission.YOUTUBE_MUSIC_WRITE)
        return self._bridge.invoke(
            "youtube_music.create_playlist",
            {"title": title, "description": description, "video_ids": list(video_ids)},
        )

    def youtube_music_add_tracks(self, playlist_id: str, video_ids) -> Any:
        self.require(PluginPermission.YOUTUBE_MUSIC_WRITE)
        return self._bridge.invoke(
            "youtube_music.add_tracks", {"playlist_id": playlist_id, "video_ids": list(video_ids)}
        )

    def resolve_media(self, media_path: str, *, use_account_auth: bool = False) -> dict[str, Any]:
        """Resolve a playable URL through KeyTune's configured yt-dlp runtime."""
        self.require(PluginPermission.YT_DLP)
        if use_account_auth:
            self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke(
            "yt_dlp.resolve", {"media_path": media_path, "use_account_auth": use_account_auth}
        )

    def yt_dlp_info(
        self,
        media_path: str,
        *,
        flat_playlist: bool = False,
        playlist_limit: int = 100,
        use_account_auth: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Extract metadata with KeyTune's managed yt-dlp executable."""
        self.require(PluginPermission.YT_DLP)
        if use_account_auth:
            self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke(
            "yt_dlp.info",
            {
                "media_path": media_path,
                "flat_playlist": flat_playlist,
                "playlist_limit": playlist_limit,
                "use_account_auth": use_account_auth,
            },
        )

    def yt_dlp_download(
        self,
        media_path: str,
        destination_directory: str,
        *,
        format_selector: str = "best[ext=mp4]/best",
        filename_template: str = "%(title).200B [%(id)s].%(ext)s",
        playlist: bool = False,
        playlist_limit: int = 100,
        use_account_auth: bool = False,
    ) -> list[str]:
        """Download media with yt-dlp after explicit filesystem consent."""
        self.require(PluginPermission.YT_DLP)
        self.require(PluginPermission.FILESYSTEM_WRITE)
        if use_account_auth:
            self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke(
            "yt_dlp.download",
            {
                "media_path": media_path,
                "destination_directory": destination_directory,
                "format_selector": format_selector,
                "filename_template": filename_template,
                "playlist": playlist,
                "playlist_limit": playlist_limit,
                "use_account_auth": use_account_auth,
            },
        )

    def analyze_media(self, media_path: str, *, use_account_auth: bool = False) -> dict[str, Any]:
        """Analyze a local or remote track through the shared AutoDJ cache."""
        self.require(PluginPermission.AUTODJ_ANALYZE)
        if use_account_auth:
            self.require(PluginPermission.YOUTUBE_MUSIC_READ)
        return self._bridge.invoke(
            "autodj.analyze", {"media_path": media_path, "use_account_auth": use_account_auth}
        )

    def notify(self, message: str) -> None:
        self.require(PluginPermission.NOTIFICATIONS)
        self._bridge.invoke("notifications.show", {"message": message})

    def request(self, url: str, *, method: str = "GET", body: str | None = None) -> dict[str, Any]:
        self.require(PluginPermission.NETWORK)
        return self._bridge.invoke("network.request", {"url": url, "method": method, "body": body})

    def read_text(self, path: str, *, encoding: str = "utf-8", max_bytes: int = 2 * 1024 * 1024) -> str:
        """Read a text file through the permission-checked host."""
        self.require(PluginPermission.FILESYSTEM_READ)
        return self._bridge.invoke(
            "filesystem.read_text", {"path": path, "encoding": encoding, "max_bytes": max_bytes}
        )

    def write_text(self, path: str, text: str, *, encoding: str = "utf-8") -> None:
        """Write a reasonably sized text file through the host."""
        self.require(PluginPermission.FILESYSTEM_WRITE)
        self._bridge.invoke(
            "filesystem.write_text", {"path": path, "text": text, "encoding": encoding}
        )

    def clipboard_text(self) -> str:
        self.require(PluginPermission.CLIPBOARD)
        return self._bridge.invoke("clipboard.read_text", {})

    def set_clipboard_text(self, text: str) -> None:
        self.require(PluginPermission.CLIPBOARD)
        self._bridge.invoke("clipboard.write_text", {"text": text})

    def get_setting(self, key: str, default: Any = None) -> Any:
        self.require(PluginPermission.SETTINGS)
        return self._bridge.invoke("settings.get", {"key": key, "default": default})

    def set_setting(self, key: str, value: Any) -> None:
        self.require(PluginPermission.SETTINGS)
        self._bridge.invoke("settings.set", {"key": key, "value": value})

    def add_menu_action(self, identifier: str, label: str, callback: Callable[[], None], *, submenu: str = "") -> None:
        self.require(PluginPermission.UI_MENU)
        self._bridge.register_contribution("menu", {"id": identifier, "label": label, "submenu": submenu, "callback": callback})

    def add_tab(self, identifier: str, label: str, factory: Callable[[Any], Any]) -> None:
        self.require(PluginPermission.UI_TAB)
        self._bridge.register_contribution("tab", {"id": identifier, "label": label, "factory": factory})

    def add_view(self, identifier: str, label: str, factory: Callable[[Any], Any]) -> None:
        self.require(PluginPermission.UI_VIEW)
        self._bridge.register_contribution("view", {"id": identifier, "label": label, "factory": factory})
