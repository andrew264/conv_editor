from typing import Optional, TYPE_CHECKING

from conv_editor.core.commands.base_command import BaseCommand
from conv_editor.core.models import Item

if TYPE_CHECKING:
    from conv_editor.core.conversation import Conversation


class InsertItemCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", index: int, role: str):
        super().__init__(conversation)
        self.index = index
        self.role = role

    def execute(self):
        self.conversation.insert_item(self.index, self.role)

    def undo(self):
        self.conversation.remove_item(self.index)


class RemoveItemCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", index: int):
        super().__init__(conversation)
        self.index = index
        self.removed_item: Optional[Item] = None

    def execute(self):
        self.removed_item = self.conversation[self.index]
        self.conversation.remove_item(self.index)

    def undo(self):
        if self.removed_item:
            self.conversation.data.insert(self.index, self.removed_item)


class MoveItemCommand(BaseCommand):
    def __init__(self, conversation: "Conversation", source_index: int, target_index: int):
        super().__init__(conversation)
        self.source_index = source_index
        self.target_index = target_index
        self.final_target_index = -1

    def execute(self):
        item_to_move = self.conversation.data[self.source_index]
        temp_data = self.conversation.data[: self.source_index] + self.conversation.data[self.source_index + 1 :]
        temp_data.insert(self.target_index if self.source_index > self.target_index else self.target_index - 1, item_to_move)
        self.final_target_index = temp_data.index(item_to_move)

        self.conversation.move_item(self.source_index, self.target_index)

    def undo(self):
        if self.final_target_index != -1:
            self.conversation.move_item(self.final_target_index, self.source_index)
