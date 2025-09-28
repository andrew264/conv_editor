from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, current_settings: dict, openai_model_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.settings = current_settings.copy()
        self.openai_model_name = openai_model_name
        self._setup_ui()

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

    def _setup_ui(self):
        self.preview_buttons = {}
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        root_layout = QHBoxLayout()
        self.root_edit = QLineEdit(self.settings.get("root", ""))
        self.root_edit.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_root)
        root_layout.addWidget(self.root_edit)
        root_layout.addWidget(browse_button)
        form_layout.addRow("Root Folder:", root_layout)

        self.assistant_name_edit = QLineEdit(self.settings.get("assistant_name", ""))
        form_layout.addRow("Assistant Name:", self.assistant_name_edit)

        model_label = QLabel(f"<b>{self.openai_model_name}</b> (from .env file)")
        model_label.setTextFormat(Qt.TextFormat.RichText)
        form_layout.addRow("OpenAI Model:", model_label)

        self.reasoning_checkbox = QCheckBox("Include Reasoning (<think>)")
        self.reasoning_checkbox.setChecked(self.settings.get("reasoning", False))
        form_layout.addRow(self.reasoning_checkbox)

        self.search_cutoff_spinbox = QSpinBox()
        self.search_cutoff_spinbox.setRange(0, 100)
        self.search_cutoff_spinbox.setValue(self.settings.get("search_score_cutoff", 75))
        form_layout.addRow("Search Score Cutoff:", self.search_cutoff_spinbox)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        form_layout.addRow(separator)
        form_layout.addRow(QLabel("<b>Theme Colors</b>"))

        form_layout.addRow("Unlearnable BG:", self._create_color_picker("unlearnable_bg"))
        form_layout.addRow("Unlearnable Text:", self._create_color_picker("unlearnable_fg"))
        form_layout.addRow("Reasoning BG:", self._create_color_picker("reasoning_bg"))
        form_layout.addRow("Tools BG:", self._create_color_picker("tools_bg"))
        form_layout.addRow("Tool Response BG:", self._create_color_picker("tool_response_bg"))

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._apply_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @Slot(str)
    def _open_color_dialog(self, setting_key: str):
        current_color = QColor(self.settings.get(setting_key))
        color = QColorDialog.getColor(current_color, self, "Select Color")
        if color.isValid():
            self.settings[setting_key] = color.name()
            self._update_color_preview(setting_key)

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

    @Slot()
    def _apply_settings(self):
        self.settings["root"] = self.root_edit.text()
        self.settings["assistant_name"] = self.assistant_name_edit.text()
        self.settings["reasoning"] = self.reasoning_checkbox.isChecked()
        self.settings["search_score_cutoff"] = self.search_cutoff_spinbox.value()
        self.accept()

    def get_settings(self) -> dict:
        return self.settings
