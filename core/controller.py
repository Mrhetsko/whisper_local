"""Ядро логіки: стан-машина, хоткей, idle-вивантаження, авто-вставка, звук."""

import threading

import keyboard
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from core import clipboard

try:
    import winsound  # лише Windows
except ImportError:
    winsound = None

# Стани
IDLE = "idle"
RECORDING = "recording"
TRANSCRIBING = "transcribing"

# Частоти/тривалість сигналів: старт / завершення / скасування
BEEPS = {"start": (880, 90), "stop": (1245, 110), "cancel": (420, 160)}


class Controller(QObject):
    # Сигнали для UI (емітяться у т.ч. з робочих потоків — Qt ставить їх у чергу).
    state_changed = Signal(str)
    status = Signal(str)          # текст статусу для оверлею
    overlay_show = Signal()
    overlay_hide = Signal()
    notify = Signal(str, str)     # (заголовок, текст) — для трей-сповіщень

    _toggle_requested = Signal()  # з потоку хоткея в головний потік
    _cancel_requested = Signal()  # Esc під час запису → скасувати
    _done = Signal(str)           # результат транскрипції в головний потік

    def __init__(self, settings, recorder, transcriber):
        super().__init__()
        self.settings = settings
        self.recorder = recorder
        self.transcriber = transcriber
        self.state = IDLE
        self._hotkey_handle = None
        self._esc_handle = None

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._on_idle_timeout)

        self._toggle_requested.connect(self.toggle)
        self._cancel_requested.connect(self.cancel_recording)
        self._done.connect(self._on_done)

        self.register_hotkey()

    # ---------- Хоткей ----------
    def register_hotkey(self):
        if self._hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
            except (KeyError, ValueError):
                pass
            self._hotkey_handle = None
        try:
            self._hotkey_handle = keyboard.add_hotkey(
                self.settings["hotkey"], self._on_hotkey
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[hotkey] не вдалося зареєструвати {self.settings['hotkey']}: {exc}")

    def _on_hotkey(self):
        # Викликається у внутрішньому потоці keyboard → маршалимо в головний потік.
        self._toggle_requested.emit()

    def _add_esc(self):
        # Тимчасовий Esc-хоткей лише на час запису (скасування). Не блокує Esc деінде.
        try:
            self._esc_handle = keyboard.add_hotkey("esc", self._cancel_requested.emit)
        except Exception:  # noqa: BLE001
            self._esc_handle = None

    def _remove_esc(self):
        if self._esc_handle is not None:
            try:
                keyboard.remove_hotkey(self._esc_handle)
            except (KeyError, ValueError):
                pass
            self._esc_handle = None

    # ---------- Звук ----------
    def _beep(self, kind):
        if winsound is None or not self.settings["sound_enabled"]:
            return
        freq, dur = BEEPS[kind]
        threading.Thread(target=lambda: self._safe_beep(freq, dur), daemon=True).start()

    @staticmethod
    def _safe_beep(freq, dur):
        if winsound is None:
            return
        try:
            winsound.Beep(freq, dur)
        except Exception:  # noqa: BLE001
            pass

    # ---------- Стан-машина ----------
    @Slot()
    def toggle(self):
        if self.state == IDLE:
            self.start_recording()
        elif self.state == RECORDING:
            self.stop_and_transcribe()
        # У стані TRANSCRIBING ігноруємо.

    @Slot()
    def cancel_recording(self):
        """Скасувати запис без розпізнавання/вставки."""
        if self.state != RECORDING:
            return
        self.recorder.stop()  # відкидаємо аудіо
        self._remove_esc()
        self._set_state(IDLE)
        self.overlay_hide.emit()
        self._beep("cancel")
        self._reset_idle_timer()

    def _set_state(self, state):
        self.state = state
        self.state_changed.emit(state)

    def start_recording(self):
        self._set_state(RECORDING)
        self.status.emit("Запис…")
        self.overlay_show.emit()
        self._beep("start")
        self._add_esc()
        # Підвантажуємо модель фоном, поки користувач говорить.
        if not self.transcriber.is_loaded:
            threading.Thread(target=self._safe_preload, daemon=True).start()
        self.recorder.start()

    def _safe_preload(self):
        try:
            self.transcriber.ensure_loaded()
        except Exception as exc:  # noqa: BLE001
            print(f"[model] помилка завантаження: {exc}")

    def stop_and_transcribe(self):
        self._remove_esc()
        self._beep("stop")
        audio = self.recorder.stop()
        self._set_state(TRANSCRIBING)
        if not self.transcriber.is_loaded:
            self.status.emit("Завантаження моделі…")
        else:
            self.status.emit("Розпізнаю…")
        threading.Thread(target=self._do_transcribe, args=(audio,), daemon=True).start()

    def _do_transcribe(self, audio):
        text = ""
        try:
            if not self.transcriber.is_loaded:
                self.status.emit("Завантаження моделі…")
                self.transcriber.ensure_loaded()
                self.status.emit("Розпізнаю…")
            text = self.transcriber.transcribe(audio)
        except Exception as exc:  # noqa: BLE001
            print(f"[transcribe] помилка: {exc}")
        self._done.emit(text)

    @Slot(str)
    def _on_done(self, text):
        self._set_state(IDLE)
        self.overlay_hide.emit()
        if text:
            clipboard.set_text(
                text, include_in_history=bool(self.settings["clipboard_history"])
            )
            if self.settings["auto_paste"]:
                # Дати оверлею сховатись і фокусу повернутись у цільове поле.
                QTimer.singleShot(120, lambda: keyboard.send("ctrl+v"))
        self._reset_idle_timer()

    # ---------- Idle-вивантаження ----------
    def _reset_idle_timer(self):
        self.idle_timer.stop()
        if self.settings["idle_unload"]:
            self.idle_timer.start(int(self.settings["idle_minutes"]) * 60 * 1000)

    def _on_idle_timeout(self):
        if self.state == IDLE and self.transcriber.is_loaded:
            self.transcriber.unload()
            self.notify.emit("WhisperDictation", "Модель вивантажено з памʼяті (простій).")

    # ---------- Застосування налаштувань ----------
    def apply_settings(self):
        self.transcriber.reconfigure(
            model_size=self.settings["model_size"],
            language=self.settings["language"],
        )
        self.recorder.sample_rate = int(self.settings["sample_rate"])
        self.register_hotkey()
        self._reset_idle_timer()

    # ---------- Завершення ----------
    def shutdown(self):
        self._remove_esc()
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:  # noqa: BLE001
            pass
        self.recorder.close()
