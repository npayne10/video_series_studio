"""Reusable live progress checklist for guided VSCS workflows."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .workflow_steps import WorkflowStepState


class _WorkflowStepButton(QToolButton):
    """Activate workflow navigation consistently from mouse or keyboard."""

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Treat Enter and Return as the same action as a mouse click."""
        if event.key() in {Qt.Key.Key_Enter, Qt.Key.Key_Return}:
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


class WorkflowProgressChecklist(QFrame):
    """Display ordered workflow completion and emit selected steps."""

    step_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sceneWorkflowProgressChecklist")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._buttons: dict[str, QToolButton] = {}
        self._active_step_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        title = QLabel("Scene creation progress", self)
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("sceneWorkflowProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAccessibleName("Scene creation progress")
        layout.addWidget(self.progress_bar)

        self.steps_layout = QVBoxLayout()
        self.steps_layout.setContentsMargins(0, 2, 0, 2)
        self.steps_layout.setSpacing(2)
        layout.addLayout(self.steps_layout)

        self.next_step_label = QLabel(self)
        self.next_step_label.setObjectName("sceneWorkflowNextStep")
        self.next_step_label.setWordWrap(True)
        self.next_step_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.next_step_label)

    @property
    def active_step_id(self) -> str | None:
        """Return the step currently selected for guided navigation."""
        return self._active_step_id

    def update_states(self, states: Iterable[WorkflowStepState]) -> None:
        """Refresh checklist controls and progress from evaluated states."""
        state_tuple = tuple(states)
        known = {state.step.step_id for state in state_tuple}
        for step_id, button in tuple(self._buttons.items()):
            if step_id not in known:
                self.steps_layout.removeWidget(button)
                button.deleteLater()
                del self._buttons[step_id]

        for state in state_tuple:
            button = self._buttons.get(state.step.step_id)
            if button is None:
                button = _WorkflowStepButton(self)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                button.setAutoRaise(True)
                button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                button.clicked.connect(
                    lambda _checked=False, step_id=state.step.step_id: self.step_requested.emit(
                        step_id
                    )
                )
                self.steps_layout.addWidget(button)
                self._buttons[state.step.step_id] = button
            marker = "✓" if state.completed else "□"
            active = "→ " if state.step.step_id == self._active_step_id else ""
            optional = " (optional)" if state.step.optional else ""
            button.setText(f"{active}{marker} {state.step.label}{optional}")
            button.setProperty(
                "workflowActiveStep",
                state.step.step_id == self._active_step_id,
            )
            button.setAccessibleName(
                f"{'Completed' if state.completed else 'Incomplete'}: {state.step.label}"
            )
            button.setToolTip(state.step.recommendation)
            button.style().unpolish(button)
            button.style().polish(button)

        completed = sum(state.completed for state in state_tuple)
        total = len(state_tuple)
        percentage = round((completed / total) * 100) if total else 100
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{completed} of {total} steps · %p%")

        next_state = next((state for state in state_tuple if not state.completed), None)
        if next_state is None:
            self.next_step_label.setText("Scene complete. Ready to save.")
        else:
            self.next_step_label.setText(f"Next recommended step: {next_state.step.recommendation}")

    def set_active_step(self, step_id: str | None) -> None:
        """Mark the workflow step currently selected for guided navigation."""
        self._active_step_id = step_id
        for current_id, button in self._buttons.items():
            button.setProperty("workflowActiveStep", current_id == step_id)
            button.style().unpolish(button)
            button.style().polish(button)

    def button_for_step(self, step_id: str) -> QToolButton | None:
        """Return the checklist button for a canonical step ID."""
        return self._buttons.get(step_id)
