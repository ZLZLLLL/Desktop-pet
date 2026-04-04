import ctypes
import json
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QLabel, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QColor, QFont, QPainter, QPalette

from state_machine import StateMachine
from intimacy import Intimacy
from dialog_bubble import DialogBubble
from data_manager import DataManager


def _remove_dwm_shadow(hwnd):
    """禁用 Windows DWM 对该窗口的阴影效果"""
    try:
        hwnd_int = int(hwnd)
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        class IVAL(ctypes.Structure):
            _fields_ = [("v", ctypes.c_int)]
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd_int, DWMWA_NCRENDERING_POLICY,
            ctypes.byref(IVAL(DWMNCRP_DISABLED)),
            ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass


class BubbleLabel(QLabel):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: rgba(255, 255, 255, 220);"
            "border: 2px solid #aaa;"
            "border-radius: 12px;"
            "padding: 8px 14px;"
            "color: #333;"
            "font-size: 14px;"
        )
        self.setFixedSize(180, 60)
        self.setText("")

    def setText(self, text: str):
        self._text = text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor("#aaa"))
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        painter.setPen(QColor("#333"))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)

    def show_text(self, text: str, pos: QPoint):
        self._text = text
        self.repaint()
        self.move(pos.x(), pos.y() - self.height() - 10)
        self.show()
        self.raise_()


class PetWindow(QWidget):
    CONFIG_PATH = Path(__file__).parent / "config.json"
    ASSETS_PATH = Path(__file__).parent / "assets"

    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.state_machine = StateMachine()
        self.intimacy_system = Intimacy(data_manager)
        self.dialog_system = DialogBubble()

        self._config = self._load_config()
        self._animations: dict[str, list[QPixmap]] = {}
        self._current_state = "idle"
        self._current_frame = 0
        self._fps = 8
        self._loop = True

        self._init_window()
        self._load_animations()
        self._init_ui()
        self._init_timer()
        self._init_click_detection()

        # Bubble
        self.bubble = BubbleLabel()
        self._bubble_timer = QTimer()
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.setInterval(2000)
        self._bubble_timer.timeout.connect(self.bubble.hide)

        # 初始化完成后统一启动 idle 动画
        self._start_animation("idle")

        # Apply daily bonus on start
        val, level_up = self.intimacy_system.add_daily_bonus()
        if level_up:
            self._trigger_level_up()
        else:
            text = self.dialog_system.get_daily_first_dialog()
            if text:
                self._show_bubble(text)

    def _load_config(self) -> dict:
        try:
            if self.CONFIG_PATH.exists():
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {
            "window": {"width": 200, "height": 200, "default_position": "bottom_right", "margin": 50},
            "animations": {
                "idle":    {"fps": 8,  "loop": True},
                "run":     {"fps": 12, "loop": False},
                "jump":    {"fps": 10, "loop": False},
                "click":   {"fps": 10, "loop": False},
                "levelup": {"fps": 10, "loop": False},
            },
        }

    def _init_window(self):
        w = self._config["window"].get("width", 200)
        h = self._config["window"].get("height", 200)
        self.setFixedSize(w, h)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setBackgroundRole(QPalette.ColorRole.NoRole)
        self.setAutoFillBackground(False)
        self.setPalette(QPalette())
        self.setContentsMargins(0, 0, 0, 0)

        _remove_dwm_shadow(self.winId())

        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        default_margin = self._config["window"].get("margin", 50)
        x = geo.width() - w - default_margin
        y = geo.height() - h - default_margin
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

    def _generate_placeholder(self, w: int, h: int, color: QColor) -> QPixmap:
        pixmap = QPixmap(w, h)
        pixmap.fill(color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255, 180))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        return pixmap

    def _load_animations(self):
        colors = {
            "idle":    QColor(100, 180, 255),
            "run":     QColor(255, 160, 60),
            "jump":    QColor(120, 220, 120),
            "click":   QColor(255, 100, 120),
            "levelup": QColor(200, 140, 255),
        }
        w = self._config["window"].get("width", 200)
        h = self._config["window"].get("height", 200)

        for state_name in self._config["animations"]:
            folder = self.ASSETS_PATH / state_name
            frames = []
            if folder.exists():
                imgs = sorted(folder.glob("*.png")) + sorted(folder.glob("*.jpg"))
                imgs = sorted(imgs)
                for p in imgs:
                    pm = QPixmap(str(p)).scaled(
                        w, h,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    if not pm.isNull():
                        frames.append(pm)
            if not frames:
                frames.append(self._generate_placeholder(w, h, colors.get(state_name, QColor(200, 200, 200))))
            self._animations[state_name] = frames

    def _init_ui(self):
        self._label = QLabel(self)
        self._label.setGeometry(0, 0, self.width(), self.height())
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 关键：关掉 QLabel 默认的 frameShape 边框！
        self._label.setFrameShape(QLabel.Shape.NoFrame)
        self._label.setBackgroundRole(QPalette.ColorRole.NoRole)
        self._label.setAutoFillBackground(False)
        self._label.setPalette(QPalette())
        self._label.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")
        self._update_frame()

    def _init_timer(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._advance_frame)

    def _start_animation(self, state_name: str):
        if state_name not in self._animations:
            state_name = "idle"
        self._current_state = state_name
        self._current_frame = 0
        anim_cfg = self._config["animations"].get(state_name, {})
        self._fps = anim_cfg.get("fps", 8)
        self._loop = anim_cfg.get("loop", state_name == "idle")

        self._timer.stop()
        interval = max(16, int(1000 / max(1, self._fps)))
        self._timer.setInterval(interval)
        self._timer.start()
        self._update_frame()

    def _advance_frame(self):
        frames = self._animations.get(self._current_state, [])
        if not frames:
            return
        self._current_frame += 1
        if self._current_frame >= len(frames):
            if self._loop:
                self._current_frame = 0
            else:
                self._timer.stop()
                idle_state = self.state_machine.on_animation_done()
                self._start_animation(idle_state)
                return
        self._update_frame()

    def _update_frame(self):
        frames = self._animations.get(self._current_state, [])
        if frames:
            idx = min(self._current_frame, len(frames) - 1)
            self._label.setPixmap(frames[idx])

    # ─── Bubble ──────────────────────────────────────────────

    def _show_bubble(self, text: str):
        pos = self.pos()
        bx = pos.x() + self.width() // 2 - self.bubble.width() // 2
        by = pos.y()
        self.bubble.show_text(text, QPoint(bx, by))
        self._bubble_timer.stop()
        self._bubble_timer.start()

    def _update_bubble_position(self):
        if self.bubble.isVisible():
            pos = self.pos()
            bx = pos.x() + self.width() // 2 - self.bubble.width() // 2
            by = pos.y()
            self.bubble.move(bx, by - self.bubble.height() - 10)

    # ─── Mouse events ────────────────────────────────────────

    def _init_click_detection(self):
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._click_timer.timeout.connect(self._handle_click)
        self._pending_double = False

        self.is_dragging = False
        self._drag_start = QPoint()
        self._drag_pos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self._drag_start = event.globalPosition().toPoint()
            self._drag_pos = self.pos()
            if self._click_timer.isActive():
                self._click_timer.stop()
                self._pending_double = True
            else:
                self._pending_double = False

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self._drag_start
            if diff.manhattanLength() > 5:
                self.is_dragging = True
                new_pos = self._drag_pos + diff
                self.move(new_pos)
                self._update_bubble_position()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_dragging:
                self.is_dragging = False
                return
            if self._pending_double:
                self._pending_double = False
                self._handle_double_click()
            else:
                self._click_timer.start()

    def _handle_click(self):
        val, level_up = self.intimacy_system.add_click_intimacy()
        if level_up:
            self._trigger_level_up()
            return
        state = self.state_machine.on_click(self.intimacy_system.get_unlocked_animations())
        self._start_animation(state)
        text = self.dialog_system.get_dialog(self.intimacy_system.get_current_level())
        if text:
            self._show_bubble(text)

    def _handle_double_click(self):
        val, level_up = self.intimacy_system.add_double_click_intimacy()
        if level_up:
            self._trigger_level_up()
            return
        state = self.state_machine.on_double_click(self.intimacy_system.get_unlocked_animations())
        self._start_animation(state)
        text = self.dialog_system.get_dialog(self.intimacy_system.get_current_level())
        if text:
            self._show_bubble(text)

    def _trigger_level_up(self):
        self._start_animation("levelup")
        text = self.dialog_system.get_levelup_dialog()
        if text:
            self._show_bubble(text)

    # ─── Public helpers ──────────────────────────────────────

    def reset_position(self):
        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        margin = self._config["window"].get("margin", 50)
        x = geo.width() - self.width() - margin
        y = geo.height() - self.height() - margin
        self.move(x, y)
        self._update_bubble_position()
