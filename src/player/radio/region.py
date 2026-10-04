"""País do usuário, para a lista de rádios começar pelo que está perto dele."""

import locale
import sys


def _windows_region():
    import ctypes

    kernel32 = ctypes.windll.kernel32
    code_buffer = ctypes.create_unicode_buffer(16)
    if kernel32.GetUserDefaultGeoName(code_buffer, len(code_buffer)) <= 0:
        return "", ""
    country_code = code_buffer.value.strip().upper()

    geo_friendly_name = 8
    name_buffer = ctypes.create_unicode_buffer(128)
    if kernel32.GetGeoInfoEx(country_code, geo_friendly_name, name_buffer, len(name_buffer)) <= 0:
        return country_code, ""
    return country_code, name_buffer.value.strip()


def _locale_region():
    language_code = locale.getlocale()[0] or ""
    _language, separator, territory = language_code.partition("_")
    return territory.strip().upper() if separator else ""


def default_radio_region():
    """Devolve ``(código ISO de duas letras, nome do país)``; vazios quando não dá para saber."""
    country_code = ""
    country_name = ""
    if sys.platform.startswith("win"):
        try:
            country_code, country_name = _windows_region()
        except Exception:
            country_code, country_name = "", ""
    if not country_code:
        try:
            country_code = _locale_region()
        except Exception:
            country_code = ""

    if len(country_code) != 2 or not country_code.isalpha():
        return "", ""
    return country_code, country_name or country_code
