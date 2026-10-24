"""Automated MiniMax H3 execution wiring for Phase 20.18.2.3.6.4f.4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from vscs.application.acpp.reference_roles import ReferencePriority, ReferenceRole
from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.production_execution.provider_policy_profiles import (
    ProviderPolicyProfile,
)
from vscs.application.production_package import ProductionPackageService
from vscs.application.production_tasks import ProductionTask
from vscs.application.provider_reference_capacity import project_provider_reference_capacity
from vscs.infrastructure.production import JsonProductionTaskRepository

from .h3_persisted_authority_gate import verify_persisted_h3_reference_authority
from .h3_reference_selection_governance import H3ReferenceGovernanceError
from .minimax_h3_comfyui_provider import (
    LiveMiniMaxH3ComfyUISpanProvider,
    MiniMaxH3ComfyUICompiledJob,
    MiniMaxH3ComfyUIProviderError,
    MiniMaxH3ComfyUIWorkflowCompiler,
)
from .minimax_h3_span_adapter import (
    MiniMaxH3SpanAdapterCompiler,
    MiniMaxH3SpanAdapterError,
    MiniMaxH3SpanExecution,
    MiniMaxH3SpanExecutionPlan,
)
from .minimax_h3_span_orchestration import (
    GovernedMiniMaxH3SpanOrchestrationService,
    MiniMaxH3SpanOrchestrationError,
    MiniMaxH3SpanOrchestrationResult,
)
from .package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)
from .provider_policy_profiles import (
    MINIMAX_H3_EXECUTION_ADAPTER_ID,
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)


@dataclass(frozen=True, slots=True)
class _H3ReadinessReference:
    reference_id: str
    role: ReferenceRole
    priority: ReferencePriority
    provider_ready: bool


if TYPE_CHECKING:
    from vscs.application.projects import ProjectService
    from vscs.application.story.planning_integration import GovernedPlanningIntegrationService


class MiniMaxH3AutomatedExecutionError(RuntimeError):
    """Raised when governed H3 automated execution cannot proceed safely."""


class _CurrentPackageCompiler(Protocol):
    def compile_current(
        self,
        task: ProductionTask,
        *,
        profile: str = "production",
    ) -> CompiledProductionPackage: ...


class _H3PlanCompiler(Protocol):
    def compile(self, compiled: CompiledProductionPackage) -> MiniMaxH3SpanExecutionPlan: ...


class _H3WorkflowCompiler(Protocol):
    def compile(
        self,
        execution: MiniMaxH3SpanExecution,
    ) -> MiniMaxH3ComfyUICompiledJob: ...


class _H3Orchestrator(Protocol):
    def run(
        self,
        compiled: CompiledProductionPackage,
        *,
        output_path: Path | None = None,
    ) -> MiniMaxH3SpanOrchestrationResult: ...


@dataclass(frozen=True, slots=True)
class MiniMaxH3AutomatedExecutionPreflight:
    """Fail-closed evidence that every H3 span is ready for provider submission."""

    task_id: str
    shot_id: str
    package_fingerprint: str
    plan_id: str
    plan_fingerprint: str
    span_job_ids: tuple[str, ...]
    prompt_fingerprints: tuple[str, ...]
    reference_slot_fingerprints: tuple[str, ...]
    prompt_validation_fingerprints: tuple[str, ...]
    workflow_fingerprints: tuple[str, ...]
    model_config_fingerprints: tuple[str, ...]
    provider_profile_id: str
    provider_profile_fingerprint: str
    execution_adapter_id: str
    provider_id: str = "minimax-h3-ref2va"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "task_id",
            "shot_id",
            "package_fingerprint",
            "plan_id",
            "plan_fingerprint",
            "provider_profile_id",
            "provider_profile_fingerprint",
            "execution_adapter_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise MiniMaxH3AutomatedExecutionError(
                    f"H3 automated preflight requires {field_name}"
                )
            object.__setattr__(self, field_name, value)
        if self.schema_version != "1.0":
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated preflight requires schema version 1.0"
            )
        counts = {
            len(self.span_job_ids),
            len(self.prompt_fingerprints),
            len(self.reference_slot_fingerprints),
            len(self.prompt_validation_fingerprints),
            len(self.workflow_fingerprints),
            len(self.model_config_fingerprints),
        }
        if counts == {0} or len(counts) != 1:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated preflight requires one complete evidence row per span"
            )

    @property
    def span_count(self) -> int:
        return len(self.span_job_ids)


class MiniMaxH3AutomatedExecutionService:
    """Wire governed package authority through validation into live H3 execution."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_input_directory: Path,
        comfyui_output_directory: Path,
        workflow_path: Path | None = None,
        task_repository: JsonProductionTaskRepository | None = None,
        package_compiler: _CurrentPackageCompiler | None = None,
        plan_compiler: _H3PlanCompiler | None = None,
        workflow_compiler: _H3WorkflowCompiler | None = None,
        orchestrator: _H3Orchestrator | None = None,
        policy_profile: ProviderPolicyProfile | None = None,
        execution_profile: str = "production",
        authority_packages: ProductionPackageService | None = None,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.endpoint = endpoint.strip().rstrip("/")
        self.execution_profile = execution_profile.strip().lower() or "production"
        if self.execution_profile not in {"preview", "production", "master"}:
            raise MiniMaxH3AutomatedExecutionError(
                f"Unsupported H3 execution profile: {execution_profile!r}"
            )
        self.comfyui_input_directory = (
            Path(comfyui_input_directory).expanduser().resolve(strict=False)
        )
        self.comfyui_output_directory = (
            Path(comfyui_output_directory).expanduser().resolve(strict=False)
        )
        if not self.endpoint:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution requires a ComfyUI endpoint"
            )
        if not self.comfyui_input_directory.is_dir():
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution requires the configured ComfyUI input directory"
            )
        if not self.comfyui_output_directory.is_dir():
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution requires the configured ComfyUI output directory"
            )

        self.policy_profile = policy_profile or default_provider_policy_profile_registry().require(
            MINIMAX_H3_POLICY_PROFILE_ID
        )
        self._require_h3_policy_profile(self.policy_profile)

        default_workflow = (
            Path(__file__).resolve().parents[4]
            / "resources"
            / "workflows"
            / "manual"
            / "minimax_h3_ref2va_sht002_baseline_api.json"
        )
        self.workflow_path = (
            Path(workflow_path).expanduser().resolve(strict=False)
            if workflow_path is not None
            else default_workflow.resolve(strict=False)
        )
        if not self.workflow_path.is_file():
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution workflow is unavailable: {self.workflow_path}"
            )

        self.task_repository = task_repository or JsonProductionTaskRepository(
            self.project_directory / "production" / "scheduling" / "tasks"
        )
        self.package_compiler = package_compiler or LocalProductionPackageCompilationService(
            self.project_directory
        )
        self.plan_compiler = plan_compiler or MiniMaxH3SpanAdapterCompiler(self.project_directory)
        self.workflow_compiler = workflow_compiler or MiniMaxH3ComfyUIWorkflowCompiler(
            self.project_directory,
            comfyui_input_directory=self.comfyui_input_directory,
            workflow_path=self.workflow_path,
        )

        if orchestrator is None:
            live_provider = LiveMiniMaxH3ComfyUISpanProvider(
                self.project_directory,
                endpoint=self.endpoint,
                comfyui_input_directory=self.comfyui_input_directory,
                comfyui_output_directory=self.comfyui_output_directory,
                workflow_path=self.workflow_path,
            )
            orchestrator = GovernedMiniMaxH3SpanOrchestrationService(
                self.project_directory,
                provider=live_provider,
            )
        self.orchestrator = orchestrator
        self.authority_packages = authority_packages

    @classmethod
    def from_project_services(
        cls,
        projects: ProjectService,
        planning: GovernedPlanningIntegrationService,
        *,
        endpoint: str,
        comfyui_input_directory: Path,
        comfyui_output_directory: Path,
        workflow_path: Path | None = None,
        execution_profile: str = "production",
    ) -> MiniMaxH3AutomatedExecutionService:
        """Wire the live H3 caller to genuine VSCS project/planning authority.

        The project and planning services must refer to the same open project.
        Never infer a current source from the compiled package alone.
        """
        project_directory = projects.project_directory
        if project_directory is None:
            raise MiniMaxH3AutomatedExecutionError("H3 execution requires an open VSCS project")
        if planning.projects is not projects:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 planning authority does not belong to the open VSCS project service"
            )
        packages = ProductionPackageService(projects, planning)
        return cls(
            project_directory,
            endpoint=endpoint,
            comfyui_input_directory=comfyui_input_directory,
            comfyui_output_directory=comfyui_output_directory,
            workflow_path=workflow_path,
            authority_packages=packages,
            execution_profile=execution_profile,
        )

    def preflight(self, task_id: str) -> MiniMaxH3AutomatedExecutionPreflight:
        compiled = self._compiled_for_task(task_id)
        return self._preflight_compiled(compiled)

    def dry_run(self, task_id: str) -> MiniMaxH3AutomatedExecutionPreflight:
        """Validate live H3 compilation and authority without provider submission."""
        return self.preflight(task_id)

    def execute(
        self,
        task_id: str,
        *,
        output_path: Path | None = None,
        operator_authorized: bool = False,
        expected_preflight_fingerprint: str | None = None,
    ) -> MiniMaxH3SpanOrchestrationResult:
        """Explicit operator-gated H3 execution; never accept implied authorization."""
        if not operator_authorized or not expected_preflight_fingerprint:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 provider execution requires explicit operator authorization "
                "and a matching current preflight fingerprint"
            )
        compiled = self._compiled_for_task(task_id)
        first = self._preflight_compiled(compiled)
        if first.plan_fingerprint != expected_preflight_fingerprint:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 provider execution blocked: authorized preflight plan fingerprint changed"
            )
        # Re-read the current persisted task/package immediately before handing
        # control to the orchestrator; no stale cached preflight may be replayed.
        second_compiled = self._compiled_for_task(task_id)
        second = self._preflight_compiled(second_compiled)
        if (
            second.package_fingerprint != first.package_fingerprint
            or second.plan_fingerprint != first.plan_fingerprint
            or second.workflow_fingerprints != first.workflow_fingerprints
            or second.provider_profile_fingerprint != first.provider_profile_fingerprint
        ):
            raise MiniMaxH3AutomatedExecutionError(
                "H3 provider execution blocked: authority or provider payload changed"
            )
        real_orchestrator = isinstance(
            self.orchestrator, GovernedMiniMaxH3SpanOrchestrationService
        )
        if real_orchestrator:
            provider = self.orchestrator.provider
            if not isinstance(provider, LiveMiniMaxH3ComfyUISpanProvider):
                raise MiniMaxH3AutomatedExecutionError(
                    "Live H3 execution requires the authenticated ComfyUI provider"
                )
            try:
                provider.probe_readiness()
            except MiniMaxH3ComfyUIProviderError as exc:
                raise MiniMaxH3AutomatedExecutionError(
                    f"H3 provider readiness blocked: {exc}"
                ) from exc

            def verify_span(current_package, current_plan, execution):
                refreshed = self._compiled_for_task(task_id)
                report = self._preflight_compiled(refreshed)
                if (
                    refreshed.package_fingerprint != second_compiled.package_fingerprint
                    or report.plan_fingerprint != second.plan_fingerprint
                    or report.workflow_fingerprints != second.workflow_fingerprints
                    or report.provider_profile_fingerprint != second.provider_profile_fingerprint
                    or current_package.package_fingerprint != second_compiled.package_fingerprint
                    or current_plan.fingerprint != second.plan_fingerprint
                    or execution.job_id not in second.span_job_ids
                ):
                    raise MiniMaxH3AutomatedExecutionError(
                        "H3 submission blocked: per-span persisted authority or payload changed"
                    )
            setattr(self.orchestrator, "submission_guard", verify_span)
        try:
            return self.orchestrator.run(second_compiled, output_path=output_path)
        except MiniMaxH3SpanOrchestrationError as exc:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution failed safely: {exc}"
            ) from exc
        finally:
            if real_orchestrator:
                setattr(self.orchestrator, "submission_guard", None)

    def _compiled_for_task(self, task_id: str) -> CompiledProductionPackage:
        normalized = task_id.strip()
        if not normalized:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution requires a ProductionTask identity"
            )
        task = self.task_repository.get(normalized)
        if task is None:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution cannot find ProductionTask {normalized}"
            )
        try:
            compiled = self.package_compiler.compile_current(
                task,
                profile=self.execution_profile,
            )
        except LocalProductionPackageCompilationError as exc:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution requires current compiled authority: {exc}"
            ) from exc
        if compiled.task_id != normalized:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution compiled the wrong ProductionTask authority"
            )
        return compiled

    def _preflight_compiled(
        self,
        compiled: CompiledProductionPackage,
    ) -> MiniMaxH3AutomatedExecutionPreflight:
        try:
            plan = self.plan_compiler.compile(compiled)
        except MiniMaxH3SpanAdapterError as exc:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution governance/validation failed: {exc}"
            ) from exc

        # Provider submission is forbidden until the current persisted planning
        # authority has been reloaded and independently recompiled for EVERY span.
        if self.authority_packages is None:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 execution requires an authenticated current planning/package authority service"
            )
        if not isinstance(compiled.reference_plan, dict):
            raise MiniMaxH3AutomatedExecutionError(
                "H3 execution requires a governed ReferencePlan for freshness verification"
            )
        by_reference_id = {
            str(item.get("reference_id")): item
            for item in compiled.reference_plan.get("references", [])
            if isinstance(item, dict)
        }
        for execution in plan.spans:
            try:
                records = []
                selected_ids = tuple(slot.reference_id for slot in execution.reference_slots)
                for reference_id in (*selected_ids, *execution.deferred_reference_ids):
                    raw = by_reference_id[reference_id]
                    records.append(
                        _H3ReadinessReference(
                            reference_id=reference_id,
                            role=ReferenceRole(str(raw["role"])),
                            priority=ReferencePriority(str(raw["priority"])),
                            provider_ready=raw.get("provider_ready") is True,
                        )
                    )
                projection = project_provider_reference_capacity(self.policy_profile, records)
                if (
                    not projection.passed
                    or projection.selected_reference_ids
                    != tuple(slot.reference_id for slot in execution.reference_slots)
                    or projection.deferred_preferred_reference_ids
                    != execution.deferred_reference_ids
                ):
                    raise H3ReferenceGovernanceError(
                        "H3 provider reference selection differs from current governed policy"
                    )
                verify_persisted_h3_reference_authority(
                    reference_root=self.project_directory,
                    tasks=self.task_repository,
                    packages=self.authority_packages,
                    original=compiled,
                    execution=execution,
                    projection=projection,
                )
            except (H3ReferenceGovernanceError, KeyError, TypeError, ValueError) as exc:
                raise MiniMaxH3AutomatedExecutionError(
                    f"H3 execution freshness authority is blocked: {exc}"
                ) from exc

        jobs: list[MiniMaxH3ComfyUICompiledJob] = []
        try:
            for execution in plan.spans:
                jobs.append(self.workflow_compiler.compile(execution))
        except MiniMaxH3ComfyUIProviderError as exc:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution provider payload preflight failed: {exc}"
            ) from exc

        if plan.provider_id != self.policy_profile.provider_id:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution plan provider does not match selected policy profile"
            )
        if plan.provider_profile_id != self.policy_profile.profile_id:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution plan profile identity does not match selected policy profile"
            )
        if plan.provider_profile_fingerprint != self.policy_profile.fingerprint:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution plan profile fingerprint is stale"
            )
        if plan.execution_adapter_id != self.policy_profile.execution_adapter_id:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution plan adapter does not match selected policy profile"
            )
        if any(
            execution.provider_id != self.policy_profile.provider_id for execution in plan.spans
        ):
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution span provider does not match selected policy profile"
            )

        return MiniMaxH3AutomatedExecutionPreflight(
            task_id=compiled.task_id,
            shot_id=compiled.shot_id,
            package_fingerprint=compiled.package_fingerprint,
            plan_id=plan.plan_id,
            plan_fingerprint=plan.fingerprint,
            span_job_ids=tuple(execution.job_id for execution in plan.spans),
            prompt_fingerprints=tuple(execution.prompt_fingerprint for execution in plan.spans),
            reference_slot_fingerprints=tuple(
                execution.reference_slot_fingerprint for execution in plan.spans
            ),
            prompt_validation_fingerprints=tuple(
                execution.prompt_validation_fingerprint for execution in plan.spans
            ),
            workflow_fingerprints=tuple(job.workflow_fingerprint for job in jobs),
            model_config_fingerprints=tuple(job.model_config_fingerprint for job in jobs),
            provider_profile_id=self.policy_profile.profile_id,
            provider_profile_fingerprint=self.policy_profile.fingerprint,
            execution_adapter_id=self.policy_profile.execution_adapter_id,
            provider_id=self.policy_profile.provider_id,
        )

    @staticmethod
    def _require_h3_policy_profile(profile: ProviderPolicyProfile) -> None:
        if not profile.enabled:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 provider policy profile is disabled: {profile.profile_id}"
            )
        expected = {
            "provider_id": "minimax-h3-ref2va",
            "model_family": "MiniMax H3",
            "prompt_policy_id": "learned_span_local_v1",
            "validation_policy_id": "h3-001-through-h3-008-v1",
            "execution_adapter_id": MINIMAX_H3_EXECUTION_ADAPTER_ID,
            "guide_semantics": "frame_state_anchor",
            "native_frame_rule": "17k+5",
            "reference_projection_mode": "direct_span_scoped_canonical_refs",
        }
        for field_name, expected_value in expected.items():
            if getattr(profile, field_name) != expected_value:
                raise MiniMaxH3AutomatedExecutionError(
                    "Selected provider policy profile is incompatible with H3 automated "
                    f"execution: {field_name}={getattr(profile, field_name)!r}"
                )
        if profile.temporal_asset_gate:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 frame-state guides cannot be configured as temporal asset gates"
            )
        if profile.max_reference_images != 5:
            raise MiniMaxH3AutomatedExecutionError(
                "H3 automated execution requires a five-reference policy limit"
            )
