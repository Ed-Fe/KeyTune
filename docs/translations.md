# Translating KeyTune

KeyTune uses Python's standard translation system (GNU `gettext`). The
language the code is written in - **Portuguese (Brazil)** - is the source
language: every user-visible string appears in Portuguese inside the code, and
translations for other languages live in separate catalogs under `locale/`.

That means you **do not need to change the code** to add a language: you only
need to create a translation catalog.

English and Spanish are already available as examples in the repository.

## Structure

```
locale/
  keytune.pot                      # template with all program strings
  en/LC_MESSAGES/keytune.po        # editable translation for English
  en/LC_MESSAGES/keytune.mo        # compiled version loaded by the app
  es/LC_MESSAGES/keytune.po        # editable translation for Spanish
  es/LC_MESSAGES/keytune.mo        # compiled version loaded by the app
```

- `.pot` - template generated from the code. Do not translate this file; use it
  as the base for a new language.
- `.po` - the file you edit, with each `msgid` (source text in Portuguese) and
  its `msgstr` (your translation).
- `.mo` - the binary version compiled from the `.po`. This is what the
  application reads at runtime, so it **must be recompiled** whenever the `.po`
  changes.

## Adding a new language

1. Register the language in `src/player/i18n.py`, in the
   `SUPPORTED_LANGUAGES` dictionary (language code -> native name). Use codes
   such as `en`, `es`, `fr`, `pt_BR`.
2. Refresh the template from the current code:

   ```
   python scripts/i18n.py extract
   ```

3. Copy `locale/keytune.pot` to `locale/<language>/LC_MESSAGES/keytune.po` and
   translate each `msgstr`. Leave `msgstr ""` blank for strings you have not
   translated yet - the app falls back to Portuguese automatically.
4. Compile the catalogs:

   ```
   python scripts/i18n.py compile
   ```

5. Open KeyTune, go to *Settings > Preferences > General > Language*, and pick
   the new language (the change takes effect the next time the app starts).

## Translation tips

- **Menu accelerators** (`&`): the `&` marks the menu shortcut key
  (for example, `&File` -> Alt+F). Keep one `&` in your translation, ideally on
  a unique letter in each menu.
- **Tab-separated shortcuts** (`\t`): in texts like `Save\tCtrl+S`, the part
  after `\t` is the displayed shortcut. **Do not translate or alter** the
  shortcut.
- **Placeholders** (`{...}`): texts like `About {app}` or `Page {current} of
  {total}` contain fields filled in by the program. Keep the names inside the
  braces exactly as they are; only reorder them if it makes sense in your
  language.
- **Line breaks** (`\n`): preserve the line breaks from the source text.

## Manual, credits, and installer

- **Manual**: create `docs/manual.<language>.md` (for example,
  `docs/manual.en.md`). The build renders it to `manual.<language>.html`, and
  the app opens that version when the corresponding language is active, falling
  back to the Portuguese manual if the translation does not exist.
- **Credits**: the library and contributor lists are language-neutral; only the
  titles are translated. Add the language in `CREDITS_STRINGS` in
  `scripts/generate_credits.py`, and generate it with
  `python scripts/generate_credits.py --language <language>`.
- **Installer**: add the language in `[Languages]` and translate the entries in
  `[CustomMessages]` in `installer/keytune.iss` (the wizard texts come ready
  from the Inno Setup `.isl` files).

## `scripts/i18n.py`

It does not depend on `xgettext`/`msgfmt` being installed - it is pure Python:

- `python scripts/i18n.py extract` - scans `src/` and rewrites
  `locale/keytune.pot`.
- `python scripts/i18n.py compile` - compiles all `locale/**/keytune.po` files
  into `.mo`. The release build runs this automatically too.
