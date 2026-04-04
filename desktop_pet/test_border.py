"""
自动测试：透明窗口无边框方案逐一验证
"""
import ctypes
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter


class TestWindow(QWidget):
    def __init__(self, label, method):
        super().__init__()
        self._label = label
        self._method = method
        self.setWindowTitle(label)
        self.setFixedSize(200, 200)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        method(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)


def make_test1(w):
    pass


def make_test2(w):
    w.setAutoFillBackground(False)


def make_test3(w):
    try:
        class MARGINS(ctypes.Structure):
            _fields_ = [("cxLeftWidth", ctypes.c_int),
                        ("cxRightWidth", ctypes.c_int),
                        ("cyTopHeight", ctypes.c_int),
                        ("cyBottomHeight", ctypes.c_int)]
        margins = MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(int(w.winId()), ctypes.byref(margins))
    except Exception as e:
        print(f"  DWM failed: {e}")


def make_test4(w):
    pm = QPixmap(200, 200)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setBrush(Qt.GlobalColor.red)
    p.drawEllipse(5, 5, 190, 190)
    p.end()
    w.setMask(pm.mask())


def make_test5(w):
    w.setAutoFillBackground(False)
    try:
        class MARGINS(ctypes.Structure):
            _fields_ = [("cxLeftWidth", ctypes.c_int),
                        ("cxRightWidth", ctypes.c_int),
                        ("cyTopHeight", ctypes.c_int),
                        ("cyBottomHeight", ctypes.c_int)]
        margins = MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(int(w.winId()), ctypes.byref(margins))
    except Exception:
        pass
    pm = QPixmap(200, 200)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setBrush(Qt.GlobalColor.blue)
    p.drawEllipse(5, 5, 190, 190)
    p.end()
    w.setMask(pm.mask())


TESTS = [
    ("Test1 基础透明无边框", make_test1),
    ("Test2 +autoFillBackground=False", make_test2),
    ("Test3 +DwmExtendFrameIntoClientArea", make_test3),
    ("Test4 +setMask 裁剪", make_test4),
    ("Test5 全部结合", make_test5),
]


def main():
    print("=== 透明窗口无边框测试 ===")
    print("每个窗口显示 2 秒后自动切到下一个，请观察是否有灰色边框。")
    print("最终停在 Test5，结合了所有方法。\n")
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("透明窗口测试")
    root.setFixedSize(600, 80)
    root.setStyleSheet("background:#222; color:#fff; font-size:14px; padding:10px;")
    root.setWindowFlags(Qt.WindowType.Tool)
    root.move(100, 100)
    root.show()

    idx = [0]
    windows = []

    def show_next():
        # 关闭之前的
        for w in windows:
            w.close()
        windows.clear()

        label, method = TESTS[idx[0]]
        w = TestWindow(label, method)
        w.show()
        windows.append(w)
        print(f"  显示: {label}")

        idx[0] = (idx[0] + 1) % len(TESTS)

    show_next()
    timer = QTimer()
    timer.timeout.connect(show_next)
    timer.start(2500)  # 每 2.5 秒切换

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
