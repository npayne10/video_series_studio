"""Reusable in-window welcome overlay for VSCS onboarding guides."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OnboardingWelcomeOverlay(QFrame):
    """Dim an editor and present a focused first-run welcome card."""

    start_requested = Signal()
    skip_requested = Signal()

    def __init__(
        self,
        title: str,
        parent: QWidget,
        *,
        estimated_minutes: int = 2,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("onboardingWelcomeOverlay")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#onboardingWelcomeOverlay { background-color: rgba(0, 0, 0, 145); }"
            "#onboardingWelcomeCard { background: palette(base); border: 1px solid "
            "palette(mid); border-radius: 10px; }"
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)

        card = QFrame(self)
        card.setObjectName("onboardingWelcomeCard")
        card.setMinimumWidth(430)
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(12)

        title_label = QLabel(title, card)
        title_label.setObjectName("onboardingWelcomeTitle")
        title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        introduction = QLabel(
            "This short guide introduces the Scene Editor and the recommended "
            "workflow for creating a production-ready scene.",
            card,
        )
        introduction.setObjectName("onboardingWelcomeIntroduction")
        introduction.setWordWrap(True)
        card_layout.addWidget(introduction)

        estimate = QLabel(
            f"Estimated time: about {estimated_minutes} minutes.",
            card,
        )
        estimate.setObjectName("onboardingWelcomeEstimate")
        estimate.setStyleSheet("font-weight: 600;")
        card_layout.addWidget(estimate)

        features = QLabel(
            "• Learn the scene workflow\n"
            "• Understand the adaptive workspace\n"
            "• Discover VKF help and live documentation\n"
            "• Prepare your first scene for saving",
            card,
        )
        features.setObjectName("onboardingWelcomeFeatures")
        features.setWordWrap(True)
        card_layout.addWidget(features)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.skip_button = QPushButton("Skip", card)
        self.skip_button.setObjectName("onboardingWelcomeSkip")
        self.skip_button.setToolTip(
            "Skip this tour and do not show it automatically again."
        )
        self.start_button = QPushButton("Start Guide", card)
        self.start_button.setObjectName("onboardingWelcomeStart")
        self.start_button.setDefault(True)
        self.start_button.setAutoDefault(True)
        self.start_button.setToolTip("Begin the Scene Editor onboarding guide.")
        actions.addWidget(self.skip_button)
        actions.addWidget(self.start_button)
        card_layout.addLayout(actions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(card)
        centered.addStretch(1)
        layout.addLayout(centered)
        layout.addStretch(1)

        self.start_button.clicked.connect(
            lambda _checked=False: self.start_requested.emit()
        )
        self.skip_button.clicked.connect(
            lambda _checked=False: self.skip_requested.emit()
        )
        parent.installEventFilter(self)
        self.hide()

    def show_welcome(self) -> None:
        """Cover the parent and place keyboard focus on Start Guide."""
        self._fit_parent()
        self.show()
        self.raise_()
        self.start_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def dismiss(self) -> None:
        """Hide the overlay without changing onboarding persistence."""
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Keep the overlay aligned to its parent during resize and movement."""
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._fit_parent()
        return super().eventFilter(watched, event)

    def _fit_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
