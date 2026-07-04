"""Робота з буфером обміну Windows із контролем історії (Win+V).

За замовчуванням текст кладеться в буфер, але виключається з історії Win+V та
хмарного буфера. Якщо include_in_history=True — навпаки, дозволяється потрапити в історію.
"""

import ctypes
from ctypes import wintypes

import pyperclip

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

try:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.EmptyClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _user32.SetClipboardData.restype = wintypes.HANDLE
    _user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    _user32.RegisterClipboardFormatW.restype = wintypes.UINT

    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalLock.restype = wintypes.LPVOID
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalUnlock.restype = wintypes.BOOL
    _WINAPI_OK = True
except (AttributeError, OSError):
    _WINAPI_OK = False


def _alloc(data: bytes):
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    ptr = _kernel32.GlobalLock(h)
    ctypes.memmove(ptr, data, len(data))
    _kernel32.GlobalUnlock(h)
    return h


def _alloc_dword(value: int):
    return _alloc(int(value).to_bytes(4, "little"))


def set_text(text: str, include_in_history: bool = False):
    """Кладе text у буфер обміну; керує потраплянням у історію Win+V.

    Падає назад на pyperclip, якщо Win32 API недоступний або стався збій.
    """
    if not _WINAPI_OK:
        pyperclip.copy(text)
        return

    if not _user32.OpenClipboard(None):
        pyperclip.copy(text)
        return
    try:
        _user32.EmptyClipboard()
        # Сам текст (UTF-16LE з нуль-термінатором).
        _user32.SetClipboardData(
            CF_UNICODETEXT, _alloc(text.encode("utf-16-le") + b"\x00\x00")
        )
        # Якщо історія дозволена — копіюємо як звичайний буфер (без прапорців),
        # щоб текст гарантовано потрапив у Win+V (як стандартне копіювання).
        # Якщо ні — додаємо прапорці-виключення (0), щоб НЕ потрапляв у Win+V/хмару.
        if not include_in_history:
            for fmt_name in ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard"):
                fmt = _user32.RegisterClipboardFormatW(fmt_name)
                if fmt:
                    _user32.SetClipboardData(fmt, _alloc_dword(0))
    except Exception:  # noqa: BLE001
        pyperclip.copy(text)
    finally:
        _user32.CloseClipboard()
