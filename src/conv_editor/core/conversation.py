import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from conv_editor.core.formatter import PromptFormatter
from conv_editor.core.models import ConversationData, Item, TextContent, TextSegment

logger = logging.getLogger(__name__)


class Conversation:
    def __init__(self, assistant_name: str):
        self.data: ConversationData = []
        self.file_path: Optional[Path] = None
        self.assistant_name = assistant_name
        self._has_unsaved_changes = False
        self.formatter = PromptFormatter(json_indent=0)

    @property
    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, val: Union[slice, int]) -> Union[Item, List[Item]]:
        return self.data[val]

    def load(self, file_path: Union[str, Path], root_dir: Optional[Path] = None):
        self.file_path = Path(file_path)
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                raw_data = json.load(f) or []
            self.data = [Item.model_validate(item) for item in raw_data]
            logger.info(f"Loaded and validated conversation from {self.file_path}")
        except (FileNotFoundError, json.JSONDecodeError, ValidationError) as e:
            self.data = []
            logger.error(f"Failed to load or validate file '{self.file_path}': {e}")

        prompt_added = self._ensure_system_prompt(root_dir)
        self._has_unsaved_changes = prompt_added

    def save(self):
        if not self.file_path:
            raise ValueError("File path is not set. Cannot save.")
        try:
            with self.file_path.open("w", encoding="utf-8") as f:
                json_data = [item.model_dump() for item in self.data]
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            self._has_unsaved_changes = False
            logger.info(f"Saved conversation to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise

    def add_item(self, role: str) -> Item:
        new_item = Item(role=role, content=[])
        self.data.append(new_item)
        self._has_unsaved_changes = True
        return new_item

    def insert_item(self, index: int, role: str) -> Item:
        if not (0 <= index <= len(self.data)):
            raise IndexError("Insertion index out of range.")
        new_item = Item(role=role, content=[])
        self.data.insert(index, new_item)
        self._has_unsaved_changes = True
        return new_item

    def update_item(self, index: int, item: Item):
        if 0 <= index < len(self.data):
            self.data[index] = item
            self._has_unsaved_changes = True
        else:
            raise IndexError("Item index out of range.")

    def remove_item(self, index: int):
        if 0 <= index < len(self.data):
            del self.data[index]
            self._has_unsaved_changes = True
        else:
            raise IndexError("Item index out of range.")

    def move_item(self, source_index: int, target_index: int):
        if not (0 <= source_index < len(self.data) and 0 <= target_index <= len(self.data)):
            logger.warning(f"Attempted to move item with invalid indices: src={source_index}, tgt={target_index}")
            return
        if source_index == target_index:
            return

        item_to_move = self.data.pop(source_index)

        if source_index < target_index:
            target_index -= 1

        self.data.insert(target_index, item_to_move)
        self._has_unsaved_changes = True
        logger.debug(f"Moved item from index {source_index} to {target_index}")

    def move_content(self, source_item_idx: int, source_content_idx: int, target_item_idx: int, target_content_idx: int):
        if not (0 <= source_item_idx < len(self.data) and 0 <= target_item_idx < len(self.data)):
            logger.warning(f"Invalid item index for move_content: src={source_item_idx}, tgt={target_item_idx}")
            return

        source_item = self.data[source_item_idx]
        target_item = self.data[target_item_idx]

        if not (0 <= source_content_idx < len(source_item.content) and 0 <= target_content_idx <= len(target_item.content)):
            logger.warning(f"Invalid content index for move_content: src={source_content_idx}, tgt={target_content_idx}")
            return

        content_to_move = source_item.content.pop(source_content_idx)

        if source_item_idx == target_item_idx and source_content_idx < target_content_idx:
            target_content_idx -= 1

        target_item.content.insert(target_content_idx, content_to_move)
        self._has_unsaved_changes = True
        logger.debug(f"Moved content from item[{source_item_idx}][{source_content_idx}] to item[{target_item_idx}][{target_content_idx}]")

    def discard_and_close(self):
        self.data = []
        self.file_path = None
        self._has_unsaved_changes = False

    def delete_file(self):
        if not self.file_path:
            raise ValueError("File path is not set. Cannot delete.")
        try:
            self.file_path.unlink()
            logger.info(f"Deleted file: {self.file_path}")
        except FileNotFoundError:
            logger.warning(f"File not found, nothing to delete: {self.file_path}")
        self.discard_and_close()

    def get_all_items(self) -> ConversationData:
        return self.data

    def get_data_slice_as_string(self, end_idx: int, with_reason: bool) -> str:
        return self.formatter(
            data_slice=self.data[:end_idx],
            assistant_name=self.assistant_name,
            with_reason=with_reason,
        )

    def get_data_slice_for_chat(self, end_idx: int, with_reason: bool) -> List[Dict[str, Any]]:
        res = []
        for item in self.data[:end_idx]:
            if item.role == self.assistant_name:
                api_role = "assistant"
            elif item.role == "system":
                api_role = "system"
            else:
                api_role = "user"

            content_str = ""
            for content_part in item.content:
                if hasattr(content_part, "full_text"):
                    if content_part.type == "reason":
                        if with_reason:
                            content_str += f"<think>{content_part.full_text}</think>\n"
                    else:
                        content_str += content_part.full_text
            res.append({"role": api_role, "content": content_str})
        return res

    def _ensure_system_prompt(self, root_dir: Optional[Path] = None) -> bool:
        if not self.data or self.data[0].role == "system":
            return False

        if not root_dir:
            logger.warning("Root directory not provided, cannot automatically add system prompt.")
            return False

        sys_prompt_path = root_dir / "sysprompt.txt"
        if not sys_prompt_path.exists():
            logger.warning(f"System prompt file not found at: {sys_prompt_path}")
            return False

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
            self.data.insert(0, sys_item)
            logger.info("System prompt added to new conversation.")
            return True
        except Exception as e:
            logger.error(f"Failed to read or format system prompt: {e}", exc_info=True)
            return False
