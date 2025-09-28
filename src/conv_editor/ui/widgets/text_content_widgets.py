import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QSizePolicy, QTextEdit, QWidget

from conv_editor.core.models import TextSegment
from conv_editor.ui.widgets.base_content_widget import BaseContentWidget
from conv_editor.ui.widgets.maskable_text_edit import MaskableTextEdit

if TYPE_CHECKING:
    from conv_editor.core.models import ContentItem, ReasoningContent, TextContent

logger = logging.getLogger(__name__)


class BaseTextSegmentWidget(BaseContentWidget):
    MIN_TEXT_EDIT_LINES = 3
    MAX_TEXT_EDIT_LINES = 10

    def __init__(self, content_item: "ContentItem", index: int, colors: dict, parent=None):
        super().__init__(content_item, index, colors, parent)
        self.toggle_button.setVisible(True)
        self.toggle_button.clicked.connect(self._on_toggle_block)

    def update_colors(self, colors: dict):
        super().update_colors(colors)
        self.text_edit.update_colors(
            bg_color=self.colors.get("unlearnable_bg"),
            fg_color=self.colors.get("unlearnable_fg"),
        )

    def _create_editor_widget(self) -> QWidget:
        self.text_edit = MaskableTextEdit(
            unlearnable_bg=self.colors.get("unlearnable_bg"),
            unlearnable_fg=self.colors.get("unlearnable_fg"),
        )
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.text_edit.set_segments(self.content_item.segments)

        self._connect_signals()
        self._adjust_height()
        return self.text_edit

    def _connect_signals(self):
        self.text_edit.segmentsChanged.connect(self._on_segments_changed)
        self.height_adjust_timer = QTimer(self)
        self.height_adjust_timer.setSingleShot(True)
        self.height_adjust_timer.setInterval(50)
        self.text_edit.document().documentLayout().documentSizeChanged.connect(self.height_adjust_timer.start)
        self.height_adjust_timer.timeout.connect(self._adjust_height)

    @Slot()
    def _on_segments_changed(self):
        new_segments = self.text_edit.get_segments()
        if self.content_item.segments != new_segments:
            self.content_item.segments = new_segments
            self.content_changed.emit()

    @Slot()
    def _on_toggle_block(self):
        current_segments = self.text_edit.get_segments()
        full_text = "".join(s.text for s in current_segments)
        is_any_part_learnable = any(s.learnable for s in current_segments)
        new_state = not is_any_part_learnable
        new_segment_list = [TextSegment(text=full_text, learnable=new_state)]
        self.text_edit.set_segments(new_segment_list)

    @Slot()
    def _adjust_height(self):
        fm = QFontMetrics(self.text_edit.font())
        margins = self.text_edit.contentsMargins()
        v_margin = margins.top() + margins.bottom()
        line_height = fm.height()
        min_height = self.MIN_TEXT_EDIT_LINES * line_height + v_margin
        max_height = self.MAX_TEXT_EDIT_LINES * line_height + v_margin
        doc_height = self.text_edit.document().size().height()
        ideal_height = int(doc_height) + v_margin
        clamped_height = max(min_height, min(ideal_height, max_height))
        if self.text_edit.height() != clamped_height:
            self.text_edit.setFixedHeight(clamped_height)


class TextContentWidget(BaseTextSegmentWidget):
    content_item: "TextContent"


class ReasoningContentWidget(BaseTextSegmentWidget):
    content_item: "ReasoningContent"

    def __init__(self, content_item: "ContentItem", index: int, colors: dict, parent=None):
        super().__init__(content_item, index, colors, parent)
        self._apply_reasoning_style()

    def update_colors(self, colors: dict):
        super().update_colors(colors)
        self._apply_reasoning_style()

    def _apply_reasoning_style(self):
        bg_color = self.colors.get("reasoning_bg", "#f0f0f0")
        self.text_edit.setStyleSheet(f"background-color: {bg_color}; border-radius: 4px;")
