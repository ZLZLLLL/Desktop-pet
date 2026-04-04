"""
使用 Windows 原生 API 创建完全无阴影的透明窗口
彻底绕过 Qt 的窗口合成机制
"""
import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QCursor

from PyQt6.QtCore import pyqtSignal, QPoint

# ── Windows 常量 ──────────────────────────────────────────────
GWL_EXSTYLE    = -20
WS_EX_LAYERED  = 0x80000
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_EX_TOPMOST  = 0x8
ULW_ALPHA      = 2
AC_SRC_OVER    = 0x0

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

# ── Windows API ──────────────────────────────────────────────
def GetWindowLong(hwnd, idx):
    return user32.GetWindowLongW(hwnd, idx)

def SetWindowLong(hwnd, idx, val):
    return user32.SetWindowLongW(hwnd, idx, val)

def SetLayeredWindowAttributes(hwnd, key, alpha, flags):
    return user32.SetLayeredWindowAttributes(hwnd, key, alpha, flags)

def UpdateLayeredWindow(hwnd, hdcDst, dst, size, hdcSrc, src, key, alpha, flags):
    return user32.UpdateLayeredWindow(hwnd, hdcDst, dst, size, hdcSrc, src, key, alpha, flags)

def GetDC(hwnd):
    return user32.GetDC(hwnd)

def ReleaseDC(hwnd, hdc):
    return user32.ReleaseDC(hwnd, hdc)

def CreateCompatibleDC(hdc):
    return user32.CreateCompatibleDC(hdc)

def SelectObject(hdc, obj):
    return user32.SelectObject(hdc, obj)

def DeleteDC(hdc):
    return user32.DeleteDC(hdc)

def DeleteObject(obj):
    user32.DeleteObject(obj)

def CreateDIBSection(hdc, info, usage, bits, sections, offset):
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

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = info[0]
    bmi.biHeight = -info[1]   # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0
    bmi.biSizeImage = info[0] * info[1] * 4
    bits_ptr = ctypes.POINTER(ctypes.c_ubyte)()
    handle = ctypes.windll.gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits_ptr), None, 0)
    return handle, bits_ptr


class LayeredWindow(QWidget):
    """用 Windows UpdateLayeredWindow 实现真正无边框无阴影的透明窗口"""
    _w, _h = 200, 200

    def __init__(self):
        super().__init__()
        self.setFixedSize(self._w, self._h)

        # 先设置 Qt 窗口标志（无边框、置顶）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen, False)

        hwnd = int(self.winId())

        # ── 1. 移除 WS_EX_CLIENTEDGE 等可能导致边框的样式 ──
        exstyle = GetWindowLong(hwnd, GWL_EXSTYLE)
        SetWindowLong(hwnd, GWL_EXSTYLE, exstyle)

        # ── 2. 设置 WS_EX_LAYERED 让窗口内容完全由 UpdateLayeredWindow 控制 ──
        SetWindowLong(hwnd, GWL_EXSTYLE, exstyle | WS_EX_LAYERED)

        # ── 3. 禁用 DWM 阴影 ──
        try:
            DWMWA_NCRENDERING_POLICY = 2
            DWMNCRP_DISABLED = 1
            class I32(ctypes.Structure):
                _fields_ = [("v", ctypes.c_int)]
            dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_NCRENDERING_POLICY,
                ctypes.byref(I32(DWMNCRP_DISABLED)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception as e:
            print(f"DWM disable failed: {e}")

        # 移到右下角
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self._w - 50, screen.height() - self._h - 50)

        self._frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next)
        self._timer.start(125)

    def _draw_to_hbitmap(self, pm: QPixmap):
        """把 QPixmap 的像素数据写入 HBITMAP，返回 (hdc, hbitmap, old_bitmap)"""
        hdc = GetDC(0)
        mem_dc = CreateCompatibleDC(hdc)

        w, h = pm.width(), pm.height()
        hbitmap, bits = CreateDIBSection(mem_dc, (w, h))

        # QPixmap → HBITMAP
        hbm_old = SelectObject(mem_dc, hbitmap)

        # 用 Qt 画到 HDC
        from PyQt6.QtGui import QPaintDevice, QImage
        img = pm.toImage()
        img = img.convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)

        # 复制像素数据到 bits
        ptr = img.bits()
        ptr.setsize(w * h * 4)
        ctypes.memmove(bits, ptr, w * h * 4)

        SelectObject(mem_dc, hbm_old)
        ReleaseDC(0, hdc)
        return mem_dc, hbitmap

    def _update_layered(self):
        """用 UpdateLayeredWindow 更新窗口内容"""
        hwnd = int(self.winId())

        # 读取当前帧
        pm = QPixmap(f"assets/idle/{self._frame + 1:04d}.png")
        if pm.isNull():
            return
        pm = pm.scaled(self._w, self._h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

        # 创建 HBITMAP
        hdc_dst = GetDC(0)
        mem_dc = CreateCompatibleDC(hdc_dst)
        hbitmap, bits = CreateDIBSection(mem_dc, (self._w, self._h))

        # 复制像素
        img = pm.toImage().convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
        ptr = img.bits()
        ptr.setsize(self._w * self._h * 4)
        ctypes.memmove(bits, ptr, self._w * self._h * 4)

        hbm_old = SelectObject(mem_dc, hbitmap)

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
        class SIZE(ctypes.Structure):
            _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

        dst = POINT()
        size = SIZE(self._w, self._h)
        src = POINT(0, 0)

        BLENDFUNCTION = ctypes.c_ubyte * 4
        bf = BLENDFUNCTION(AC_SRC_OVER, 0, 255, ULW_ALPHA)

        UpdateLayeredWindow(hwnd, hdc_dst, ctypes.byref(dst), ctypes.byref(size),
                            mem_dc, ctypes.byref(src), 0, ctypes.byref(bf), ULW_ALPHA)

        SelectObject(mem_dc, hbm_old)
        DeleteObject(hbitmap)
        DeleteDC(mem_dc)
        ReleaseDC(0, hdc_dst)

    def _next(self):
        self._frame = (self._frame + 1) % 4
        self._update_layered()

    def showEvent(self, event):
        self._update_layered()

    # 鼠标拖拽
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.globalPosition().toPoint()
            self._origin = self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self._origin + (event.globalPosition().toPoint() - self._start))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = LayeredWindow()
    w.show()
    sys.exit(app.exec())
