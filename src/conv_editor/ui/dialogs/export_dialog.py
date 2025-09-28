import logging
from pathlib import Path

from PySide6.QtCore import QStringListModel, Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)
from tokenizers import Tokenizer

from conv_editor.export.config import ExportConfig, SpecialTokensConfig
from conv_editor.workers.export_worker import ExportWorker

logger = logging.getLogger(__name__)


class ExportDialog(QDialog):
    DEBOUNCE_MS = 250

    def __init__(self, root_dir: str, assistant_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Conversations for Training")
        self.setMinimumWidth(600)

        self.root_dir = root_dir
        self.assistant_name = assistant_name
        self.tokenizer: Tokenizer | None = None
        self.worker: ExportWorker | None = None
        self.completer: QCompleter | None = None

        self.token_edits: dict[str, QLineEdit] = {}
        self.token_id_labels: dict[str, QLabel] = {}

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(self.DEBOUNCE_MS)

        self._setup_ui()
        self._connect_signals()
        self._update_ui_state()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Paths Group
        paths_group = QGroupBox("File Paths")
        paths_layout = QFormLayout(paths_group)
        self.tokenizer_path_edit = QLineEdit()
        self.tokenizer_path_edit.setReadOnly(True)
        browse_tokenizer_button = QPushButton("Browse...")
        tokenizer_layout = QHBoxLayout()
        tokenizer_layout.addWidget(self.tokenizer_path_edit)
        tokenizer_layout.addWidget(browse_tokenizer_button)
        paths_layout.addRow("Tokenizer (.json):", tokenizer_layout)

        self.output_path_edit = QLineEdit()
        browse_output_button = QPushButton("Browse...")
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(browse_output_button)
        paths_layout.addRow("Output (.h5):", output_layout)
        main_layout.addWidget(paths_group)

        # Config Group
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout(config_group)
        self.include_reasoning_checkbox = QCheckBox("Include <think> blocks in training")
        self.include_reasoning_checkbox.setChecked(True)
        config_layout.addWidget(self.include_reasoning_checkbox)
        main_layout.addWidget(config_group)

        # Tokens Group
        tokens_group = QGroupBox("Special Tokens")
        tokens_main_layout = QVBoxLayout(tokens_group)
        self.load_defaults_button = QPushButton("Load Defaults from Model")
        tokens_main_layout.addWidget(self.load_defaults_button, 0, Qt.AlignmentFlag.AlignLeft)
        tokens_form_layout = QFormLayout()
        tokens_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        for key, field_info in SpecialTokensConfig.model_fields.items():
            edit = QLineEdit(field_info.default)
            id_label = QLabel("-")
            id_label.setMinimumWidth(80)
            id_label.setStyleSheet("color: #aaa;")

            row_layout = QHBoxLayout()
            row_layout.addWidget(edit)
            row_layout.addWidget(id_label)

            self.token_edits[key] = edit
            self.token_id_labels[key] = id_label
            tokens_form_layout.addRow(f"{key}:", row_layout)

        tokens_main_layout.addLayout(tokens_form_layout)
        main_layout.addWidget(tokens_group)

        # Progress Section
        self.status_label = QLabel("Ready to export.")
        main_layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.start_button = QPushButton("Start Export")
        self.close_button = QPushButton("Close")
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

        self.browse_tokenizer_button = browse_tokenizer_button
        self.browse_output_button = browse_output_button
        self.config_widgets = [paths_group, config_group, tokens_group]

    def _connect_signals(self):
        self.browse_tokenizer_button.clicked.connect(self._browse_tokenizer)
        self.browse_output_button.clicked.connect(self._browse_output)
        self.tokenizer_path_edit.textChanged.connect(self._update_ui_state)
        self.output_path_edit.textChanged.connect(self._update_ui_state)
        self.load_defaults_button.clicked.connect(self._load_defaults)
        self.start_button.clicked.connect(self._start_or_stop_export)
        self.close_button.clicked.connect(self.reject)

        for edit in self.token_edits.values():
            edit.textChanged.connect(self.debounce_timer.start)
        self.debounce_timer.timeout.connect(self._update_token_ids)

    @Slot()
    def _browse_tokenizer(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tokenizer", "", "Tokenizer files (*.json)")
        if path:
            self.tokenizer_path_edit.setText(path)
            self._load_tokenizer(Path(path))

    def _load_tokenizer(self, path: Path):
        try:
            self.tokenizer = Tokenizer.from_file(str(path))
            self.status_label.setText(f"Successfully loaded tokenizer with {self.tokenizer.get_vocab_size()} tokens.")
            logger.info("Tokenizer loaded successfully.")
        except Exception as e:
            self.tokenizer = None
            QMessageBox.critical(self, "Tokenizer Error", f"Failed to load tokenizer file:\n\n{e}")
            logger.error(f"Failed to load tokenizer: {e}")

        self._setup_completer()
        self._update_ui_state()
        self._update_token_ids()

    @Slot()
    def _setup_completer(self):
        if not self.tokenizer:
            logger.warning("Tokenizer not loaded, cannot setup completer. Clearing existing completers.")
            if self.completer is not None:
                for edit in self.token_edits.values():
                    edit.setCompleter(None)
                self.completer.deleteLater()
            self.completer = None
            return

        special_tokens_list = list(v.content for v in self.tokenizer.get_added_tokens_decoder().values())

        if self.completer is None:
            self.completer = QCompleter(special_tokens_list, self)
            self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.completer.setFilterMode(Qt.MatchFlag.MatchContains)

            for edit in self.token_edits.values():
                edit.setCompleter(self.completer)
        else:
            self.completer.setModel(QStringListModel([]))

    @Slot()
    def _update_token_ids(self):
        if not self.tokenizer:
            for label in self.token_id_labels.values():
                label.setText("-")
            return

        for key, edit in self.token_edits.items():
            text = edit.text()
            label = self.token_id_labels[key]
            if not text:
                label.setText("-")
                continue

            try:
                encoding = self.tokenizer.encode(text, add_special_tokens=False)
                if encoding.ids:
                    label.setText(str(encoding.ids))
                else:
                    label.setText("[]")
                label.setToolTip("")
            except Exception as e:
                label.setText("Error")
                label.setToolTip(f"Could not encode token: {e}")

    @Slot()
    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Export File", "", "HDF5 files (*.h5)")
        if path:
            self.output_path_edit.setText(path)

    @Slot()
    def _load_defaults(self):
        defaults = SpecialTokensConfig()
        for key, edit in self.token_edits.items():
            edit.setText(getattr(defaults, key, ""))
        self._update_token_ids()

    @Slot()
    def _start_or_stop_export(self):
        if self.worker and self.worker.isRunning():
            self.start_button.setEnabled(False)
            self.start_button.setText("Stopping...")
            self.worker.stop()
            return

        token_config_data = {key: edit.text() for key, edit in self.token_edits.items()}
        try:
            special_tokens = SpecialTokensConfig.model_validate(token_config_data)
            config = ExportConfig(
                root_directory=Path(self.root_dir),
                tokenizer_path=Path(self.tokenizer_path_edit.text()),
                output_path=Path(self.output_path_edit.text()),
                include_reasoning=self.include_reasoning_checkbox.isChecked(),
                special_tokens=special_tokens,
                assistant_name=self.assistant_name,
            )
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", f"Invalid settings: {e}")
            return

        self.worker = ExportWorker(config, self)
        self.worker.status_update.connect(self.status_label.setText)
        self.worker.progress.connect(self._on_progress)
        self.worker.export_completed.connect(self._on_export_completed)
        self.worker.error.connect(self._on_error)

        self._set_running_state(True)
        self.worker.start()

    @Slot(int, int)
    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    @Slot()
    def _on_export_completed(self):
        self._set_running_state(False)
        if self.isVisible():
            QMessageBox.information(self, "Success", "Export process completed successfully.")

    @Slot(str)
    def _on_error(self, message: str):
        self._set_running_state(False)
        if self.isVisible():
            QMessageBox.critical(self, "Export Error", message)

    def _update_ui_state(self):
        is_ready = bool(self.tokenizer_path_edit.text() and self.output_path_edit.text())
        self.start_button.setEnabled(is_ready)

    def _set_running_state(self, is_running: bool):
        for widget in self.config_widgets:
            widget.setEnabled(not is_running)

        self.progress_bar.setVisible(is_running)
        if not is_running:
            self.progress_bar.setValue(0)
            self.start_button.setText("Start Export")
            self.start_button.setEnabled(True)
            if self.worker:
                self.worker.deleteLater()
            self.worker = None
            self._update_ui_state()
        else:
            self.start_button.setText("Stop")
            self.start_button.setEnabled(True)

    def reject(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Export in Progress",
                "An export is currently running. Do you want to stop it and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                super().reject()
        else:
            super().reject()

    def closeEvent(self, event: QCloseEvent):
        if self.worker and self.worker.isRunning():
            self.reject()
            if self.worker and self.worker.isRunning():
                event.ignore()
        else:
            event.accept()
