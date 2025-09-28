import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from conv_editor.config.logging_config import setup_logging
from conv_editor.config.settings import settings
from conv_editor.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def run():
    setup_logging()
    logger.info("Starting Conversation Editor application.")

    try:
        app = QApplication(sys.argv)
        QApplication.setOrganizationName(settings.APP_ORGANIZATION_NAME)
        QApplication.setApplicationName(settings.APP_NAME)

        default_font = QFont("Noto Sans", 10)
        app.setFont(default_font)

        main_window = MainWindow()
        main_window.show()

        sys.exit(app.exec())

    except Exception as e:
        logger.critical("An unhandled exception occurred during application startup.", exc_info=True)
        QMessageBox.critical(None, "Application Startup Error", f"Failed to start the application:\n\n{e}")
        sys.exit(1)
