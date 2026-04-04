"""
使用 Windows UpdateLayeredWindow 无阴影透明窗口
手动 DIB 创建，像素从 QPixmap 复制
"""
import ctypes
import sys
from pathlib import Path
from ctypes import wintypes

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage

user32 = ctypes.windll.user32
gdi32   = ctypes.windll.gdi32
dwmapi  = ctypes.windll.dwmapi

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TOPMOST = 0x8
ULW_ALPHA = 2
AC_SRC_OVER = 0

# 设置返回值类型
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HGDIOBJ
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.restype = wintypes.INT
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.GetWindowLongW.restype = wintypes.LONG
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.UpdateLayeredWindow.restype = wintypes.BOOL


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


def qpixmap_to_hbitmap(pm: QPixmap):
    """QPixmap → HBITMAP，返回 (hMemDC, hBitmap)"""
    w, h = pm.width(), pm.height()

    # 创建与屏幕兼容的 DC
    hdc_screen = user32.GetDC(0)
    hdc = gdi32.CreateCompatibleDC(hdc_screen)
    user32.ReleaseDC(0, hdc_screen)

    # 创建 32bpp DIB
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h   # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0
    bmi.biSizeImage = w * h * 4

    bits = ctypes.POINTER(ctypes.c_ubyte)()
    hbitmap = gdi32.CreateDIBSection(
        hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
    )
    if not hbitmap:
        raise RuntimeError(f"CreateDIBSection failed, error={ctypes.GetLastError()}")

    # 复制像素数据
    img = pm.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.bits()
    ptr.setsize(w * h * 4)
    ctypes.memmove(bits, int(ptr), w * h * 4)

    gdi32.SelectObject(hdc, hbitmap)
    return hdc, hbitmap


def update_layered(hwnd, pm: QPixmap):
    """用 UpdateLayeredWindow 一次性更新窗口"""
    w, h = pm.width(), pm.height()

    hdc_dst = user32.GetDC(hwnd)
    try:
        hdc = gdi32.CreateCompatibleDC(hdc_dst)
        try:
            hbitmap = int(pm.handle()) if hasattr(pm, 'handle') else 0

            if not hbitmap or hbitmap == 0:
                # 没有 handle，手动复制像素
                hdc2, hbitmap = qpixmap_to_hbitmap(pm)
                gdi32.DeleteDC(hdc2)
                hdc = gdi32.CreateCompatibleDC(hdc_dst)

            hbm_old = gdi32.SelectObject(hdc, hbitmap)

            dst = POINT()
            sz = SIZE(w, h)
            src = POINT(0, 0)
            bf = BLENDFUNCTION(AC_SRC_OVER, 0, 255, ULW_ALPHA)

            user32.UpdateLayeredWindow(
                hwnd, hdc, ctypes.byref(dst),
                ctypes.byref(sz),
                hdc, ctypes.byref(src),
                0, ctypes.byref(bf), ULW_ALPHA
            )

            gdi32.SelectObject(hdc, hbm_old)
        finally:
            gdi32.DeleteDC(hdc)
    finally:
        user32.ReleaseDC(hwnd, hdc_dst)


class ShadowlessPetWindow(QWidget):
    W, H = 200, 200

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.W, self.H)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen, False)

        hwnd = int(self.winId())

        # WS_EX_LAYERED 必须加，让 DWM 使用 UpdateLayeredWindow 合成
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TOPMOST)

        # 禁用 DWM 阴影
        try:
            class IVAL(ctypes.Structure):
                _fields_ = [("v", ctypes.c_int)]
            dwmapi.DwmSetWindowAttribute(
                hwnd, 2,  # DWMWA_NCRENDERING_POLICY
                ctypes.byref(IVAL(1)),  # DWMNCRP_DISABLED
                ctypes.sizeof(ctypes.c_int)
            )
            print("DWM shadow disabled via DwmSetWindowAttribute")
        except Exception as e:
            print(f"DWM API failed: {e}")

        geo = QApplication.primaryScreen().geometry()
        self.move(geo.width() - self.W - 50, geo.height() - self.H - 50)

        # 加载帧
        self._frames: list[QPixmap] = []
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
            print("WARNING: No frames loaded, using blank")

        self._frame = 0
        self._hwnd = hwnd

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(125)

        self._update()

    def _update(self):
        try:
            update_layered(self._hwnd, self._frames[self._frame])
        except Exception as e:
            print(f"Update error: {e}")

    def _advance(self):
        self._frame = (self._frame + 1) % len(self._frames)
        self._update()

    def showEvent(self, event):
        self._update()

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


if __name__ == "__main__":
    print("=== UpdateLayeredWindow 无阴影测试 ===")
    print("请告诉：这个窗口是否有灰色边框？")
    app = QApplication(sys.argv)
    w = ShadowlessPetWindow()
    w.show()
    sys.exit(app.exec())
