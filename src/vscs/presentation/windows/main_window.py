"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    """Primary window for the Video Series Studio desktop application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Series Studio — VSCS Framework v0.1")
        self.resize(1280, 800)

        placeholder = QLabel("VSCS Framework\nInitial development environment ready")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
        self.statusBar().showMessage("Ready")
