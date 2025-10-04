from typing import Optional, TYPE_CHECKING

from conv_editor.core.commands.base_command import BaseCommand
from conv_editor.core.models import ContentItem

if TYPE_CHECKING:
    from conv_editor.core.conversation import Conversation


class UpdateRoleCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", item_index: int, old_role: str, new_role: str):
        super().__init__(conversation)
        self.item_index = item_index
        self.old_role = old_role
        self.new_role = new_role

    def execute(self):
        self.conversation[self.item_index].role = self.new_role
        self.conversation._has_unsaved_changes = True

    def undo(self):
        self.conversation[self.item_index].role = self.old_role
        self.conversation._has_unsaved_changes = True


class AddContentBlockCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", item_index: int, new_content_block: ContentItem):
        super().__init__(conversation)
        self.item_index = item_index
        self.new_content_block = new_content_block

    def execute(self):
        self.conversation[self.item_index].content.append(self.new_content_block)
        self.conversation._has_unsaved_changes = True

    def undo(self):
        self.conversation[self.item_index].content.pop()
        self.conversation._has_unsaved_changes = True


class RemoveContentBlockCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", item_index: int, content_index: int):
        super().__init__(conversation)
        self.item_index = item_index
        self.content_index = content_index
        self.removed_block: Optional[ContentItem] = None

    def execute(self):
        self.removed_block = self.conversation[self.item_index].content.pop(self.content_index)
        self.conversation._has_unsaved_changes = True

    def undo(self):
        if self.removed_block:
            self.conversation[self.item_index].content.insert(self.content_index, self.removed_block)
            self.conversation._has_unsaved_changes = True


class UpdateContentCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", item_index: int, content_index: int, old_content: ContentItem, new_content: ContentItem):
        super().__init__(conversation)
        self.item_index = item_index
        self.content_index = content_index
        self.old_content = old_content.model_copy(deep=True)
        self.new_content = new_content.model_copy(deep=True)

    def execute(self):
        self.conversation[self.item_index].content[self.content_index] = self.new_content
        self.conversation._has_unsaved_changes = True

    def undo(self):
        self.conversation[self.item_index].content[self.content_index] = self.old_content
        self.conversation._has_unsaved_changes = True


class MoveContentBlockCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", source_item_idx: int, source_content_idx: int, target_item_idx: int, target_content_idx: int):
        super().__init__(conversation)
        self.source_item_idx = source_item_idx
        self.source_content_idx = source_content_idx
        self.target_item_idx = target_item_idx
        self.target_content_idx = target_content_idx
        self.final_target_content_idx = -1

    def execute(self):
        if self.source_item_idx == self.target_item_idx and self.source_content_idx < self.target_content_idx:
            self.final_target_content_idx = self.target_content_idx - 1
        else:
            self.final_target_content_idx = self.target_content_idx

        self.conversation.move_content(self.source_item_idx, self.source_content_idx, self.target_item_idx, self.target_content_idx)

    def undo(self):
        if self.final_target_content_idx != -1:
            self.conversation.move_content(self.target_item_idx, self.final_target_content_idx, self.source_item_idx, self.source_content_idx)
