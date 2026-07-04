"""Іконка в системному треї з меню."""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ui import icons


class Tray(QSystemTrayIcon):
    """Трей-іконка: меню (Запис, Налаштування, Історія, Вихід) + сповіщення."""

    def __init__(self, settings, controller, main_window, parent=None):
        super().__init__(icons.tray_icon(False), parent)
        self.settings = settings
        self.controller = controller
        self.main_window = main_window

        self.setToolTip(f"WhisperDictation — хоткей: {settings['hotkey']}")

        menu = QMenu()
        act_record = QAction("Запис / Стоп (хоткей)", menu)
        act_record.triggered.connect(self.controller.toggle)
        menu.addAction(act_record)
        menu.addSeparator()

        act_settings = QAction("Налаштування", menu)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)
        menu.addSeparator()

        act_quit = QAction("Вихід", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

        # Реакція на стан: міняти іконку (червона під час запису).
        self.controller.state_changed.connect(self._on_state)
        self.controller.notify.connect(
            lambda title, msg: self.showMessage(title, msg, icons.tray_icon(False), 3000)
        )

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_settings()

    def _on_state(self, state):
        self.setIcon(icons.tray_icon(state == "recording"))

    def _open_settings(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _quit(self):
        from PySide6.QtWidgets import QApplication
        self.controller.shutdown()
        QApplication.quit()
