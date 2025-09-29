import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from PySide6.QtCore import QThread, Signal
from tokenizers import Tokenizer

from conv_editor.core.models import ConversationData, Item, TextContent, TextSegment
from conv_editor.export.config import ExportConfig
from conv_editor.export.exporter import TrainingExporter
from conv_editor.export.hdf5_writer import HDF5Writer

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    status_update = Signal(str)
    progress = Signal(int, int)  # current, total
    export_completed = Signal()
    error = Signal(str)

    def __init__(self, config: ExportConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_running = True

    def run(self):
        try:
            self.status_update.emit("Initializing exporter...")
            try:
                tokenizer = Tokenizer.from_file(str(self.config.tokenizer_path))
            except Exception as e:
                self.error.emit(f"Failed to load tokenizer: {e}")
                return

            exporter = TrainingExporter(tokenizer, self.config)

            self.status_update.emit("Scanning for conversation files...")
            root_path = Path(self.config.root_directory)
            files_to_process = sorted(list(root_path.rglob("*.json")))
            total_files = len(files_to_process)

            if total_files == 0:
                self.error.emit("No .json files found in the specified directory.")
                return

            logger.info(f"Found {total_files} files to process for export.")
            self.progress.emit(0, total_files)

            self.status_update.emit(f"Preparing to write to {self.config.output_path.name}...")
            with HDF5Writer(self.config.output_path) as writer:
                for i, file_path in enumerate(files_to_process):
                    if not self._is_running:
                        break

                    self.progress.emit(i + 1, total_files)
                    self.status_update.emit(f"Processing ({i + 1}/{total_files}): {file_path.name}")

                    try:
                        with file_path.open("r", encoding="utf-8") as f:
                            raw_data = json.load(f)

                        conversation_data = TypeAdapter(ConversationData).validate_python(raw_data)

                    except (json.JSONDecodeError, ValidationError, IOError) as e:
                        logger.warning(f"Skipping file '{file_path.name}' due to error: {e}")
                        continue

                    if not conversation_data or conversation_data[0].role != "system":
                        self._add_system_prompt(conversation_data)

                    tokenized_data = exporter.process_conversation(conversation_data)

                    if tokenized_data["input_ids"].size > 0:
                        writer.append(tokenized_data)

            if self._is_running:
                self.status_update.emit(f"Export complete. Data saved to {self.config.output_path.name}")
                logger.info("Export process completed successfully.")
            else:
                self.status_update.emit("Export cancelled by user.")
                logger.info("Export process was cancelled.")

            self.export_completed.emit()

        except Exception as e:
            logger.exception("An unhandled error occurred in the export worker.")
            self.error.emit(f"A critical error occurred: {e}")

    def _add_system_prompt(self, conversation_data: ConversationData):
        sys_prompt_path = self.config.root_directory / "sysprompt.txt"
        if not sys_prompt_path.exists():
            logger.warning(f"System prompt file not found at: {sys_prompt_path}. Not adding to export.")
            return

        try:
            with sys_prompt_path.open("r", encoding="utf-8") as f:
                prompt_template = f.read().strip()

            formatted_prompt = prompt_template
            if "{datetime}" in prompt_template:
                formatted_prompt = prompt_template.format(datetime=datetime.now().strftime("%d %B %Y %I:%M %p"))

            sys_item = Item(
                role="system",
                content=[TextContent(segments=[TextSegment(text=formatted_prompt, learnable=False)])],
            )
            conversation_data.insert(0, sys_item)
            logger.debug("System prompt added to a conversation for export.")
        except Exception as e:
            logger.error(f"Failed to read or format system prompt for export: {e}", exc_info=True)

    def stop(self):
        logger.info("Stop signal received by ExportWorker.")
        self._is_running = False
