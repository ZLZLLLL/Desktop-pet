import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from data_manager import DataManager
from pet_window import PetWindow
from tray_manager import TrayManager


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    data_manager = DataManager()
    pet = PetWindow(data_manager)
    tray = TrayManager(app, pet)
    pet.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
