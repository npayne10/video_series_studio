"""VSCS application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from vscs.presentation.windows.main_window import MainWindow


def main() -> int:
    """Launch the VSCS desktop application."""
    application = QApplication(sys.argv)
    application.setApplicationName("Video Series Studio")
    application.setOrganizationName("VSCS")

    window = MainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
