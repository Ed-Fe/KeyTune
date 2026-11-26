# Contributing to KeyTune

Thanks for wanting to help. KeyTune is used every day by people who rely on a screen reader and the keyboard, so every change has to keep working that way. This guide covers what you need to know before you send one.

[Leia em português](CONTRIBUTING.pt-BR.md)

## Ways to help

- **Report a bug** with the [bug report form](https://github.com/Ed-Fe/KeyTune/issues/new/choose). Paste the report from **Help > Diagnostics > Copy report** when the problem is about playback, YouTube or downloads.
- **Suggest a feature** with the feature request form, or start a [discussion](https://github.com/Ed-Fe/KeyTune/discussions) if the idea is still loose.
- **Translate** the interface, the manual or the installer. The [translation guide](docs/translations.md) explains the catalogs under `locale/`.
- **Write a plugin**. The [plugin guide](docs/plugins.en.md) covers the API, permissions and the marketplace.
- **Send code**. Issues labeled [good first issue](https://github.com/Ed-Fe/KeyTune/labels/good%20first%20issue) are a good place to start.

## Local setup

KeyTune runs on Windows. You need [uv](https://docs.astral.sh/uv/) and Git; uv installs Python 3.14 for you.

```powershell
git clone https://github.com/<your-user>/KeyTune.git
cd KeyTune
uv sync
uv run python scripts/download_mpv_runtime.py
uv run keytune
```

- `uv sync` creates `.venv` with the exact versions from `uv.lock`, including the optional YouTube and AutoDJ dependencies. Add a package with `uv add <package>` and upgrade with `uv lock --upgrade`.
- The MPV script needs 7-Zip. If you already have libmpv, point `MPV_HOME` or `MPV_DLL_DIR` to it instead.

## Rules every change follows

- **Keyboard first.** Every feature must be reachable from the keyboard. Keep existing shortcuts working, and never add a flow that needs the mouse.
- **Screen reader first.** Every field, button, list and group needs a name the screen reader announces. Focus must never land on the native video area. Announcements go through `src/player/accessibility.py`.
- **Building or changing a screen?** Read [`.github/instructions/ui-screens.instructions.md`](.github/instructions/ui-screens.instructions.md) first, build it with the helpers in `src/player/widgets.py` and `src/player/reading_dialog.py`, and register the new dialog or panel in the `SCREENS` list of the audit script.
- **Portuguese is the source language.** Every user-facing string (labels, menus, status, announcements) is written in Portuguese and wrapped in `_()`. After changing those strings, run `python scripts/i18n.py extract` and then `python scripts/i18n.py compile`, and add the English and Spanish translations.
- **One module, one job.** Keep UI, persistence, parsing and external services in separate modules, following the layout under `src/player/`. Windows-only code (`single_instance.py`, `file_associations.py`, `smtc/`) stays isolated and must fail gracefully on other systems.
- **Small and focused.** Prefer a targeted change over a broad refactor, and open an issue first if you plan a large one.

The architecture is described in [`.github/instructions/player-architecture.instructions.md`](.github/instructions/player-architecture.instructions.md).

## Checks before a pull request

- `python -m compileall src` for a quick syntax check.
- `python -m unittest discover -s tests` for backend, parsing and service changes.
- `uv run python scripts/audit_ui_accessibility.py` after any change to a dialog, panel, tab or preferences page. It checks that every control has an accessible name and that groups are real groups.
- A manual pass with a screen reader (NVDA is the reference) over the keyboard flows you touched.

## Changelog and manual

- Changes users will notice go into `docs/changelog/unreleased.md` (Portuguese), `unreleased.en.md` and `unreleased.es.md`. Keep the three in step.
- When a feature or shortcut changes, update `docs/manual.md`, `docs/manual.en.md` and `docs/manual.es.md`.
- Writing rules for both are in [`.github/instructions/writing.instructions.md`](.github/instructions/writing.instructions.md).

## Commits and pull requests

- Commit messages and PR titles are in English and follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`, in the imperative and lowercase, for example `fix(youtube): start playback at the chosen chapter`.
- Fill in the pull request template: what changed, why, how you tested it, and anything that affects accessibility, playback, playlists or the update flow.
- Keep one topic per pull request.

## License

By contributing, you agree that your contribution is released under the [MIT License](LICENSE).
