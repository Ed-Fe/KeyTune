"""Localization (i18n) core for KeyTune.

KeyTune is written *Portuguese-first*: the source strings embedded in the code
(the ``msgid`` of every ``_()`` call) are Brazilian Portuguese. This module wires
those strings to GNU ``gettext`` catalogs so the interface can be localized into
other languages without rewriting the source. When no catalog is active, ``_()``
simply returns the original Portuguese text, so the app keeps working exactly as
before even with no translation files present.

Design notes
------------
* ``pt_BR`` is the *source* language. It never needs a catalog — the msgids are
  already Portuguese. Translators add catalogs for the other languages listed in
  :data:`SUPPORTED_LANGUAGES`.
* :func:`gettext` (aliased to ``_``) delegates to the *currently active*
  translation object, so importing ``_`` once and calling it later always
  reflects the language selected at startup.
* The module has **no third-party dependencies** and never imports wx, so it is
  safe to set up very early in ``main`` — before any UI module is imported.
* Compiled catalogs live in ``locale/<language>/LC_MESSAGES/keytune.mo`` next to
  the project root (development) or next to the executable (frozen build).
"""

from __future__ import annotations

import builtins
import gettext as _gettext
import os
import sys
from pathlib import Path

DOMAIN = "keytune"

# The language the source strings are written in. No catalog is required for it.
SOURCE_LANGUAGE = "pt_BR"

# Sentinel preference value meaning "follow the operating system language".
AUTOMATIC_LANGUAGE = "auto"

# Languages the project knows how to present, mapped to their native display
# name (shown in the preferences picker). Adding a new language is a matter of
# adding an entry here plus a compiled catalog under ``locale/``.
SUPPORTED_LANGUAGES = {
    "pt_BR": "Português (Brasil)",
    "en": "English",
}

# Prefixes used to map an operating-system locale (e.g. ``en_US``) onto one of
# the supported languages above.
_LANGUAGE_PREFIX_ALIASES = {
    "pt": "pt_BR",
    "en": "en",
}

_active_translation: _gettext.NullTranslations = _gettext.NullTranslations()
_active_language: str = SOURCE_LANGUAGE


def gettext(message: str) -> str:
    """Translate *message* using the active catalog (identity when none)."""

    return _active_translation.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Plural-aware translation using the active catalog."""

    return _active_translation.ngettext(singular, plural, n)


# Short alias matching the conventional gettext ``_`` used throughout the code.
_ = gettext


def locale_directories() -> list[Path]:
    """Return candidate ``locale`` directories, most specific first."""

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "locale")

    # src/player/i18n.py -> parents[2] is the repository root.
    candidates.append(Path(__file__).resolve().parents[2] / "locale")
    candidates.append(Path.cwd() / "locale")

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def normalize_language(language: str | None) -> str:
    """Map an arbitrary language tag onto a supported language code.

    Returns the matching :data:`SUPPORTED_LANGUAGES` key, or
    :data:`SOURCE_LANGUAGE` when nothing matches.
    """

    raw = str(language or "").strip().replace("-", "_")
    if not raw:
        return SOURCE_LANGUAGE

    # Exact match (case-insensitive on the region part, e.g. pt_br -> pt_BR).
    for code in SUPPORTED_LANGUAGES:
        if raw.lower() == code.lower():
            return code

    prefix = raw.split("_", 1)[0].lower()
    return _LANGUAGE_PREFIX_ALIASES.get(prefix, SOURCE_LANGUAGE)


def detect_system_language() -> str:
    """Best-effort detection of the operating-system language.

    Reads the usual locale environment variables first (honoured on every
    platform and by screen-reader users who set them explicitly), then falls
    back to the C library locale. Always resolves to a supported language.
    """

    for env_var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env_var)
        if value:
            # LANGUAGE may hold a colon-separated priority list.
            first = value.split(":", 1)[0].split(".", 1)[0]
            normalized = normalize_language(first)
            if first and normalized != SOURCE_LANGUAGE:
                return normalized
            if first:
                return normalized

    try:
        import locale as _locale

        code = None
        try:
            code = _locale.getlocale(_locale.LC_MESSAGES)[0]
        except (AttributeError, ValueError):
            code = None
        if not code:
            # getdefaultlocale is deprecated but still the most portable probe
            # for the system UI language across Python versions.
            try:
                code = _locale.getdefaultlocale()[0]
            except (ValueError, AttributeError):
                code = None
        if code:
            return normalize_language(code)
    except Exception:  # pragma: no cover - defensive, locale layer is finicky
        pass

    return SOURCE_LANGUAGE


def available_languages() -> list[str]:
    """List languages that can actually be presented right now.

    The source language is always available; every other supported language is
    offered only when a compiled catalog is found for it.
    """

    available = [SOURCE_LANGUAGE]
    for directory in locale_directories():
        for code in SUPPORTED_LANGUAGES:
            if code in available:
                continue
            if _gettext.find(DOMAIN, str(directory), languages=[code]):
                available.append(code)
    return available


def language_display_name(code: str) -> str:
    """Native display name for *code*, falling back to the code itself."""

    return SUPPORTED_LANGUAGES.get(code, code)


def _load_translation(language: str) -> tuple[_gettext.NullTranslations, str]:
    if language == SOURCE_LANGUAGE:
        return _gettext.NullTranslations(), SOURCE_LANGUAGE

    for directory in locale_directories():
        try:
            translation = _gettext.translation(DOMAIN, str(directory), languages=[language])
        except OSError:
            continue
        return translation, language

    # No catalog available — show the Portuguese source text.
    return _gettext.NullTranslations(), SOURCE_LANGUAGE


def setup_translation(language: str | None = None) -> str:
    """Activate the catalog for *language* and install ``_`` globally.

    *language* may be an explicit code (``"en"``, ``"pt_BR"``), the
    :data:`AUTOMATIC_LANGUAGE` sentinel / an empty value (auto-detect), or any OS
    locale tag. Returns the language code that ended up active so callers can,
    for example, report it.
    """

    global _active_translation, _active_language

    requested = str(language or "").strip()
    if not requested or requested.lower() in (AUTOMATIC_LANGUAGE, "system", "automatic", "default"):
        resolved_request = detect_system_language()
    else:
        resolved_request = normalize_language(requested)

    translation, active = _load_translation(resolved_request)
    _active_translation = translation
    _active_language = active

    # Expose ``_`` and ``ngettext`` as builtins too, so the occasional module
    # that uses a bare ``_(...)`` without importing it still resolves.
    builtins.__dict__.setdefault("_", gettext)
    builtins.__dict__["_"] = gettext
    builtins.__dict__["ngettext"] = ngettext

    return active


def get_active_language() -> str:
    """Return the language code currently driving translations."""

    return _active_language
