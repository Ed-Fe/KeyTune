import queue
import threading
from importlib import import_module

import wx


_AUTO_OUTPUT_UNRESOLVED = object()
_auto_output_factory = _AUTO_OUTPUT_UNRESOLVED


def _resolve_auto_output_factory():
    """Import the optional accessible_output2 backend on first use.

    Importing accessible_output2 pulls in heavy platform helpers that noticeably
    slow down application startup. Resolving it lazily keeps that cost off the
    startup path; the announcer triggers this from its worker thread.
    """

    global _auto_output_factory
    if _auto_output_factory is _AUTO_OUTPUT_UNRESOLVED:
        try:
            accessible_output2_auto = import_module("accessible_output2.outputs.auto")
            _auto_output_factory = getattr(accessible_output2_auto, "Auto", None)
        except Exception:  # pragma: no cover - defensive guard for optional dependency
            _auto_output_factory = None
    return _auto_output_factory


class NamedControlAccessible(wx.Accessible):
    def __init__(self, window, name, description="", role=None, value_provider=None):
        super().__init__(window)
        self._window = window
        self._name = name
        self._description = description
        self._role = role
        self._value_provider = value_provider

    def GetName(self, childId):
        if childId != 0:
            return wx.ACC_NOT_IMPLEMENTED, ""
        return wx.ACC_OK, self._name

    def GetDescription(self, childId):
        if childId != 0:
            return wx.ACC_NOT_IMPLEMENTED, ""
        return wx.ACC_OK, self._description

    def GetHelpText(self, childId):
        if childId != 0:
            return wx.ACC_NOT_IMPLEMENTED, ""
        return wx.ACC_OK, self._description

    def GetRole(self, childId):
        if childId != 0 or self._role is None:
            return wx.ACC_NOT_IMPLEMENTED, 0
        return wx.ACC_OK, self._role

    def GetValue(self, childId):
        if childId != 0 or self._value_provider is None:
            return wx.ACC_NOT_IMPLEMENTED, ""

        try:
            value = self._value_provider()
        except Exception:
            return wx.ACC_NOT_IMPLEMENTED, ""

        return wx.ACC_OK, str(value)


def attach_named_accessible(window, name, description="", role=None, value_provider=None):
    if not hasattr(wx, "Accessible") or not hasattr(window, "SetAccessible"):
        return None

    accessible = NamedControlAccessible(
        window=window,
        name=name,
        description=description,
        role=role,
        value_provider=value_provider,
    )
    window.SetAccessible(accessible)
    return accessible


class ScreenReaderAnnouncer:
    def __init__(self, prefer_screen_reader_only=True):
        self._prefer_screen_reader_only = prefer_screen_reader_only
        self._queue = queue.Queue()
        self._stop_token = object()
        self._output = None
        self._close_event = threading.Event()
        # Optimistically enabled: the optional accessible_output2 backend is
        # resolved on the worker thread so its slow import never blocks startup.
        self._enabled = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def speak(self, message):
        if not self._enabled or not message:
            return

        self._queue.put(message)

    def close(self):
        self.request_close()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

    def request_close(self):
        # Signal shutdown without waiting, so the caller can let the worker wind
        # down in parallel with other shutdown work and join later.
        if not self._close_event.is_set():
            self._close_event.set()
            self._queue.put(self._stop_token)

    def _worker(self):
        auto_output_factory = _resolve_auto_output_factory()
        # The factory import can be slow; if close was requested meanwhile, bail
        # out immediately instead of constructing an output we will never use.
        if self._close_event.is_set():
            self._enabled = False
            return
        if auto_output_factory is None:
            self._enabled = False
            self._drain_queue()
            return

        try:
            self._output = auto_output_factory()
        except Exception:
            self._output = None
            self._enabled = False
            self._drain_queue()
            return

        if self._close_event.is_set():
            return

        while True:
            message = self._queue.get()
            if message is self._stop_token:
                break

            try:
                self._speak_message(message)
            except Exception:
                continue

    def _drain_queue(self):
        # Release any messages queued before the optional backend was found to
        # be unavailable so the queue does not grow without bound.
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _speak_message(self, message):
        if not self._output:
            return

        if self._prefer_screen_reader_only and hasattr(self._output, "is_system_output"):
            try:
                if self._output.is_system_output():
                    return
            except Exception:
                pass

        try:
            self._output.speak(message, interrupt=True)
            return
        except TypeError:
            pass
        except Exception:
            pass

        try:
            self._output.speak(message)
            return
        except Exception:
            pass

        try:
            self._output.output(message)
        except Exception:
            return
