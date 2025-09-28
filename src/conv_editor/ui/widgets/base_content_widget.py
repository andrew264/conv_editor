import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QMimeData, Qt, Signal, Slot
from PySide6.QtGui import QDrag, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from conv_editor.core.models import ContentItem
    from conv_editor.ui.widgets.item_widget import ItemWidget

logger = logging.getLogger(__name__)


class ContentHeaderWidget(QWidget):
    drag_started = Signal(QMouseEvent)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_position = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton and self._drag_start_position):
            super().mouseMoveEvent(event)
            return

        if (event.position().toPoint() - self._drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        self.drag_started.emit(event)
        self._drag_start_position = None

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_position = None
        super().mouseReleaseEvent(event)


class BaseContentWidget(QWidget):
    content_changed = Signal()
    request_delete = Signal(int)

    def __init__(self, content_item: "ContentItem", index: int, colors: dict, parent=None):
        super().__init__(parent)
        self.content_item = content_item
        self.index = index
        self.colors = colors
        self._setup_base_ui()

    def _setup_base_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(4)

        self.header_widget = ContentHeaderWidget(self)
        self.header_widget.drag_started.connect(self._initiate_drag)
        self.header_widget.setCursor(Qt.CursorShape.OpenHandCursor)
        self.header_widget.setToolTip("Click and drag to move this block")

        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.type_label = QLabel(f"<b>{self.content_item.type.replace('_', ' ').title()}</b>")
        self.type_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        self.toggle_button = QPushButton(QIcon.fromTheme("system-run"), "")
        self.toggle_button.setToolTip("Toggle the learnable state of the entire block")
        self.toggle_button.setFixedSize(25, 25)
        self.toggle_button.setFlat(True)
        self.toggle_button.setVisible(False)

        remove_button = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton), "")
        remove_button.setToolTip(f"Remove this '{self.content_item.type}' block")
        remove_button.setFixedSize(25, 25)
        remove_button.setFlat(True)
        remove_button.clicked.connect(lambda: self.request_delete.emit(self.index))

        header_layout.addWidget(self.type_label)
        header_layout.addWidget(self.toggle_button)
        header_layout.addStretch()
        header_layout.addWidget(remove_button)

        self.editor_widget = self._create_editor_widget()

        main_layout.addWidget(self.header_widget)
        main_layout.addWidget(self.editor_widget)

    def _create_editor_widget(self) -> QWidget:
        raise NotImplementedError

    def update_colors(self, colors: dict):
        self.colors = colors

    @Slot(QMouseEvent)
    def _initiate_drag(self, event: QMouseEvent):
        drag = QDrag(self)
        mime_data = QMimeData()

        parent_item_candidate = self.parent().parent()

        if not isinstance(parent_item_candidate, QWidget) or not hasattr(parent_item_candidate, "index"):
            logger.warning("Could not find valid ItemWidget parent for drag operation. Found type: %s", type(parent_item_candidate))
            return

        parent_item: "ItemWidget" = parent_item_candidate

        payload = {
            "source_item_index": parent_item.index,
            "source_content_index": self.index,
        }
        json_payload = json.dumps(payload).encode("utf-8")
        mime_data.setData("application/x-conv-editor-content", QByteArray(json_payload))
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap)

        hot_spot = self.header_widget.mapTo(self, event.position().toPoint())
        drag.setHotSpot(hot_spot)

        self.header_widget.setCursor(Qt.CursorShape.ClosedHandCursor)

        drag.exec(Qt.DropAction.MoveAction)

        self.header_widget.setCursor(Qt.CursorShape.OpenHandCursor)
