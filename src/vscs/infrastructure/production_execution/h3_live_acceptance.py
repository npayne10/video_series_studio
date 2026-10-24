"""Q3.1.3.5.8a: fail-closed disposable H3 acceptance scope and one-use authorization.

This module NEVER submits a provider request. Live execution is introduced only
after separate output/evidence acceptance and explicit operator-run approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Protocol, Any

from .minimax_h3_automated_execution import MiniMaxH3AutomatedExecutionPreflight

if TYPE_CHECKING:
    from .h3_live_acceptance_evidence import H3ValidatedOutput


class H3IsolatedAcceptanceError(RuntimeError):
    """The proposed H3 acceptance scope or authorization is unsafe."""


class _H3ReadinessService(Protocol):
    project_directory: Path

    def dry_run(self, task_id: str) -> MiniMaxH3AutomatedExecutionPreflight: ...


@dataclass(frozen=True, slots=True)
class H3IsolatedAcceptancePreparation:
    task_id: str
    project_root: Path
    output_root: Path
    report: MiniMaxH3AutomatedExecutionPreflight

    @property
    def plan_fingerprint(self) -> str:
        return self.report.plan_fingerprint


class H3IsolatedAcceptanceCoordinator:
    """Non-submitting preparation and one-use operator approval boundary.

    The repository cannot be imported or executed against an arbitrary VSCS
    project: it must be under an explicitly supplied acceptance root. The root
    itself is not an eligible project. Both are resolved before comparing.
    """

    def __init__(
        self,
        service: _H3ReadinessService,
        *,
        acceptance_root: Path,
        project_root: Path,
        output_root: Path,
    ) -> None:
        root = Path(acceptance_root).expanduser().resolve(strict=False)
        project = Path(project_root).expanduser().resolve(strict=False)
        output = Path(output_root).expanduser().resolve(strict=False)
        service_project = Path(service.project_directory).expanduser().resolve(strict=False)
        if not root.is_dir() or not project.is_dir():
            raise H3IsolatedAcceptanceError("Acceptance root and disposable project must exist")
        marker = root / ".vscs_h3_disposable_acceptance"
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != "Q3.1.3.5.8":
            raise H3IsolatedAcceptanceError("Acceptance root lacks the explicit disposable marker")
        if project == root or not project.is_relative_to(root):
            raise H3IsolatedAcceptanceError(
                "H3 acceptance project must be a child of the designated disposable root"
            )
        if project != service_project:
            raise H3IsolatedAcceptanceError(
                "H3 execution service is not bound to the disposable acceptance project"
            )
        if output == project or not output.is_relative_to(project):
            raise H3IsolatedAcceptanceError(
                "H3 acceptance output must be confined beneath the disposable project"
            )
        if not output.is_dir():
            raise H3IsolatedAcceptanceError("H3 acceptance output directory must exist")
        self.service = service
        self.project_root = project
        self.output_root = output
        self._pending: tuple[str, H3IsolatedAcceptancePreparation] | None = None

    def prepare(self, task_id: str) -> H3IsolatedAcceptancePreparation:
        """Exercise real readiness with NO provider request or approvals."""
        self._pending = None
        normalized = task_id.strip()
        if not normalized:
            raise H3IsolatedAcceptanceError("H3 acceptance requires a task ID")
        report = self.service.dry_run(normalized)
        if report.task_id != normalized or report.span_count != 1:
            raise H3IsolatedAcceptanceError(
                "H3 acceptance requires exactly one governed span for the selected task"
            )
        return H3IsolatedAcceptancePreparation(
            task_id=normalized,
            project_root=self.project_root,
            output_root=self.output_root,
            report=report,
        )

    def authorize_once(
        self,
        prepared: H3IsolatedAcceptancePreparation,
        *,
        operator_confirmed: bool,
        expected_plan_fingerprint: str,
    ) -> str:
        """Produce an ephemeral single-use capability; DOES NOT submit."""
        self._pending = None
        if not operator_confirmed:
            raise H3IsolatedAcceptanceError("Explicit H3 operator authorization is required")
        if (
            prepared.project_root != self.project_root
            or prepared.output_root != self.output_root
            or prepared.report.task_id != prepared.task_id
            or expected_plan_fingerprint != prepared.plan_fingerprint
        ):
            raise H3IsolatedAcceptanceError("H3 acceptance scope or fingerprint changed")
        token = token_urlsafe(32)
        self._pending = (token, prepared)
        return token

    def consume_authorization(self, token: str) -> H3IsolatedAcceptancePreparation:
        """One-use authorization check and second fresh dry-run, still NO submit."""
        pending, self._pending = self._pending, None
        if pending is None or not token or token != pending[0]:
            raise H3IsolatedAcceptanceError("H3 authorization is missing, invalid or consumed")
        prepared = pending[1]
        refreshed = self.service.dry_run(prepared.task_id)
        if refreshed != prepared.report:
            raise H3IsolatedAcceptanceError("H3 authorization is stale after fresh preflight")
        return prepared

    def validate_completed_output(
        self,
        prepared: H3IsolatedAcceptancePreparation,
        *,
        output_path: Path,
        expected_frames: int,
        expected_fps: int,
        evidence_root: Path,
        run_id: str,
        provider_evidence: dict[str, object],
    ) -> tuple[H3ValidatedOutput, Path]:
        """Offline integration acceptance; NO provider submission or QC transition.

        Bind provider proof to the exact prepared span before writing results.
        Caller must supply separately obtained actual provider execution evidence.
        """
        from .h3_live_acceptance_evidence import (
            validate_h3_acceptance_output,
            write_h3_acceptance_evidence,
        )

        if (
            prepared.project_root != self.project_root
            or prepared.output_root != self.output_root
            or prepared.report.span_count != 1
        ):
            raise H3IsolatedAcceptanceError("H3 acceptance preparation does not match scope")
        if (
            provider_evidence.get("job_id") != prepared.report.span_job_ids[0]
            or provider_evidence.get("workflow_fingerprint")
            != prepared.report.workflow_fingerprints[0]
            or provider_evidence.get("model_config_fingerprint")
            != prepared.report.model_config_fingerprints[0]
            or not str(provider_evidence.get("prompt_id") or "").strip()
        ):
            raise H3IsolatedAcceptanceError("H3 provider evidence does not match authorized span")
        validated = validate_h3_acceptance_output(
            output_path,
            allowed_root=self.output_root,
            expected_frames=expected_frames,
            expected_fps=expected_fps,
        )
        report_path = write_h3_acceptance_evidence(
            evidence_root=evidence_root,
            acceptance_project=self.project_root,
            run_id=run_id,
            task_id=prepared.task_id,
            shot_id=prepared.report.shot_id,
            plan_fingerprint=prepared.plan_fingerprint,
            output=validated,
            provider_evidence=provider_evidence,
        )
        return validated, report_path


    def execute_single_authorized_run(
        self,
        token: str,
        *,
        run_id: str,
        evidence_root: Path,
        expected_frames: int,
        expected_fps: int,
    ) -> tuple[H3ValidatedOutput, Path]:
        """Operator-triggered ONE live attempt using the existing guarded executor.

        Never call from an automated test with a real provider. The token is
        consumed before invoking execution; even failed attempts cannot retry.
        """
        from .h3_live_acceptance_evidence import validate_h3_acceptance_output
        from .minimax_h3_span_orchestration import GovernedMiniMaxH3SpanOrchestrationService

        prepared = self.consume_authorization(token)
        if not prepared.report.span_job_ids or len(prepared.report.span_job_ids) != 1:
            raise H3IsolatedAcceptanceError("H3 live acceptance requires exactly one span")
        orchestrator = getattr(self.service, "orchestrator", None)
        if not isinstance(orchestrator, GovernedMiniMaxH3SpanOrchestrationService):
            raise H3IsolatedAcceptanceError("H3 live acceptance requires governed orchestration")
        provider = getattr(orchestrator, "provider", None)
        from .minimax_h3_comfyui_provider import LiveMiniMaxH3ComfyUISpanProvider

        if not isinstance(provider, LiveMiniMaxH3ComfyUISpanProvider):
            raise H3IsolatedAcceptanceError("H3 live acceptance requires the genuine ComfyUI provider")
        # Never allow a previous run to be overwritten or silently reused.
        final = self.output_root / f"{run_id}.mp4"
        safe_id = run_id.replace("-", "").replace("_", "")
        if not run_id or not safe_id.isascii() or not safe_id.isalnum():
            raise H3IsolatedAcceptanceError("H3 live acceptance requires a safe ASCII run ID")
        if final.exists() or (Path(evidence_root) / f"{run_id}.json").exists():
            raise H3IsolatedAcceptanceError("H3 acceptance run ID already has artifacts")
        if Path(provider.project_directory).resolve() != self.project_root:
            raise H3IsolatedAcceptanceError("H3 provider is not bound to the disposable project")
        execute = getattr(self.service, "execute", None)
        if not callable(execute):
            raise H3IsolatedAcceptanceError("H3 live acceptance executor is unavailable")
        result: Any = execute(
            prepared.task_id,
            output_path=final,
            operator_authorized=True,
            expected_preflight_fingerprint=prepared.plan_fingerprint,
        )
        if result.task_id != prepared.task_id or result.shot_id != prepared.report.shot_id:
            raise H3IsolatedAcceptanceError("H3 live execution returned the wrong shot identity")
        if result.plan_fingerprint != prepared.plan_fingerprint or result.final_path.resolve() != final.resolve():
            raise H3IsolatedAcceptanceError("H3 live execution result is not the authorized plan/output")
        if len(result.raw_span_paths) != 1:
            raise H3IsolatedAcceptanceError("H3 live execution produced an unexpected span count")
        # Read genuine persisted provider evidence, not caller-supplied assertions.
        provider_path = provider.evidence_root / f"{prepared.report.span_job_ids[0]}.json"
        if not provider_path.is_file():
            raise H3IsolatedAcceptanceError("H3 provider execution evidence is absent")
        import json

        try:
            provider_evidence = json.loads(provider_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise H3IsolatedAcceptanceError("H3 provider evidence cannot be decoded") from exc
        if not isinstance(provider_evidence, dict):
            raise H3IsolatedAcceptanceError("H3 provider evidence is invalid")
        if Path(str(provider_evidence.get("output_path", ""))).resolve() != result.raw_span_paths[0].resolve():
            raise H3IsolatedAcceptanceError("H3 provider evidence output does not match the returned raw span")
        if (
            provider_evidence.get("job_id") != prepared.report.span_job_ids[0]
            or provider_evidence.get("workflow_fingerprint") != prepared.report.workflow_fingerprints[0]
            or provider_evidence.get("model_config_fingerprint") != prepared.report.model_config_fingerprints[0]
            or not str(provider_evidence.get("prompt_id") or "").strip()
        ):
            raise H3IsolatedAcceptanceError("H3 live provider evidence does not match prepared authority")
        import hashlib

        with result.raw_span_paths[0].open("rb") as handle:
            raw_sha = hashlib.file_digest(handle, "sha256").hexdigest()
        if provider_evidence.get("output_sha256") != raw_sha:
            raise H3IsolatedAcceptanceError("H3 raw provider output digest changed")
        # The offline validator checks the produced final media independently.
        validate_h3_acceptance_output(
            result.final_path,
            allowed_root=self.output_root,
            expected_frames=expected_frames,
            expected_fps=expected_fps,
        )
        return self.validate_completed_output(
            prepared,
            output_path=result.final_path,
            expected_frames=expected_frames,
            expected_fps=expected_fps,
            evidence_root=evidence_root,
            run_id=run_id,
            provider_evidence=provider_evidence,
        )
