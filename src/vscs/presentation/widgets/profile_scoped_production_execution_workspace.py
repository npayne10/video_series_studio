"""Phase 20.16.2 profile-scoped behavior for the Production Execution workspace."""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox

from .production_execution_workspace import ProductionExecutionWorkspace


class ProfileScopedProductionExecutionWorkspace(ProductionExecutionWorkspace):
    """Bind execution, retry and telemetry controls to the selected quality profile."""

    def _profile_changed(self, _profile: str) -> None:
        if self._selected_task_id is None:
            return
        self._poll_timer.stop()
        self._execution_active = False
        self._refresh_execution_availability()
        self._refresh_retry_override_status()
        self._refresh_package_status()
        candidate = self._candidates.get(self._selected_task_id)
        if candidate is not None:
            self._render_candidate(candidate)

    def _refresh_execution_availability(self) -> None:
        if self._selected_task_id is None:
            self.status_button.setEnabled(False)
            self._reset_monitor()
            return
        service = self._service_provider()
        if service is None:
            self.status_button.setEnabled(False)
            self._reset_monitor()
            return
        try:
            available = service.has_execution(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception:
            available = False
        self.status_button.setEnabled(available)
        if available:
            self._refresh_telemetry()
        else:
            self._reset_monitor()

    def _refresh_retry_override_status(self) -> None:
        if self._selected_task_id is None:
            self._retry_status = None
            self.retry_button.setEnabled(False)
            self.retry_state.setText("Retry Override: -")
            return
        service = self._service_provider()
        if service is None:
            return
        profile = self.profile.currentText()
        try:
            status = service.retry_override_status(
                self._selected_task_id,
                profile=profile,
            )
        except Exception as exc:
            self._retry_status = None
            self.retry_button.setEnabled(False)
            self.retry_state.setText(f"{profile.title()} Retry: unavailable — {exc}")
            return
        self._retry_status = status
        self.retry_button.setEnabled(status.eligible)
        self.retry_state.setText(
            f"{profile.title()} Retry: {status.state.value.upper()} — profile attempts "
            f"{status.attempts_recorded}/{status.effective_maximum_attempts}. {status.message}"
        )

    def _authorize_retry(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        profile = self.profile.currentText()
        authorized_by, accepted = QInputDialog.getText(
            self,
            f"Authorize Additional {profile.title()} Retry",
            "Authorized by (human operator):",
        )
        if not accepted:
            return
        actor = authorized_by.strip()
        if not actor:
            QMessageBox.warning(
                self,
                "Authorize Additional Retry",
                "Authorizing identity is required.",
            )
            return
        reason, accepted = QInputDialog.getMultiLineText(
            self,
            f"Authorize Additional {profile.title()} Retry",
            f"Reason for exceeding the configured {profile} retry limit:",
        )
        if not accepted:
            return
        justification = reason.strip()
        if not justification:
            QMessageBox.warning(
                self,
                "Authorize Additional Retry",
                "A retry reason is required.",
            )
            return
        try:
            status = service.authorize_retry(
                self._selected_task_id,
                profile=profile,
                authorized_by=actor,
                reason=justification,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Authorize Additional Retry", str(exc))
            self._refresh_retry_override_status()
            return
        self._retry_status = status
        self.summary.setText(status.message)
        self._refresh_retry_override_status()
        self._refresh_execution_availability()
        self._refresh_package_status()

    def _refresh_telemetry(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            snapshot = service.telemetry(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self.monitor_note.setText(f"Telemetry unavailable: {exc}")
            return
        self._render_telemetry(snapshot)
        if snapshot.live and not snapshot.terminal:
            self._execution_active = True
            if not self._poll_timer.isActive():
                self._poll_timer.start()
        elif not snapshot.live:
            self._poll_timer.stop()

    def _start(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        self._execution_active = True
        self._update_start_enabled()
        try:
            result = service.start(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self._execution_active = False
            self._refresh_retry_override_status()
            self._refresh_package_status()
            QMessageBox.warning(self, "Start Production", str(exc))
            return
        self._execution_active = not result.terminal
        self._render_result(result)
        self._refresh_retry_override_status()
        self._update_start_enabled()
        self.status_button.setEnabled(not result.terminal)
        self._refresh_telemetry()

    def _refresh_execution(self, *, show_warning: bool) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            result = service.reconcile(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            if show_warning:
                QMessageBox.warning(self, "Production Execution Status", str(exc))
            else:
                self.monitor_note.setText(f"Automatic monitoring paused: {exc}")
                self._poll_timer.stop()
            return
        self._execution_active = not result.terminal
        self._render_result(result)
        self._refresh_telemetry()
        self._refresh_retry_override_status()
        if show_warning:
            self._refresh_package_status()
        self.status_button.setEnabled(not result.terminal)
        if result.terminal:
            self._poll_timer.stop()
            self._update_start_enabled()
