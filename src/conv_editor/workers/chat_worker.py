import logging
from typing import Dict, List

from PySide6.QtCore import QThread, Signal

from conv_editor.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class ChatWorker(QThread):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, openai_service: OpenAIService, data: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.openai_service = openai_service
        self.data = data

    def run(self):
        try:
            logger.info("ChatWorker started.")
            stream = self.openai_service.get_chat_response_stream(self.data)
            for chunk in stream:
                if self.isInterruptionRequested():
                    break
                self.progress.emit(chunk)
        except Exception as e:
            logger.exception("Error during chat generation.")
            self.error.emit(str(e))
        finally:
            logger.info("ChatWorker finished.")
            self.finished.emit()

    def stop(self):
        logger.info("Stopping ChatWorker...")
        self.openai_service.stop_generation()
        self.requestInterruption()
