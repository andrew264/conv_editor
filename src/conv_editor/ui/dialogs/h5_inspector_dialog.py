import html
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from conv_editor.config.settings import settings
from conv_editor.services.h5_reader_service import H5ReaderService

logger = logging.getLogger(__name__)


class H5InspectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HDF5 Dataset Inspector")
        self.setMinimumSize(800, 600)

        self.reader_service: Optional[H5ReaderService] = None
        self.current_index: int = 0
        self.total_conversations: int = 0

        self._setup_ui()
        self._connect_signals()
        self._update_ui_state()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # File Selection Group
        selection_group = QGroupBox("Dataset Selection")
        form_layout = QFormLayout(selection_group)

        self.h5_path_edit = QLineEdit()
        self.h5_path_edit.setReadOnly(True)
        self.browse_h5_button = QPushButton("Browse...")
        h5_layout = QHBoxLayout()
        h5_layout.addWidget(self.h5_path_edit)
        h5_layout.addWidget(self.browse_h5_button)
        form_layout.addRow("HDF5 File:", h5_layout)

        self.tokenizer_path_edit = QLineEdit()
        self.tokenizer_path_edit.setReadOnly(True)
        self.browse_tokenizer_button = QPushButton("Browse...")
        tokenizer_layout = QHBoxLayout()
        tokenizer_layout.addWidget(self.tokenizer_path_edit)
        tokenizer_layout.addWidget(self.browse_tokenizer_button)
        form_layout.addRow("Tokenizer File:", tokenizer_layout)

        self.load_button = QPushButton("Load Dataset")
        form_layout.addRow(self.load_button)
        main_layout.addWidget(selection_group)

        # Display Area
        self.display_area = QTextEdit()
        self.display_area.setReadOnly(True)
        self.display_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        main_layout.addWidget(self.display_area)

        # Pagination Controls
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("<< Previous")
        self.page_label = QLabel("Conversation 0 of 0")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QPushButton("Next >>")

        self.page_jump_spinbox = QSpinBox()
        self.page_jump_spinbox.setMinimum(1)
        self.jump_button = QPushButton("Go")

        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(QLabel("Jump to:"))
        pagination_layout.addWidget(self.page_jump_spinbox)
        pagination_layout.addWidget(self.jump_button)
        main_layout.addLayout(pagination_layout)

        # Status Label
        self.status_label = QLabel("Please select an HDF5 file and a tokenizer to begin.")
        main_layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.browse_h5_button.clicked.connect(self._browse_h5)
        self.browse_tokenizer_button.clicked.connect(self._browse_tokenizer)
        self.load_button.clicked.connect(self._load_dataset)
        self.prev_button.clicked.connect(self._on_previous)
        self.next_button.clicked.connect(self._on_next)
        self.jump_button.clicked.connect(self._on_jump_to)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key in (Qt.Key.Key_Up, Qt.Key.Key_Left):
            self._on_previous()
            event.accept()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            self._on_next()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _browse_h5(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HDF5 File", "", "HDF5 files (*.h5 *.hdf5)")
        if path:
            self.h5_path_edit.setText(path)

    def _browse_tokenizer(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tokenizer", "", "Tokenizer files (*.json)")
        if path:
            self.tokenizer_path_edit.setText(path)

    def _load_dataset(self):
        h5_path_str = self.h5_path_edit.text()
        tokenizer_path_str = self.tokenizer_path_edit.text()

        if not h5_path_str or not tokenizer_path_str:
            QMessageBox.warning(self, "Missing Files", "Please select both an HDF5 file and a tokenizer file.")
            return

        self.status_label.setText("Loading dataset...")
        try:
            if self.reader_service:
                self.reader_service.close()

            self.reader_service = H5ReaderService(Path(h5_path_str), Path(tokenizer_path_str))
            self.reader_service.load()

            self.total_conversations = self.reader_service.conversation_count
            self.current_index = 0
            self.page_jump_spinbox.setMaximum(self.total_conversations or 1)
            self._render_current_conversation()
            self.status_label.setText(f"Successfully loaded {self.total_conversations} conversations.")

        except (FileNotFoundError, ValueError, IndexError, IOError) as e:
            QMessageBox.critical(self, "Loading Error", f"Failed to load dataset:\n\n{e}")
            self.status_label.setText("Error loading dataset. Please check files and try again.")
            if self.reader_service:
                self.reader_service.close()
                self.reader_service = None
            self.total_conversations = 0

        self._update_ui_state()

    def _render_current_conversation(self):
        if not self.reader_service or self.total_conversations == 0:
            self.display_area.clear()
            return

        try:
            data = self.reader_service.get_processed_conversation(self.current_index)
            html_content = self._format_as_html(data)
            self.display_area.setHtml(html_content)
        except Exception as e:
            logger.exception(f"Error rendering conversation index {self.current_index}")
            self.display_area.setPlainText(f"Error rendering conversation: {e}")

        self.page_label.setText(f"Conversation {self.current_index + 1} of {self.total_conversations}")
        self.page_jump_spinbox.setValue(self.current_index + 1)

    def _format_as_html(self, data: List[Tuple[str, bool]]) -> str:
        unlearnable_color = settings.APP_THEME_UNLEARNABLE_BG
        parts = []
        for text, is_learnable in data:
            escaped_text = html.escape(text).replace("\n", "<br>")
            if is_learnable:
                parts.append(escaped_text)
            else:
                parts.append(f'<span style="background-color:{unlearnable_color};">{escaped_text}</span>')
        return f'<pre style="font-family: Consolas, monospace; white-space: pre-wrap;">{"".join(parts)}</pre>'

    def _on_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._render_current_conversation()
            self._update_ui_state()

    def _on_next(self):
        if self.current_index < self.total_conversations - 1:
            self.current_index += 1
            self._render_current_conversation()
            self._update_ui_state()

    def _on_jump_to(self):
        target_page = self.page_jump_spinbox.value()
        target_index = target_page - 1
        if 0 <= target_index < self.total_conversations:
            self.current_index = target_index
            self._render_current_conversation()
            self._update_ui_state()

    def _update_ui_state(self):
        is_loaded = self.reader_service is not None and self.total_conversations > 0

        self.browse_h5_button.setEnabled(not is_loaded)
        self.browse_tokenizer_button.setEnabled(not is_loaded)
        self.load_button.setEnabled(not is_loaded)

        self.display_area.setVisible(is_loaded)
        self.prev_button.setEnabled(is_loaded and self.current_index > 0)
        self.next_button.setEnabled(is_loaded and self.current_index < self.total_conversations - 1)
        self.page_jump_spinbox.setEnabled(is_loaded)
        self.jump_button.setEnabled(is_loaded)

        if not is_loaded:
            self.display_area.clear()
            self.page_label.setText("Conversation 0 of 0")

    def closeEvent(self, event: QCloseEvent):
        if self.reader_service:
            self.reader_service.close()
        super().closeEvent(event)
