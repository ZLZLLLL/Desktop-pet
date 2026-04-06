from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class AddTodoBubble(QWidget):
    submit_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(10, 9, 10, 9)
        self._root_layout.setSpacing(7)

        self._summary_edit = QLineEdit(self)
        self._summary_edit.setPlaceholderText("请输入待办内容...")
        self._summary_edit.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(255, 255, 255, 14);"
            "  color: #F2F2F2;"
            "  border: 1px solid rgba(230, 230, 230, 120);"
            "  border-radius: 7px;"
            "  padding: 5px 8px;"
            "  font-size: 12px;"
            "}"
            "QLineEdit:focus { border-color: rgba(245, 245, 245, 210); }"
        )
        self._root_layout.addWidget(self._summary_edit)

        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(8)

        self._group = QButtonGroup(self)

        self._radio_today = QRadioButton("今天", self)
        self._radio_tomorrow = QRadioButton("明天", self)
        self._radio_after = QRadioButton("后天", self)
        self._radio_today.setChecked(True)

        for btn in (self._radio_today, self._radio_tomorrow, self._radio_after):
            btn.setStyleSheet(
                "QRadioButton { color: #ECECEC; font-size: 11px; spacing: 5px; }"
                "QRadioButton::indicator { width: 10px; height: 10px; }"
                "QRadioButton::indicator:unchecked {"
                "  border: 1px solid rgba(230, 230, 230, 160);"
                "  border-radius: 5px;"
                "  background: rgba(255, 255, 255, 10);"
                "}"
                "QRadioButton::indicator:checked {"
                "  border: 1px solid #D9D9D9;"
                "  border-radius: 5px;"
                "  background: #D9D9D9;"
                "}"
            )
            self._group.addButton(btn)
            control_row.addWidget(btn)

        control_row.addStretch(1)

        self._cancel_btn = QPushButton("取消", self)
        self._ok_btn = QPushButton("确定", self)

        self._cancel_btn.clicked.connect(self.hide)
        self._ok_btn.clicked.connect(self._emit_submit)
        self._summary_edit.returnPressed.connect(self._emit_submit)

        self._cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255, 255, 255, 12);"
            "  color: #F0F0F0;"
            "  border: 1px solid rgba(225, 225, 225, 130);"
            "  border-radius: 7px;"
            "  padding: 3px 10px;"
            "  font-size: 11px;"
            "}"
            "QPushButton:hover { background: rgba(255, 255, 255, 20); }"
        )
        self._ok_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255, 255, 255, 18);"
            "  color: #F8F8F8;"
            "  border: 1px solid rgba(235, 235, 235, 150);"
            "  border-radius: 7px;"
            "  padding: 3px 10px;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "}"
            "QPushButton:hover { background: rgba(255, 255, 255, 28); }"
        )

        control_row.addWidget(self._cancel_btn)
        control_row.addWidget(self._ok_btn)
        self._root_layout.addLayout(control_row)

        self._max_width = 312
        self.setFixedWidth(self._max_width)
        self._filter_installed = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawRect(self.rect())

    def _due_str(self) -> str:
        if self._radio_tomorrow.isChecked():
            return "+1d"
        if self._radio_after.isChecked():
            return "+2d"
        return "+0d"

    def _emit_submit(self):
        summary = self._summary_edit.text().strip()
        if not summary:
            self._summary_edit.setFocus()
            return
        self.submit_signal.emit(summary, self._due_str())
        self.hide()

    def _move_above_pet(self, pet_rect):
        center = QPoint(pet_rect.x() + pet_rect.width() // 2, pet_rect.y() + pet_rect.height() // 2)
        screen = QApplication.screenAt(center)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            self.move(pet_rect.x(), max(0, pet_rect.y() - self.height() - 10))
            return

        geo = screen.availableGeometry()
        x = pet_rect.x() + (pet_rect.width() - self.width()) // 2
        y = pet_rect.y() - self.height() - 10

        x = max(geo.left() + 8, min(x, geo.right() - self.width() - 8))
        if y < geo.top() + 8:
            y = min(pet_rect.y() + pet_rect.height() + 10, geo.bottom() - self.height() - 8)

        self.move(x, y)

    def _install_outside_click_filter(self):
        app = QApplication.instance()
        if app is not None and not self._filter_installed:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_outside_click_filter(self):
        app = QApplication.instance()
        if app is not None and self._filter_installed:
            app.removeEventFilter(self)
            self._filter_installed = False

    def show_above_pet(self, pet_rect):
        self.adjustSize()
        self.setFixedWidth(self._max_width)
        self._move_above_pet(pet_rect)
        self.show()
        self.raise_()
        self._summary_edit.setFocus()

    def update_position(self, pet_rect):
        if self.isVisible():
            self._move_above_pet(pet_rect)

    def showEvent(self, event):
        self._install_outside_click_filter()
        super().showEvent(event)

    def hideEvent(self, event):
        self._remove_outside_click_filter()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if not self.isVisible():
            return super().eventFilter(obj, event)

        if event.type() == event.Type.MouseButtonPress:
            global_pos = None
            if hasattr(event, "globalPosition"):
                global_pos = event.globalPosition().toPoint()
            elif hasattr(event, "globalPos"):
                global_pos = event.globalPos()

            if global_pos is not None and not self.frameGeometry().contains(global_pos):
                self.hide()

        return super().eventFilter(obj, event)
