"""Minimal isolated-process lifecycle runner.

The process boundary prevents a crash from taking down the player. It is not an
OS sandbox: users must still trust plugin code for the permissions shown.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import uuid


class WorkerAPI:
    """Synchronous JSON-RPC facade available inside an isolated plugin."""

    def __init__(self, context):
        self.plugin_id = context["plugin_id"]
        self.data_directory = Path(context["data_directory"])
        self.permissions = frozenset(context["permissions"])
        self._menu_callbacks = {}

    def invoke(self, method, **arguments):
        request_id = uuid.uuid4().hex
        sys.stdout.write(json.dumps({"type": "request", "id": request_id, "method": method, "arguments": arguments}) + "\n")
        sys.stdout.flush()
        while True:
            response = json.loads(sys.stdin.readline())
            if response.get("type") == "response" and response.get("id") == request_id:
                if response.get("error"):
                    raise RuntimeError(response["error"])
                return response.get("result")

    def playback_state(self): return self.invoke("playback.state")
    def playback(self, action, **arguments): return self.invoke("playback.control", action=action, **arguments)
    def library_search(self, query, limit=50): return self.invoke("library.search", query=query, limit=limit)
    def playlists(self): return self.invoke("library.playlists")
    def active_playlist(self): return self.invoke("library.active_playlist")
    def add_to_playlist(self, media_paths, playlist_index=None): return self.invoke("library.add_to_playlist", media_paths=media_paths, playlist_index=playlist_index)
    def youtube_music_account(self): return self.invoke("youtube_music.account")
    def youtube_music_search(self, query, scope="music_songs"): return self.invoke("youtube_music.search", query=query, scope=scope)
    def youtube_music_playlists(self, limit=100): return self.invoke("youtube_music.playlists", limit=limit)
    def youtube_music_playlist(self, playlist_id): return self.invoke("youtube_music.playlist", playlist_id=playlist_id)
    def youtube_music_rate(self, media_path, rating): return self.invoke("youtube_music.rate", media_path=media_path, rating=rating)
    def youtube_music_create_playlist(self, title, description="", video_ids=()): return self.invoke("youtube_music.create_playlist", title=title, description=description, video_ids=list(video_ids))
    def youtube_music_add_tracks(self, playlist_id, video_ids): return self.invoke("youtube_music.add_tracks", playlist_id=playlist_id, video_ids=list(video_ids))
    def resolve_media(self, media_path): return self.invoke("yt_dlp.resolve", media_path=media_path)
    def yt_dlp_info(self, media_path, flat_playlist=False, playlist_limit=100):
        return self.invoke("yt_dlp.info", media_path=media_path, flat_playlist=flat_playlist, playlist_limit=playlist_limit)
    def yt_dlp_download(self, media_path, destination_directory, format_selector="best[ext=mp4]/best", filename_template="%(title).200B [%(id)s].%(ext)s", playlist=False, playlist_limit=100):
        return self.invoke("yt_dlp.download", media_path=media_path, destination_directory=destination_directory, format_selector=format_selector, filename_template=filename_template, playlist=playlist, playlist_limit=playlist_limit)
    def analyze_media(self, media_path): return self.invoke("autodj.analyze", media_path=media_path)
    def notify(self, message): return self.invoke("notifications.show", message=message)
    def request(self, url, method="GET", body=None): return self.invoke("network.request", url=url, method=method, body=body)
    def get_setting(self, key, default=None): return self.invoke("settings.get", key=key, default=default)
    def set_setting(self, key, value): return self.invoke("settings.set", key=key, value=value)
    def add_menu_action(self, identifier, label, callback=None, *, submenu=""):
        if callable(callback):
            self._menu_callbacks[str(identifier)] = callback
        return self.invoke("ui.register_menu", id=identifier, label=label, submenu=submenu)


def main():
    first = json.loads(sys.stdin.readline())
    context = first["context"]
    sys.path.insert(0, context["plugin_path"])
    module_name, object_name = context["entrypoint"].split(":", 1)
    api = WorkerAPI(context)
    instance = getattr(importlib.import_module(module_name), object_name)(api)
    if hasattr(instance, "on_start"):
        instance.on_start()
    sys.stdout.write(json.dumps({"type": "ready"}) + "\n")
    sys.stdout.flush()
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "event":
            event = message["event"]
            payload = message.get("payload", {})
            callback = api._menu_callbacks.get(str(payload.get("id", ""))) if event == "ui.action" else None
            if callback:
                callback()
            elif hasattr(instance, "on_event"):
                instance.on_event(event, payload)
    if hasattr(instance, "on_stop"):
        instance.on_stop()


if __name__ == "__main__":
    main()
