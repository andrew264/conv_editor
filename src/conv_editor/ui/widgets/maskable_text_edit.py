import logging
from typing import List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QKeyEvent, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from conv_editor.core.models import TextSegment

logger = logging.getLogger(__name__)


class MaskableTextEdit(QTextEdit):
    segmentsChanged = Signal()

    def __init__(self, unlearnable_bg: str, unlearnable_fg: str, parent=None):
        super().__init__(parent)
        self._unlearnable_format = None
        self._segments: List[TextSegment] = [TextSegment(text="")]
        self._is_programmatic_change = False

        self._learnable_format = QTextCharFormat()

        self.update_colors(unlearnable_bg, unlearnable_fg)

        self.textChanged.connect(self._on_text_changed)

    def update_colors(self, bg_color: str, fg_color: str):
        self._learnable_format.setBackground(Qt.GlobalColor.transparent)
        self._learnable_format.setForeground(self.palette().color(QPalette.ColorRole.Text))

        self._unlearnable_format = QTextCharFormat()
        self._unlearnable_format.setBackground(QColor(bg_color))
        self._unlearnable_format.setForeground(QColor(fg_color))
        self._apply_full_formatting()

    def set_segments(self, segments: List[TextSegment]):
        self._is_programmatic_change = True
        try:
            self._segments = segments if segments else [TextSegment(text="")]
            full_text = "".join(s.text for s in self._segments)
            self.setPlainText(full_text)
            self._apply_full_formatting()
        finally:
            self._is_programmatic_change = False
        self.segmentsChanged.emit()

    def get_segments(self) -> List[TextSegment]:
        return self._segments

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.textCursor()
        if cursor.hasSelection():
            menu.addSeparator()
            mark_unlearnable_action = QAction("Mark as Unlearnable", self)
            mark_unlearnable_action.triggered.connect(lambda: self._toggle_selection_learnable(False))
            menu.addAction(mark_unlearnable_action)

            mark_learnable_action = QAction("Mark as Learnable", self)
            mark_learnable_action.triggered.connect(lambda: self._toggle_selection_learnable(True))
            menu.addAction(mark_learnable_action)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_L:
            cursor = self.textCursor()
            if cursor.hasSelection():
                is_currently_unlearnable = self._is_selection_unlearnable(cursor)
                self._toggle_selection_learnable(is_currently_unlearnable)
                event.accept()
                return
        super().keyPressEvent(event)

    @Slot(bool)
    def _toggle_selection_learnable(self, make_learnable: bool):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        self._update_segments_from_selection(start, end, make_learnable)
        self.segmentsChanged.emit()

    def _is_selection_unlearnable(self, cursor: QTextCursor) -> bool:
        if not cursor.hasSelection():
            return False

        selection_format = cursor.charFormat()
        return selection_format.background() == self._unlearnable_format.background()

    def _apply_full_formatting(self):
        self._is_programmatic_change = True
        try:
            cursor = self.textCursor()
            current_pos = 0
            for segment in self._segments:
                cursor.setPosition(current_pos)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(segment.text))
                format_to_apply = self._learnable_format if segment.learnable else self._unlearnable_format
                cursor.mergeCharFormat(format_to_apply)
                current_pos += len(segment.text)

            cursor.clearSelection()
            self.setTextCursor(cursor)
        finally:
            self._is_programmatic_change = False

    def _update_segments_from_selection(self, start: int, end: int, make_learnable: bool):
        new_segments = []
        current_pos = 0

        for segment in self._segments:
            seg_start = current_pos
            seg_end = current_pos + len(segment.text)
            current_pos = seg_end

            # Case 1: Segment is completely before the selection
            if seg_end <= start:
                new_segments.append(segment)
                continue
            # Case 2: Segment is completely after the selection
            if seg_start >= end:
                new_segments.append(segment)
                continue

            # Case 3: Segment intersects with the selection
            if seg_start < start:
                new_segments.append(TextSegment(text=segment.text[: start - seg_start], learnable=segment.learnable))

            sel_start_in_seg = max(start, seg_start)
            sel_end_in_seg = min(end, seg_end)
            new_segments.append(TextSegment(text=segment.text[sel_start_in_seg - seg_start : sel_end_in_seg - seg_start], learnable=make_learnable))

            if seg_end > end:
                new_segments.append(TextSegment(text=segment.text[end - seg_start :], learnable=segment.learnable))

        self._segments = self._merge_segments(new_segments)
        self._apply_full_formatting()

    def _merge_segments(self, segments: List[TextSegment]) -> List[TextSegment]:
        if not segments:
            return []

        segments = [s for s in segments if s.text]
        if not segments:
            return []

        merged = [segments[0]]
        for current_segment in segments[1:]:
            last_segment = merged[-1]
            if last_segment.learnable == current_segment.learnable:
                last_segment.text += current_segment.text
            else:
                merged.append(current_segment)
        return merged

    @Slot()
    def _on_text_changed(self):
        if self._is_programmatic_change:
            return

        self._is_programmatic_change = True
        try:
            full_text = self.toPlainText()
            new_segments = []

            if not full_text:
                self._segments = [TextSegment(text="")]
                self.segmentsChanged.emit()
                return

            cursor = QTextCursor(self.document())

            cursor.setPosition(0)
            current_learnable = cursor.charFormat().background() != self._unlearnable_format.background()
            current_text = ""

            for i, char in enumerate(full_text):
                cursor.setPosition(i)
                is_learnable = cursor.charFormat().background() != self._unlearnable_format.background()

                if is_learnable == current_learnable:
                    current_text += char
                else:
                    if current_text:
                        new_segments.append(TextSegment(text=current_text, learnable=current_learnable))

                    current_text = char
                    current_learnable = is_learnable

            if current_text:
                new_segments.append(TextSegment(text=current_text, learnable=current_learnable))

            self._segments = self._merge_segments(new_segments)
            if not self._segments:
                self._segments = [TextSegment(text="")]

            self.segmentsChanged.emit()

        finally:
            self._is_programmatic_change = False
