"""Reusable spotlight overlay and navigation card for onboarding tours."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .onboarding_controller import OnboardingState


class GuidedTourOverlay(QWidget):
    """Dim an editor, spotlight one target and present onboarding navigation."""

    previous_requested = Signal()
    next_requested = Signal()
    skip_requested = Signal()
    try_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("guidedTourOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Guided interface tour")
        self._spotlight = QRect()

        self.card = QFrame(self)
        self.card.setObjectName("guidedTourCard")
        self.card.setMinimumWidth(390)
        self.card.setMaximumWidth(500)
        self.card.setStyleSheet(
            "#guidedTourCard { background: palette(base); border: 1px solid "
            "palette(mid); border-radius: 10px; }"
        )
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        self.progress_label = QLabel(self.card)
        self.progress_label.setObjectName("guidedTourProgressLabel")
        self.progress_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar(self.card)
        self.progress_bar.setObjectName("guidedTourProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.title_label = QLabel(self.card)
        self.title_label.setObjectName("guidedTourTitle")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.description_label = QLabel(self.card)
        self.description_label.setObjectName("guidedTourDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.action_hint_label = QLabel(self.card)
        self.action_hint_label.setObjectName("guidedTourActionHint")
        self.action_hint_label.setWordWrap(True)
        self.action_hint_label.setStyleSheet("font-weight: 600;")
        self.action_hint_label.hide()
        layout.addWidget(self.action_hint_label)

        actions = QHBoxLayout()
        self.skip_button = QPushButton("Skip Tour", self.card)
        self.skip_button.setObjectName("guidedTourSkip")
        self.try_button = QPushButton("Try It", self.card)
        self.try_button.setObjectName("guidedTourTry")
        self.try_button.hide()
        self.previous_button = QPushButton("Previous", self.card)
        self.previous_button.setObjectName("guidedTourPrevious")
        self.next_button = QPushButton("Next", self.card)
        self.next_button.setObjectName("guidedTourNext")
        self.next_button.setDefault(True)
        self.next_button.setAutoDefault(True)
        actions.addWidget(self.skip_button)
        actions.addWidget(self.try_button)
        actions.addStretch(1)
        actions.addWidget(self.previous_button)
        actions.addWidget(self.next_button)
        layout.addLayout(actions)

        self.previous_button.clicked.connect(self.previous_requested.emit)
        self.next_button.clicked.connect(self.next_requested.emit)
        self.skip_button.clicked.connect(self.skip_requested.emit)
        self.try_button.clicked.connect(self.try_requested.emit)
        parent.installEventFilter(self)
        self.hide()

    @property
    def spotlight_rect(self) -> QRect:
        """Return the current spotlight rectangle in overlay coordinates."""
        return QRect(self._spotlight)

    def show_state(self, state: OnboardingState, target: QWidget | None) -> None:
        """Render an active onboarding state and optional spotlight target."""
        step = state.current_step
        if step is None:
            self.hide_tour()
            return
        self.progress_label.setText(
            f"Step {state.current_index + 1} of {state.total_steps}"
        )
        self.progress_bar.setValue(state.progress_percent)
        self.title_label.setText(step.title)
        self.description_label.setText(step.description)
        self.previous_button.setEnabled(state.can_go_previous)
        self.next_button.setText("Finish" if state.is_final_step else "Next")
        self.configure_action(required=False, ready=True, hint="")
        self._fit_parent()
        self._set_spotlight(target)
        self._position_card()
        self.show()
        self.raise_()
        self.next_button.setFocus(Qt.FocusReason.OtherFocusReason)
        self.update()

    def configure_action(self, *, required: bool, ready: bool, hint: str) -> None:
        """Configure an optional user action required before advancing."""
        blocked = required and not ready
        self.next_button.setEnabled(not blocked)
        self.try_button.setVisible(blocked)
        self.action_hint_label.setVisible(bool(hint))
        self.action_hint_label.setText(hint)
        if blocked:
            self.try_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def hide_tour(self) -> None:
        """Hide the guided tour and clear its spotlight."""
        self._spotlight = QRect()
        self.hide()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Dim everything except the current spotlight rectangle."""
        del event
        painter = QPainter(self)
        dim = QColor(0, 0, 0, 150)
        if self._spotlight.isNull():
            painter.fillRect(self.rect(), dim)
            return

        hole = self._spotlight.intersected(self.rect())
        painter.fillRect(QRect(0, 0, self.width(), hole.top()), dim)
        painter.fillRect(
            QRect(
                0,
                hole.bottom() + 1,
                self.width(),
                self.height() - hole.bottom(),
            ),
            dim,
        )
        painter.fillRect(QRect(0, hole.top(), hole.left(), hole.height()), dim)
        painter.fillRect(
            QRect(
                hole.right() + 1,
                hole.top(),
                self.width() - hole.right(),
                hole.height(),
            ),
            dim,
        )
        painter.setPen(QPen(self.palette().highlight().color(), 3))
        painter.drawRoundedRect(hole, 6, 6)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Keep the overlay and card aligned when the parent changes size."""
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._fit_parent()
            self._position_card()
        return super().eventFilter(watched, event)

    def _set_spotlight(self, target: QWidget | None) -> None:
        if target is None or not target.isVisible():
            self._spotlight = QRect()
            return
        top_left = target.mapTo(self, target.rect().topLeft())
        self._spotlight = QRect(top_left, target.size()).adjusted(-8, -8, 8, 8)

    def _fit_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def _position_card(self) -> None:
        self.card.adjustSize()
        margin = 24
        x = max(margin, self.width() - self.card.width() - margin)
        y = margin
        card_rect = QRect(x, y, self.card.width(), self.card.height())
        if not self._spotlight.isNull() and self._spotlight.intersects(card_rect):
            y = max(margin, self.height() - self.card.height() - margin)
        self.card.move(x, y)
