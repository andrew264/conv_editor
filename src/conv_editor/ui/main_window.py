import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL.Image import Image as PILImage
from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QComboBox,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from conv_editor.config.settings import settings
from conv_editor.core.commands.item_commands import InsertItemCommand, MoveItemCommand, RemoveItemCommand
from conv_editor.core.commands.undo_manager import UndoManager
from conv_editor.core.conversation import Conversation
from conv_editor.core.models import Item, SearchMatch
from conv_editor.services.file_service import FileService
from conv_editor.services.openai_service import OpenAIService
from conv_editor.ui.dialogs.export_dialog import ExportDialog
from conv_editor.ui.dialogs.generation_dialogs import ChatDialog, CompletionDialog
from conv_editor.ui.dialogs.h5_inspector_dialog import H5InspectorDialog
from conv_editor.ui.dialogs.search_dialog import SearchDialog
from conv_editor.ui.dialogs.settings_dialog import SettingsDialog
from conv_editor.ui.dialogs.word_cloud_dialog import WordCloudDialog
from conv_editor.ui.widgets.drop_indicator import DropIndicator
from conv_editor.ui.widgets.empty_state_widget import EmptyStateWidget
from conv_editor.ui.widgets.insertion_widget import InsertionWidget
from conv_editor.ui.widgets.item_widget import ItemWidget
from conv_editor.workers.word_cloud_worker import WordCloudWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    SETTING_KEYS = ["root", "assistant_name", "reasoning", "search_score_cutoff", "unlearnable_bg", "unlearnable_fg", "reasoning_bg", "tools_bg", "tool_response_bg"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(settings.APP_NAME)
        self.resize(800, 600)

        self.q_settings = QSettings(settings.APP_ORGANIZATION_NAME, settings.APP_NAME)

        self.openai_service = OpenAIService()
        self._initialize_settings()

        self.file_service = FileService(self.current_settings["root"])
        self.conversation = Conversation(self.current_settings["assistant_name"])
        self.undo_manager = UndoManager()

        self.word_cloud_worker: Optional[WordCloudWorker] = None
        self.word_cloud_dialog: Optional[WordCloudDialog] = None
        self.search_dialog: Optional[SearchDialog] = None
        self.settings_dialog: Optional[SettingsDialog] = None
        self.original_settings: Optional[dict] = None
        self._current_file: Optional[str] = None
        self._pending_scroll_index: Optional[int] = None

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_central_widget()
        self.setStatusBar(QStatusBar())
        self.item_drop_indicator = DropIndicator(self.conversation_container)

        self._connect_signals()
        self._refresh_directories()
        self._update_main_view_state()
        self.restoreGeometry(self.q_settings.value("geometry", b""))
        self.update_ui_state()

        QTimer.singleShot(0, self._restore_last_session)

    def _initialize_settings(self):
        defaults = {
            "root": settings.APP_ROOT_DIR,
            "assistant_name": settings.APP_ASSISTANT_NAME,
            "reasoning": settings.APP_USE_REASONING,
            "search_score_cutoff": settings.APP_SEARCH_SCORE_CUTOFF,
            "unlearnable_bg": settings.APP_THEME_UNLEARNABLE_BG,
            "unlearnable_fg": settings.APP_THEME_UNLEARNABLE_FG,
            "reasoning_bg": settings.APP_THEME_REASONING_BG,
            "tools_bg": settings.APP_THEME_TOOLS_BG,
            "tool_response_bg": settings.APP_THEME_TOOL_RESULTS_BG,
        }

        self.current_settings = {}
        for key in self.SETTING_KEYS:
            self.current_settings[key] = self.q_settings.value(key, defaults[key])

        self.current_settings["reasoning"] = (
            self.current_settings["reasoning"] == "true" if isinstance(self.current_settings["reasoning"], str) else bool(self.current_settings["reasoning"])
        )
        self.current_settings["search_score_cutoff"] = int(self.current_settings["search_score_cutoff"])
        self.current_settings["openai_model_name"] = self.openai_service.model

    def _save_user_settings(self):
        logger.info("Saving user settings...")
        for key in self.SETTING_KEYS:
            if key in self.current_settings:
                self.q_settings.setValue(key, self.current_settings[key])
        self.q_settings.sync()

    def _restore_last_session(self):
        last_dir = self.q_settings.value("last_directory", "")
        last_file = self.q_settings.value("last_file", "")

        if last_dir:
            dir_index = self.dir_combo.findText(last_dir)
            if dir_index != -1:
                logger.info(f"Restoring last directory: {last_dir}")
                self.dir_combo.setCurrentIndex(dir_index)
                if last_file:
                    QTimer.singleShot(100, lambda: self._select_file_by_name(last_file))

    def _select_file_by_name(self, file_name: str):
        file_index = self.file_combo.findText(file_name)
        if file_index != -1:
            logger.info(f"Restoring last file: {file_name}")
            self.file_combo.setCurrentIndex(file_index)

    def _create_actions(self):
        self.settings_action = QAction("&Settings...", self)

        self.save_action = QAction(QIcon.fromTheme("document-save"), "&Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)

        self.refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        self.refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)

        self.new_file_action = QAction(QIcon.fromTheme("document-new"), "New File", self)
        self.new_file_action.setShortcut(QKeySequence.StandardKey.New)

        self.delete_file_action = QAction(QIcon.fromTheme("edit-delete"), "Delete File", self)

        self.search_action = QAction(QIcon.fromTheme("edit-find"), "&Search...", self)
        self.search_action.setShortcut(QKeySequence.StandardKey.Find)

        self.wordcloud_action = QAction("Generate &Word Cloud...", self)
        self.export_action = QAction(QIcon.fromTheme("document-export"), "Export for &Training...", self)
        self.inspect_h5_action = QAction("&Inspect H5 Dataset...", self)

        self.undo_action = QAction(QIcon.fromTheme("edit-undo"), "&Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setEnabled(False)

        self.redo_action = QAction(QIcon.fromTheme("edit-redo"), "&Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setEnabled(False)

    def _connect_signals(self):
        self.settings_action.triggered.connect(self._open_settings_dialog)
        self.save_action.triggered.connect(self.save_conversation)
        self.exit_action.triggered.connect(self.close)
        self.refresh_action.triggered.connect(self._refresh_ui_data)
        self.new_file_action.triggered.connect(self._create_new_file)
        self.delete_file_action.triggered.connect(self._delete_current_file)
        self.search_action.triggered.connect(self._open_search_dialog)
        self.wordcloud_action.triggered.connect(self._show_word_cloud)
        self.export_action.triggered.connect(self._open_export_dialog)
        self.inspect_h5_action.triggered.connect(self._open_h5_inspector)

        self.undo_action.triggered.connect(self.undo_manager.undo)
        self.redo_action.triggered.connect(self.undo_manager.redo)

        self.undo_manager.canUndoChanged.connect(self.undo_action.setEnabled)
        self.undo_manager.canRedoChanged.connect(self.redo_action.setEnabled)
        self.undo_manager.cleanChanged.connect(self._on_clean_state_changed)
        self.undo_manager.command_executed.connect(self._render_conversation)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_file_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.delete_file_action)
        file_menu.addSeparator()
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.search_action)
        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(self.wordcloud_action)
        tools_menu.addAction(self.export_action)
        tools_menu.addAction(self.inspect_h5_action)

    def _create_tool_bar(self):
        tool_bar = self.addToolBar("Main Toolbar")
        tool_bar.setIconSize(QSize(16, 16))
        self.dir_combo = QComboBox()
        self.dir_combo.setMinimumWidth(150)
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(200)

        tool_bar.addWidget(QLabel(" Directory: "))
        tool_bar.addWidget(self.dir_combo)
        tool_bar.addWidget(QLabel(" File: "))
        tool_bar.addWidget(self.file_combo)
        tool_bar.addAction(self.refresh_action)
        tool_bar.addAction(self.new_file_action)
        tool_bar.addAction(self.save_action)
        tool_bar.addAction(self.delete_file_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.undo_action)
        tool_bar.addAction(self.redo_action)

        self.dir_combo.currentIndexChanged.connect(self._on_directory_selected)
        self.file_combo.currentIndexChanged.connect(self._on_file_selected)

    def _create_central_widget(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_stack = QStackedWidget()
        main_layout.addWidget(self.main_stack)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.conversation_container = QWidget()
        self.conversation_container.setAcceptDrops(True)
        self.conversation_container.dragEnterEvent = self.dragEnterEvent
        self.conversation_container.dragMoveEvent = self.dragMoveEvent
        self.conversation_container.dragLeaveEvent = self.dragLeaveEvent
        self.conversation_container.dropEvent = self.dropEvent

        self.conversation_layout = QVBoxLayout(self.conversation_container)
        self.conversation_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.conversation_container)

        self.empty_state_widget = EmptyStateWidget()
        self.main_stack.addWidget(self.scroll_area)
        self.main_stack.addWidget(self.empty_state_widget)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-conv-editor-item"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.item_drop_indicator.hide()
        event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent):
        target_idx, y_pos = self._get_item_drop_pos(event.position().toPoint())
        if y_pos is not None:
            self.item_drop_indicator.move(0, y_pos)
            self.item_drop_indicator.setFixedWidth(self.conversation_container.width())
            self.item_drop_indicator.show()
            event.acceptProposedAction()
        else:
            self.item_drop_indicator.hide()
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        self.item_drop_indicator.hide()
        if not event.mimeData().hasFormat("application/x-conv-editor-item"):
            event.ignore()
            return

        try:
            mime_data = event.mimeData().data("application/x-conv-editor-item")
            payload = json.loads(mime_data.data().decode("utf-8"))
            source_item_index = payload["source_item_index"]
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to decode item drop payload: {e}")
            event.ignore()
            return

        target_item_index, _ = self._get_item_drop_pos(event.position().toPoint())

        if source_item_index != target_item_index:
            command = MoveItemCommand(self.conversation, source_item_index, target_item_index)
            self.undo_manager.do(command)

        event.acceptProposedAction()

    def _update_main_view_state(self):
        is_root_set = self.file_service.root and self.file_service.root.is_dir()
        is_file_loaded = self.conversation.file_path is not None

        if not is_root_set:
            self.empty_state_widget.set_content(
                title="No Root Directory Set", subtitle="Please select a project root directory via\nFile > Settings... to begin.", icon_theme="folder-open"
            )
            self.main_stack.setCurrentIndex(1)
        elif not is_file_loaded:
            self.empty_state_widget.set_content(
                title="No File Loaded", subtitle="Select a conversation from the dropdown above, or create one using the 'New File' button.", icon_theme="document-open"
            )
            self.main_stack.setCurrentIndex(1)
        else:
            self.main_stack.setCurrentIndex(0)

    def _get_item_drop_pos(self, pos) -> tuple[int, int]:
        if self.conversation_layout.count() == 0:
            return 0, 0

        target_model_idx = 0
        for i in range(self.conversation_layout.count()):
            widget = self.conversation_layout.itemAt(i).widget()
            if not widget:
                continue

            if isinstance(widget, ItemWidget):
                if pos.y() < widget.y() + widget.height() / 2:
                    return target_model_idx, widget.y()
                target_model_idx += 1

        last_widget = self.conversation_layout.itemAt(self.conversation_layout.count() - 2).widget()
        return self.conversation_layout.count() // 2, last_widget.y() + last_widget.height()

    @Slot()
    def _open_settings_dialog(self):
        if self.settings_dialog is None:
            logger.info("Creating new Settings dialog instance.")
            self.original_settings = self.current_settings.copy()
            self.settings_dialog = SettingsDialog(self.current_settings, self)

            self.settings_dialog.setting_changed.connect(self._on_setting_preview_changed)
            self.settings_dialog.apply_clicked.connect(self._on_settings_applied)
            self.settings_dialog.accepted.connect(self._on_settings_accepted)  # OK
            self.settings_dialog.rejected.connect(self._on_settings_rejected)  # Cancel or 'X'
            self.settings_dialog.finished.connect(lambda: setattr(self, "settings_dialog", None))

            self.settings_dialog.show()
        else:
            logger.info("Settings dialog already open, bringing to front.")
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()

    @Slot(str, object)
    def _on_setting_preview_changed(self, key: str, value: object):
        if key not in self.current_settings:
            return

        self.current_settings[key] = value
        logger.debug(f"Previewing setting change: {key} = {value}")

        theme_keys = ["unlearnable_bg", "unlearnable_fg", "reasoning_bg", "tools_bg", "tool_response_bg"]
        if key in theme_keys:
            self._apply_theme_update()
        elif key == "assistant_name":
            self.conversation.assistant_name = value
            self._update_all_item_widgets_assistant_name()

    @Slot()
    def _on_settings_applied(self):
        logger.info("Applying settings.")

        if self.original_settings and self.current_settings["root"] != self.original_settings["root"]:
            try:
                self.file_service.set_root(self.current_settings["root"])
                self._clear_and_reset_state()
                self._refresh_directories()
                self._update_main_view_state()
            except (NotADirectoryError, FileNotFoundError) as e:
                QMessageBox.critical(self, "Invalid Path", str(e))
                self.current_settings["root"] = self.original_settings["root"]
                if self.settings_dialog:
                    self.settings_dialog.set_setting_value("root", self.original_settings["root"])

        self.original_settings = self.current_settings.copy()
        self._save_user_settings()
        self.statusBar().showMessage("Settings applied.", 3000)

    @Slot()
    def _on_settings_accepted(self):
        self._on_settings_applied()

    @Slot()
    def _on_settings_rejected(self):
        logger.info("Cancelling settings changes.")
        if self.original_settings:
            settings_to_revert = self.current_settings.copy()
            self.current_settings = self.original_settings.copy()
            self.original_settings = None

            for key, value in self.current_settings.items():
                if settings_to_revert.get(key) != value:
                    if self.settings_dialog:
                        self.settings_dialog.set_setting_value(key, value)
                    self._on_setting_preview_changed(key, value)

    @Slot()
    def _open_export_dialog(self):
        if not self.file_service.root or not self.file_service.root.is_dir():
            QMessageBox.warning(self, "No Root Directory", "Please set a valid root directory in Settings before exporting.")
            return

        dialog = ExportDialog(root_dir=str(self.file_service.root), assistant_name=self.current_settings["assistant_name"], parent=self)
        dialog.exec()

    @Slot()
    def _open_h5_inspector(self):
        dialog = H5InspectorDialog(self)
        dialog.exec()

    def _clear_and_reset_state(self):
        self._current_file = None
        self.conversation.discard_and_close()
        self.undo_manager.clear()
        self._clear_conversation_view()
        self._pending_scroll_index = None
        self.update_ui_state()
        self._update_window_title()
        self._update_main_view_state()

    def _refresh_ui_data(self):
        stored_dir = self.file_service.working_dir_name
        stored_file = self._current_file
        self._refresh_directories()
        if stored_dir and (dir_idx := self.dir_combo.findText(stored_dir)) != -1:
            self.dir_combo.setCurrentIndex(dir_idx)
            self._refresh_files()
            if stored_file and (file_idx := self.file_combo.findText(stored_file)) != -1:
                self.file_combo.setCurrentIndex(file_idx)
        self.statusBar().showMessage("Refreshed.", 2000)

    def _refresh_directories(self):
        self.dir_combo.blockSignals(True)
        self.dir_combo.clear()
        self.dir_combo.addItem("- Select Directory -")
        try:
            dirs = self.file_service.list_directories()
            if dirs:
                self.dir_combo.addItems(dirs)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not list directories:\n{e}")
        self.dir_combo.blockSignals(False)

    def _refresh_files(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        self.file_combo.addItem("- Select File -")
        try:
            if self.file_service.working_dir_name:
                files = self.file_service.list_files_in_working_dir()
                if files:
                    self.file_combo.addItems(files)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not list files:\n{e}")
        self.file_combo.blockSignals(False)

    @Slot(int)
    def _on_directory_selected(self, index: int):
        if not self._maybe_save():
            self.dir_combo.blockSignals(True)
            prev_idx = self.dir_combo.findText(self.file_service.working_dir_name or "")
            self.dir_combo.setCurrentIndex(prev_idx if prev_idx != -1 else 0)
            self.dir_combo.blockSignals(False)
            return

        self._clear_and_reset_state()
        selected_dir = ""
        if index > 0:
            selected_dir = self.dir_combo.itemText(index)
            self.file_service.set_working_dir(selected_dir)
        else:
            self.file_service.set_working_dir("")

        self.q_settings.setValue("last_directory", selected_dir)
        self.q_settings.setValue("last_file", "")

        self._refresh_files()
        self.update_ui_state()
        self._update_main_view_state()

    @Slot(int)
    def _on_file_selected(self, index: int):
        if not self._maybe_save():
            self.file_combo.blockSignals(True)
            prev_idx = self.file_combo.findText(self._current_file or "")
            self.file_combo.setCurrentIndex(prev_idx if prev_idx != -1 else 0)
            self.file_combo.blockSignals(False)
            return

        selected_file = ""
        if index > 0:
            selected_file = self.file_combo.itemText(index)
            self._load_conversation(selected_file)
        else:
            self._clear_and_reset_state()
        self.q_settings.setValue("last_file", selected_file)

    def _load_conversation(self, file_name: str):
        full_path = self.file_service.get_full_path(file_name)
        if not full_path or not full_path.exists():
            QMessageBox.critical(self, "Error", f"Could not find file: {file_name}")
            return
        self.conversation.load(full_path, self.file_service.root)
        self.undo_manager.clear()
        self._current_file = file_name
        self._render_conversation()
        self.update_ui_state()
        self._update_main_view_state()
        self.statusBar().showMessage(f"Loaded: {file_name}", 3000)

    def save_conversation(self):
        if not self.conversation.file_path:
            return
        try:
            self.conversation.save()
            self.undo_manager.set_clean()
            self.statusBar().showMessage("Saved successfully.", 3000)
            self.update_ui_state()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")

    def _maybe_save(self) -> bool:
        if self.undo_manager.is_clean:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Do you want to save your changes?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self.save_conversation()
            return self.undo_manager.is_clean
        return reply == QMessageBox.StandardButton.Discard

    def _clear_conversation_view(self):
        while (item := self.conversation_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()

    def _render_conversation(self):
        self._clear_conversation_view()
        self._add_insertion_widget(0)
        for index, item_data in enumerate(self.conversation.get_all_items()):
            self._add_item_widget(item_data, index)
            self._add_insertion_widget(index + 1)
        self._execute_pending_scroll()

    def _add_item_widget(self, item_data: Item, index: int):
        widget = ItemWidget(
            item=item_data,
            index=index,
            model=self.conversation,
            undo_manager=self.undo_manager,
            assistant_name=self.current_settings["assistant_name"],
            colors=self.current_settings,
            parent=self.conversation_container,
        )
        widget.request_delete.connect(self._on_delete_item_requested)
        widget.request_generate.connect(self._on_generate_requested)
        widget.request_chat.connect(self._on_chat_requested)
        widget.request_global_rerender.connect(self._render_conversation)
        widget.request_global_rerender.connect(self.update_ui_state)
        self.conversation_layout.addWidget(widget)

    def _add_insertion_widget(self, index: int):
        insertion_widget = InsertionWidget(index, self.current_settings["assistant_name"], self.conversation_container)
        insertion_widget.request_insert_item.connect(self._on_insert_item_requested)
        self.conversation_layout.addWidget(insertion_widget)

    @Slot(int, str)
    def _on_insert_item_requested(self, index: int, role: str):
        command = InsertItemCommand(self.conversation, index, role)
        self.undo_manager.do(command)
        QTimer.singleShot(50, lambda: self._scroll_to_item(index))

    def _apply_theme_update(self):
        for i in range(self.conversation_layout.count()):
            widget = self.conversation_layout.itemAt(i).widget()
            if isinstance(widget, ItemWidget):
                widget.update_all_colors(self.current_settings)

    @Slot(int)
    def _on_delete_item_requested(self, index: int):
        command = RemoveItemCommand(self.conversation, index)
        self.undo_manager.do(command)

    @Slot(bool)
    def _on_clean_state_changed(self, is_dirty: bool):
        self.update_ui_state()

    @Slot()
    def _create_new_file(self):
        if not self._maybe_save():
            return
        default = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_name, ok = QInputDialog.getText(self, "New File", "Filename:", text=default)
        if ok and file_name:
            if self.file_service.create_new_file(file_name):
                self._refresh_files()
                if (idx := self.file_combo.findText(file_name)) != -1:
                    self.file_combo.setCurrentIndex(idx)
            else:
                QMessageBox.warning(self, "Error", "File already exists or is invalid.")

    @Slot()
    def _delete_current_file(self):
        if not self._current_file or not self.conversation.file_path:
            return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{self._current_file}' permanently?")
        if reply == QMessageBox.StandardButton.Yes:
            self.conversation.delete_file()
            self._clear_and_reset_state()
            self._refresh_files()

    @Slot(int)
    def _on_generate_requested(self, index: int):
        if self.openai_service.is_generating:
            QMessageBox.warning(self, "Busy", "A generation task is already running.")
            return
        prompt = self.conversation.get_data_slice_as_string(
            end_idx=index,
            with_reason=self.current_settings["reasoning"],
        )
        dialog = CompletionDialog(prompt, self.openai_service, self)
        dialog.start_generation()

    @Slot(int)
    def _on_chat_requested(self, index: int):
        if self.openai_service.is_generating:
            QMessageBox.warning(self, "Busy", "A generation task is already running.")
            return
        chat_data = self.conversation.get_data_slice_for_chat(end_idx=index, with_reason=self.current_settings["reasoning"])
        if not chat_data:
            QMessageBox.information(self, "Chat Error", "No valid history to start chat.")
            return
        dialog = ChatDialog(chat_data, self.openai_service, self)
        dialog.start_generation()

    @Slot()
    def _open_search_dialog(self):
        if self.search_dialog is None:
            self.search_dialog = SearchDialog(self.current_settings["root"], self.current_settings["search_score_cutoff"], self)
            self.search_dialog.search_result_selected.connect(self._navigate_to_search_result)
            self.search_dialog.finished.connect(lambda: setattr(self, "search_dialog", None))

        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()

    @Slot(SearchMatch)
    def _navigate_to_search_result(self, result: SearchMatch):
        if not self._maybe_save():
            return

        try:
            target_path = Path(result.file_path)
            root_path = self.file_service.root
            relative_path = target_path.relative_to(root_path)
            target_dir, target_file = relative_path.parent.name, relative_path.name
        except (ValueError, IndexError) as e:
            QMessageBox.critical(self, "Navigation Error", f"Invalid path: {e}")
            return

        if result.item_index is not None:
            self._pending_scroll_index = result.item_index

        dir_index = self.dir_combo.findText(target_dir)
        if dir_index == -1:
            self._refresh_directories()
            dir_index = self.dir_combo.findText(target_dir)
            if dir_index == -1:
                QMessageBox.warning(self, "Navigation Error", f"Directory '{target_dir}' not found.")
                self._pending_scroll_index = None
                return

        if self.dir_combo.currentIndex() != dir_index:
            self.dir_combo.setCurrentIndex(dir_index)

        file_index = self.file_combo.findText(target_file)
        if file_index == -1:
            QMessageBox.warning(self, "Navigation Error", f"File '{target_file}' not found.")
            self._pending_scroll_index = None
            return

        if self.file_combo.currentIndex() != file_index:
            self.file_combo.setCurrentIndex(file_index)
        else:
            self._execute_pending_scroll()

    def _execute_pending_scroll(self):
        if self._pending_scroll_index is not None:
            index_to_scroll_to = self._pending_scroll_index
            self._pending_scroll_index = None
            QTimer.singleShot(0, lambda: self._scroll_to_item(index_to_scroll_to))

    def _scroll_to_item(self, item_index: int):
        # The layout index is 2 * item_index + 1 because of the insertion widgets
        layout_index = 2 * item_index + 1
        if 0 <= layout_index < self.conversation_layout.count():
            widget = self.conversation_layout.itemAt(layout_index).widget()
            if isinstance(widget, ItemWidget):
                self.scroll_area.ensureWidgetVisible(widget, ymargin=50)

    @Slot()
    def _show_word_cloud(self):
        if self.word_cloud_worker and self.word_cloud_worker.isRunning():
            return
        self.wordcloud_action.setEnabled(False)
        self.statusBar().showMessage("Generating word cloud...")

        self.word_cloud_worker = WordCloudWorker(self.current_settings["root"], self.current_settings["assistant_name"], self)
        self.word_cloud_worker.progress.connect(self.statusBar().showMessage)
        self.word_cloud_worker.error.connect(lambda msg: QMessageBox.warning(self, "Word Cloud Error", msg))
        self.word_cloud_worker.finished.connect(self._on_word_cloud_finished)
        self.word_cloud_worker.start()

    @Slot(object)
    def _on_word_cloud_finished(self, pil_image: Optional[PILImage]):
        if pil_image:
            self.word_cloud_dialog = WordCloudDialog(pil_image, self)
            self.word_cloud_dialog.show()
        self.wordcloud_action.setEnabled(True)
        self.statusBar().clearMessage()
        self.word_cloud_worker = None

    def _update_all_item_widgets_assistant_name(self):
        new_name = self.current_settings["assistant_name"]
        for i in range(self.conversation_layout.count()):
            widget = self.conversation_layout.itemAt(i).widget()
            if isinstance(widget, ItemWidget):
                widget.update_assistant_name(new_name)
            elif isinstance(widget, InsertionWidget):
                widget.update_assistant_name(new_name)

    def update_ui_state(self):
        is_file_loaded = self.conversation.file_path is not None
        has_changes = not self.undo_manager.is_clean
        is_dir_selected = self.file_service.working_dir_name is not None

        self.save_action.setEnabled(is_file_loaded and has_changes)
        self.delete_file_action.setEnabled(is_file_loaded)
        self.new_file_action.setEnabled(is_dir_selected)
        self._update_window_title()

    def _update_window_title(self):
        title = settings.APP_NAME
        if self.file_service.working_dir_name and self._current_file:
            title += f" - {self.file_service.working_dir_name}/{self._current_file}"
        if not self.undo_manager.is_clean:
            title += "*"
        self.setWindowTitle(title)

    def closeEvent(self, event: QCloseEvent):
        if self._maybe_save():
            self.q_settings.setValue("geometry", self.saveGeometry())
            if self.file_service.working_dir_name:
                self.q_settings.setValue("last_directory", self.file_service.working_dir_name)
            if self._current_file:
                self.q_settings.setValue("last_file", self._current_file)

            self._save_user_settings()
            event.accept()
        else:
            event.ignore()
