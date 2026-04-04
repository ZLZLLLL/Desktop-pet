from pathlib import Path

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QPixmap, QAction


class TrayManager:
    IDLE_01_PNG = Path(__file__).parent / "assets" / "idle" / "0001.png"
    IDLE_01_JPG = Path(__file__).parent / "assets" / "idle" / "0001.jpg"

    def __init__(self, app, pet):
        self.app = app
        self.pet = pet
        self._setup()

    def _setup(self):
        icon_path = None
        if self.IDLE_01_PNG.exists():
            icon_path = str(self.IDLE_01_PNG)
        elif self.IDLE_01_JPG.exists():
            icon_path = str(self.IDLE_01_JPG)

        if icon_path:
            icon = QIcon(icon_path)
        else:
            icon = QIcon(QPixmap(16, 16))

        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("桌面桌宠")

        menu = QMenu()

        action_status = QAction("查看亲密度")
        action_status.triggered.connect(self._show_status)
        menu.addAction(action_status)

        action_reset = QAction("重置位置")
        action_reset.triggered.connect(self.pet.reset_position)
        menu.addAction(action_reset)

        menu.addSeparator()

        action_quit = QAction("退出")
        action_quit.triggered.connect(self._quit)
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _show_status(self):
        status = self.pet.intimacy_system.get_intimacy_status()
        QMessageBox.information(None, "亲密度状态", status)

    def _quit(self):
        self.tray.hide()
        self.pet.bubble.close()
        self.pet.close()
        self.app.quit()
