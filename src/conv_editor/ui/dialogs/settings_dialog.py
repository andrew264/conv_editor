from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    setting_changed = Signal(str, object)  # Emits: key, value
    apply_clicked = Signal()

    def __init__(self, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.settings = current_settings.copy()
        self.preview_buttons = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Project Settings Group ---
        project_group = QGroupBox("Project Settings")
        project_layout = QFormLayout(project_group)
        self.root_edit = QLineEdit(self.settings.get("root", ""))
        self.root_edit.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        root_layout = QHBoxLayout()
        root_layout.addWidget(self.root_edit)
        root_layout.addWidget(browse_button)
        project_layout.addRow("Root Folder:", root_layout)
        self.assistant_name_edit = QLineEdit(self.settings.get("assistant_name", ""))
        project_layout.addRow("Assistant Name:", self.assistant_name_edit)
        main_layout.addWidget(project_group)

        # --- AI & Generation Group ---
        ai_group = QGroupBox("AI & Generation")
        ai_layout = QFormLayout(ai_group)
        model_label = QLabel(f"<b>{self.settings.get('openai_model_name', 'N/A')}</b> (from .env file)")
        model_label.setTextFormat(Qt.TextFormat.RichText)
        ai_layout.addRow("OpenAI Model:", model_label)
        self.reasoning_checkbox = QCheckBox("Include Reasoning (<think>) for Generation")
        self.reasoning_checkbox.setChecked(self.settings.get("reasoning", False))
        ai_layout.addRow(self.reasoning_checkbox)
        main_layout.addWidget(ai_group)

        # --- Editor & Behavior Group ---
        editor_group = QGroupBox("Editor & Behavior")
        editor_layout = QFormLayout(editor_group)
        self.search_cutoff_spinbox = QSpinBox()
        self.search_cutoff_spinbox.setRange(0, 100)
        self.search_cutoff_spinbox.setValue(self.settings.get("search_score_cutoff", 75))
        self.search_cutoff_spinbox.setSuffix("%")
        editor_layout.addRow("Fuzzy Search Score Cutoff:", self.search_cutoff_spinbox)
        main_layout.addWidget(editor_group)

        # --- Theme Colors Group ---
        theme_group = QGroupBox("Theme Colors")
        theme_layout = QFormLayout(theme_group)
        theme_layout.addRow("Unlearnable BG:", self._create_color_picker("unlearnable_bg"))
        theme_layout.addRow("Unlearnable Text:", self._create_color_picker("unlearnable_fg"))
        theme_layout.addRow("Reasoning BG:", self._create_color_picker("reasoning_bg"))
        theme_layout.addRow("Tools BG:", self._create_color_picker("tools_bg"))
        theme_layout.addRow("Tool Response BG:", self._create_color_picker("tool_response_bg"))
        main_layout.addWidget(theme_group)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply)
        main_layout.addWidget(self.button_box)

        self.browse_root_button = browse_button

    def _connect_signals(self):
        self.browse_root_button.clicked.connect(self._browse_root)
        self.assistant_name_edit.textChanged.connect(lambda text: self.setting_changed.emit("assistant_name", text))
        self.reasoning_checkbox.toggled.connect(lambda checked: self.setting_changed.emit("reasoning", checked))
        self.search_cutoff_spinbox.valueChanged.connect(lambda value: self.setting_changed.emit("search_score_cutoff", value))

        self.button_box.accepted.connect(self.accept)  # Ok
        self.button_box.rejected.connect(self.reject)  # Cancel
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_clicked.emit)

    def _create_color_picker(self, setting_key: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.preview_buttons[setting_key] = QPushButton()
        self.preview_buttons[setting_key].setFixedSize(25, 25)
        self.preview_buttons[setting_key].setAutoFillBackground(True)
        self.preview_buttons[setting_key].setFlat(True)
        self._update_color_preview(setting_key)
        choose_button = QPushButton("Choose...")
        choose_button.clicked.connect(lambda: self._open_color_dialog(setting_key))
        layout.addWidget(self.preview_buttons[setting_key])
        layout.addWidget(choose_button)
        layout.addStretch()
        return layout

    @Slot(str)
    def _open_color_dialog(self, setting_key: str):
        current_color_hex = self.settings.get(setting_key, "#ffffff")
        color = QColorDialog.getColor(QColor(current_color_hex), self, "Select Color")
        if color.isValid():
            new_color_hex = color.name()
            self.settings[setting_key] = new_color_hex
            self._update_color_preview(setting_key)
            self.setting_changed.emit(setting_key, new_color_hex)

    def _update_color_preview(self, setting_key: str):
        color = QColor(self.settings.get(setting_key, "#ffffff"))
        palette = self.preview_buttons[setting_key].palette()
        palette.setColor(QPalette.ColorRole.Button, color)
        self.preview_buttons[setting_key].setPalette(palette)

    @Slot()
    def _browse_root(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Root Directory", self.root_edit.text() or ".")
        if directory:
            self.root_edit.setText(directory)
            self.setting_changed.emit("root", directory)

    def set_setting_value(self, key: str, value: object):
        self.settings[key] = value

        if key == "root":
            self.root_edit.blockSignals(True)
            self.root_edit.setText(value)
            self.root_edit.blockSignals(False)
        elif key == "assistant_name":
            self.assistant_name_edit.blockSignals(True)
            self.assistant_name_edit.setText(value)
            self.assistant_name_edit.blockSignals(False)
        elif key == "reasoning":
            self.reasoning_checkbox.blockSignals(True)
            self.reasoning_checkbox.setChecked(value)
            self.reasoning_checkbox.blockSignals(False)
        elif key == "search_score_cutoff":
            self.search_cutoff_spinbox.blockSignals(True)
            self.search_cutoff_spinbox.setValue(value)
            self.search_cutoff_spinbox.blockSignals(False)
        elif key in self.preview_buttons:
            self._update_color_preview(key)
