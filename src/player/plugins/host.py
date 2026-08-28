"""Supported mapping between public plugin RPC methods and player services."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .manifest import PluginManifest, PluginPermission

MAX_NETWORK_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024


def json_value(value):
    """Convert KeyTune models to stable JSON-compatible plugin values."""
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


METHOD_PERMISSIONS = {
    "playback.state": PluginPermission.PLAYBACK_READ,
    "playback.control": PluginPermission.PLAYBACK_CONTROL,
    "library.search": PluginPermission.LIBRARY_READ,
    "library.playlists": PluginPermission.LIBRARY_READ,
    "library.active_playlist": PluginPermission.LIBRARY_READ,
    "library.add_to_playlist": PluginPermission.LIBRARY_WRITE,
    "youtube_music.account": PluginPermission.YOUTUBE_MUSIC_READ,
    "youtube_music.search": PluginPermission.YOUTUBE_MUSIC_READ,
    "youtube_music.playlists": PluginPermission.YOUTUBE_MUSIC_READ,
    "youtube_music.playlist": PluginPermission.YOUTUBE_MUSIC_READ,
    "youtube_music.rate": PluginPermission.YOUTUBE_MUSIC_WRITE,
    "youtube_music.create_playlist": PluginPermission.YOUTUBE_MUSIC_WRITE,
    "youtube_music.add_tracks": PluginPermission.YOUTUBE_MUSIC_WRITE,
    "yt_dlp.resolve": frozenset({PluginPermission.YT_DLP}),
    "yt_dlp.info": frozenset({PluginPermission.YT_DLP}),
    "yt_dlp.download": frozenset({PluginPermission.YT_DLP, PluginPermission.FILESYSTEM_WRITE}),
    "autodj.analyze": PluginPermission.AUTODJ_ANALYZE,
    "notifications.show": PluginPermission.NOTIFICATIONS,
    "network.request": PluginPermission.NETWORK,
    "filesystem.read_text": PluginPermission.FILESYSTEM_READ,
    "filesystem.write_text": PluginPermission.FILESYSTEM_WRITE,
    "clipboard.read_text": PluginPermission.CLIPBOARD,
    "clipboard.write_text": PluginPermission.CLIPBOARD,
    "settings.get": PluginPermission.SETTINGS,
    "settings.set": PluginPermission.SETTINGS,
    "ui.register_menu": PluginPermission.UI_MENU,
}


class PluginHostAdapter:
    def __init__(self, frame, plugin_data_dir):
        self.frame = frame
        self.plugin_data_dir = Path(plugin_data_dir)

    def dispatch(self, method: str, arguments: dict, manifest: PluginManifest):
        raw_required = METHOD_PERMISSIONS.get(method)
        if raw_required is None:
            raise NotImplementedError(f"Método de plugin desconhecido: {method}")
        required = raw_required if isinstance(raw_required, frozenset) else frozenset({raw_required})
        missing = required.difference(manifest.permissions)
        if missing:
            names = ", ".join(sorted(permission.value for permission in missing))
            raise PermissionError(f"O plugin não declarou: {names}.")
        if (
            method in {"yt_dlp.resolve", "yt_dlp.info", "yt_dlp.download", "autodj.analyze"}
            and arguments.get("use_account_auth")
            and PluginPermission.YOUTUBE_MUSIC_READ not in manifest.permissions
        ):
            raise PermissionError("O uso da conta exige youtube_music.read.")
        handler = getattr(self, "_" + method.replace(".", "_"))
        return json_value(handler(arguments, manifest))

    def _playback_state(self, _arguments, _manifest):
        state = self.frame._get_active_playlist_state()
        player = getattr(self.frame, "player", None)
        return {
            "playing": bool(player and player.is_playing()),
            "media_path": getattr(state, "current_media_path", None),
            "position_ms": getattr(state, "last_position_ms", 0),
            "volume": self.frame.current_volume,
            "rate": self.frame.current_playback_rate,
            "pitch_semitones": self.frame.current_pitch_semitones,
            "playlist_index": self.frame._get_active_playlist_index(),
        }

    def _playback_control(self, arguments, _manifest):
        action = str(arguments.get("action", ""))
        handlers = {
            "play_pause": self.frame.on_play_pause,
            "stop": self.frame.on_stop,
            "next": self.frame.on_next_track,
            "previous": self.frame.on_previous_track,
        }
        if action not in handlers:
            raise ValueError("Ação de reprodução desconhecida.")
        handlers[action](None)
        return True

    def _library_playlists(self, _arguments, _manifest):
        result = []
        for index, state in enumerate(self.frame.playlists):
            if getattr(state, "is_screen_tab", False):
                continue
            result.append(self._playlist_value(state, index))
        return result

    def _library_active_playlist(self, _arguments, _manifest):
        state = self.frame._get_active_playlist_state()
        if state is None:
            return None
        return self._playlist_value(state, self.frame._get_active_playlist_index())

    @staticmethod
    def _playlist_value(state, index):
        return {
            "index": index,
            "title": state.title,
            "items": list(state.items),
            "item_labels": list(state.browser_item_labels),
            "current_index": state.current_index,
            "current_media_path": state.current_media_path,
            "source_path": state.source_path,
            "is_folder": state.is_folder_tab,
            "shuffle": state.shuffle_enabled,
            "repeat_mode": state.repeat_mode,
        }

    def _library_search(self, arguments, _manifest):
        service = self.frame._smart_library()
        if service is None:
            return []
        limit = max(1, min(500, int(arguments.get("limit", 50))))
        return service.search(str(arguments.get("query", "")), limit=limit)

    def _library_add_to_playlist(self, arguments, _manifest):
        paths = [str(item).strip() for item in arguments.get("media_paths", []) if str(item).strip()]
        requested_index = arguments.get("playlist_index")
        state = self.frame._get_playlist_state(requested_index) if requested_index is not None else self.frame._get_active_playlist_state()
        if state is None:
            raise ValueError("Playlist de destino inexistente.")
        state.append_items(paths)
        if state is self.frame._get_tab_state():
            self.frame._refresh_playlist_browser()
        return len(paths)

    def _youtube_service(self):
        return self.frame._get_youtube_music_service()

    def _youtube_music_account(self, _arguments, _manifest):
        service = self._youtube_service()
        authenticated = service.has_saved_browser_auth()
        return {
            "connected": authenticated,
            "name": service.get_connected_account_name() if authenticated else "",
        }

    def _youtube_music_search(self, arguments, _manifest):
        return self._youtube_service().search(
            str(arguments.get("query", "")),
            search_scope=str(arguments.get("scope", "music_songs")),
        )

    def _youtube_music_playlists(self, arguments, _manifest):
        limit = max(1, min(500, int(arguments.get("limit", 100))))
        value = self._youtube_service().get_user_library_playlists(limit=limit)
        return value[0] if isinstance(value, tuple) else value

    def _youtube_music_playlist(self, arguments, _manifest):
        playlist_id = str(arguments.get("playlist_id", "")).strip()
        if not playlist_id:
            raise ValueError("playlist_id é obrigatório.")
        return self._youtube_service().get_playlist_content(playlist_id, require_auth=False)

    def _youtube_music_rate(self, arguments, _manifest):
        rating = str(arguments.get("rating", "")).upper()
        if rating not in {"LIKE", "DISLIKE", "INDIFFERENT"}:
            raise ValueError("rating deve ser LIKE, DISLIKE ou INDIFFERENT.")
        return self._youtube_service().rate_media_feedback(str(arguments.get("media_path", "")), rating)

    def _youtube_music_create_playlist(self, arguments, _manifest):
        title = str(arguments.get("title", "")).strip()
        if not title:
            raise ValueError("O título da playlist é obrigatório.")
        return self._youtube_service().create_playlist(
            title,
            description=str(arguments.get("description", "")),
            video_ids=[str(item) for item in arguments.get("video_ids", [])],
        )

    def _youtube_music_add_tracks(self, arguments, _manifest):
        return self._youtube_service().add_tracks_to_playlist(
            str(arguments.get("playlist_id", "")),
            [str(item) for item in arguments.get("video_ids", [])],
        )

    def _yt_dlp_resolve(self, arguments, _manifest):
        from ..youtube_music.streams import resolve_stream_playback

        resolved = resolve_stream_playback(
            str(arguments.get("media_path", "")),
            use_account_cookies=bool(arguments.get("use_account_auth", False)),
        )
        # Authentication headers are deliberately not exposed to plugins.
        return {"stream_url": resolved.stream_url, "title": resolved.display_title, "artist": resolved.display_artist}

    def _yt_dlp_info(self, arguments, _manifest):
        from ..youtube_music.auth import load_saved_playback_auth
        from ..youtube_music.yt_dlp_runtime import extract_info, find_all_available_javascript_runtimes

        authentication = load_saved_playback_auth() if arguments.get("use_account_auth") else None
        response = extract_info(
            str(arguments.get("media_path", "")),
            cookie_file_path=authentication.cookie_file_path if authentication else "",
            http_headers=authentication.yt_dlp_http_headers if authentication else {},
            js_runtimes=find_all_available_javascript_runtimes(),
            noplaylist=not bool(arguments.get("flat_playlist", False)),
            extract_flat="in_playlist" if arguments.get("flat_playlist", False) else None,
            playlist_end=max(1, min(500, int(arguments.get("playlist_limit", 100)))),
            socket_timeout_seconds=20,
            no_warnings=True,
        )
        return response.data

    def _yt_dlp_download(self, arguments, _manifest):
        from ..youtube_music.auth import load_saved_playback_auth
        from ..youtube_music.yt_dlp_runtime import download_media, find_all_available_javascript_runtimes

        authentication = load_saved_playback_auth() if arguments.get("use_account_auth") else None
        return download_media(
            str(arguments.get("media_path", "")),
            destination_directory=str(arguments.get("destination_directory", "")),
            format_selector=str(arguments.get("format_selector", "")),
            filename_template=str(arguments.get("filename_template", "")),
            playlist=bool(arguments.get("playlist", False)),
            playlist_limit=max(1, min(500, int(arguments.get("playlist_limit", 100)))),
            cookie_file_path=authentication.cookie_file_path if authentication else "",
            http_headers=authentication.yt_dlp_http_headers if authentication else {},
            js_runtimes=find_all_available_javascript_runtimes(),
        )

    def _autodj_analyze(self, arguments, _manifest):
        from ..youtube_music.streams import resolve_stream_playback

        service = getattr(self.frame, "autodj_service", None)
        if service is None:
            raise RuntimeError("O serviço AutoDJ não está disponível.")
        use_account_auth = bool(arguments.get("use_account_auth", False))
        return service.analyze(
            str(arguments.get("media_path", "")),
            remote_resolver=lambda media_path: resolve_stream_playback(
                media_path, use_account_cookies=use_account_auth
            ),
        )

    def _notifications_show(self, arguments, _manifest):
        self.frame._announce(str(arguments.get("message", "")))

    def _network_request(self, arguments, _manifest):
        url = str(arguments.get("url", ""))
        if not url.startswith(("https://", "http://")):
            raise ValueError("Somente URLs HTTP e HTTPS são permitidas.")
        method = str(arguments.get("method", "GET")).upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("Método HTTP não permitido.")
        body = arguments.get("body")
        request = Request(url, data=None if body is None else str(body).encode("utf-8"), method=method)
        with urlopen(request, timeout=20) as response:
            payload = response.read(MAX_NETWORK_RESPONSE_BYTES + 1)
            if len(payload) > MAX_NETWORK_RESPONSE_BYTES:
                raise ValueError("A resposta excede o limite de 2 MB.")
            return {"status": response.status, "headers": dict(response.headers.items()), "body": payload.decode("utf-8", errors="replace")}

    @staticmethod
    def _filesystem_read_text(arguments, _manifest):
        path = Path(str(arguments.get("path", ""))).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        limit = max(1, min(MAX_TEXT_FILE_BYTES, int(arguments.get("max_bytes", MAX_TEXT_FILE_BYTES))))
        if path.stat().st_size > limit:
            raise ValueError(f"O arquivo excede o limite de {limit} bytes.")
        return path.read_text(encoding=str(arguments.get("encoding", "utf-8")))

    @staticmethod
    def _filesystem_write_text(arguments, _manifest):
        path = Path(str(arguments.get("path", ""))).expanduser()
        if not str(path).strip():
            raise ValueError("O caminho de destino é obrigatório.")
        payload = str(arguments.get("text", ""))
        encoding = str(arguments.get("encoding", "utf-8"))
        encoded = payload.encode(encoding)
        if len(encoded) > MAX_TEXT_FILE_BYTES:
            raise ValueError(f"O conteúdo excede o limite de {MAX_TEXT_FILE_BYTES} bytes.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        return True

    @staticmethod
    def _clipboard_read_text(_arguments, _manifest):
        import wx

        data = wx.TextDataObject()
        if not wx.TheClipboard.Open():
            raise RuntimeError("Não foi possível abrir a área de transferência.")
        try:
            return data.GetText() if wx.TheClipboard.GetData(data) else ""
        finally:
            wx.TheClipboard.Close()

    @staticmethod
    def _clipboard_write_text(arguments, _manifest):
        import wx

        if not wx.TheClipboard.Open():
            raise RuntimeError("Não foi possível abrir a área de transferência.")
        try:
            if not wx.TheClipboard.SetData(wx.TextDataObject(str(arguments.get("text", "")))):
                raise RuntimeError("Não foi possível alterar a área de transferência.")
            wx.TheClipboard.Flush()
        finally:
            wx.TheClipboard.Close()
        return True

    def _settings_path(self, manifest):
        directory = self.plugin_data_dir / manifest.id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "settings.json"

    def _settings(self, manifest):
        try:
            value = json.loads(self._settings_path(manifest).read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _settings_get(self, arguments, manifest):
        return self._settings(manifest).get(str(arguments.get("key", "")), arguments.get("default"))

    def _settings_set(self, arguments, manifest):
        values = self._settings(manifest)
        values[str(arguments.get("key", ""))] = arguments.get("value")
        path = self._settings_path(manifest)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return True

    def _ui_register_menu(self, arguments, manifest):
        return {"id": str(arguments["id"]), "label": str(arguments["label"]), "submenu": str(arguments.get("submenu", ""))}
