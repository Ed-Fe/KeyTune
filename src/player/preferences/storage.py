import json
import os

from ..log import get_logger
from ..session import get_app_storage_dir
from .models import AppSettings


_logger = get_logger(__name__)
SETTINGS_FILE_NAME = "settings.json"


def load_settings():
    settings_path = os.path.join(_get_storage_dir(), SETTINGS_FILE_NAME)
    if not os.path.exists(settings_path):
        return AppSettings()

    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            payload = json.load(settings_file)
    except (json.JSONDecodeError, OSError) as exc:
        _logger.warning("Failed to load settings from %s: %s", settings_path, exc)
        return AppSettings()

    if not isinstance(payload, dict):
        return AppSettings()

    return AppSettings.from_dict(payload)


def save_settings(settings):
    settings_path = os.path.join(_get_storage_dir(), SETTINGS_FILE_NAME)
    try:
        with open(settings_path, "w", encoding="utf-8") as settings_file:
            json.dump(settings.to_dict(), settings_file, ensure_ascii=False, indent=2)
    except OSError as exc:
        _logger.error("Failed to save settings to %s: %s", settings_path, exc)


def _get_storage_dir():
    return get_app_storage_dir()
