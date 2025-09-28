import logging

from PySide6.QtCore import QThread, Signal

from conv_editor.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class CompletionWorker(QThread):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, openai_service: OpenAIService, prompt: str, parent=None):
        super().__init__(parent)
        self.openai_service = openai_service
        self.prompt = prompt

    def run(self):
        try:
            logger.info("CompletionWorker started.")
            stream = self.openai_service.get_completion_response_stream(self.prompt)
            for chunk in stream:
                if self.isInterruptionRequested():
                    break
                self.progress.emit(chunk)
        except Exception as e:
            logger.exception("Error during completion generation.")
            self.error.emit(str(e))
        finally:
            logger.info("CompletionWorker finished.")
            self.finished.emit()

    def stop(self):
        logger.info("Stopping CompletionWorker...")
        self.openai_service.stop_generation()
        self.requestInterruption()
