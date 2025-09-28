from typing import Dict, List

from PySide6.QtCore import Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QPushButton

from conv_editor.services.openai_service import OpenAIService
from conv_editor.ui.dialogs.base_dialog import BaseGenerationDialog
from conv_editor.workers.chat_worker import ChatWorker
from conv_editor.workers.completion_worker import CompletionWorker


class CompletionDialog(BaseGenerationDialog):
    def __init__(self, prompt: str, openai_service: OpenAIService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Completion Generation")

        self.openai_service = openai_service
        self.current_prompt = prompt

        self.display_area.setReadOnly(False)
        self.display_area.setText(self.current_prompt)

    def _add_custom_buttons(self, layout: QHBoxLayout):
        self.regen_button = QPushButton("Regenerate Response")
        self.regen_button.clicked.connect(self._regenerate_response)
        layout.insertWidget(0, self.regen_button)

    def start_generation(self):
        self.worker = CompletionWorker(self.openai_service, self.current_prompt, self)
        super().start_generation()

    def _regenerate_response(self):
        self.current_prompt = self.display_area.toPlainText()
        self.display_area.clear()
        self.display_area.insertPlainText(self.current_prompt)
        self.display_area.moveCursor(QTextCursor.MoveOperation.End)
        self.start_generation()


class ChatDialog(BaseGenerationDialog):
    def __init__(self, data: List[Dict], openai_service: OpenAIService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat Generation")
        self.openai_service = openai_service
        self.data = data
        self.response_start_pos = 0

    def _add_custom_buttons(self, layout: QHBoxLayout):
        self.copy_button = QPushButton("Copy Response")
        self.copy_button.clicked.connect(self._copy_response)
        layout.insertWidget(0, self.copy_button)

        self.regen_button = QPushButton("Regenerate Response")
        self.regen_button.clicked.connect(self._regenerate_response)
        layout.insertWidget(1, self.regen_button)

    def start_generation(self):
        self.display_area.clear()
        history = self._format_chat_history(self.data)
        self.display_area.insertPlainText(history)
        self.response_start_pos = len(history)

        self.worker = ChatWorker(self.openai_service, self.data, self)
        super().start_generation()

    @Slot()
    def _copy_response(self):
        full_text = self.display_area.toPlainText()
        response_text = full_text[self.response_start_pos :].strip()
        QApplication.clipboard().setText(response_text)
        QMessageBox.information(self, "Copied", "Response copied to clipboard.")

    def _regenerate_response(self):
        self.start_generation()

    def _format_chat_history(self, messages: List[Dict]) -> str:
        formatted = [f"<{m['role'].upper()}>\n{m['content']}\n" for m in messages]
        return "\n".join(formatted) + "\n<ASSISTANT>\n"
