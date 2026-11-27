# KeyTune

**A keyboard-first music and video player for Windows, built for screen readers.**
Local files, YouTube and YouTube Music, online radio, downloads, lyrics and an AutoDJ, all in one window you can drive without ever touching the mouse.

[![Latest release](https://img.shields.io/github/v/release/Ed-Fe/KeyTune?label=latest%20release)](https://github.com/Ed-Fe/KeyTune/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Ed-Fe/KeyTune/total?label=downloads)](https://github.com/Ed-Fe/KeyTune/releases)
[![License: MIT](https://img.shields.io/github/license/Ed-Fe/KeyTune)](LICENSE)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)

**[Download KeyTune for Windows](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe)** · [User manual](docs/manual.en.md) · [What's new](docs/changelog/) · [Leia em português](README.pt-BR.md)

<!-- Screenshot: add docs/images/main-window.png (main window with a playlist and the time panel) and uncomment the line below.
![KeyTune main window with a playlist open and the time panel at the bottom](docs/images/main-window.png)
-->

## Why KeyTune

- **Every feature works from the keyboard.** Playback, playlists, search, YouTube, radio, downloads and settings all have shortcuts, and you can change any of them.
- **Made for screen readers.** Built and tested with NVDA. Every field, button, list and group has a proper name, focus never jumps to the video area, and KeyTune speaks what changes (track, volume, time, status) through your screen reader. You decide which notices speak.
- **One player instead of five.** Your music folder, YouTube, YouTube Music, radio stations from around the world and podcasts live side by side, in tabs.
- **Picks up where you left off.** Tabs, the current track, the position and the volume come back the next time you open it.

## Features

### Playback and library

- Audio and video playback powered by [MPV](https://mpv.io/), with speed and pitch control and audio output selection.
- Playlists in tabs, `.m3u` and `.m3u8` support, a playback queue and a folder explorer next to the tabs (`Ctrl+E`).
- Smart library: global search across your indexed music (`Ctrl+G`), favorites, star ratings, playback history and smart playlists built from rules.
- Resume per file for podcasts, audiobooks and long videos, with a "continue listening" list.
- Lyrics panel that finds the lyrics of the current track on its own (`Ctrl+Alt+L`).
- Equalizer with built-in and custom presets, sleep timer and full-screen video (`Alt+Enter`).
- A quick player: press `Enter` on a song in File Explorer and it plays right away in a small window.

### KeyTube: YouTube and YouTube Music

- YouTube and YouTube Music in one accessible list (`Ctrl+Shift+Y`): search, your playlists and mixes, likes, history, subscriptions, channels and trending.
- Comments, live chat, notifications, chapters and transcripts, all readable and writable from the keyboard.
- Live broadcasts, Shorts, a radio from the current track (`Ctrl+R`) and resume that stays in sync with your phone and TV.
- [SponsorBlock](https://sponsor.ajay.app/) support to skip sponsor segments and the non-music parts of music videos (off by default).

### Radio, downloads and conversion

- Online radio from the open [Radio Browser](https://www.radio-browser.info/) directory, with favorites and browsing by country, genre and language (`Ctrl+Shift+N`).
- Download songs, videos and whole playlists from YouTube and YouTube Music with [yt-dlp](https://github.com/yt-dlp/yt-dlp), in the original quality, MP3 or FLAC (`Ctrl+Shift+B`).
- Convert audio and video between formats with FFmpeg (`Ctrl+Shift+K`), one file or many at once.

### AutoDJ

- An optional AutoDJ that mixes your playlist like a DJ: it analyzes tempo, beats, phrases, key and loudness, and lines up each transition on the beat.

### Make it yours

- Customize every shortcut, with conflict checks (**Settings > Customize keyboard**).
- Global shortcuts that work while KeyTune is minimized, a system tray icon and Windows media controls.
- Alert sounds for events, which you can turn off or replace with your own.
- Plugins with explicit permissions, a plugin manager and a community marketplace. See the [plugin guide](docs/plugins.en.md).
- Interface in Portuguese, English and Spanish.

## Installation

1. Download **[KeyTune-Setup.exe](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe)** from the [latest release](https://github.com/Ed-Fe/KeyTune/releases/latest).
2. Run it. You can install for your user only, without administrator rights, or for every user of the computer.
3. On the additional tasks page you can create a desktop shortcut and associate audio, video and playlist formats with KeyTune. All of these are optional.

To skip the installer, download **[KeyTune-Portable.zip](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Portable.zip)** from the same release, extract it to a folder or a USB drive and open `KeyTune.exe`. Settings and downloads stay in the `data` folder next to the program. The `portable.ini` file in that folder turns this mode on. See [Portable version](docs/manual.en.md#portable-version) in the manual.

KeyTune runs on 64-bit Windows. The installer already includes the MPV runtime, so it plays right away. The YouTube integration and the AutoDJ are optional downloads: KeyTune lists what it will install and asks before downloading anything (**Settings > Preferences > Additional resources**).

KeyTune updates itself. When a new version comes out, it shows what changed, in your language, and asks before downloading and installing it.

## First steps

- `Ctrl+O` opens files, and `Ctrl+V` plays a file, a folder or a link you copied.
- `Space` plays or pauses, `Ctrl+PageUp` and `Ctrl+PageDown` change tracks, and the up and down arrows change the volume.
- `T`, `V` and `S` say the time, the volume and the status.
- `F1` opens the quick shortcuts help at any time.
- `Ctrl+,` opens the preferences.

The full list is in the [user manual](docs/manual.en.md), which you can also open inside KeyTune from the **Help** menu. If something doesn't play, **Help > Diagnostics** tells you what is wrong and what to do.

## Building from source

You need Windows, [uv](https://docs.astral.sh/uv/) and Git. uv installs Python 3.14 for you.

```powershell
git clone https://github.com/Ed-Fe/KeyTune.git
cd KeyTune
uv sync
uv run python scripts/download_mpv_runtime.py
uv run keytune
```

- `uv sync` creates `.venv` with the exact versions from `uv.lock`, including the optional YouTube and AutoDJ dependencies.
- `scripts/download_mpv_runtime.py` downloads the latest libmpv build into `./mpv/` and needs 7-Zip to unpack it. If you already have libmpv, point `MPV_HOME` or `MPV_DLL_DIR` to it instead.
- `iniciar_player.bat` is a shortcut that runs `uv run keytune` for you.

Run the tests with `python -m unittest discover -s tests`. The Windows release (app, MPV runtime and Inno Setup installer) is built by `.github/workflows/release-windows.yml`, or locally with `scripts/build_windows_release.ps1`.

## Contributing

Bug reports, ideas, translations and code are all welcome.

- Found a bug? [Open an issue](https://github.com/Ed-Fe/KeyTune/issues/new/choose). The report from **Help > Diagnostics** helps a lot.
- Have an idea or a question? Start a [discussion](https://github.com/Ed-Fe/KeyTune/discussions).
- Want to write code? Read [CONTRIBUTING.md](CONTRIBUTING.md) and look for issues labeled [good first issue](https://github.com/Ed-Fe/KeyTune/labels/good%20first%20issue).
- Want KeyTune in your language? See the [translation guide](docs/translations.md).

## Credits

KeyTune is created and maintained by [Eduardo Ferreira](https://github.com/Ed-Fe), with code contributions from [reffehcsoibaf](https://github.com/reffehcsoibaf) and [paulosantesso1](https://github.com/paulosantesso1). See everyone on the [contributors page](https://github.com/Ed-Fe/KeyTune/graphs/contributors).

KeyTune stands on the shoulders of [MPV](https://mpv.io/), [wxPython](https://wxpython.org/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ytmusicapi](https://github.com/sigma67/ytmusicapi), [YouTube.js](https://github.com/LuanRT/YouTube.js), [FFmpeg](https://ffmpeg.org/), [librosa](https://librosa.org/), [accessible-output2](https://pypi.org/project/accessible-output2/), [Radio Browser](https://www.radio-browser.info/), [LRCLIB](https://lrclib.net/) and [SponsorBlock](https://sponsor.ajay.app/). The full list of libraries is in [docs/credits.en.md](docs/credits.en.md).

The project is developed with the help of AI coding assistants, including GitHub Copilot, OpenAI Codex and Anthropic's Claude Code.

## License

KeyTune is free software under the [MIT License](LICENSE).
