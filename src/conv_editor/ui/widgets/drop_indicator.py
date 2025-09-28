from PySide6.QtWidgets import QFrame


class DropIndicator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)

        self.setStyleSheet("border: 2px solid #55aaff;")
        self.hide()
