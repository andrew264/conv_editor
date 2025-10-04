from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyStateWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.setSpacing(15)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setObjectName("emptyStateTitle")
        self._title_label.setWordWrap(True)

        self._subtitle_label = QLabel()
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setObjectName("emptyStateSubtitle")
        self._subtitle_label.setWordWrap(True)

        self._layout.addStretch()
        self._layout.addWidget(self._icon_label)
        self._layout.addWidget(self._title_label)
        self._layout.addWidget(self._subtitle_label)
        self._layout.addStretch()

        self.setStyleSheet("""
            #emptyStateTitle {
                font-size: 14pt;
                font-weight: bold;
            }
            #emptyStateSubtitle {
                font-size: 10pt;
                color: #888;
            }
        """)

    def set_content(self, title: str, subtitle: str, icon_theme: str = None, icon_size: int = 64):
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)

        if icon_theme:
            icon = QIcon.fromTheme(icon_theme)
            if not icon.isNull():
                pixmap = icon.pixmap(icon_size, icon_size)
                self._icon_label.setPixmap(pixmap)
                self._icon_label.setVisible(True)
        else:
            self._icon_label.setVisible(False)
