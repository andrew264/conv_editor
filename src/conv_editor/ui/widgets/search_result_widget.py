from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from conv_editor.core.models import SearchMatch

HIGHLIGHT_COLOR = QColor("#FF4500")  # OrangeRed


class SearchResultWidget(QWidget):
    def __init__(self, result: SearchMatch, parent=None):
        super().__init__(parent)
        self._setup_ui(result)

    def _setup_ui(self, result: SearchMatch):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(1)

        path_label = QLabel(f"<b>File:</b> {result.file_path}")
        path_label.setTextFormat(Qt.TextFormat.RichText)
        path_label.setWordWrap(True)

        preview_label = QLabel()
        preview_label.setTextFormat(Qt.TextFormat.RichText)
        preview_label.setWordWrap(True)
        preview_label.setText(self._format_preview(result))

        layout.addWidget(path_label)
        layout.addWidget(preview_label)

    def _format_preview(self, result: SearchMatch) -> str:
        preview = result.preview
        indices = result.match_indices
        item_str = f"Item:{result.item_index}" if result.item_index is not None else "Item:?"
        prefix = f"<small><i>(Score: {result.score}, {item_str})</i></small> "

        escaped_preview = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if not indices:
            return f"{prefix}{escaped_preview}"

        start, end = indices
        before = escaped_preview[:start]
        matched = escaped_preview[start:end]
        after = escaped_preview[end:]

        return f"{prefix}{before}<font color='{HIGHLIGHT_COLOR.name()}'><b>{matched}</b></font>{after}"
