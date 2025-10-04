import json
import logging
from typing import List, TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QTextEdit, QWidget

from conv_editor.core.commands.content_commands import UpdateContentCommand
from conv_editor.core.models import ToolCall, ToolCallContent, ToolDefinition, ToolResult, ToolResultsContent, ToolsContent
from conv_editor.ui.widgets.base_content_widget import BaseContentWidget

if TYPE_CHECKING:
    from conv_editor.core.models import ContentItem

logger = logging.getLogger(__name__)


class ToolsWidget(BaseContentWidget):
    content_item: "ToolsContent"

    def __init__(self, content_item: "ContentItem", index: int, colors: dict, undo_manager, parent=None):
        super().__init__(content_item, index, colors, undo_manager, parent)
        self.toggle_button.setVisible(False)
        self.update_colors(colors)
        self.content_on_focus = None

    def _create_editor_widget(self) -> QWidget:
        self.json_edit = QTextEdit()
        self.json_edit.setAcceptRichText(False)
        self.json_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.json_edit.setMinimumHeight(120)

        try:
            definitions_as_dicts = [d.model_dump() for d in self.content_item.definitions]
            json_text = json.dumps(definitions_as_dicts, indent=2)
            self.json_edit.setText(json_text)
        except Exception as e:
            logger.error(f"Failed to serialize tool definitions to JSON: {e}")
            self.json_edit.setText("[]")

        self.json_edit.textChanged.connect(self._on_data_changed)
        self.json_edit.focusInEvent = self.on_focus_in
        self.json_edit.focusOutEvent = self.on_focus_out
        return self.json_edit

    def on_focus_in(self, event):
        self.content_on_focus = self.content_item.model_copy(deep=True)
        QTextEdit.focusInEvent(self.json_edit, event)

    def on_focus_out(self, event):
        if self.content_on_focus and self.content_on_focus != self.content_item:
            command = UpdateContentCommand(self.conversation_model, self.item_index, self.index, self.content_on_focus, self.content_item)
            self.undo_manager.do(command)
        self.content_on_focus = None
        QTextEdit.focusOutEvent(self.json_edit, event)

    def update_colors(self, colors: dict):
        super().update_colors(colors)
        bg_color = self.colors.get("tools_bg", "#2A3B4D")
        self.json_edit.setStyleSheet(f"background-color: {bg_color}; border-radius: 4px;")

    @Slot()
    def _on_data_changed(self):
        text = self.json_edit.toPlainText()
        try:
            parsed_data = json.loads(text)
            if not isinstance(parsed_data, list):
                raise TypeError("Top-level JSON structure must be a list.")

            adapter = TypeAdapter(List[ToolDefinition])
            validated_definitions = adapter.validate_python(parsed_data)

            self.content_item.definitions = validated_definitions
            self.json_edit.setStyleSheet(f"background-color: {self.colors.get('tools_bg', '#2A3B4D')}; border-radius: 4px;")
            self.json_edit.setToolTip("")

        except (json.JSONDecodeError, TypeError, ValidationError) as e:
            self.json_edit.setStyleSheet("background-color: #5A3A3A; border: 1px solid red; border-radius: 4px;")
            error_message = "\n".join([f"{err['loc']}: {err['msg']}" for err in e.errors()]) if isinstance(e, ValidationError) else str(e)
            self.json_edit.setToolTip(error_message)


class ToolCallWidget(BaseContentWidget):
    content_item: "ToolCallContent"

    def __init__(self, content_item: "ContentItem", index: int, colors: dict, undo_manager, parent=None):
        super().__init__(content_item, index, colors, undo_manager, parent)
        self.content_on_focus = None

    def _create_editor_widget(self) -> QWidget:
        self.json_edit = QTextEdit()
        self.json_edit.setAcceptRichText(False)
        self.json_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.json_edit.setMinimumHeight(80)

        try:
            calls_as_dicts = [call.model_dump() for call in self.content_item.calls]
            json_text = json.dumps(calls_as_dicts, indent=2)
            self.json_edit.setText(json_text)
        except Exception as e:
            logger.error(f"Failed to serialize function calls to JSON: {e}")
            self.json_edit.setText("[]")

        self.json_edit.textChanged.connect(self._on_data_changed)
        self.json_edit.focusInEvent = self.on_focus_in
        self.json_edit.focusOutEvent = self.on_focus_out
        return self.json_edit

    def on_focus_in(self, event):
        self.content_on_focus = self.content_item.model_copy(deep=True)
        QTextEdit.focusInEvent(self.json_edit, event)

    def on_focus_out(self, event):
        if self.content_on_focus and self.content_on_focus != self.content_item:
            command = UpdateContentCommand(self.conversation_model, self.item_index, self.index, self.content_on_focus, self.content_item)
            self.undo_manager.do(command)
        self.content_on_focus = None
        QTextEdit.focusOutEvent(self.json_edit, event)

    @Slot()
    def _on_data_changed(self):
        text = self.json_edit.toPlainText()
        try:
            parsed_data = json.loads(text)
            if not isinstance(parsed_data, list):
                raise TypeError("Top-level JSON must be a list of function calls.")

            adapter = TypeAdapter(List[ToolCall])
            validated_calls = adapter.validate_python(parsed_data)

            self.content_item.calls = validated_calls
            self.json_edit.setStyleSheet("border: none;")
            self.json_edit.setToolTip("")

        except (json.JSONDecodeError, TypeError, ValidationError) as e:
            self.json_edit.setStyleSheet("border: 1px solid red;")
            error_message = "\n".join([f"{err['loc']}: {err['msg']}" for err in e.errors()]) if isinstance(e, ValidationError) else str(e)
            self.json_edit.setToolTip(error_message)


class ToolResultsWidget(BaseContentWidget):
    content_item: "ToolResultsContent"

    def __init__(self, content_item: "ContentItem", index: int, colors: dict, undo_manager, parent=None):
        super().__init__(content_item, index, colors, undo_manager, parent)
        self.toggle_button.setVisible(False)
        self.update_colors(colors)
        self.content_on_focus = None

    def _create_editor_widget(self) -> QWidget:
        self.json_edit = QTextEdit()
        self.json_edit.setAcceptRichText(False)
        self.json_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.json_edit.setMinimumHeight(100)

        try:
            results_as_dicts = [r.model_dump() for r in self.content_item.results]
            json_text = json.dumps(results_as_dicts, indent=2)
            self.json_edit.setText(json_text)
        except Exception as e:
            logger.error(f"Failed to serialize tool results to JSON: {e}")
            self.json_edit.setText("[]")

        self.json_edit.textChanged.connect(self._on_data_changed)
        self.json_edit.focusInEvent = self.on_focus_in
        self.json_edit.focusOutEvent = self.on_focus_out
        return self.json_edit

    def on_focus_in(self, event):
        self.content_on_focus = self.content_item.model_copy(deep=True)
        QTextEdit.focusInEvent(self.json_edit, event)

    def on_focus_out(self, event):
        if self.content_on_focus and self.content_on_focus != self.content_item:
            command = UpdateContentCommand(self.conversation_model, self.item_index, self.index, self.content_on_focus, self.content_item)
            self.undo_manager.do(command)
        self.content_on_focus = None
        QTextEdit.focusOutEvent(self.json_edit, event)

    def update_colors(self, colors: dict):
        super().update_colors(colors)
        bg_color = self.colors.get("tool_response_bg", "#2A4D3B")
        self.json_edit.setStyleSheet(f"background-color: {bg_color}; border-radius: 4px;")

    @Slot()
    def _on_data_changed(self):
        text = self.json_edit.toPlainText()
        try:
            parsed_data = json.loads(text)
            if not isinstance(parsed_data, list):
                raise TypeError("Top-level JSON must be a list of tool results.")

            adapter = TypeAdapter(List[ToolResult])
            validated_results = adapter.validate_python(parsed_data)

            self.content_item.results = validated_results
            self.json_edit.setStyleSheet(f"background-color: {self.colors.get('tool_response_bg', '#2A4D3B')}; border-radius: 4px;")
            self.json_edit.setToolTip("")

        except (json.JSONDecodeError, TypeError, ValidationError) as e:
            self.json_edit.setStyleSheet("background-color: #5A3A3A; border: 1px solid red; border-radius: 4px;")
            error_message = "\n".join([f"{err['loc']}: {err['msg']}" for err in e.errors()]) if isinstance(e, ValidationError) else str(e)
            self.json_edit.setToolTip(error_message)
