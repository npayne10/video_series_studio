"""Reusable collapsible panels for adaptive VSCS editor workspaces."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleWorkspacePanel(QFrame):
    """Wrap existing editor content in a compact collapsible panel."""

    collapsed_changed = Signal(bool)

    def __init__(
        self,
        title: str,
        content: QWidget,
        parent: QWidget | None = None,
        *,
        collapsed: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._title = title
        self._collapsed = False

        self.toggle_button = QToolButton(self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setToolTip(f"Expand or collapse {title.lower()}.")
        self.toggle_button.setAccessibleName(f"Toggle {title}")

        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet("font-weight: 600;")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.toggle_button)
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.content = content
        self.content.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 8)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addWidget(self.content)

        self.toggle_button.clicked.connect(self.toggle)
        self.set_collapsed(collapsed)

    @property
    def collapsed(self) -> bool:
        """Return whether the panel content is hidden."""
        return self._collapsed

    def set_title(self, title: str) -> None:
        """Update the visible panel heading."""
        self._title = title
        self.title_label.setText(title)
        self.toggle_button.setToolTip(f"Expand or collapse {title.lower()}.")

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the panel state without losing its content."""
        changed = collapsed != self._collapsed
        self._collapsed = collapsed
        self.content.setVisible(not collapsed)
        self.toggle_button.setChecked(not collapsed)
        self.toggle_button.setText("▸" if collapsed else "▾")
        if changed:
            self.collapsed_changed.emit(collapsed)

    def toggle(self) -> None:
        """Toggle the content visibility."""
        self.set_collapsed(not self._collapsed)
