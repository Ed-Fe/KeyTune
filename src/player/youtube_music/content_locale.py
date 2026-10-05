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


def configure_content_locale(*, language="", region=""):
    """Guarda as preferências; devolve se alguma coisa mudou."""
    global _language, _region

    language = normalize_content_language(language)
    region = normalize_content_region(region)
    with _lock:
        changed = (language, region) != (_language, _region)
        _language, _region = language, region
    return changed


def content_language():
    """O idioma pedido ao YouTube: o escolhido ou, sem escolha, o do KeyTune."""
    with _lock:
        language = _language
    if language:
        return language
    app_language = str(get_active_language() or "").replace("-", "_")
    return (
        normalize_content_language(app_language)
        or normalize_content_language(app_language.split("_")[0])
        or "en"
    )


def content_region():
    with _lock:
        return _region


def youtubejs_locale():
    """O idioma e a região que acompanham cada pedido ao YouTube.js."""
    return {"lang": content_language(), "location": content_region()}
