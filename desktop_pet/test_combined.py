"""
测试：用 Windows 11/10 系统级阴影控制 API
"""
import ctypes
import sys
import subprocess

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter

from pathlib import Path

GWL_EXSTYLE = -20
user32 = ctypes.windll.user32
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long


class ShadowTest(QWidget):
    W, H = 200, 200

    def __init__(self, label, setup_fn):
        super().__init__()
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
        setup_fn(self, hwnd)

        geo = QApplication.primaryScreen().geometry()
        self.move(geo.width() - self.W - 50, geo.height() - self.H - 50)

        # 加载帧
        self._frames = []
        folder = Path(__file__).parent / "assets" / "idle"
        if folder.exists():
            for f in sorted(folder.glob("*.png")):
                pm = QPixmap(str(f)).scaled(
                    self.W, self.H,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                if not pm.isNull():
                    self._frames.append(pm)

        if not self._frames:
            pm = QPixmap(self.W, self.H)
            pm.fill(Qt.GlobalColor.transparent)
            self._frames.append(pm)

        self._frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next)
        self._timer.start(125)

    def _next(self):
        self._frame = (self._frame + 1) % max(1, len(self._frames))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if self._frames:
            painter.drawPixmap(0, 0, self._frames[self._frame])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._drag_origin = self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self._drag_origin + (event.globalPosition().toPoint() - self._drag_start))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = self.pos()


def setup_basic(w, hwnd):
    pass


def setup_mask(w, hwnd):
    # setMask 用第一帧的 alpha 通道裁剪窗口形状
    folder = Path(__file__).parent / "assets" / "idle"
    files = sorted(folder.glob("*.png"))
    if files:
        pm = QPixmap(str(files[0])).scaled(w.W, w.H, Qt.AspectRatioMode.IgnoreAspectRatio)
        w.setMask(pm.mask())
        print(f"  setMask applied, mask rect: {pm.mask().boundingRect()}")


def setup_dwm_off(w, hwnd):
    # 禁用 DWM NCR 渲染
    try:
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        class IVAL(ctypes.Structure):
            _fields_ = [("v", ctypes.c_int)]
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_NCRENDERING_POLICY,
            ctypes.byref(IVAL(DWMNCRP_DISABLED)),
            ctypes.sizeof(ctypes.c_int)
        )
        print("  DWM NCR disabled")
    except Exception as e:
        print(f"  DWM failed: {e}")


def setup_all(w, hwnd):
    # mask + DWM off
    folder = Path(__file__).parent / "assets" / "idle"
    files = sorted(folder.glob("*.png"))
    if files:
        pm = QPixmap(str(files[0])).scaled(w.W, w.H, Qt.AspectRatioMode.IgnoreAspectRatio)
        w.setMask(pm.mask())
    try:
        class IVAL(ctypes.Structure):
            _fields_ = [("v", ctypes.c_int)]
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 2, ctypes.byref(IVAL(1)), ctypes.sizeof(ctypes.c_int)
        )
    except:
        pass


TESTS = [
    ("Test1: 基础透明", setup_basic),
    ("Test2: + setMask(alpha裁剪)", setup_mask),
    ("Test3: + DwmNCR禁用", setup_dwm_off),
    ("Test4: mask+DWM禁用 全部", setup_all),
]


if __name__ == "__main__":
    print("=== 无阴影透明测试 ===")
    print("自动轮播，请观察每个窗口是否有灰色边框。\n")

    app = QApplication(sys.argv)

    idx = [0]
    cur = [None]

    def show_next():
        if cur[0]:
            cur[0].close()
        label, fn = TESTS[idx[0]]
        w = ShadowTest(label, fn)
        w.show()
        cur[0] = w
        print(f"  显示: {label}")
        idx[0] = (idx[0] + 1) % len(TESTS)

    show_next()
    t = QTimer()
    t.timeout.connect(show_next)
    t.start(3000)

    sys.exit(app.exec())
