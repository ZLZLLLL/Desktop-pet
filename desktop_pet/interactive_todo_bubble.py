from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QCheckBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class InteractiveTodoBubble(QWidget):
    task_checked_signal = pyqtSignal(str)

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

        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(14, 12, 14, 12)
        self._content_layout.setSpacing(8)

        self._task_widgets: list[QCheckBox] = []
        self._max_width = 360
        self._last_pet_pos = QPoint(0, 0)
        self._filter_installed = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(220, 235, 255, 120), 1))
        painter.setBrush(QColor(15, 23, 35, 150))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

    def _clear_task_widgets(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_task_toggled(self, guid: str, checkbox: QCheckBox, checked: bool):
        if not checked:
            return

        checkbox.setDisabled(True)
        font = checkbox.font()
        font.setStrikeOut(True)
        checkbox.setFont(font)
        self.task_checked_signal.emit(guid)

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
        self._last_pet_pos = QPoint(pet_rect.x(), pet_rect.y())

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

    def show_tasks(self, tasks: list[dict], pet_rect):
        self._clear_task_widgets()
        self._task_widgets.clear()

        if not tasks:
            empty_label = QLabel("当前没有待办", self)
            empty_label.setStyleSheet(
                "QLabel {"
                "  background-color: transparent;"
                "  color: #EAF2FF;"
                "  padding: 2px 0;"
                "}"
            )
            self._content_layout.addWidget(empty_label)
        else:
            for task in tasks:
                guid = str(task.get("guid") or "")
                title = str(task.get("title") or "(未命名任务)")
                due_time = str(task.get("due_time") or "").strip()

                row_widget = QWidget(self)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                checkbox = QCheckBox(title, row_widget)
                checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
                checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                checkbox.setStyleSheet(
                    "QCheckBox {"
                    "  color: #F3F7FF;"
                    "  font-size: 13px;"
                    "  spacing: 10px;"
                    "  padding: 2px 0;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 14px;"
                    "  height: 14px;"
                    "  border: 1px solid rgba(255, 255, 255, 170);"
                    "  border-radius: 3px;"
                    "  background: rgba(255, 255, 255, 28);"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #7FC3FF;"
                    "  border-color: #7FC3FF;"
                    "}"
                    "QCheckBox:disabled { color: rgba(243, 247, 255, 130); }"
                )
                checkbox.toggled.connect(
                    lambda checked, g=guid, cb=checkbox: self._on_task_toggled(g, cb, checked)
                )

                due_label = QLabel(due_time, row_widget)
                due_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                due_label.setStyleSheet("color: #D7E7FF; font-size: 12px;")
                due_label.setFixedWidth(126)
                due_label.setVisible(bool(due_time))

                row_layout.addWidget(checkbox, 1)
                row_layout.addWidget(due_label, 0)

                self._content_layout.addWidget(row_widget)
                self._task_widgets.append(checkbox)

        self.setMaximumWidth(self._max_width)
        self.setFixedWidth(self._max_width)
        self.adjustSize()
        self._move_above_pet(pet_rect)
        self.show()
        self.raise_()

    def update_position(self, pet_rect):
        if self.isVisible():
            self._move_above_pet(pet_rect)
