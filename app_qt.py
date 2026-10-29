"""Точка входу: резидентний застосунок диктування у системному треї.

Запуск:  venv\\Scripts\\python.exe app_qt.py
"""

import multiprocessing
import os
import sys

if __name__ == "__main__":
    # У зібраному .exe процес розпізнавання — це той самий .exe. Перехоплюємо його
    # тут, до імпорту Qt, щоб воркер не тягнув за собою зайві бібліотеки.
    multiprocessing.freeze_support()

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from core.controller import Controller
from core.recorder import Recorder
from core.transcriber import Transcriber
from settings import Settings
from ui.main_window import MainWindow
from ui.overlay import Overlay
from ui.tray import Tray


def resource_path(rel):
    """Шлях до ресурсу — працює і з venv, і з PyInstaller (.exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # закриття вікна не завершує — живемо в треї

    try:
        with open(resource_path(os.path.join("ui", "style.qss")), "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except OSError:
        pass

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "WhisperDictation", "Системний трей недоступний.")
        return 1

    settings = Settings()
    recorder = Recorder(
        sample_rate=int(settings["sample_rate"]),
        channels=int(settings["channels"]),
    )
    transcriber = Transcriber(
        model_size=settings["model_size"],
        language=settings["language"],
        device=settings["device"],
    )

    controller = Controller(settings, recorder, transcriber)
    overlay = Overlay(recorder, settings)
    main_window = MainWindow(settings, controller)
    tray = Tray(settings, controller, main_window)
    tray.show()

    # Звʼязування контролера з оверлеєм
    controller.overlay_show.connect(overlay.show_recording)
    controller.overlay_hide.connect(overlay.hide_overlay)
    controller.status.connect(overlay.set_status)
    controller.device_label.connect(overlay.set_device)
    controller.state_changed.connect(
        lambda s: overlay.set_transcribing() if s == "transcribing" else None
    )
    overlay.done_clicked.connect(controller.toggle)
    overlay.cancel_clicked.connect(controller.cancel_recording)

    tray.showMessage(
        "WhisperDictation",
        f"Готово. Хоткей: {settings['hotkey']}",
        QSystemTrayIcon.Information,
        3000,
    )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
