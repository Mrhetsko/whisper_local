"""Вікно налаштувань."""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

import settings as settings_mod
from core.transcriber import nvidia_present


class MainWindow(QWidget):
    """Вікно налаштувань. Закриття ховає вікно (застосунок живе в треї)."""

    def __init__(self, settings, controller):
        super().__init__()
        self.settings = settings
        self.controller = controller

        self.setWindowTitle("WhisperDictation — налаштування")
        self.resize(480, 520)

        v = QVBoxLayout(self)

        # Модель
        v.addWidget(QLabel("Модель:"))
        self.model_box = QComboBox()
        for name in settings_mod.MODEL_CHOICES:
            self.model_box.addItem(f"{name}  (≈{settings_mod.MODEL_SIZES[name]})", name)
        self.model_box.setCurrentIndex(max(0, self.model_box.findData(self.settings["model_size"])))
        v.addWidget(self.model_box)

        # Пристрій
        v.addWidget(QLabel("Пристрій для розпізнавання:"))
        self.device_box = QComboBox()
        for value, label in settings_mod.DEVICE_CHOICES:
            self.device_box.addItem(label, value)
        self.device_box.setCurrentIndex(max(0, self.device_box.findData(self.settings["device"])))
        self.device_box.currentIndexChanged.connect(self._update_gpu_row)
        v.addWidget(self.device_box)
        gpu_info = QLabel(
            "NVIDIA GPU знайдено ✓" if nvidia_present()
            else "NVIDIA GPU не знайдено — працюватиме CPU"
        )
        gpu_info.setStyleSheet("color:#9a9aa6;")
        v.addWidget(gpu_info)

        # Мова
        v.addWidget(QLabel("Мова:"))
        self.lang_box = QComboBox()
        self.lang_box.addItems(settings_mod.LANGUAGE_CHOICES)
        self.lang_box.setCurrentText(self.settings["language"])
        v.addWidget(self.lang_box)

        # Хоткей
        v.addWidget(QLabel("Глобальний хоткей (toggle):"))
        self.hotkey_edit = QLineEdit(self.settings["hotkey"])
        self.hotkey_edit.setPlaceholderText("напр. ctrl+alt+z")
        v.addWidget(self.hotkey_edit)

        # Авто-вставка
        self.autopaste_cb = QCheckBox("Авто-вставка в активне поле (Ctrl+V)")
        self.autopaste_cb.setChecked(bool(self.settings["auto_paste"]))
        v.addWidget(self.autopaste_cb)

        # Історія буфера Windows (Win+V)
        self.cliphist_cb = QCheckBox("Зберігати в історію буфера обміну Windows (Win+V)")
        self.cliphist_cb.setChecked(bool(self.settings["clipboard_history"]))
        v.addWidget(self.cliphist_cb)

        # Звуковий сигнал
        self.sound_cb = QCheckBox("Звуковий сигнал (старт / стоп / скасування)")
        self.sound_cb.setChecked(bool(self.settings["sound_enabled"]))
        v.addWidget(self.sound_cb)

        # Idle-вивантаження на GPU: завершуємо процес розпізнавання, щоб NVIDIA заснула
        gpu_row = QHBoxLayout()
        self.gpu_cb = QCheckBox("Вивантажувати з GPU після простою (карта засинає), хв:")
        self.gpu_cb.setChecked(bool(self.settings["gpu_unload"]))
        self.gpu_spin = QSpinBox()
        self.gpu_spin.setRange(1, 240)
        self.gpu_spin.setValue(int(self.settings["gpu_unload_minutes"]))
        gpu_row.addWidget(self.gpu_cb)
        gpu_row.addWidget(self.gpu_spin)
        gpu_row.addStretch()
        v.addLayout(gpu_row)

        # Idle-вивантаження на будь-якому пристрої (для CPU — основне)
        idle_row = QHBoxLayout()
        self.idle_cb = QCheckBox("Вивантажувати модель з памʼяті після простою, хв:")
        self.idle_cb.setChecked(bool(self.settings["idle_unload"]))
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(1, 1440)
        self.idle_spin.setValue(int(self.settings["idle_minutes"]))
        idle_row.addWidget(self.idle_cb)
        idle_row.addWidget(self.idle_spin)
        idle_row.addStretch()
        v.addLayout(idle_row)
        self._update_gpu_row()

        v.addStretch()

        save_btn = QPushButton("Зберегти")
        save_btn.clicked.connect(self._save)
        v.addWidget(save_btn)

        self.saved_label = QLabel("")
        self.saved_label.setStyleSheet("color:#4cd964;")
        v.addWidget(self.saved_label)

    def _save(self):
        self.settings["model_size"] = self.model_box.currentData()
        self.settings["device"] = self.device_box.currentData()
        self.settings["language"] = self.lang_box.currentText()
        self.settings["hotkey"] = self.hotkey_edit.text().strip() or "ctrl+alt+z"
        self.settings["auto_paste"] = self.autopaste_cb.isChecked()
        self.settings["clipboard_history"] = self.cliphist_cb.isChecked()
        self.settings["sound_enabled"] = self.sound_cb.isChecked()
        self.settings["gpu_unload"] = self.gpu_cb.isChecked()
        self.settings["gpu_unload_minutes"] = self.gpu_spin.value()
        self.settings["idle_unload"] = self.idle_cb.isChecked()
        self.settings["idle_minutes"] = self.idle_spin.value()
        self.settings.save()
        self.controller.apply_settings()
        self.saved_label.setText("Збережено ✓")

    def _update_gpu_row(self):
        # Таймер VRAM має сенс лише тоді, коли модель може опинитись на GPU.
        enabled = self.device_box.currentData() != "cpu"
        self.gpu_cb.setEnabled(enabled)
        self.gpu_spin.setEnabled(enabled)

    # Закриття вікна не завершує застосунок — лише ховаємо.
    def closeEvent(self, event):
        event.ignore()
        self.hide()
