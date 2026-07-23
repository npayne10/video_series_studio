"""VSCS application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from vscs.infrastructure.configuration import ConfigurationError, ConfigurationService
from vscs.presentation.windows.main_window import MainWindow


def main() -> int:
    """Launch the VSCS desktop application."""
    application = QApplication(sys.argv)
    application.setApplicationName("Video Series Studio")
    application.setOrganizationName("VSCS")

    configuration = ConfigurationService()
    try:
        configuration.load()
    except ConfigurationError as exc:
        QMessageBox.critical(None, "Configuration Error", str(exc))
        return 1

    window = MainWindow(configuration)
    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
