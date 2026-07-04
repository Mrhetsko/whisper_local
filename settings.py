"""Налаштування застосунку: дефолти + читання/запис у JSON (%APPDATA%)."""

import json
import os

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WhisperDictation")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

# Варіанти для випадаючих списків у вікні налаштувань.
MODEL_CHOICES = ["tiny", "base", "small", "medium"]
LANGUAGE_CHOICES = ["auto", "en", "uk"]

DEFAULTS = {
    "model_size": "base",        # tiny/base/small/medium
    "language": "en",            # "auto" | "en" | "uk"
    "device": "cpu",             # cpu | cuda (лише NVIDIA)
    "compute_type": "int8",
    "hotkey": "ctrl+alt+z",      # глобальний toggle-хоткей
    "auto_paste": True,          # авто-вставка (Ctrl+V) в активне поле
    "clipboard_history": False,  # зберігати в історію буфера Windows (Win+V)
    "sound_enabled": True,       # звуковий сигнал на старт/стоп/скасування
    "idle_unload": True,         # вивантажувати модель після простою
    "idle_minutes": 10,          # таймаут простою (хв)
    "sample_rate": 16000,
    "channels": 1,
}


class Settings:
    """Простий контейнер налаштувань з підвантаженням/збереженням у JSON."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Зберігаємо лише відомі ключі, решту ігноруємо.
            for k in DEFAULTS:
                if k in saved:
                    self._data[k] = saved[k]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self):
        os.makedirs(APP_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)
