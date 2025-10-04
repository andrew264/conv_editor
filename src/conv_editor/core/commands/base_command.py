from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conv_editor.core.conversation import Conversation


class BaseCommand(ABC):
    def __init__(self, conversation: "Conversation"):
        self.conversation = conversation

    @abstractmethod
    def execute(self):
        raise NotImplementedError

    @abstractmethod
    def undo(self):
        raise NotImplementedError

    def redo(self):
        self.execute()

    def merge_with(self, other: "BaseCommand") -> bool:
        return False
