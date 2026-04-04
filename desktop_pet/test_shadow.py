"""
使用 setMask + WS_EX_COMPOSITED 彻底消除 DWM 阴影边框
"""
import ctypes
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QPainter

from PyQt6.QtCore import pyqtSignal

GWL_EXSTYLE = -20
WS_EX_COMPOSITED = 0x20000000
WS_EX_LAYERED = 0x80000

user32 = ctypes.windll.user32

def GetWindowLong(hwnd, idx):
    return user32.GetWindowLongW(hwnd, idx)

def SetWindowLong(hwnd, idx, val):
    return user32.SetWindowLongW(hwnd, idx, val)


class TestWin(QWidget):
    W, H = 200, 200

    def __init__(self, label, setup_fn):
        super().__init__()
        self._label = label
        self.setWindowTitle(label)
        self.setFixedSize(self.W, self.H)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        hwnd = int(self.winId())
        # 加上 WS_EX_COMPOSITED 防止 DWM 阴影
        ex = GetWindowLong(hwnd, GWL_EXSTYLE)
        SetWindowLong(hwnd, GWL_EXSTYLE, ex | WS_EX_COMPOSITED)

        # 调用各自的 setup
        setup_fn(self, hwnd)

        # 移到右下角
        geo = QApplication.primaryScreen().geometry()
        self.move(geo.width() - self.W - 50, geo.height() - self.H - 50)

        self._frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(120)

    def _advance(self):
        self._frame = (self._frame + 1) % 4
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # 画帧
        frame_file = Path(f"assets/idle/{self._frame+1:04d}.png")
        if frame_file.exists():
            pm = QPixmap(str(frame_file)).scaled(
                self.W, self.H,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, pm)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._drag_origin = self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self._drag_origin + (event.globalPosition().toPoint() - self._drag_start))


def setup_basic(w, hwnd):
    pass

def setup_mask(w, hwnd):
    pm = QPixmap(f"assets/idle/0001.png").scaled(w.W, w.H, Qt.AspectRatioMode.IgnoreAspectRatio)
    w.setMask(pm.mask())

def setup_dwm_disable(w, hwnd):
    try:
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        class I(ctypes.Structure):
            _fields_ = [("v", ctypes.c_int)]
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_NCRENDERING_POLICY,
            ctypes.byref(I(DWMNCRP_DISABLED)),
            ctypes.sizeof(ctypes.c_int)
        )
    except:
        pass

def setup_combined(w, hwnd):
    # mask + DWM disable
    pm = QPixmap(f"assets/idle/0001.png").scaled(w.W, w.H, Qt.AspectRatioMode.IgnoreAspectRatio)
    w.setMask(pm.mask())
    try:
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        class I(ctypes.Structure):
            _fields_ = [("v", ctypes.c_int)]
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_NCRENDERING_POLICY,
            ctypes.byref(I(DWMNCRP_DISABLED)),
            ctypes.sizeof(ctypes.c_int)
        )
    except:
        pass


if __name__ == "__main__":
    print("=== 透明无阴影测试 ===")
    print("每个窗口显示 2.5 秒后自动切换，共 4 个测试。")
    print("请观察每个是否还有灰色边框。\n")

    app = QApplication(sys.argv)

    idx = [0]
    cur = [None]

    tests = [
        ("Test1: 基础透明窗口 + WS_EX_COMPOSITED", setup_basic),
        ("Test2: + setMask(alpha裁剪)", setup_mask),
        ("Test3: + DwmSetWindowAttribute禁用阴影", setup_dwm_disable),
        ("Test4: mask + DWM禁用 全部结合", setup_combined),
    ]

    def show_next():
        if cur[0]:
            cur[0].close()
        label, fn = tests[idx[0]]
        w = TestWin(label, fn)
        w.show()
        cur[0] = w
        print(f"  显示: {label}")
        idx[0] = (idx[0] + 1) % len(tests)

    show_next()
    t = QTimer()
    t.timeout.connect(show_next)
    t.start(2500)

    sys.exit(app.exec())
