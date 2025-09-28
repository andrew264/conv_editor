import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QMimeData, Qt, Signal, Slot
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from conv_editor.core.models import (
    FunctionParameters,
    FunctionSchema,
    Item,
    ReasoningContent,
    TextContent,
    ToolCall,
    ToolCallContent,
    ToolDefinition,
    ToolResult,
    ToolResultsContent,
    ToolsContent,
)
from conv_editor.ui.widgets.base_content_widget import BaseContentWidget
from conv_editor.ui.widgets.drop_indicator import DropIndicator
from conv_editor.ui.widgets.text_content_widgets import ReasoningContentWidget, TextContentWidget
from conv_editor.ui.widgets.tool_content_widgets import ToolCallWidget, ToolResultsWidget, ToolsWidget

if TYPE_CHECKING:
    from conv_editor.core.conversation import Conversation

logger = logging.getLogger(__name__)

WIDGET_MAP = {
    "text": TextContentWidget,
    "reason": ReasoningContentWidget,
    "tools": ToolsWidget,
    "tool_call": ToolCallWidget,
    "tool_response": ToolResultsWidget,
}


class ItemWidget(QFrame):
    item_changed = Signal()
    request_delete = Signal(int)
    request_generate = Signal(int)
    request_chat = Signal(int)
    request_global_rerender = Signal()

    def __init__(
        self,
        item: Item,
        index: int,
        model: "Conversation",
        assistant_name: str,
        colors: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.item = item
        self.index = index
        self.model = model
        self.assistant_name = assistant_name
        self.colors = colors
        self.drag_start_position = None

        self.setAcceptDrops(True)
        self._setup_ui()
        self.content_drop_indicator = DropIndicator(self.content_area)

    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)

        top_row_layout = self._create_top_row()
        main_layout.addLayout(top_row_layout)

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 0, 10, 0)
        main_layout.addWidget(self.content_area)
        self._build_content_widgets()

        self.add_content_button = QPushButton("+ Add Content")
        self.add_content_button.clicked.connect(self._show_add_content_menu)
        main_layout.addWidget(self.add_content_button, 0, Qt.AlignmentFlag.AlignLeft)

        self._update_action_button_visibility()

    def _create_top_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.drag_handle = QLabel("⠿")
        self.drag_handle.setFixedWidth(20)
        self.drag_handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self.drag_handle.setToolTip("Click and drag to reorder item")
        layout.addWidget(self.drag_handle)

        self.role_edit = QLineEdit(self.item.role)
        self.role_edit.setFixedWidth(100)
        self.role_edit.editingFinished.connect(self._on_role_changed)
        layout.addWidget(QLabel("Role:"))
        layout.addWidget(self.role_edit)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(lambda: self.request_generate.emit(self.index))
        layout.addWidget(self.generate_button)

        self.chat_button = QPushButton("Chat")
        self.chat_button.clicked.connect(lambda: self.request_chat.emit(self.index))
        layout.addWidget(self.chat_button)

        remove_button = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon), "")
        remove_button.setFixedSize(25, 25)
        remove_button.setFlat(True)
        remove_button.setToolTip("Remove this entire item")
        remove_button.clicked.connect(lambda: self.request_delete.emit(self.index))
        layout.addWidget(remove_button)

        return layout

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_handle.geometry().contains(event.pos()):
            self.drag_start_position = event.position().toPoint()
            self.drag_handle.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton and self.drag_start_position):
            super().mouseMoveEvent(event)
            return

        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        payload = {"source_item_index": self.index}
        json_payload = json.dumps(payload).encode("utf-8")
        mime_data.setData("application/x-conv-editor-item", QByteArray(json_payload))
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())

        drag.exec(Qt.DropAction.MoveAction)
        self.drag_start_position = None
        self.drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-conv-editor-content"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.content_drop_indicator.hide()
        event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent):
        pos_in_content_area = self.content_area.mapFrom(self, event.position().toPoint())
        target_idx, y_pos = self._get_content_drop_pos(pos_in_content_area)

        if y_pos is not None:
            self.content_drop_indicator.move(0, y_pos)
            self.content_drop_indicator.setFixedWidth(self.content_area.width())
            self.content_drop_indicator.show()
            event.acceptProposedAction()
        else:
            self.content_drop_indicator.hide()
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        self.content_drop_indicator.hide()
        if not event.mimeData().hasFormat("application/x-conv-editor-content"):
            event.ignore()
            return

        try:
            mime_data = event.mimeData().data("application/x-conv-editor-content")
            payload = json.loads(mime_data.data().decode("utf-8"))
            source_item_index = payload["source_item_index"]
            source_content_index = payload["source_content_index"]
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to decode drop event payload: {e}")
            event.ignore()
            return

        pos_in_content_area = self.content_area.mapFrom(self, event.position().toPoint())
        target_content_index, _ = self._get_content_drop_pos(pos_in_content_area)

        self.model.move_content(source_item_index, source_content_index, self.index, target_content_index)
        self.request_global_rerender.emit()
        event.acceptProposedAction()

    def _get_content_drop_pos(self, pos) -> tuple[int, int]:
        if self.content_layout.count() == 0:
            return 0, 0

        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if not widget:
                continue

            if pos.y() < widget.y() + widget.height() / 2:
                return i, widget.y()

        last_widget = self.content_layout.itemAt(self.content_layout.count() - 1).widget()
        return self.content_layout.count(), last_widget.y() + last_widget.height()

    def _build_content_widgets(self):
        while (item := self.content_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()

        for idx, content_item in enumerate(self.item.content):
            widget_class = WIDGET_MAP.get(content_item.type)

            if widget_class:
                widget = widget_class(content_item, idx, self.colors, self)
                widget.content_changed.connect(self._update_model)
                widget.request_delete.connect(self._on_delete_content_requested)
                self.content_layout.addWidget(widget)
            else:
                unknown_label = QLabel(f"Unsupported content type: '{content_item.type}'")
                unknown_label.setStyleSheet("color: red; font-style: italic;")
                self.content_layout.addWidget(unknown_label)
                logger.warning(f"No widget found for content type: {content_item.type}")

    def update_all_colors(self, colors: dict):
        self.colors = colors
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if isinstance(widget, BaseContentWidget):
                widget.update_colors(colors)

    def _update_model(self):
        self.model.update_item(self.index, self.item)
        self.item_changed.emit()

    @Slot()
    def _on_role_changed(self):
        new_role = self.role_edit.text().strip()
        if new_role and self.item.role != new_role:
            self.item.role = new_role
            self._update_model()
            self._update_action_button_visibility()

    def update_assistant_name(self, new_name: str):
        self.assistant_name = new_name
        self._update_action_button_visibility()

    def _update_action_button_visibility(self):
        is_assistant = self.item.role == self.assistant_name
        self.generate_button.setVisible(is_assistant)
        self.chat_button.setVisible(is_assistant)

    @Slot(int)
    def _on_delete_content_requested(self, content_index: int):
        if 0 <= content_index < len(self.item.content):
            del self.item.content[content_index]
            self._update_model()
            self._build_content_widgets()

    @Slot()
    def _show_add_content_menu(self):
        menu = QMenu(self)
        add_text_action = menu.addAction("Add Text")
        add_reason_action = menu.addAction("Add Reason")
        menu.addSeparator()
        add_tools_action = menu.addAction("Add Tools")
        add_tool_call_action = menu.addAction("Add Tool Call")
        add_tool_response_action = menu.addAction("Add Tool Response")

        action = menu.exec(self.add_content_button.mapToGlobal(self.add_content_button.rect().bottomLeft()))

        new_content = None
        if action == add_text_action:
            new_content = TextContent(segments=[])
        elif action == add_reason_action:
            new_content = ReasoningContent(segments=[])
        elif action == add_tools_action:
            if self.item.role != "system":
                QMessageBox.information(self, "Role Suggestion", "Tool definitions are typically placed in an item with the 'system' role.")
            default_tool = ToolDefinition(
                function=FunctionSchema(
                    name="get_current_weather",
                    description="Get the current weather in a given location",
                    parameters=FunctionParameters(
                        properties={
                            "location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"},
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        },
                        required=["location"],
                    ),
                )
            )
            new_content = ToolsContent(definitions=[default_tool])
        elif action == add_tool_call_action:
            new_content = ToolCallContent(calls=[ToolCall(name="function_name", arguments={"arg": "value"})])
        elif action == add_tool_response_action:
            new_content = ToolResultsContent(results=[ToolResult(name="function_name", content="example result")])
            if self.item.role != "tool":
                self.item.role = "tool"
                self.role_edit.setText("tool")
                self._update_action_button_visibility()
        else:
            return

        if new_content:
            self.item.content.append(new_content)
            self._update_model()
            self._build_content_widgets()
