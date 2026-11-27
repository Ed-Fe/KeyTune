# KeyTune

A music and video player for Windows, made for people who use a keyboard and a screen reader. It plays local files, YouTube and YouTube Music, online radio and podcasts, downloads and converts media, shows lyrics and has an AutoDJ.

[![Latest release](https://img.shields.io/github/v/release/Ed-Fe/KeyTune?label=latest%20release)](https://github.com/Ed-Fe/KeyTune/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Ed-Fe/KeyTune/total?label=downloads)](https://github.com/Ed-Fe/KeyTune/releases)
[![License: MIT](https://img.shields.io/github/license/Ed-Fe/KeyTune)](LICENSE)

**[Download KeyTune](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe)** · [Manual](docs/manual.en.md) · [What's new](docs/changelog/) · [Português](README.pt-BR.md)

## What it does

- Plays audio and video with speed, pitch and output device control. Playlists live in tabs, with a queue, a folder browser and `.m3u` support.
- Library with global search (`Ctrl+G`), favorites, ratings, history and smart playlists. Podcasts and audiobooks pick up where you left off.
- KeyTube (`Ctrl+Shift+Y`): YouTube and YouTube Music in one list, with search, your playlists, subscriptions, comments, live chat, notifications, chapters and transcripts. SponsorBlock is available, off by default.
- Online radio from [Radio Browser](https://www.radio-browser.info/), by country, genre and language (`Ctrl+Shift+N`).
- Downloads songs, videos and playlists with [yt-dlp](https://github.com/yt-dlp/yt-dlp) (`Ctrl+Shift+B`) and converts between formats with FFmpeg (`Ctrl+Shift+K`).
- Lyrics for the current track (`Ctrl+Alt+L`), an equalizer, a sleep timer and an AutoDJ that mixes on the beat.
- Every shortcut can be changed. There are global hotkeys, a tray icon and plugins (see the [plugin guide](docs/plugins.en.md)).
- Interface in English, Portuguese and Spanish.

It is built and tested with NVDA. KeyTune speaks what changes (track, volume, time), and you choose which announcements you want. When you open it again, your tabs, track and position come back as they were.

## Installing

Download [KeyTune-Setup.exe](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe) and run it. It runs on 64-bit Windows. If you'd rather not install, use [KeyTune-Portable.zip](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Portable.zip): extract it and open `KeyTune.exe` (see [portable version](docs/manual.en.md#portable-version)).

YouTube and the AutoDJ are installed separately, from **Preferences > Additional resources**.

## Getting started

- `Ctrl+O` opens files; `Ctrl+V` plays what you copied (a file, folder or link).
- `Space` plays and pauses, `Ctrl+PageUp` and `Ctrl+PageDown` change tracks, the up and down arrows change the volume.
- `T`, `V` and `S` speak the time, volume and status.
- `F1` lists the shortcuts and `Ctrl+,` opens preferences.

Everything else is in the [manual](docs/manual.en.md), which also opens from the **Help** menu. If something won't play, **Help > Diagnostics** shows what's wrong.

## Running from source

You need Windows, [uv](https://docs.astral.sh/uv/) and Git.

```powershell
git clone https://github.com/Ed-Fe/KeyTune.git
cd KeyTune
uv sync
uv run python scripts/download_mpv_runtime.py
uv run keytune
```

The MPV script uses 7-Zip to extract. Tests: `python -m unittest discover -s tests`. The Windows build comes from `scripts/build_windows_release.ps1`.

## Contributing

- Bugs: [open an issue](https://github.com/Ed-Fe/KeyTune/issues/new/choose) and, if you can, attach the **Help > Diagnostics** report.
- Ideas and questions: [discussions](https://github.com/Ed-Fe/KeyTune/discussions).
- Code: read [CONTRIBUTING.md](CONTRIBUTING.md).
- Translations: see the [translation guide](docs/translations.md).

## Credits

Created by [Eduardo Ferreira](https://github.com/Ed-Fe). [Vinicius Siqueira](https://github.com/viniciusSiqueira195) and [Paulo](https://github.com/paulosantesso1) contributed the most, along with [reffehcsoibaf](https://github.com/reffehcsoibaf). The full list of contributors and libraries is in [docs/credits.en.md](docs/credits.en.md).

Built on [MPV](https://mpv.io/), [wxPython](https://wxpython.org/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ytmusicapi](https://github.com/sigma67/ytmusicapi), [YouTube.js](https://github.com/LuanRT/YouTube.js), [FFmpeg](https://ffmpeg.org/), [librosa](https://librosa.org/), [Radio Browser](https://www.radio-browser.info/), [LRCLIB](https://lrclib.net/) and [SponsorBlock](https://sponsor.ajay.app/).

Some of the code was written with help from AI assistants (GitHub Copilot, OpenAI Codex and Claude Code).

## License

[MIT](LICENSE).
