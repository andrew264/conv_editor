from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget


class InsertionWidget(QWidget):
    request_insert_item = Signal(int, str)

    def __init__(self, index: int, assistant_name: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.assistant_name = assistant_name

        self.setMouseTracking(True)
        self.setMinimumHeight(30)
        self.setMaximumHeight(35)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.line = QFrame()
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)
        self.line.setStyleSheet("border-color: #555;")
        self.line.setVisible(False)

        self.add_user_button = QPushButton("+ User")
        self.add_assistant_button = QPushButton(f"+ {self.assistant_name}")
        self.add_system_button = QPushButton("+ System")
        self.add_tool_button = QPushButton("+ Tool")

        self.buttons = [
            self.add_user_button,
            self.add_assistant_button,
            self.add_system_button,
            self.add_tool_button,
        ]

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        for button in self.buttons:
            button.setVisible(False)
            button.setFlat(True)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a;
                    border: 1px solid #666;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
            """)
            button_layout.addWidget(button)

        layout.addWidget(self.line)
        layout.addWidget(button_container)

        self.add_user_button.clicked.connect(lambda: self.request_insert_item.emit(self.index, "user"))
        self.add_assistant_button.clicked.connect(lambda: self.request_insert_item.emit(self.index, self.assistant_name))
        self.add_system_button.clicked.connect(lambda: self.request_insert_item.emit(self.index, "system"))
        self.add_tool_button.clicked.connect(lambda: self.request_insert_item.emit(self.index, "tool"))

    def enterEvent(self, event):
        self.line.setVisible(True)
        for button in self.buttons:
            button.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.line.setVisible(False)
        for button in self.buttons:
            button.setVisible(False)
        super().leaveEvent(event)

    def update_assistant_name(self, new_name: str):
        self.assistant_name = new_name
        self.add_assistant_button.setText(f"+ {self.assistant_name}")
