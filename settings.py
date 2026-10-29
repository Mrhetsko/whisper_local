"""Налаштування застосунку: дефолти + читання/запис у JSON (%APPDATA%)."""

import json
import os

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WhisperDictation")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

# Варіанти для випадаючих списків у вікні налаштувань.
MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"]
# Приблизний розмір ваг на диску (≈ стільки ж займає у VRAM на GPU; на CPU int8 — менше).
MODEL_SIZES = {
    "tiny": "75 МБ",
    "base": "141 МБ",
    "small": "464 МБ",
    "medium": "1.5 ГБ",
    "large-v3-turbo": "1.6 ГБ",
    "large-v3": "2.9 ГБ",
}
LANGUAGE_CHOICES = ["auto", "en", "uk"]
# (значення, підпис) для вибору пристрою.
DEVICE_CHOICES = [
    ("auto", "Авто (NVIDIA, якщо є, інакше CPU)"),
    ("cuda", "NVIDIA GPU (CUDA)"),
    ("cpu", "CPU"),
]

DEFAULTS = {
    "model_size": "base",        # див. MODEL_CHOICES
    "language": "en",            # "auto" | "en" | "uk"
    "device": "auto",            # auto | cuda | cpu
    "hotkey": "ctrl+alt+z",      # глобальний toggle-хоткей
    "auto_paste": True,          # авто-вставка (Ctrl+V) в активне поле
    "clipboard_history": False,  # зберігати в історію буфера Windows (Win+V)
    "sound_enabled": True,       # звуковий сигнал на старт/стоп/скасування
    "gpu_unload": True,          # після простою вивантажувати модель з GPU (NVIDIA засинає)
    "gpu_unload_minutes": 5,     # таймаут простою для VRAM (хв)
    "idle_unload": True,         # вивантажувати модель після простою (будь-який пристрій)
    "idle_minutes": 120,         # таймаут простою (хв)
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
