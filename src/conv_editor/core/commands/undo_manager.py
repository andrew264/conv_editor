from collections import deque

from PySide6.QtCore import QObject, Signal

from conv_editor.core.commands.base_command import BaseCommand


class UndoManager(QObject):
    canUndoChanged = Signal(bool)
    canRedoChanged = Signal(bool)
    cleanChanged = Signal(bool)
    command_executed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack: deque[BaseCommand] = deque()
        self.redo_stack: deque[BaseCommand] = deque()
        self.clean_index = 0

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    @property
    def is_clean(self) -> bool:
        return len(self.undo_stack) == self.clean_index

    def do(self, command: BaseCommand):
        old_can_undo = self.can_undo
        old_can_redo = self.can_redo
        old_is_clean = self.is_clean

        command.execute()

        self.undo_stack.append(command)
        self.redo_stack.clear()

        if old_can_undo != self.can_undo:
            self.canUndoChanged.emit(self.can_undo)
        if old_can_redo != self.can_redo:
            self.canRedoChanged.emit(self.can_redo)
        if old_is_clean != self.is_clean:
            self.cleanChanged.emit(not self.is_clean)

        self.command_executed.emit()

    def undo(self):
        if not self.can_undo:
            return

        old_is_clean = self.is_clean
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)

        self.canUndoChanged.emit(self.can_undo)
        self.canRedoChanged.emit(self.can_redo)
        if old_is_clean != self.is_clean:
            self.cleanChanged.emit(not self.is_clean)

        self.command_executed.emit()

    def redo(self):
        if not self.can_redo:
            return

        old_is_clean = self.is_clean
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)

        self.canUndoChanged.emit(self.can_undo)
        self.canRedoChanged.emit(self.can_redo)
        if old_is_clean != self.is_clean:
            self.cleanChanged.emit(not self.is_clean)

        self.command_executed.emit()

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.clean_index = 0
        self.canUndoChanged.emit(False)
        self.canRedoChanged.emit(False)
        self.cleanChanged.emit(False)

    def set_clean(self):
        was_dirty = not self.is_clean
        self.clean_index = len(self.undo_stack)
        if was_dirty:
            self.cleanChanged.emit(False)
