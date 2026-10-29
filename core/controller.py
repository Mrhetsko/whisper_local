"""Ядро логіки: стан-машина, хоткей, idle-вивантаження, авто-вставка, звук."""

import threading

import keyboard
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from core import clipboard, hotkey

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
    device_label = Signal(str)    # "GPU" | "CPU" — на чому працює модель
    overlay_show = Signal()
    overlay_hide = Signal()
    notify = Signal(str, str)     # (заголовок, текст) — для трей-сповіщень

    _toggle_requested = Signal()  # хоткей → toggle (через чергу подій)
    _done = Signal(str)           # результат транскрипції в головний потік

    def __init__(self, settings, recorder, transcriber):
        super().__init__()
        self.settings = settings
        self.recorder = recorder
        self.transcriber = transcriber
        self.state = IDLE
        self._hotkey = hotkey.GlobalHotkey(self._toggle_requested.emit)

        # Простій на GPU: короткий таймер — щоб NVIDIA могла заснути.
        # Загальний таймер — запасний, вивантажує модель на будь-якому пристрої.
        self.gpu_idle_timer = QTimer(self)
        self.gpu_idle_timer.setSingleShot(True)
        self.gpu_idle_timer.timeout.connect(self._on_gpu_idle_timeout)

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._on_idle_timeout)

        # Esc під час запису → скасувати. Опитуємо стан клавіші, а не ставимо хук.
        self._esc_timer = QTimer(self)
        self._esc_timer.setInterval(25)
        self._esc_timer.timeout.connect(self._poll_esc)

        # Queued: toggle виконується вже після виходу з обробника WM_HOTKEY.
        self._toggle_requested.connect(self.toggle, Qt.QueuedConnection)
        self._done.connect(self._on_done)

        # Відкладено до старту циклу подій, щоб трей уже міг показати помилку.
        QTimer.singleShot(0, self.register_hotkey)

    # ---------- Хоткей ----------
    def register_hotkey(self):
        combo = self.settings["hotkey"]
        try:
            self._hotkey.register(combo)
        except (ValueError, OSError) as exc:
            print(f"[hotkey] не вдалося зареєструвати {combo}: {exc}")
            self.notify.emit(
                "WhisperDictation",
                f"Хоткей {combo} не зареєстровано (можливо, зайнятий іншою програмою).",
            )

    def _add_esc(self):
        # Esc лише на час запису (скасування). Не блокує Esc деінде.
        self._esc_timer.start()

    def _remove_esc(self):
        self._esc_timer.stop()

    def _poll_esc(self):
        if hotkey.is_key_down(hotkey.VK_ESCAPE):
            self.cancel_recording()

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
        self._emit_device()
        self.overlay_show.emit()
        self._beep("start")
        self._add_esc()
        # Підвантажуємо модель фоном, поки користувач говорить.
        if not self.transcriber.is_ready:
            threading.Thread(target=self._safe_preload, daemon=True).start()
        self.recorder.start()

    def _emit_device(self):
        self.device_label.emit("GPU" if self.transcriber.resolve_device() == "cuda" else "CPU")

    def _safe_preload(self):
        try:
            self._load_model()
        except Exception as exc:  # noqa: BLE001
            print(f"[model] помилка завантаження: {exc}")

    def _load_model(self):
        """Готує модель; якщо GPU не запустився і перейшли на CPU — повідомляє."""
        loaded_now = self.transcriber.ensure_loaded()
        self._emit_device()
        if (loaded_now and self.settings["device"] == "cuda"
                and self.transcriber.active_device == "cpu"):
            self.notify.emit(
                "WhisperDictation",
                "NVIDIA GPU недоступний — розпізнавання працює на CPU.",
            )

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
            if not self.transcriber.is_ready:
                self.status.emit("Завантаження моделі…")
                self._load_model()
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
        self.gpu_idle_timer.stop()
        self.idle_timer.stop()
        if self.settings["gpu_unload"]:
            self.gpu_idle_timer.start(int(self.settings["gpu_unload_minutes"]) * 60 * 1000)
        if self.settings["idle_unload"]:
            self.idle_timer.start(int(self.settings["idle_minutes"]) * 60 * 1000)

    def _on_gpu_idle_timeout(self):
        if self.state == IDLE and self.transcriber.active_device == "cuda":
            # Завершення воркера займає ~секунду — не блокуємо GUI.
            threading.Thread(target=self.transcriber.unload, daemon=True).start()

    def _on_idle_timeout(self):
        if self.state == IDLE and self.transcriber.is_loaded:
            threading.Thread(target=self._unload_and_notify, daemon=True).start()

    def _unload_and_notify(self):
        self.transcriber.unload()
        self.notify.emit("WhisperDictation", "Модель вивантажено з памʼяті (простій).")

    # ---------- Застосування налаштувань ----------
    def apply_settings(self):
        self.transcriber.reconfigure(
            model_size=self.settings["model_size"],
            language=self.settings["language"],
            device=self.settings["device"],
        )
        self.recorder.sample_rate = int(self.settings["sample_rate"])
        self.register_hotkey()
        self._reset_idle_timer()

    # ---------- Завершення ----------
    def shutdown(self):
        self._remove_esc()
        self._hotkey.unregister()
        self.recorder.close()
