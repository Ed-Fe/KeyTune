#!/usr/bin/env python3
"""Accessibility audit of every KeyTune screen (Windows only).

    uv run python scripts/audit_ui_accessibility.py

Builds each dialog and panel without showing it and asks Windows — through
MSAA, the same interface NVDA and JAWS read — what every control is called.
Reading the code is not enough: ``SetName`` alone, a label created in the wrong
order or a group box next to its controls all look right in the source and
still reach the screen reader as nothing.

It fails (exit code 1) when:

* a group box has no children, i.e. it is only a drawing around its controls
  and its name is never announced;
* a focusable control has no accessible name, or only the generic one wx gives
  it ("text", "filepicker", ...);
* a ``wx.Dialog``/``wx.Panel`` subclass under ``src/player`` is missing from
  ``SCREENS`` below — a new screen must be registered here to be audited.

The rules these checks enforce are explained in
``.github/instructions/ui-screens.instructions.md``.
"""

from __future__ import annotations

import ctypes
import pathlib
import re
import sys
import traceback
from types import SimpleNamespace

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if sys.platform != "win32":
    print("The UI accessibility audit reads MSAA and only runs on Windows; skipped.")
    sys.exit(0)

from ctypes import wintypes  # noqa: E402

import wx  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# --------------------------------------------------------------------------
# MSAA: what the screen reader actually receives
# --------------------------------------------------------------------------
class _GUID(ctypes.Structure):
    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]


class _VARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("r1", ctypes.c_ushort),
        ("r2", ctypes.c_ushort),
        ("r3", ctypes.c_ushort),
        ("val", ctypes.c_longlong),
        ("pad", ctypes.c_longlong),
    ]


_IID_IACCESSIBLE = _GUID(0x618736E0, 0x3C3D, 0x11CF, (ctypes.c_ubyte * 8)(0x81, 0x0C, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71))
_OBJID_CLIENT = 0xFFFFFFFC
_ACC_NAME_SLOT = 10
_ACC_DESCRIPTION_SLOT = 12
_oleacc = ctypes.windll.oleacc
_oleaut = ctypes.windll.oleaut32
_oleaut.SysFreeString.argtypes = [ctypes.c_void_p]


def _accessible_text(window, slot):
    pointer = ctypes.c_void_p()
    result = _oleacc.AccessibleObjectFromWindow(
        wintypes.HWND(window.GetHandle()),
        ctypes.c_ulong(_OBJID_CLIENT),
        ctypes.byref(_IID_IACCESSIBLE),
        ctypes.byref(pointer),
    )
    if result != 0 or not pointer:
        return None
    vtable = ctypes.cast(ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    getter = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, _VARIANT, ctypes.POINTER(ctypes.c_void_p))(vtable[slot])
    out = ctypes.c_void_p()
    getter(pointer, _VARIANT(3, 0, 0, 0, 0, 0), ctypes.byref(out))
    text = ctypes.wstring_at(out.value) if out.value else None
    if out.value:
        _oleaut.SysFreeString(out)
    return text


def accessible_name(window):
    return _accessible_text(window, _ACC_NAME_SLOT)


def accessible_description(window):
    return _accessible_text(window, _ACC_DESCRIPTION_SLOT)


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------
INPUT_CONTROLS = (
    wx.TextCtrl,
    wx.Choice,
    wx.ComboBox,
    wx.SpinCtrl,
    wx.SpinCtrlDouble,
    wx.ListBox,
    wx.ListCtrl,
    wx.CheckBox,
    wx.RadioBox,
    wx.Slider,
    wx.Button,
)

# Names wx hands out by default: reaching the screen reader, they mean the
# control was never really named.
GENERIC_NAMES = {
    "text",
    "textctrl",
    "choice",
    "combobox",
    "listbox",
    "listctrl",
    "check",
    "checkbox",
    "radiobox",
    "slider",
    "button",
    "filepicker",
    "wxspinctrl",
    "wxspinctrldouble",
    "spinctrl",
    "panel",
    "dialog",
}

# Known exceptions, each with the reason it is acceptable. Keys are
# ``(screen, control class)``; ``"*"`` matches every screen.
ALLOWED = {
    ("*", "SpinCtrlDouble"): (
        "wx wraps the field in an extra window that hides its name from MSAA; the screen must speak "
        "'label: value' on focus and on change instead (see equalizer/dialog.py)"
    ),
    ("YouTubeMusicTabPanel", "VirtualItemsListCtrl"): "named by the summary label above it, empty until the first load",
    ("RadioTabPanel", "VirtualItemsListCtrl"): "named by the summary label above it, empty until the first load",
}


def audit_window(screen, root, verbose=False):
    """Return the list of problems found under *root*."""
    problems = []
    boxes = []

    def walk(window, group):
        for child in window.GetChildren():
            if isinstance(child, wx.RadioBox):
                check(child, group)
            elif isinstance(child, wx.StaticBox):
                boxes.append(child)
                walk(child, child.GetLabel())
            elif isinstance(child, INPUT_CONTROLS):
                check(child, group)
            else:
                walk(child, group)

    def check(control, group):
        kind = type(control).__name__
        name = accessible_name(control)
        if verbose:
            description = accessible_description(control) or ""
            print(f"    [{group or '-'}] {kind}: {name!r}" + (f" — {description!r}" if description else ""))
        if name and name.strip() and name.strip().lower() not in GENERIC_NAMES:
            return
        if (screen, kind) in ALLOWED or ("*", kind) in ALLOWED:
            return
        hint = control.GetLabel() or control.GetName()
        problems.append(f"{kind} ({hint!r}) has no accessible name (MSAA returned {name!r})")

    walk(root, "")
    for box in boxes:
        if not box.GetChildren():
            problems.append(
                f"group '{box.GetLabel()}' has no children: create its controls with the box as parent (widgets.create_group)"
            )
    return problems


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------
def _noop(*_args, **_kwargs):
    return None


def _empty(*_args, **_kwargs):
    return []


def _manifest():
    return SimpleNamespace(
        id="example",
        name="Exemplo",
        version="1.0",
        author="Autor",
        description="",
        license="",
        homepage="",
        permissions=(),
        isolation="process",
    )


def _update_info():
    from player.update.service import UpdateInfo

    return UpdateInfo(
        current_version="1.0.0",
        latest_version="1.0.1",
        release_name="1.0.1",
        release_page_url="https://example.invalid",
        release_notes="Notas.",
        archive_name="KeyTune-Setup.exe",
        archive_url="https://example.invalid/KeyTune-Setup.exe",
        archive_size_bytes=1,
    )


def _build_screens():
    """Map each screen class name to a factory taking the parent window."""
    from player.about.dialog import AboutDialog
    from player.convert import dialog as convert_dialog
    from player.download.dialog import DownloadDialog
    from player.equalizer.dialog import EqualizerPresetDialog
    from player.equalizer.panel import EqualizerTabPanel
    from player.frames.autodj_panel import AutoDJSessionPanel
    from player.frames.lyrics_panel import LyricsPanel
    from player.library.browser import PlaylistBrowserPanel
    from player.library.search_dialog import ItemSearchDialog
    from player.playlists.queue_dialog import QueueManagerDialog
    from player.plugins.dialog import (
        InstallationConfirmationDialog,
        MarketplaceDialog,
        PermissionDialog,
        PluginManagerDialog,
    )
    from player.preferences.audio_output_dialog import AudioOutputDialog
    from player.preferences.dialog import PreferencesDialog
    from player.preferences.models import AppSettings
    from player.radio.panel import RadioTabPanel
    from player.sleep_timer.dialog import SleepTimerDialog
    from player.smart_library.history_dialog import PlaybackHistoryDialog
    from player.smart_library.search_dialog import GlobalSearchDialog
    from player.smart_library.smart_playlist_dialog import SmartPlaylistEditorDialog, SmartPlaylistManagerDialog
    from player.task_failures_dialog import TaskFailuresDialog
    from player.update.dialog import UpdateAvailableDialog, UpdateDownloadDialog
    from player.welcome.dialog import WelcomeDialog
    from player.youtube_music.dialog import (
        YouTubeMusicBrowserAuthDialog,
        YouTubeMusicCreatePlaylistDialog,
        YouTubeMusicJavascriptRuntimeDialog,
    )
    from player.youtube_music.panel import YouTubeMusicTabPanel

    plugin_service = SimpleNamespace(discover=_empty, runtimes={})

    def reading_dialog(parent):
        # ``show_reading_dialog`` is modal; its only field comes from ``add_reading_field``.
        from player.reading_dialog import add_reading_field

        dialog = wx.Dialog(parent)
        add_reading_field(dialog, wx.BoxSizer(wx.VERTICAL), "Detalhes", "texto")
        return dialog

    return {
        "AboutDialog": lambda parent: AboutDialog(parent),
        "AudioOutputDialog": lambda parent: AudioOutputDialog(parent, [], ""),
        "AutoDJSessionPanel": lambda parent: AutoDJSessionPanel(
            parent, on_replace_next=_noop, on_recalculate=_noop, on_toggle_preparation=_noop, on_stop=_noop
        ),
        "ConvertDialog": lambda parent: convert_dialog.ConvertDialog(
            parent, convert_dialog.MODE_VIDEO_TO_VIDEO, "video.mp4", settings=AppSettings()
        ),
        "DownloadDialog": lambda parent: DownloadDialog(parent, AppSettings()),
        "EqualizerPresetDialog": lambda parent: EqualizerPresetDialog(
            parent, title="Preset", intro_text="Preset", band_frequencies_hz=[60, 1000, 8000]
        ),
        "EqualizerTabPanel": lambda parent: EqualizerTabPanel(
            parent,
            on_toggle_enabled=_noop,
            on_select_preset=_noop,
            on_apply_to_all_tabs=_noop,
            on_create_preset=_noop,
            on_edit_preset=_noop,
            on_duplicate_preset=_noop,
            on_delete_preset=_noop,
        ),
        "GlobalSearchDialog": lambda parent: GlobalSearchDialog(parent, _empty),
        "InstallationConfirmationDialog": lambda parent: InstallationConfirmationDialog(parent, _manifest(), "arquivo"),
        "ItemSearchDialog": lambda parent: ItemSearchDialog(parent),
        "LyricsPanel": lambda parent: LyricsPanel(parent),
        "MarketplaceDialog": lambda parent: MarketplaceDialog(parent, [], {}),
        "PermissionDialog": lambda parent: PermissionDialog(parent, _manifest()),
        "PlaybackHistoryDialog": lambda parent: PlaybackHistoryDialog(parent, _empty),
        "PlaylistBrowserPanel": lambda parent: PlaylistBrowserPanel(parent, _noop, _noop),
        "PluginManagerDialog": lambda parent: PluginManagerDialog(parent, plugin_service),
        "PreferencesDialog": lambda parent: PreferencesDialog(parent, AppSettings()),
        "QueueManagerDialog": lambda parent: QueueManagerDialog(
            parent, get_entries=_empty, on_remove=_noop, on_move=_noop, on_clear=_noop
        ),
        "RadioTabPanel": lambda parent: RadioTabPanel(
            parent,
            search_scope_labels=["Nome", "País"],
            on_search=_noop,
            on_activate=_noop,
            on_browse=_noop,
            on_back=_noop,
            on_load_more=_noop,
            on_toggle_favorite=_noop,
            on_copy_stream_url=_noop,
            on_show_actions_menu=_noop,
        ),
        "ReadingDialog": reading_dialog,
        "SleepTimerDialog": lambda parent: SleepTimerDialog(parent),
        "SmartPlaylistEditorDialog": lambda parent: SmartPlaylistEditorDialog(parent),
        "SmartPlaylistManagerDialog": lambda parent: SmartPlaylistManagerDialog(parent, []),
        "TaskFailuresDialog": lambda parent: TaskFailuresDialog(parent, "Falhas", [("item", "motivo")]),
        "UpdateAvailableDialog": lambda parent: UpdateAvailableDialog(parent, _update_info()),
        "UpdateDownloadDialog": lambda parent: UpdateDownloadDialog(parent, _update_info()),
        "WelcomeDialog": lambda parent: WelcomeDialog(parent),
        "YouTubeMusicBrowserAuthDialog": lambda parent: YouTubeMusicBrowserAuthDialog(parent),
        "YouTubeMusicCreatePlaylistDialog": lambda parent: YouTubeMusicCreatePlaylistDialog(parent),
        "YouTubeMusicJavascriptRuntimeDialog": lambda parent: YouTubeMusicJavascriptRuntimeDialog(
            parent, winget_available=True
        ),
        "YouTubeMusicTabPanel": lambda parent: YouTubeMusicTabPanel(
            parent,
            on_connect=_noop,
            on_disconnect=_noop,
            on_refresh_library=_noop,
            on_search=_noop,
            on_add_search_results_to_current_playlist=_noop,
            on_show_search_actions_menu=_noop,
        ),
    }


# Screen classes audited through another entry, or not screens at all.
COVERED_ELSEWHERE = {
    "DownloadOptionsPanel": "audited inside DownloadDialog and PreferencesDialog",
}

_SCREEN_CLASS_PATTERN = re.compile(r"^class (\w+)\((?:wx\.Dialog|wx\.Panel)\b", re.MULTILINE)


def discover_screen_classes():
    names = set()
    for path in (SRC_ROOT / "player").rglob("*.py"):
        names.update(_SCREEN_CLASS_PATTERN.findall(path.read_text(encoding="utf-8")))
    return names


def main(argv):
    verbose = "--verbose" in argv or "-v" in argv
    app = wx.App(False)
    wx.Log.EnableLogging(False)
    parent = wx.Frame(None)
    screens = _build_screens()
    failures = {}

    missing = sorted(discover_screen_classes() - set(screens) - set(COVERED_ELSEWHERE))
    if missing:
        failures["(registry)"] = [
            f"{name} is a screen class not registered in SCREENS of scripts/audit_ui_accessibility.py" for name in missing
        ]

    for screen in sorted(screens):
        if verbose:
            print(f"  {screen}")
        try:
            window = screens[screen](parent)
        except Exception:
            failures[screen] = ["could not be built:\n" + traceback.format_exc(limit=4)]
            continue
        problems = audit_window(screen, window, verbose=verbose)
        if problems:
            failures[screen] = problems

    parent.Destroy()
    del app

    if failures:
        print("UI accessibility audit FAILED:")
        for screen, problems in failures.items():
            print(f"\n{screen}")
            for problem in problems:
                print(f"  - {problem}")
        print("\nSee .github/instructions/ui-screens.instructions.md for the rules and how to fix each case.")
        return 1

    print(f"UI accessibility audit OK: {len(screens)} screens, every control named and every group real.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
