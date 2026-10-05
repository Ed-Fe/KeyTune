from .models import AppSettings
from .storage import load_settings, save_settings

__all__ = ["AppSettings", "AudioOutputDialog", "PreferencesDialog", "load_settings", "save_settings"]


def __getattr__(name):
    # The dialogs pull in most of the UI. Loading them on first use keeps the
    # quick player, which only reads the settings, from paying for them.
    if name == "PreferencesDialog":
        from .dialog import PreferencesDialog

        return PreferencesDialog
    if name == "AudioOutputDialog":
        from .audio_output_dialog import AudioOutputDialog

        return AudioOutputDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
