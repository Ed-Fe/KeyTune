"""Idioma e região do conteúdo do YouTube.

As preferências são da janela; quem busca, lista ou toca só pergunta aqui.
"""

import threading

from ..i18n import get_active_language
from .models import YOUTUBE_CHART_COUNTRIES, YOUTUBE_CHART_DEFAULT_COUNTRY_CODE


# Códigos que o YouTube aceita em ``hl``, com o nome que cada idioma dá a si mesmo.
CONTENT_LANGUAGES = (
    ("pt", "Português (Brasil)"),
    ("pt-PT", "Português (Portugal)"),
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("tr", "Türkçe"),
    ("ru", "Русский"),
    ("ar", "العربية"),
    ("hi", "हिन्दी"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("zh-CN", "中文 (简体)"),
)
CONTENT_LANGUAGE_CODES = tuple(code for code, _label in CONTENT_LANGUAGES)

# Os mesmos países do "Em alta", sem o Global.
CONTENT_REGIONS = tuple(
    (code, label) for code, label in YOUTUBE_CHART_COUNTRIES if code != YOUTUBE_CHART_DEFAULT_COUNTRY_CODE
)
CONTENT_REGION_CODES = tuple(code for code, _label in CONTENT_REGIONS)

_lock = threading.Lock()
_language = ""
_region = ""
_app_language = ""


def normalize_content_language(language):
    """O código como o YouTube espera, ou vazio para seguir o idioma do KeyTune."""
    wanted = str(language or "").strip().replace("_", "-").casefold()
    for code in CONTENT_LANGUAGE_CODES:
        if code.casefold() == wanted:
            return code
    return ""


def normalize_content_region(region):
    """O código do país, ou vazio para deixar o YouTube decidir."""
    wanted = str(region or "").strip().upper()
    return wanted if wanted in CONTENT_REGION_CODES else ""


def _from_app_language(app_language):
    """O idioma do conteúdo que corresponde a *app_language*, um idioma do KeyTune; vazio sem correspondência."""
    app_language = str(app_language or "").replace("-", "_")
    return normalize_content_language(app_language) or normalize_content_language(app_language.split("_")[0])


def configure_content_locale(*, language="", region="", app_language=""):
    """Guarda as preferências; devolve se alguma coisa mudou.

    *app_language* é o idioma escolhido para o KeyTune: ele só passa a valer na
    interface quando o player reabre, mas o conteúdo o segue na hora.
    """
    global _language, _region, _app_language

    language = normalize_content_language(language)
    region = normalize_content_region(region)
    app_language = _from_app_language(app_language)
    with _lock:
        changed = (language, region, app_language) != (_language, _region, _app_language)
        _language, _region, _app_language = language, region, app_language
    return changed


def content_language():
    """O idioma pedido ao YouTube: o escolhido ou, sem escolha, o do KeyTune."""
    with _lock:
        language = _language or _app_language
    return language or _from_app_language(get_active_language()) or "en"


def content_region():
    with _lock:
        return _region


def youtubejs_locale():
    """O idioma e a região que acompanham cada pedido ao YouTube.js."""
    return {"lang": content_language(), "location": content_region()}
