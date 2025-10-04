import json
import logging
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from conv_editor.core.models import SearchMatch
from conv_editor.ui.widgets.search_result_widget import SearchResultWidget
from conv_editor.workers.search_worker import SearchWorker

logger = logging.getLogger(__name__)


class SearchDialog(QDialog):
    search_result_selected = Signal(SearchMatch)

    def __init__(self, root_dir: str, score_cutoff: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Conversations")
        self.setMinimumSize(850, 600)
        self.root_dir = root_dir
        self.initial_score_cutoff = score_cutoff

        self.search_worker: Optional[SearchWorker] = None
        self.search_timer = QTimer(self)
        self.search_timer.setInterval(300)
        self.search_timer.setSingleShot(True)
        self.current_results: List[SearchMatch] = []
        self.preview_cache: dict = {"path": None, "content": None}

        self._setup_ui()
        self._connect_signals()
        self._update_options_state()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Enter search query...")
        self.search_edit.setClearButtonEnabled(True)
        search_input_layout = QHBoxLayout()
        search_input_layout.addWidget(QLabel("Search:"))
        search_input_layout.addWidget(self.search_edit)
        left_layout.addLayout(search_input_layout)

        self._setup_options_ui(left_layout)

        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        left_layout.addWidget(self.results_list)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(5, 0, 0, 0)

        self.preview_path_label = QLabel("Click a result to see a preview.")
        self.preview_path_label.setWordWrap(True)
        right_layout.addWidget(self.preview_path_label)

        self.preview_text_edit = QTextEdit()
        self.preview_text_edit.setReadOnly(True)
        self.preview_text_edit.setFontFamily("monospace")
        self.preview_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        right_layout.addWidget(self.preview_text_edit)

        splitter.addWidget(left_pane)
        splitter.addWidget(right_pane)
        splitter.setSizes([350, 500])

        self.status_label = QLabel("Enter a query to start searching.")
        main_layout.addWidget(self.status_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _setup_options_ui(self, parent_layout: QVBoxLayout):
        options_layout = QGridLayout()
        options_layout.setContentsMargins(0, 5, 0, 5)

        self.fuzzy_checkbox = QCheckBox("Fuzzy Search")
        self.fuzzy_checkbox.setChecked(True)
        self.fuzzy_checkbox.setToolTip("Enable approximate, 'fuzzy' matching.\nCan be slower than exact search.")

        self.case_checkbox = QCheckBox("Case Insensitive")
        self.case_checkbox.setToolTip("For exact search: Ignore the difference between\nUPPERCASE and lowercase letters.")

        self.score_cutoff_spinbox = QSpinBox()
        self.score_cutoff_spinbox.setRange(1, 100)
        self.score_cutoff_spinbox.setValue(self.initial_score_cutoff)
        self.score_cutoff_spinbox.setSuffix("%")
        self.score_cutoff_spinbox.setToolTip("For fuzzy search: Only show results with a similarity\nscore above this value (100 is a perfect match).")

        self.max_results_spinbox = QSpinBox()
        self.max_results_spinbox.setRange(1, 1000)
        self.max_results_spinbox.setValue(25)

        options_layout.addWidget(self.fuzzy_checkbox, 0, 0)
        options_layout.addWidget(QLabel("Score Cutoff:"), 0, 1, Qt.AlignmentFlag.AlignRight)
        options_layout.addWidget(self.score_cutoff_spinbox, 0, 2)
        options_layout.addWidget(self.case_checkbox, 1, 0)
        options_layout.addWidget(QLabel("Max Results:"), 1, 1, Qt.AlignmentFlag.AlignRight)
        options_layout.addWidget(self.max_results_spinbox, 1, 2)
        options_layout.setColumnStretch(0, 1)

        parent_layout.addLayout(options_layout)

    def _connect_signals(self):
        self.search_edit.textChanged.connect(self.search_timer.start)
        self.search_timer.timeout.connect(self._trigger_search)

        self.results_list.itemClicked.connect(self._display_preview)
        self.results_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        option_widgets = [self.fuzzy_checkbox, self.case_checkbox, self.score_cutoff_spinbox, self.max_results_spinbox]
        for widget in option_widgets:
            if isinstance(widget, QCheckBox):
                widget.toggled.connect(self._maybe_retrigger_search)
            else:
                widget.valueChanged.connect(self._maybe_retrigger_search)
        self.fuzzy_checkbox.toggled.connect(self._update_options_state)

    @Slot(bool)
    def _update_options_state(self, is_fuzzy: bool = True):
        self.score_cutoff_spinbox.setEnabled(is_fuzzy)
        self.case_checkbox.setEnabled(not is_fuzzy)
        if is_fuzzy:
            self.case_checkbox.setChecked(False)

    @Slot()
    def _maybe_retrigger_search(self):
        if self.search_edit.text().strip():
            self.search_timer.start()

    @Slot()
    def _trigger_search(self):
        query = self.search_edit.text().strip()
        self._stop_current_search()
        self.results_list.clear()
        self.current_results.clear()
        self.preview_text_edit.clear()
        self.preview_path_label.setText("Click a result to see a preview.")
        self.preview_cache = {"path": None, "content": None}

        if not query:
            self.status_label.setText("Enter a query to start searching.")
            return

        self.status_label.setText(f"Searching for '{query}'...")
        self.search_worker = SearchWorker(
            root_dir=self.root_dir,
            query=query,
            is_fuzzy=self.fuzzy_checkbox.isChecked(),
            score_cutoff=self.score_cutoff_spinbox.value(),
            case_insensitive=self.case_checkbox.isChecked(),
            max_results=self.max_results_spinbox.value(),
            parent=self,
        )
        self.search_worker.result_found.connect(self._on_search_result_found)
        self.search_worker.finished.connect(self._on_search_finished)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.start()

    @Slot(QListWidgetItem)
    def _display_preview(self, item: QListWidgetItem):
        row = self.results_list.row(item)
        if not (0 <= row < len(self.current_results)):
            return

        result = self.current_results[row]
        self.preview_path_label.setText(f"<b>Preview:</b> {result.file_path}")

        try:
            if self.preview_cache["path"] != result.file_path:
                with open(result.file_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                pretty_content = json.dumps(content, indent=2)
                self.preview_cache = {"path": result.file_path, "content": pretty_content}
                self.preview_text_edit.setPlainText(pretty_content)
            else:
                self.preview_text_edit.setPlainText(self.preview_cache["content"])

            self._highlight_match(result)

        except (IOError, json.JSONDecodeError) as e:
            error_msg = f"Error reading or parsing file:\n{result.file_path}\n\n{e}"
            self.preview_text_edit.setPlainText(error_msg)
            logger.error(error_msg)

    def _highlight_match(self, result: SearchMatch):
        search_text = ""

        if result.match_indices:
            start, end = result.match_indices
            search_text = result.preview[start:end]

        if not search_text:
            search_text = self.search_edit.text().strip()

        if not search_text:
            return

        cursor = self.preview_text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.preview_text_edit.setTextCursor(cursor)

        found_cursor = self.preview_text_edit.document().find(search_text)

        if not found_cursor.isNull():
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(QColor("#D2B48C"))
            highlight_format.setForeground(QColor("black"))
            found_cursor.mergeCharFormat(highlight_format)
            self.preview_text_edit.setTextCursor(found_cursor)
            self.preview_text_edit.ensureCursorVisible()

    @Slot(SearchMatch)
    def _on_search_result_found(self, result: SearchMatch):
        self.current_results.append(result)
        item = QListWidgetItem(self.results_list)
        widget = SearchResultWidget(result, self.results_list)
        item.setSizeHint(widget.sizeHint())
        self.results_list.addItem(item)
        self.results_list.setItemWidget(item, widget)
        self.status_label.setText(f"Found {len(self.current_results)} result(s)...")

    @Slot()
    def _on_search_finished(self):
        count = len(self.current_results)
        query = self.search_edit.text()
        limit = self.max_results_spinbox.value()
        limit_reached = f" (limit of {limit} reached)" if count >= limit else ""
        self.status_label.setText(f"Found {count} result(s) for '{query}'{limit_reached}.")
        self.search_worker = None

    @Slot(str)
    def _on_search_error(self, error_message: str):
        self.status_label.setText(f"Error: {error_message}")
        logger.error(f"Search worker error: {error_message}")
        self.search_worker = None

    @Slot(QListWidgetItem)
    def _on_item_double_clicked(self, item: QListWidgetItem):
        row = self.results_list.row(item)
        if 0 <= row < len(self.current_results):
            selected_result = self.current_results[row]
            self.search_result_selected.emit(selected_result)

    def _stop_current_search(self):
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
        self.search_worker = None

    def reject(self):
        self._stop_current_search()
        super().reject()
