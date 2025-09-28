import json
import logging
from pathlib import Path
from typing import Optional

from PIL.Image import Image
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

try:
    from wordcloud import WordCloud
except ImportError:
    logger.error("WordCloud library not found. Please run: pip install wordcloud")
    WordCloud = None


class WordCloudWorker(QThread):
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, root_dir: str, assistant_name: str, parent=None):
        super().__init__(parent)
        if WordCloud is None:
            raise ImportError("WordCloud library is required but not installed.")
        self.root_dir = root_dir
        self.assistant_name = assistant_name
        self._is_running = True

    def run(self):
        try:
            self.progress.emit("Scanning files...")
            root_path = Path(self.root_dir)
            if not root_path.is_dir():
                raise FileNotFoundError(f"Root directory not found: {self.root_dir}")

            all_text = self._aggregate_assistant_text(root_path)
            if not self._is_running:
                return

            if not all_text:
                self.error.emit("No text found for the specified assistant role.")
                return

            self.progress.emit("Generating word cloud image...")
            wordcloud_gen = WordCloud(
                width=1200,
                height=600,
                background_color="white",
                collocations=False,
            ).generate(all_text)

            image: Optional[Image] = wordcloud_gen.to_image()
            if not self._is_running:
                return

            self.finished.emit(image)

        except Exception as e:
            logger.exception("Error during word cloud generation.")
            self.error.emit(str(e))

    def _aggregate_assistant_text(self, root_path: Path) -> str:
        all_text_parts = []
        json_files = list(root_path.rglob("*.json"))
        total_files = len(json_files)

        for i, file_path in enumerate(json_files):
            if not self._is_running:
                return ""
            self.progress.emit(f"Processing file {i + 1}/{total_files}")
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    continue
                for item in data:
                    if isinstance(item, dict) and item.get("role") == self.assistant_name and "content" in item:
                        for content_part in item["content"]:
                            if isinstance(content_part, dict) and content_part.get("type") == "text":
                                all_text_parts.append(content_part.get("text", ""))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Could not process file '{file_path}': {e}")

        return " ".join(filter(None, all_text_parts))

    def stop(self):
        logger.info("Stopping WordCloudWorker...")
        self._is_running = False
