"""Notificação silenciosa na central de notificações do Windows via ``Shell_NotifyIconW``.

O ``wx.adv.NotificationMessage`` no Windows sempre dispara o som de notificação
ou balão do próprio sistema porque o wxWidgets não expõe ``NIIF_NOSOUND``.
Este módulo envia a notificação com ``NIIF_NOSOUND`` para que o texto apareça
na central de notificações (lido pelo leitor de tela e clicável), enquanto o
som tocado continua sendo apenas o som de aviso configurado no KeyTune.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys

from .constants import APP_TITLE
from .log import get_logger


_logger = get_logger(__name__)

_NIM_ADD = 0x00000000
_NIM_MODIFY = 0x00000001
_NIM_DELETE = 0x00000002

_NIF_MESSAGE = 0x00000001
_NIF_ICON = 0x00000002
_NIF_TIP = 0x00000004
_NIF_INFO = 0x00000010

_NIIF_INFO = 0x00000001
_NIIF_NOSOUND = 0x00000010

_WM_DESTROY = 0x0002
_WM_USER = 0x0400
_WM_APP = 0x8000
_CALLBACK_MESSAGE = _WM_APP + 0x31

_NIN_BALLOONHIDE = _WM_USER + 3
_NIN_BALLOONTIMEOUT = _WM_USER + 4
_NIN_BALLOONUSERCLICK = _WM_USER + 5

_IDI_APPLICATION = 32512
_ERROR_CLASS_ALREADY_EXISTS = 1410

_WINDOW_CLASS_NAME = "KeyTuneSilentNotificationWindow"
_ICON_UID = 0x4B54

_LRESULT = ctypes.c_ssize_t
_WPARAM = ctypes.c_size_t
_LPARAM = ctypes.c_ssize_t
_WNDPROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    _LRESULT, wintypes.HWND, wintypes.UINT, _WPARAM, _LPARAM
)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", _GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


_INSTANCES: dict[int, "SilentWindowsNotifier"] = {}
_WIN32_APIS = None
_WINDOW_PROC_REF = None
_CLASS_REGISTERED = False


def _fit_text(text: str, limit: int) -> str:
    """Ajusta *text* ao tamanho do campo Win32 (em caracteres, deixando espaço para o NUL)."""
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return normalized[: limit - 3].rstrip() + "..."


def _load_win32_apis():
    global _WIN32_APIS
    if _WIN32_APIS is not None:
        return _WIN32_APIS

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, _WPARAM, _LPARAM]
    user32.DefWindowProcW.restype = _LRESULT

    user32.RegisterClassExW.argtypes = [ctypes.POINTER(_WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND

    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL

    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
    user32.LoadIconW.restype = wintypes.HICON

    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.DestroyIcon.restype = wintypes.BOOL

    shell32.ExtractIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT]
    shell32.ExtractIconW.restype = wintypes.HICON

    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(_NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL

    _WIN32_APIS = (kernel32, user32, shell32)
    return _WIN32_APIS


def _window_proc(hwnd, msg, wparam, lparam):
    instance = _INSTANCES.get(int(hwnd))
    if instance is not None:
        if msg == _CALLBACK_MESSAGE:
            instance._handle_tray_callback(int(lparam))
            return 0
        if msg == _WM_DESTROY:
            _INSTANCES.pop(int(hwnd), None)
    _, user32, _ = _load_win32_apis()
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _ensure_window_class(user32, hinstance):
    global _CLASS_REGISTERED, _WINDOW_PROC_REF
    if _CLASS_REGISTERED:
        return True
    _WINDOW_PROC_REF = _WNDPROC(_window_proc)
    wndclass = _WNDCLASSEXW(
        cbSize=ctypes.sizeof(_WNDCLASSEXW),
        lpfnWndProc=_WINDOW_PROC_REF,
        hInstance=hinstance,
        lpszClassName=_WINDOW_CLASS_NAME,
    )
    atom = user32.RegisterClassExW(ctypes.byref(wndclass))
    if not atom and ctypes.get_last_error() != _ERROR_CLASS_ALREADY_EXISTS:
        return False
    _CLASS_REGISTERED = True
    return True


def _dispatch_click(callback):
    try:
        import wx

        wx.CallAfter(callback)
    except Exception:
        callback()


class SilentWindowsNotifier:
    """Mostra notificações na central de notificações do Windows sem tocar som do sistema."""

    def __init__(self):
        self._hwnd = None
        self._hicon = None
        self._owns_icon = False
        self._icon_added = False
        self._on_click = None

    def _ensure_resources(self) -> bool:
        if self._hwnd:
            return True
        kernel32, user32, shell32 = _load_win32_apis()
        hinstance = kernel32.GetModuleHandleW(None)
        if not _ensure_window_class(user32, hinstance):
            return False
        hwnd = user32.CreateWindowExW(
            0, _WINDOW_CLASS_NAME, "", 0, 0, 0, 0, 0, None, None, hinstance, None
        )
        if not hwnd:
            return False

        hicon = None
        owns_icon = False
        if getattr(sys, "frozen", False):
            extracted = shell32.ExtractIconW(hinstance, sys.executable, 0)
            if extracted and int(extracted) > 1:
                hicon = extracted
                owns_icon = True
        if not hicon:
            hicon = user32.LoadIconW(None, ctypes.cast(ctypes.c_void_p(_IDI_APPLICATION), wintypes.LPCWSTR))

        self._hwnd = hwnd
        self._hicon = hicon
        self._owns_icon = owns_icon
        _INSTANCES[int(hwnd)] = self
        return True

    def _build_data(self, *, title="", message="", include_info=False) -> _NOTIFYICONDATAW:
        flags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        if include_info:
            flags |= _NIF_INFO
        return _NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(_NOTIFYICONDATAW),
            hWnd=self._hwnd,
            uID=_ICON_UID,
            uFlags=flags,
            uCallbackMessage=_CALLBACK_MESSAGE,
            hIcon=self._hicon or 0,
            szTip=_fit_text(APP_TITLE, 127),
            szInfo=_fit_text(message, 255) if include_info else "",
            szInfoTitle=_fit_text(title, 63) if include_info else "",
            dwInfoFlags=(_NIIF_INFO | _NIIF_NOSOUND) if include_info else 0,
        )

    def _delete_icon(self):
        if not self._icon_added or not self._hwnd:
            self._icon_added = False
            return
        _, _, shell32 = _load_win32_apis()
        data = _NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(_NOTIFYICONDATAW),
            hWnd=self._hwnd,
            uID=_ICON_UID,
        )
        shell32.Shell_NotifyIconW(_NIM_DELETE, ctypes.byref(data))
        self._icon_added = False

    def _handle_tray_callback(self, event_code: int):
        if event_code == _NIN_BALLOONUSERCLICK:
            callback = self._on_click
            self._on_click = None
            self._delete_icon()
            if callable(callback):
                _dispatch_click(callback)
        elif event_code in (_NIN_BALLOONTIMEOUT, _NIN_BALLOONHIDE):
            self._on_click = None
            self._delete_icon()

    def show(self, title: str, message: str, on_click=None) -> bool:
        """Exibe a notificação silenciosa no Windows; ``False`` fora do Windows ou se falhar."""
        if not sys.platform.startswith("win"):
            return False
        try:
            if not self._ensure_resources():
                return False
            _, _, shell32 = _load_win32_apis()
            self._on_click = on_click
            data = self._build_data(title=title, message=message, include_info=True)
            if self._icon_added and shell32.Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(data)):
                return True
            self._icon_added = False
            if shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(data)):
                self._icon_added = True
                return True
        except Exception as exc:
            _logger.info("The silent Windows notification could not be shown: %s", exc)
        self._on_click = None
        return False

    def close(self):
        """Remove qualquer ícone temporário da bandeja e libera a janela auxiliar."""
        self._on_click = None
        if not sys.platform.startswith("win"):
            return
        try:
            self._delete_icon()
            _, user32, _ = _load_win32_apis()
            if self._hwnd:
                _INSTANCES.pop(int(self._hwnd), None)
                user32.DestroyWindow(self._hwnd)
                self._hwnd = None
            if self._owns_icon and self._hicon:
                user32.DestroyIcon(self._hicon)
            self._hicon = None
            self._owns_icon = False
        except Exception:
            pass
