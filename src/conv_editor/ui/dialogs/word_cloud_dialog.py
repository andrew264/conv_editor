import logging
from typing import Optional

from PIL.Image import Image as PILImage
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QSizePolicy, QVBoxLayout

logger = logging.getLogger(__name__)


class WordCloudDialog(QDialog):
    def __init__(self, pil_image: PILImage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assistant Word Cloud")
        self.setMinimumSize(800, 400)
        self.setModal(False)

        self.raw_pixmap: Optional[QPixmap] = None
        layout = QVBoxLayout(self)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.image_label)

        self._convert_and_set_image(pil_image)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _convert_and_set_image(self, pil_image: PILImage):
        try:
            if pil_image.mode != "RGBA":
                pil_image = pil_image.convert("RGBA")

            img_data = pil_image.tobytes("raw", "RGBA")
            q_image = QImage(
                img_data,
                pil_image.width,
                pil_image.height,
                QImage.Format.Format_RGBA8888,
            )
            self.raw_pixmap = QPixmap.fromImage(q_image)

            if self.raw_pixmap.isNull():
                self.image_label.setText("Error: Could not display image.")
            else:
                self._update_scaled_pixmap()

        except Exception as e:
            logger.exception("Error converting PIL image to QPixmap.")
            self.image_label.setText(f"Error displaying image:\n{e}")

    def _update_scaled_pixmap(self):
        if not self.raw_pixmap:
            return
        scaled_pixmap = self.raw_pixmap.scaled(
            self.image_label.size() * 0.98,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_scaled_pixmap()
