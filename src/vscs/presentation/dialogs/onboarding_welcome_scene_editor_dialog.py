"""Scene Editor with a persisted first-time onboarding welcome experience."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.beginner_mode_scene_editor_dialog import (
    BeginnerModeSceneEditorDialog,
)
from vscs.presentation.onboarding import (
    SCENE_EDITOR_ONBOARDING,
    OnboardingController,
    OnboardingWelcomeOverlay,
)


class OnboardingWelcomeSceneEditorDialog(BeginnerModeSceneEditorDialog):
    """Introduce first-time users to the Scene Editor onboarding workflow."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        self._welcome_checked = False
        super().__init__(scene, parent, **kwargs)
        self.onboarding = OnboardingController(
            SCENE_EDITOR_ONBOARDING,
            self._workflow_settings,
            self,
        )
        self.welcome_overlay = OnboardingWelcomeOverlay(
            "Welcome to the VSCS Scene Editor",
            self,
            estimated_minutes=2,
        )
        self.welcome_overlay.start_requested.connect(self._start_onboarding)
        self.welcome_overlay.skip_requested.connect(self._skip_onboarding)
        self._install_restart_tour_action()

    def _install_restart_tour_action(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Scene Editor root layout must be a QVBoxLayout.")

        self.restart_tour_button = QPushButton("Start Scene Editor Tour…", self)
        self.restart_tour_button.setObjectName("sceneEditorRestartTour")
        self.restart_tour_button.setToolTip("Replay the Scene Editor welcome and onboarding guide.")
        self.restart_tour_button.setAccessibleName("Start Scene Editor Tour")
        self.restart_tour_button.clicked.connect(self.restart_onboarding)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.restart_tour_button)
        row.addStretch(1)

        workspace_index = root.indexOf(self.workspace_splitter)
        if workspace_index < 0:
            raise RuntimeError("Scene Editor workspace is unavailable.")
        root.insertLayout(workspace_index, row)

    def _show_welcome_if_required(self) -> None:
        if self._welcome_checked:
            return
        self._welcome_checked = True
        if self.beginner_mode.enabled and self.onboarding.should_start_automatically:
            self.welcome_overlay.show_welcome()

    def _start_onboarding(self) -> None:
        if not self.onboarding.state.active:
            self.onboarding.start(force=True)
        self.welcome_overlay.dismiss()
        if self.beginner_mode.enabled:
            self.workflow_panel.setVisible(True)
            self.workflow_panel.set_collapsed(False)

    def _skip_onboarding(self) -> None:
        if not self.onboarding.state.active:
            self.onboarding.start(force=True)
        self.onboarding.skip()
        self.welcome_overlay.dismiss()

    def restart_onboarding(self) -> None:
        """Restart the current guide version and display its welcome experience."""
        self.onboarding.restart()
        self.welcome_overlay.show_welcome()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Display first-run onboarding only after the editor has valid geometry."""
        super().showEvent(event)
        QTimer.singleShot(0, self._show_welcome_if_required)
