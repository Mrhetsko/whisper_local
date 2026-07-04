"""Оверлей-індикатор запису: стабільна «пігулка» з чутливою хвилею + Готово/Скасувати."""

import math
import random
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import QPushButton, QWidget

BARS = 24
BAR_W = 4
BAR_GAP = 3
BARS_X = 22
BARS_W = BARS * (BAR_W + BAR_GAP)        # ширина зони смужок
W = BARS_X + BARS_W + 250                # загальна ширина вікна
H = 84

LANG_LABELS = {"auto": "авто", "en": "EN", "uk": "UA", None: "авто"}

# Силует «спектра»: центральні смужки вищі — виглядає високоточніше.
_WEIGHTS = [0.45 + 0.55 * math.sin(math.pi * (i + 0.5) / BARS) for i in range(BARS)]


class Overlay(QWidget):
    """Плаваюче вікно стану запису/розпізнавання. Не краде фокус."""

    done_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, recorder, settings):
        super().__init__()
        self.recorder = recorder
        self.settings = settings
        self._levels = [0.05] * BARS
        self._mode = "recording"   # "recording" | "transcribing"
        self._spinner_phase = 0
        self._status = "Запис"
        self._start_time = 0.0
        self._lang = "EN"

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(W, H)

        # Кнопка «Готово» (зелена галочка) — завершити диктування.
        self.done_btn = QPushButton("✓", self)
        self.done_btn.setGeometry(W - 58, (H - 44) // 2, 44, 44)
        self.done_btn.setFocusPolicy(Qt.NoFocus)
        self.done_btn.setCursor(Qt.PointingHandCursor)
        self.done_btn.setToolTip("Завершити (Ctrl+Alt+Z)")
        self.done_btn.setStyleSheet(
            "QPushButton{background:#4cd964;color:white;border:none;"
            "border-radius:22px;font-size:18px;font-weight:bold;}"
            "QPushButton:hover{background:#6ee47f;}"
        )
        self.done_btn.clicked.connect(self.done_clicked.emit)

        # Кнопка «Скасувати» (сірий хрестик) — відкинути запис без вставки.
        self.cancel_btn = QPushButton("✕", self)
        self.cancel_btn.setGeometry(W - 108, (H - 40) // 2, 40, 40)
        self.cancel_btn.setFocusPolicy(Qt.NoFocus)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setToolTip("Скасувати (Esc)")
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#3a3a48;color:#e8e8ec;border:none;"
            "border-radius:20px;font-size:15px;}"
            "QPushButton:hover{background:#ff4d4f;color:white;}"
        )
        self.cancel_btn.clicked.connect(self.cancel_clicked.emit)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(33)  # ~30 fps

    # ---------- Публічне API ----------
    def show_recording(self):
        self._mode = "recording"
        self._status = "Запис"
        self._start_time = time.monotonic()
        self._lang = LANG_LABELS.get(self.settings["language"], "авто")
        self.done_btn.show()
        self.cancel_btn.show()
        self._move_to_bottom_center()
        self.show()
        self._timer.start()

    def set_transcribing(self):
        self._mode = "transcribing"
        self._status = "Розпізнаю…"
        self.done_btn.hide()
        self.cancel_btn.hide()

    def set_status(self, text):
        self._status = text
        self.update()

    def hide_overlay(self):
        self._timer.stop()
        self.hide()

    # ---------- Анімація ----------
    def _tick(self):
        if self._mode == "recording":
            level = self.recorder.get_level()
            for i in range(BARS):
                # Зважений силует спектра + жвавий шум; невеликий «живий» фон.
                target = max(0.05, level * _WEIGHTS[i] * random.uniform(0.7, 1.15))
                self._levels[i] += (target - self._levels[i]) * 0.55
        else:
            self._spinner_phase = (self._spinner_phase + 1) % 4
        self.update()

    def _move_to_bottom_center(self):
        scr = self.screen() or QGuiApplication.primaryScreen()
        screen = scr.availableGeometry()
        x = screen.x() + (screen.width() - W) // 2
        y = screen.y() + screen.height() - H - 60
        self.move(x, y)

    def _elapsed_str(self):
        secs = int(time.monotonic() - self._start_time)
        return f"{secs // 60}:{secs % 60:02d}"

    # ---------- Малювання ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, W, H, H / 2, H / 2)
        p.fillPath(path, QColor(28, 28, 34, 238))

        if self._mode == "recording":
            self._draw_bars(p)
        else:
            self._draw_spinner_dot(p)

        # Текстовий блок: статус (зверху) + інфо-рядок (знизу)
        text_x = BARS_X + BARS_W + 16
        text_w = W - text_x - 118

        p.setPen(QColor("#f2f2f5"))
        f = QFont("Segoe UI", 12)
        f.setBold(True)
        p.setFont(f)
        p.drawText(text_x, 14, text_w, 26, Qt.AlignVCenter | Qt.AlignLeft, self._status)

        if self._mode == "recording":
            p.setPen(QColor("#9a9aa6"))
            p.setFont(QFont("Segoe UI", 10))
            info = f"{self._lang}  ·  {self._elapsed_str()}"
            p.drawText(text_x, H - 36, text_w, 24,
                       Qt.AlignVCenter | Qt.AlignLeft, info)

        p.end()

    def _draw_bars(self, p):
        p.setPen(Qt.NoPen)
        cy = H / 2
        max_h = H * 0.66
        for i in range(BARS):
            lvl = self._levels[i]
            h = max(4, lvl * max_h)
            x = BARS_X + i * (BAR_W + BAR_GAP)
            p.setBrush(QColor("#4cd964") if lvl < 0.7 else QColor("#8CFF9C"))
            p.drawRoundedRect(int(x), int(cy - h / 2), BAR_W, int(h), 2, 2)

    def _draw_spinner_dot(self, p):
        p.setPen(Qt.NoPen)
        colors = ["#4cd964", "#3aa0ff", "#ffcc00", "#ff7875"]
        p.setBrush(QColor(colors[self._spinner_phase]))
        p.drawEllipse(44, int(H / 2 - 8), 16, 16)
