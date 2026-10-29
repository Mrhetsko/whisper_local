"""Глобальний хоткей через Win32 RegisterHotKey.

На відміну від низькорівневого хука клавіатури (бібліотека keyboard), хоткей
обробляє сама Windows: він не «відвалюється», коли процес зайнятий розпізнаванням,
і не ламається після блокування екрана (Win+L), UAC чи сну. WM_HOTKEY приходить
у чергу повідомлень головного потоку, тож колбек викликається вже в GUI-потоці.
"""

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000  # не повторювати, поки комбінацію тримають
VK_ESCAPE = 0x1B

MODIFIERS = {
    "alt": 0x0001,
    "ctrl": 0x0002, "control": 0x0002,
    "shift": 0x0004,
    "win": 0x0008, "windows": 0x0008,
}

# Іменовані клавіші → virtual-key код. Літери, цифри та F1–F24 обчислюються окремо.
KEYS = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
    "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
    "insert": 0x2D, "ins": 0x2D, "delete": 0x2E, "del": 0x2E,
    "home": 0x24, "end": 0x23,
    "page up": 0x21, "pageup": 0x21, "pgup": 0x21,
    "page down": 0x22, "pagedown": 0x22, "pgdn": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "pause": 0x13, "print screen": 0x2C, "printscreen": 0x2C,
    ";": 0xBA, "=": 0xBB, "plus": 0xBB, ",": 0xBC, "-": 0xBD, "minus": 0xBD,
    ".": 0xBE, "/": 0xBF, "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short


def parse_hotkey(combo):
    """'ctrl+alt+z' → (модифікатори, virtual-key). ValueError, якщо не розпізнано."""
    mods = 0
    vk = None
    for part in (p.strip().lower() for p in combo.split("+")):
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
        elif vk is not None or not part:
            raise ValueError(f"некоректний хоткей: {combo!r}")
        elif len(part) == 1 and (part.isascii() and part.isalnum()):
            vk = ord(part.upper())  # VK літер/цифр збігається з ASCII, розкладка не впливає
        elif part[0] == "f" and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        elif part in KEYS:
            vk = KEYS[part]
        else:
            raise ValueError(f"невідома клавіша {part!r} у хоткеї {combo!r}")
    if vk is None:
        raise ValueError(f"у хоткеї {combo!r} немає основної клавіші")
    return mods, vk


def is_key_down(vk):
    """Чи натиснута клавіша просто зараз (без хука, не перехоплює її в інших програм)."""
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


class GlobalHotkey(QAbstractNativeEventFilter):
    """Один глобальний хоткей; callback викликається в головному потоці."""

    _ID = 1

    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self._registered = False
        QCoreApplication.instance().installNativeEventFilter(self)

    def register(self, combo):
        """Реєструє комбінацію (замінюючи попередню). ValueError/OSError при невдачі."""
        mods, vk = parse_hotkey(combo)
        self.unregister()
        if not _user32.RegisterHotKey(None, self._ID, mods | MOD_NOREPEAT, vk):
            raise ctypes.WinError(ctypes.get_last_error())
        self._registered = True

    def unregister(self):
        if self._registered:
            _user32.UnregisterHotKey(None, self._ID)
            self._registered = False

    def nativeEventFilter(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self._ID:
            self._callback()
            return True, 0
        return False, 0
