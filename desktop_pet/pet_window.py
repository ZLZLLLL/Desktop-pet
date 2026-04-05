import ctypes
import json
import random
from ctypes import wintypes
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QLabel, QApplication, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QAbstractNativeEventFilter
from PyQt6.QtGui import QPixmap, QColor, QFont, QPainter, QPalette, QEnterEvent, QCursor, QAction

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
        # 移除窗口边框
        GWL_STYLE = -16
        WS_BORDER = 0x00800000
        WS_DLGFRAME = 0x00400000
        current_style = ctypes.windll.user32.GetWindowLongW(hwnd_int, GWL_STYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd_int, GWL_STYLE,
            current_style & ~WS_BORDER & ~WS_DLGFRAME
        )
        # 移除扩展窗口边框
        GWL_EXSTYLE = -20
        WS_EX_WINDOWEDGE = 0x00000100
        WS_EX_STATICEDGE = 0x00020000
        WS_EX_DLGMODALFRAME = 0x00000001
        current_ex_style = ctypes.windll.user32.GetWindowLongW(hwnd_int, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd_int, GWL_EXSTYLE,
            current_ex_style & ~WS_EX_WINDOWEDGE
            & ~WS_EX_STATICEDGE & ~WS_EX_DLGMODALFRAME
        )
        # 刷新窗口
        ctypes.windll.user32.SetWindowPos(
            hwnd_int, None, 0, 0, 0, 0,
            0x0001 | 0x0002 | 0x0004 | 0x0020
        )
    except Exception:
        pass


def _set_window_rgn(hwnd):
    """设置窗口区域为矩形（移除圆角）- 需在窗口创建后调用"""
    try:
        hwnd_int = int(hwnd)
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd_int, ctypes.byref(rect))
        window_w = rect.right - rect.left
        window_h = rect.bottom - rect.top
        hrgn = ctypes.windll.gdi32.CreateRectRgn(0, 0, window_w, window_h)
        ctypes.windll.user32.SetWindowRgn(hwnd_int, hrgn, True)
    except Exception:
        pass


def _disable_win11_window_frame(hwnd):
    """禁用 Win11 对无边框窗口附加的圆角与描边。"""
    try:
        hwnd_int = int(hwnd)
        # Windows 11 DWM attributes
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_DONOTROUND = 1
        DWMWA_BORDER_COLOR = 34
        DWMWA_COLOR_NONE = 0xFFFFFFFE

        class IVAL(ctypes.Structure):
            _fields_ = [("v", ctypes.c_int)]

        class UVAL(ctypes.Structure):
            _fields_ = [("v", ctypes.c_uint)]

        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd_int,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(IVAL(DWMWCP_DONOTROUND)),
            ctypes.sizeof(ctypes.c_int),
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd_int,
            DWMWA_BORDER_COLOR,
            ctypes.byref(UVAL(DWMWA_COLOR_NONE)),
            ctypes.sizeof(ctypes.c_uint),
        )
    except Exception:
        pass


class BubbleLabel(QLabel):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: rgba(255, 255, 255, 220);"
            "border: 2px solid #aaa;"
            "border-radius: 10px;"
            "padding: 6px 10px;"
            "color: #333;"
            "font-size: 12px;"
        )
        self.setFixedSize(138, 48)
        self.setText("")

    def setText(self, text: str):
        self._text = text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor("#aaa"))
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.setPen(QColor("#333"))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)

    def show_text(self, text: str, pos: QPoint):
        self._text = text
        self.repaint()
        self.move(pos.x(), pos.y() - self.height() - 10)
        self.show()
        self.raise_()


class _NativeBorderFilter(QAbstractNativeEventFilter):
    """阻止 Windows 为透明窗口绘制默认背景边框"""
    def __init__(self, hwnd):
        super().__init__()
        self._hwnd = int(hwnd)

    def nativeEventFilter(self, eventType, message):
        # 简化的消息拦截
        return (False, 0)  # 不过滤任何消息


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
        self._current_state = "sleep"
        self._current_frame = 0
        self._fps = 1
        self._loop = True
        self._remaining_loops = 0

        self._init_window()
        self._load_animations()
        self._init_ui()
        self._init_timer()
        self._init_click_detection()
        self._animation_started = False
        self._feeding_mode = False
        self._feed_eat_cooldown = False

        # Bubble
        self.bubble = BubbleLabel()
        self._bubble_timer = QTimer()
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.setInterval(1500)
        self._bubble_timer.timeout.connect(self.bubble.hide)

        self._dialog_chain_queue: list[str] = []
        self._dialog_chain_timer = QTimer()
        self._dialog_chain_timer.setSingleShot(True)
        self._dialog_chain_timer.timeout.connect(self._show_next_dialog_in_chain)

        self._feed_timer = QTimer()
        self._feed_timer.setInterval(60)
        self._feed_timer.timeout.connect(self._follow_mouse_when_feeding)

        # 初始化完成后在 showEvent 中再启动动画，避免窗口创建阶段设置 mask

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
                "sleep":   {"fps": 1,  "loop": True},
                "idle":    {"fps": 3,  "loop": True},
                "run":     {"fps": 4,  "loop": False, "play_times": 3},
                "jump":    {"fps": 4,  "loop": False, "play_times": 3},
                "click":   {"fps": 4,  "loop": False, "play_times": 3},
                "levelup": {"fps": 3,  "loop": False, "play_times": 2},
            },
        }

    def _init_window(self):
        w = self._config["window"].get("width", 200)
        h = self._config["window"].get("height", 200)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(w, h)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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
        from PyQt6.QtGui import QPainter
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 画一个圆形占位符
        from PyQt6.QtGui import QPen, QBrush
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(2, 2, w - 4, h - 4)
        painter.end()
        return pixmap

    def _load_animations(self):
        colors = {
            "sleep":   QColor(100, 180, 255),
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
            if state_name == "sleep" and not folder.exists():
                # 项目里睡觉帧当前放在 levelup 目录，优先使用它
                levelup_folder = self.ASSETS_PATH / "levelup"
                folder = levelup_folder if levelup_folder.exists() else self.ASSETS_PATH / "idle"
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
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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

    def _start_animation(self, state_name: str, force_loop: bool | None = None, force_play_times: int | None = None):
        if state_name not in self._animations:
            state_name = "sleep" if "sleep" in self._animations else "idle"
        self._current_state = state_name
        self._current_frame = 0

        # 默认待机改为静态首帧展示，不再循环播放
        if state_name == "sleep":
            self._timer.stop()
            self._update_frame()
            return

        anim_cfg = self._config["animations"].get(state_name, {})
        self._fps = anim_cfg.get("fps", 1 if state_name == "sleep" else 8)
        self._loop = anim_cfg.get("loop", state_name in ("sleep", "idle")) if force_loop is None else force_loop
        play_times = anim_cfg.get("play_times", 1) if force_play_times is None else force_play_times
        self._remaining_loops = max(1, int(play_times))

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
                self._remaining_loops -= 1
                if self._remaining_loops > 0:
                    self._current_frame = 0
                else:
                    self._timer.stop()
                    if self._feeding_mode and self._current_state == "click":
                        self._feed_eat_cooldown = False
                        self._start_animation("run", force_loop=True, force_play_times=999999)
                        return
                    idle_state = self.state_machine.on_animation_done()
                    self._start_animation(idle_state)
                    return
        self._update_frame()

    def _update_frame(self):
        frames = self._animations.get(self._current_state, [])
        if frames:
            idx = min(self._current_frame, len(frames) - 1)
            frame = frames[idx]
            self._label.setPixmap(frame)

            # 使用帧自带的 mask() 方法
            mask = frame.mask()
            if mask and not mask.isNull():
                self.setMask(mask)
            else:
                # 如果帧没有 mask，使用 alpha mask
                img = frame.toImage()
                if img.hasAlphaChannel():
                    alpha_mask = img.createAlphaMask()
                    if not alpha_mask.isNull():
                        self.setMask(QPixmap.fromImage(alpha_mask))

    # ─── Bubble ──────────────────────────────────────────────

    def _show_bubble(self, text: str):
        pos = self.pos()
        bx = pos.x() + self.width() // 2 - self.bubble.width() // 2
        by = pos.y()
        self.bubble.show_text(text, QPoint(bx, by))
        self._bubble_timer.stop()
        self._bubble_timer.start()

    def _queue_dialog_chain(self, level: int):
        first = self.dialog_system.get_dialog(level)
        if not first:
            return

        # 每次点击至少 1 条，并随机追加 0~2 条对话
        count = 1 + random.randint(0, 2)
        lines = [first]
        for _ in range(count - 1):
            extra = self.dialog_system.get_dialog(level)
            if extra:
                lines.append(extra)

        if not lines:
            return

        self._dialog_chain_queue = lines[1:]
        self._show_bubble(lines[0])
        if self._dialog_chain_queue:
            self._dialog_chain_timer.start(self._bubble_timer.interval() + 250)

    def _show_next_dialog_in_chain(self):
        if not self._dialog_chain_queue:
            return
        text = self._dialog_chain_queue.pop(0)
        self._show_bubble(text)
        if self._dialog_chain_queue:
            self._dialog_chain_timer.start(self._bubble_timer.interval() + 250)

    def _start_feeding_mode(self):
        self._feeding_mode = True
        self._feed_eat_cooldown = False
        self._dialog_chain_queue.clear()
        self._dialog_chain_timer.stop()
        self._start_animation("run", force_loop=True, force_play_times=999999)
        self._feed_timer.start()
        self._show_bubble("喂食中，跟着鼠标跑！")

    def _stop_feeding_mode(self):
        self._feeding_mode = False
        self._feed_eat_cooldown = False
        self._feed_timer.stop()
        self._dialog_chain_queue.clear()
        self._dialog_chain_timer.stop()
        self._start_animation("sleep")
        self._show_bubble("已取消喂食")

    def _follow_mouse_when_feeding(self):
        if not self._feeding_mode:
            return

        cursor = QCursor.pos()
        target = QPoint(cursor.x() - self.width() // 2, cursor.y() - self.height() // 2)
        pos = self.pos()

        dx = target.x() - pos.x()
        dy = target.y() - pos.y()
        dist2 = dx * dx + dy * dy

        # 缓慢追踪
        step = 5
        if dist2 > step * step:
            # 吃东西动画播放中时，不要被追踪逻辑打断
            if self._current_state == "click":
                return
            import math
            dist = math.sqrt(dist2)
            move_x = int(round(dx / dist * step))
            move_y = int(round(dy / dist * step))
            self.move(pos.x() + move_x, pos.y() + move_y)
            self._update_bubble_position()
            if self._current_state != "run":
                self._start_animation("run", force_loop=True, force_play_times=999999)
            return

        # 追上后播放吃东西动画
        if not self._feed_eat_cooldown:
            self._feed_eat_cooldown = True
            self._start_animation("click", force_loop=False, force_play_times=1)
            self._show_bubble("开吃！")

    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)
        if self._feeding_mode:
            action_feed = QAction("取消喂食", self)
            action_feed.triggered.connect(self._stop_feeding_mode)
        else:
            action_feed = QAction("喂食", self)
            action_feed.triggered.connect(self._start_feeding_mode)
        menu.addAction(action_feed)
        menu.exec(global_pos)

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
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            return
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
        self._queue_dialog_chain(self.intimacy_system.get_current_level())

    def _handle_double_click(self):
        val, level_up = self.intimacy_system.add_double_click_intimacy()
        if level_up:
            self._trigger_level_up()
            return
        state = self.state_machine.on_double_click(self.intimacy_system.get_unlocked_animations())
        self._start_animation(state)
        self._queue_dialog_chain(self.intimacy_system.get_current_level())

    def _trigger_level_up(self):
        self._start_animation("levelup")
        text = self.dialog_system.get_levelup_dialog()
        if text:
            self._show_bubble(text)

    # ─── Public helpers ──────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._animation_started:
            self._animation_started = True
            self._start_animation("sleep")
        QTimer.singleShot(0, lambda: _disable_win11_window_frame(self.winId()))

    def reset_position(self):
        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        margin = self._config["window"].get("margin", 50)
        x = geo.width() - self.width() - margin
        y = geo.height() - self.height() - margin
        self.move(x, y)
        self._update_bubble_position()
