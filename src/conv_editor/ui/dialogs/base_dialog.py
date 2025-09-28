import logging
from typing import TYPE_CHECKING, Union

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from conv_editor.workers.chat_worker import ChatWorker
    from conv_editor.workers.completion_worker import CompletionWorker

logger = logging.getLogger(__name__)


class BaseGenerationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 500)
        self.setWindowTitle("Generating...")
        self.setModal(True)

        self.worker: Union["CompletionWorker", "ChatWorker", None] = None
        self._stopped_manually = False
        self._has_error = False

        layout = QVBoxLayout(self)

        self.display_area = QTextEdit()
        self.display_area.setReadOnly(True)
        layout.addWidget(self.display_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        bottom_layout = QHBoxLayout()
        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_layout)
        layout.addWidget(bottom_widget)

        self._add_custom_buttons(bottom_layout)

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bottom_layout.addSpacerItem(spacer)

        self.stop_button = QPushButton("Stop Generation")
        self.stop_button.clicked.connect(self._stop_generation)
        self.stop_button.setEnabled(False)
        bottom_layout.addWidget(self.stop_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)
        bottom_layout.addWidget(self.close_button)

    def _add_custom_buttons(self, layout: QHBoxLayout):
        pass

    def start_generation(self):
        if not self.worker:
            logger.error("Worker thread not set. Cannot start generation.")
            return

        self.setWindowTitle("Generating...")
        self._stopped_manually = False
        self._has_error = False
        self.progress_bar.setVisible(True)
        self.stop_button.setEnabled(True)
        self.close_button.setEnabled(False)

        self.worker.progress.connect(self._on_generation_progress)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.error.connect(self._on_generation_error)

        self.worker.start()
        self.show()

    @Slot(str)
    def _on_generation_progress(self, text_chunk: str):
        self.display_area.moveCursor(QTextCursor.MoveOperation.End)
        self.display_area.insertPlainText(text_chunk)

    @Slot()
    def _on_generation_finished(self):
        self.progress_bar.setVisible(False)
        self.stop_button.setEnabled(False)
        self.close_button.setEnabled(True)
        if self._has_error:
            self.setWindowTitle("Generation Error")
        elif self._stopped_manually:
            self.setWindowTitle("Generation Stopped")
        else:
            self.setWindowTitle("Generation Complete")
        self.worker = None

    @Slot(str)
    def _on_generation_error(self, error_message: str):
        self._has_error = True
        self.display_area.append(f"\n\n--- ERROR ---\n{error_message}")

    @Slot()
    def _stop_generation(self):
        if self.worker and self.worker.isRunning():
            self._stopped_manually = True
            self.worker.stop()
            self.stop_button.setEnabled(False)
            self.setWindowTitle("Stopping Generation...")

    def closeEvent(self, event: QCloseEvent):
        if self.worker and self.worker.isRunning():
            self._stop_generation()
        super().closeEvent(event)
