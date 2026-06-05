import json
import logging
import os


_logger = logging.getLogger("keytune.session")
SESSION_FILE_NAME = "session.json"
APP_STORAGE_DIR = "KeyTune"
_LEGACY_APP_STORAGE_DIR = APP_STORAGE_DIR + "".join(("V", "L", "C"))


def _storage_base_dir():
    if os.name == "nt":
        return os.environ.get("APPDATA") or os.path.expanduser("~")

    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def get_app_storage_dir():
    base_dir = _storage_base_dir()
    storage_dir = os.path.join(base_dir, APP_STORAGE_DIR)
    legacy_storage_dir = os.path.join(base_dir, _LEGACY_APP_STORAGE_DIR)

    if not os.path.exists(storage_dir) and os.path.isdir(legacy_storage_dir):
        return legacy_storage_dir

    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def load_session():
    session_path = os.path.join(get_app_storage_dir(), SESSION_FILE_NAME)
    if not os.path.exists(session_path):
        return None

    try:
        with open(session_path, "r", encoding="utf-8") as session_file:
            return json.load(session_file)
    except (json.JSONDecodeError, OSError) as exc:
        _logger.warning("Failed to load session from %s: %s", session_path, exc)
        return None


def save_session(payload):
    session_path = os.path.join(get_app_storage_dir(), SESSION_FILE_NAME)
    try:
        with open(session_path, "w", encoding="utf-8") as session_file:
            json.dump(payload, session_file, ensure_ascii=False, indent=2)
    except OSError as exc:
        _logger.error("Failed to save session to %s: %s", session_path, exc)
