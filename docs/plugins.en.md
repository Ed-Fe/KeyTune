# KeyTune 2 plugins

Languages: [English](plugins.en.md) · [Português](plugins.md) · [Español](plugins.es.md). See also the [user manual](manual.en.md). HTML versions of these guides ship in the player's `docs` directory.

KeyTune 2 provides a public, permission-based API, manifest discovery, an accessible manager, verified packages, and a marketplace maintained through GitHub pull requests.

## Creating a plugin

A `.ktplugin` package is a ZIP with `keytune-plugin.json` at its root:

```json
{
  "id": "org.example.my-plugin",
  "name": "My plugin",
  "version": "1.0.0",
  "api_version": "2.0",
  "minimum_keytune_version": "2.0.0",
  "entrypoint": "plugin:Plugin",
  "author": "Example",
  "description": "An example integration.",
  "license": "MIT",
  "isolation": "process",
  "permissions": ["playback.read", "notifications", "ui.menu"]
}
```

The entrypoint receives the API in its constructor and can implement `on_start()`, `on_event(name, data)`, and `on_stop()`.

```python
class Plugin:
    def __init__(self, api):
        self.api = api

    def on_start(self):
        self.api.add_menu_action("announce", "Announce track", self.announce)

    def announce(self):
        state = self.api.playback_state()
        self.api.notify(state.get("media_path") or "Nothing playing")
```

The maintained example in [examples/plugins/now-playing](https://github.com/Ed-Fe/KeyTune/tree/main/examples/plugins/now-playing) demonstrates menus, two views, playback, library access, and private settings. Run `python scripts/package_example_plugin.py` from the source checkout to generate `examples/plugins/now-playing/now-playing-example-1.1.0.ktplugin`.

## Lifecycle and isolation

In `process` mode, menu callbacks execute in the worker: the host stores the action ID and forwards `ui.action`. A worker plugin can also handle that event directly. wxPython tab/view factories require `in_process`, which is why the maintained example uses that mode.

`in_process` runs inside KeyTune and requires fully trusted code. The default `process` mode separates ordinary failures, removes sensitive inherited environment variables, and accesses player resources through the versioned API. Plugins remain ordinary Python and can directly use files, networking, subprocesses, and libraries. **Process isolation is not a security sandbox for untrusted code.**

Calls are synchronous. In-process plugins must run network requests, yt-dlp, and analysis outside the UI thread, then marshal UI updates through wxPython. Isolated plugins make RPC calls from their worker. Returned API data is JSON-compatible and does not expose mutable internal player objects. `api.data_directory` provides the plugin's private data path; API helpers do not prevent direct use of Python libraries.

Stable events are `playback.media_changed` (path, title, artist, playlist index), `tab.changed` (index), and `ui.action` (registered action ID). `on_start()` runs after session restoration, so loaded playlists are already available.

## Permissions and API 2.0 reference

Before installation or update, KeyTune displays the manifest details, permissions, and isolation mode. Confirmation installs and activates the plugin with those permissions. Calls without the required permission raise `PermissionDeniedError`.

| Method | Permission | Result |
| --- | --- | --- |
| `playback_state()` | `playback.read` | Media, position, volume, speed, pitch, and state |
| `playback(action, **arguments)` | `playback.control` | `play_pause`, `stop`, `next`, or `previous` |
| `playlists()` / `active_playlist()` | `library.read` | Loaded tabs, items, labels, and selection |
| `library_search(query, limit=50)` | `library.read` | Smart library records |
| `add_to_playlist(media_paths, playlist_index=None)` | `library.write` | Number added |
| `youtube_music_account()` | `youtube_music.read` | Connection and account name, never cookies |
| `youtube_music_search(query, scope="music_songs")` | `youtube_music.read` | Normalized search results |
| `youtube_music_playlists(limit=100)` | `youtube_music.read` | Connected account's playlists |
| `youtube_music_playlist(playlist_id)` | `youtube_music.read` | Normalized playlist contents |
| `youtube_music_rate(media_path, rating)` | `youtube_music.write` | Rate media |
| `youtube_music_create_playlist(title, description="", video_ids=())` | `youtube_music.write` | Created playlist ID |
| `youtube_music_add_tracks(playlist_id, video_ids)` | `youtube_music.write` | Add tracks to an account playlist |
| `resolve_media(media_path, use_account_auth=False)` | `yt_dlp` | Playable URL and metadata without sensitive headers/cookies |
| `yt_dlp_info(media_path, flat_playlist=False, playlist_limit=100, use_account_auth=False)` | `yt_dlp` | Metadata, formats, or playlist entries |
| `yt_dlp_download(media_path, destination_directory, ...)` | `yt_dlp` + `filesystem.write` | Final downloaded file paths |
| `analyze_media(media_path, use_account_auth=False)` | `autodj.analyze` | BPM, beat grid, confidence, energy, and key |
| `request(url, method="GET", body=None)` | `network` | HTTP response, limited to 2 MB |
| `read_text(path, encoding="utf-8", max_bytes=2097152)` | `filesystem.read` | External text, limited to 2 MB |
| `write_text(path, text, encoding="utf-8")` | `filesystem.write` | Write external text, limited to 2 MB |
| `clipboard_text()` / `set_clipboard_text(text)` | `clipboard` | Read/write clipboard text |
| `get_setting(key, default=None)` / `set_setting(key, value)` | `settings` | Atomic private JSON settings |
| `notify(message)` | `notifications` | Accessible announcement |
| `add_menu_action(identifier, label, callback, submenu="")` | `ui.menu` | Register a menu action |
| `add_tab(identifier, label, factory)` | `ui.tab` | wxPython tab, in-process only |
| `add_view(identifier, label, factory)` | `ui.view` | wxPython view, in-process only |

Optional parameters shown after the main arguments must be passed by keyword, except `library_search`'s `limit` and `get_setting`'s `default`. See the [API source](https://github.com/Ed-Fe/KeyTune/blob/main/src/player/plugins/api.py) for exact signatures.

## Loaded library and YouTube Music

`playlists()` returns currently open playlists and folders, including visible items and labels. `library_search()` returns an empty list when the smart library is disabled. YouTube Music methods reuse KeyTune's session and services without exposing cookies, authentication files, or sensitive headers. Rating media, creating playlists, and adding tracks require the separate `youtube_music.write` permission.

## yt-dlp and online AutoDJ

KeyTune manages the official yt-dlp executable; plugins do not receive a Python `YoutubeDL` object. `yt_dlp_info()` and `yt_dlp_download()` reuse that executable and the player's JavaScript runtimes. Authentication is anonymous by default. `use_account_auth=True` additionally requires `youtube_music.read` and reuses protected credentials internally.

```python
info = api.yt_dlp_info("https://www.youtube.com/watch?v=...")
files = api.yt_dlp_download(
    "https://www.youtube.com/watch?v=...",
    r"C:\Users\user\Videos",
    format_selector="best[ext=mp4]/best",
)
```

Download keyword options are `format_selector="best[ext=mp4]/best"`, `filename_template="%(title).200B [%(id)s].%(ext)s"`, `playlist=False`, `playlist_limit=100`, and `use_account_auth=False`. Filename templates cannot contain directory components; arbitrary command-line arguments are not accepted. The default prefers progressive MP4 to avoid an external FFmpeg dependency. Combining separate video/audio streams requires a compatible FFmpeg executable.

Use `resolve_media()` when only a playable URL is needed. `analyze_media()` accepts local files, URLs, and YouTube Music references. Private online content requires account authentication and `youtube_music.read`. Online analysis downloads at most 120 MB into temporary storage, passes necessary headers internally, decodes with PyAV's bundled FFmpeg codecs, and analyzes with librosa 0.11. Remote results remain cached for seven days; temporary media is removed immediately. Analysis covers at most the first 15 minutes.

librosa supplies beat tracking, onset strength, RMS, and chroma features. PyAV avoids requiring an external FFmpeg executable for analysis. Unsupported decoding fails independently of ordinary playback. Install the required optional YouTube/AutoDJ resources through KeyTune's preferences before using these services.

## GitHub marketplace

The [community repository](https://github.com/Ed-Fe/keytune-plugins) maintains `catalog.json` with `schema_version: 1` and a `plugins` list. Entries contain `id`, `name`, `version`, `description`, `author`, `homepage`, HTTPS `download_url`, `sha256`, and `verified`.

1. Publish the `.ktplugin` in a GitHub Release.
2. Calculate the final file's SHA-256.
3. Submit a pull request adding/updating the catalog entry with `verified: false`.
4. Pass validation of schema, unique IDs, HTTPS, checksum, manifest, and compatibility.
5. Maintainers may grant `verified` after reviewing provenance; it is not a security guarantee.

The client downloads outside the UI thread, requires HTTPS after redirects, limits catalog/package/extracted sizes, blocks ZIP traversal and dangerous Windows names, checks SHA-256/ID/version, and installs transactionally. After package validation it shows the actual manifest and permissions before installation and activation, including verified status.

## Compatibility

KeyTune 2.0.0 introduces `api_version: "2.0"`. The major API number defines incompatible changes. Minor versions add methods/events; removal requires a major version and prior deprecation notice. Ignore unknown events and fields. Store private data by plugin ID without relying on internal player structures.

## Diagnostics and distribution

Failures are logged in `plugin-logs/<id>.log`. Installed packages live in `plugins/<id>`; consent/state lives in `plugins/registry.json`, under KeyTune's user data directory. Never include secrets in packages or manifests. Publish a new version instead of replacing an already cataloged release asset.
