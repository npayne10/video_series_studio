"""Automated MiniMax H3 execution wiring for Phase 20.18.2.3.6.4f.4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.production_tasks import ProductionTask
from vscs.infrastructure.production import JsonProductionTaskRepository

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


class MiniMaxH3AutomatedExecutionError(RuntimeError):
    """Raised when governed H3 automated execution cannot proceed safely."""


class _CurrentPackageCompiler(Protocol):
    def compile_current(self, task: ProductionTask) -> CompiledProductionPackage: ...


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
    workflow_fingerprints: tuple[str, ...]
    model_config_fingerprints: tuple[str, ...]
    provider_id: str = "minimax-h3-ref2va"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "task_id",
            "shot_id",
            "package_fingerprint",
            "plan_id",
            "plan_fingerprint",
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
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.endpoint = endpoint.strip().rstrip("/")
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
        self.plan_compiler = plan_compiler or MiniMaxH3SpanAdapterCompiler(
            self.project_directory
        )
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

    def preflight(self, task_id: str) -> MiniMaxH3AutomatedExecutionPreflight:
        compiled = self._compiled_for_task(task_id)
        return self._preflight_compiled(compiled)

    def execute(
        self,
        task_id: str,
        *,
        output_path: Path | None = None,
    ) -> MiniMaxH3SpanOrchestrationResult:
        compiled = self._compiled_for_task(task_id)
        self._preflight_compiled(compiled)
        try:
            return self.orchestrator.run(compiled, output_path=output_path)
        except MiniMaxH3SpanOrchestrationError as exc:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution failed safely: {exc}"
            ) from exc

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
            compiled = self.package_compiler.compile_current(task)
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

        jobs: list[MiniMaxH3ComfyUICompiledJob] = []
        try:
            for execution in plan.spans:
                jobs.append(self.workflow_compiler.compile(execution))
        except MiniMaxH3ComfyUIProviderError as exc:
            raise MiniMaxH3AutomatedExecutionError(
                f"H3 automated execution provider payload preflight failed: {exc}"
            ) from exc

        return MiniMaxH3AutomatedExecutionPreflight(
            task_id=compiled.task_id,
            shot_id=compiled.shot_id,
            package_fingerprint=compiled.package_fingerprint,
            plan_id=plan.plan_id,
            plan_fingerprint=plan.fingerprint,
            span_job_ids=tuple(execution.job_id for execution in plan.spans),
            prompt_fingerprints=tuple(
                execution.prompt_fingerprint for execution in plan.spans
            ),
            reference_slot_fingerprints=tuple(
                execution.reference_slot_fingerprint for execution in plan.spans
            ),
            workflow_fingerprints=tuple(job.workflow_fingerprint for job in jobs),
            model_config_fingerprints=tuple(job.model_config_fingerprint for job in jobs),
        )
