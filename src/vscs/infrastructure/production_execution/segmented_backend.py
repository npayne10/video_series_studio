"""Current-authority LTX backend with governed automatic provider segmentation.

Segmentation is provider adaptation only. The governed Shot remains one ProductionTask
and one authoritative Production Package. One queue-authorised attempt may execute a
sequence of smaller provider jobs, carry the prior segment final frame forward as the
continuity anchor, and assemble one final governed GeneratedMedia artifact.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from vscs.application.generated_media import GeneratedMediaIngestionService
from vscs.application.production_execution import (
    CompiledProductionPackage,
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionExecutionState,
    normalize_execution_profile,
)
from vscs.application.production_tasks import ProductionQueue, ProductionQueueCompilerService
from vscs.application.provider_execution import (
    ProviderExecutionContext,
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionState,
    RenderProviderExecutionAdapter,
)
from vscs.application.rendering import RenderRequest
from vscs.infrastructure.generated_media import LocalGeneratedMediaFileStore

from .current_authority_backend import (
    CurrentAuthorityLTX23V721ProductionPackageCompilationService as _CurrentPackageCompiler,
)
from .current_authority_backend import (
    LocalComfyUIProductionExecutionBackend as _CurrentAuthorityBackend,
)
from .package_compilation import LocalProductionPackageCompilationError
from .provider_segmentation import GovernedProviderSegmentationPlanner
from .segment_execution_runtime import SegmentExecutionRecord, SegmentExecutionStore
from .segment_media_runtime import SegmentMediaRuntime
from .segment_package_runtime import (
    SegmentPackageMaterializationError,
    SegmentPackageMaterializer,
)

_SEGMENTED_LEASE_MINIMUM_SECONDS = 900.0
_VIDEO_KINDS = frozenset({"video", "preview_video", "production_video", "lip_sync_video"})


class SegmentedLTX23V721ProductionPackageCompilationService(_CurrentPackageCompiler):
    """Emit a deterministic provider execution plan beside governed render authority."""

    def _comfyui_payload(self, compiled: CompiledProductionPackage) -> dict[str, Any]:
        content = super()._comfyui_payload(compiled)
        content["provider_execution_plan"] = GovernedProviderSegmentationPlanner().plan(
            frame_count=compiled.frame_count,
            frames_per_second=compiled.frames_per_second,
            seed=compiled.seed,
        )
        self._refresh_manifest_fingerprint(content)
        return content


@dataclass(slots=True)
class _ActiveSegmentedExecution:
    candidate: object
    queue: ProductionQueue
    lease_id: str
    handle: ProviderExecutionHandle
    service: object
    adapter: RenderProviderExecutionAdapter
    context: ProviderExecutionContext
    profile: str
    parent_package_path: Path
    parent_package: dict[str, Any]
    parent_package_fingerprint: str
    segments: tuple[dict[str, Any], ...]
    current_segment_index: int
    provider_id: str
    parent_provider_job_id: str
    parent_submitted_at: datetime


class LocalComfyUIProductionExecutionBackend(_CurrentAuthorityBackend):
    """Execute governed LTX shots as one attempt with sequential provider segments."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            project_directory,
            endpoint=endpoint,
            comfyui_output_directory=comfyui_output_directory,
            managed_media_directory=managed_media_directory,
            lease_duration_seconds=lease_duration_seconds,
        )
        self.package_compilation = SegmentedLTX23V721ProductionPackageCompilationService(
            self.project_directory
        )
        self.segment_packages = SegmentPackageMaterializer(self.project_directory)
        self.segment_executions = SegmentExecutionStore(self.project_directory)
        self._segmented_active: dict[str, _ActiveSegmentedExecution] = {}

    def start_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        if self.has_execution_for_profile(task.task_id, profile=normalized):
            raise ProductionExecutionError(
                f"{normalized.title()} execution is active, successful, or has exhausted its "
                "profile-scoped attempt allowance. Inspect profile execution status first."
            )
        package = self._resolve_parent_package(task, normalized, production_package)
        try:
            parent = self.segment_packages.read_parent(package)
        except SegmentPackageMaterializationError as exc:
            raise ProductionExecutionError(str(exc)) from exc
        plan = parent.get("provider_execution_plan")
        if not isinstance(plan, dict) or plan.get("mode") != "segmented":
            return super().start_for_profile(
                task.task_id,
                profile=normalized,
                production_package=package,
            )

        segments_raw = plan.get("segments")
        if not isinstance(segments_raw, list) or len(segments_raw) < 2:
            raise ProductionExecutionError(
                "Segmented provider execution plan must contain at least two segments."
            )
        segments = tuple(dict(item) for item in segments_raw if isinstance(item, dict))
        if len(segments) != len(segments_raw):
            raise ProductionExecutionError("Segmented provider execution plan is malformed.")
        manifest = parent.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise ProductionExecutionError("Production Package has no VSCS compilation manifest.")
        package_fingerprint = str(manifest.get("package_fingerprint") or "").strip()
        if not package_fingerprint:
            raise ProductionExecutionError(
                "Production Package manifest has no package fingerprint."
            )

        queue = ProductionQueueCompilerService(self.schedules, self.tasks).compile(
            task.production_id
        )
        entry = queue.entry_for_task(task.task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in the current approved queue: {task.task_id}"
            )
        all_jobs = tuple(
            sorted(
                self.execution_jobs.list_for_queue_entry(queue.queue_id, entry.entry_id),
                key=lambda item: item.attempt_number,
            )
        )
        history = self._global_attempt_history(task, all_jobs)
        profile_jobs = self._jobs_for_profile(all_jobs, normalized)
        effective = task.attempt_policy.maximum_attempts + len(
            self._authorizations_for_profile(task, normalized)
        )
        remaining = effective - len(profile_jobs)
        if remaining < 1:
            raise ProductionExecutionError(
                f"{normalized.title()} has exhausted its profile-scoped execution attempt allowance."
            )
        if history:
            queue = self._queue_with_profile_history(
                queue,
                task.task_id,
                history,
                maximum_attempts=len(history) + remaining,
            )
            entry = queue.entry_for_task(task.task_id)
            assert entry is not None

        next_global_attempt = len(history) + 1
        predicted_execution_id = f"PEX-{queue.queue_id}-{entry.entry_id}-A{next_global_attempt:03d}"
        self.execution_profiles.assign(predicted_execution_id, task.task_id, normalized)

        candidate = self._candidate(task, entry.resource_id, entry.entry_id)
        source_root = self._require_comfyui_output_directory()
        service, worker_id = self._execution_service(task, entry.resource_id)
        resource = service.resources.resource(entry.resource_id)
        if resource is None:
            raise ProductionExecutionError(
                f"ProductionResource not found for segmented execution: {entry.resource_id}"
            )
        eligible = service.providers.eligible_providers(task, resource)
        if len(eligible) != 1:
            provider_ids = ", ".join(item.provider_id for item in eligible) or "none"
            raise ProductionExecutionError(
                "Segmented execution requires exactly one eligible provider; resolved: "
                f"{provider_ids}"
            )
        provider = eligible[0]
        adapter = service.adapters.require(provider.provider_id)
        if not isinstance(adapter, RenderProviderExecutionAdapter):
            raise ProductionExecutionError(
                f"Provider does not expose render execution: {provider.provider_id}"
            )

        lease_seconds = max(self.lease_duration_seconds, _SEGMENTED_LEASE_MINIMUM_SECONDS)
        claim = service.runtime.claim(
            queue,
            entry.entry_id,
            worker_id,
            lease_duration_seconds=lease_seconds,
        )
        running = service.runtime.start(claim.queue, entry.entry_id, claim.lease.lease_id)
        context = service.context_factory.bind(running, entry.entry_id, claim.lease, task)
        if context.execution_id != predicted_execution_id:
            raise ProductionExecutionError(
                "Segmented execution identity did not match the governed profile assignment."
            )

        base_request = self._render_request(task)
        self.execution_jobs.prepare(
            context,
            provider.provider_id,
            render_request_id=base_request.request_id,
            workflow_id=base_request.workflow_id,
        )
        records = self.segment_executions.initialize(
            task_id=task.task_id,
            package_fingerprint=package_fingerprint,
            segments=list(segments),
        )
        if any(record.state != "PLANNED" for record in records):
            service.runtime.fail(
                running,
                entry.entry_id,
                claim.lease.lease_id,
                "Existing segmented execution history is not clean for a new governed attempt.",
            )
            self.execution_jobs.submission_failed(
                context.execution_id,
                "Existing segmented execution history is not clean for a new governed attempt.",
            )
            raise ProductionExecutionError(
                "Existing segmented execution history is not clean for a new governed attempt."
            )

        first_segment = segments[0]
        try:
            first_package = self.segment_packages.materialize(
                parent=parent,
                task_id=task.task_id,
                segment=first_segment,
            )
            first_handle, first_request = self._submit_segment(
                adapter=adapter,
                service=service,
                context=context,
                task=task,
                parent=parent,
                segment=first_segment,
                package_path=first_package,
            )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            service.runtime.fail(running, entry.entry_id, claim.lease.lease_id, message)
            self.execution_jobs.submission_failed(context.execution_id, message)
            failed = records[0].with_state("FAILED", error_message=message)
            self.segment_executions.save(failed)
            return ProductionExecutionResult(
                candidate=candidate,
                state=ProductionExecutionState.FAILED,
                provider_id=provider.provider_id,
                execution_id=context.execution_id,
                media_output_directory=self.managed_media_directory,
                message=f"SEG-001 submission failed: {message}",
            )

        parent_job_id = f"SEGMENTED-{context.execution_id}"
        parent_handle = self._parent_handle(
            first_handle,
            execution_id=context.execution_id,
            provider_job_id=parent_job_id,
            state=ProviderExecutionState.RUNNING,
            progress=0.0,
            segment_count=len(segments),
        )
        self.execution_jobs.observe(context.execution_id, parent_handle)
        first_record = self._record_submitted(
            records[0],
            context.execution_id,
            first_handle,
            first_request.request_id,
            continuity_input_path=None,
        )
        self.segment_executions.save(first_record)

        active = _ActiveSegmentedExecution(
            candidate=candidate,
            queue=running,
            lease_id=claim.lease.lease_id,
            handle=first_handle,
            service=service,
            adapter=adapter,
            context=context,
            profile=normalized,
            parent_package_path=package,
            parent_package=parent,
            parent_package_fingerprint=package_fingerprint,
            segments=segments,
            current_segment_index=0,
            provider_id=provider.provider_id,
            parent_provider_job_id=parent_job_id,
            parent_submitted_at=first_handle.submitted_at,
        )
        self._segmented_active[task.task_id] = active
        self._active[task.task_id] = active  # type: ignore[assignment]
        result = ProductionExecutionResult(
            candidate=candidate,
            state=self._state(first_handle.state),
            provider_id=provider.provider_id,
            execution_id=context.execution_id,
            provider_job_id=first_handle.provider_job_id,
            progress=0.0,
            media_output_directory=self.managed_media_directory,
            message=(
                f"{normalized.title()} segmented execution submitted SEG-001/{len(segments)} "
                f"as global execution A{next_global_attempt:03d}; source output: {source_root}"
            ),
        )
        self._latest[task.task_id] = result
        return result

    def reconcile_for_profile(self, task_id: str, *, profile: str) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        active = self._segmented_active.get(task.task_id)
        if active is None:
            return super().reconcile_for_profile(task.task_id, profile=normalized)
        if active.profile != normalized:
            raise ProductionExecutionError(
                f"Active segmented execution belongs to {active.profile}, not {normalized}."
            )

        lease_seconds = max(self.lease_duration_seconds, _SEGMENTED_LEASE_MINIMUM_SECONDS)
        active.service.runtime.heartbeat(
            active.queue,
            active.candidate.queue_entry_id,
            active.lease_id,
            duration_seconds=lease_seconds,
        )
        refreshed = active.adapter.monitor(active.handle)
        active.handle = refreshed
        current_number = active.current_segment_index + 1
        segment_count = len(active.segments)

        if refreshed.state in {ProviderExecutionState.FAILED, ProviderExecutionState.CANCELLED}:
            message = refreshed.failure_reason or refreshed.state.value
            return self._fail_segmented(active, task, current_number, message)

        if refreshed.state is not ProviderExecutionState.COMPLETED:
            cumulative = (active.current_segment_index + refreshed.progress) / segment_count
            result = ProductionExecutionResult(
                candidate=active.candidate,
                state=self._state(refreshed.state),
                provider_id=active.provider_id,
                execution_id=active.context.execution_id,
                provider_job_id=refreshed.provider_job_id,
                progress=min(0.999, cumulative),
                media_output_directory=self.managed_media_directory,
                message=f"Rendering SEG-{current_number:03d}/{segment_count}.",
            )
            self._latest[task.task_id] = result
            return result

        try:
            outputs = active.adapter.fetch_outputs(refreshed)
            _video_output, video_path = self._segment_video_output(outputs)
            record = self._current_segment_record(active)
            frame_directory = (
                self.segment_executions.package_directory(
                    task.task_id,
                    active.parent_package_fingerprint,
                )
                / "frames"
            )
            final_frame = SegmentMediaRuntime().capture_final_frame(
                video_path,
                frame_count=record.frame_count,
                destination=frame_directory / f"{record.segment_id}-final.png",
            )
            completed_record = record.with_state(
                "COMPLETED",
                output_path=str(video_path),
                final_frame_path=str(final_frame),
                provider_prompt_id=refreshed.provider_job_id,
            )
            self.segment_executions.save(completed_record)
        except Exception as exc:
            return self._fail_segmented(
                active,
                task,
                current_number,
                f"Segment completion processing failed: {str(exc) or exc.__class__.__name__}",
            )

        if active.current_segment_index + 1 < segment_count:
            next_index = active.current_segment_index + 1
            next_segment = active.segments[next_index]
            try:
                next_package = self.segment_packages.materialize(
                    parent=active.parent_package,
                    task_id=task.task_id,
                    segment=next_segment,
                    continuity_input_path=str(final_frame),
                )
                next_handle, next_request = self._submit_segment(
                    adapter=active.adapter,
                    service=active.service,
                    context=active.context,
                    task=task,
                    parent=active.parent_package,
                    segment=next_segment,
                    package_path=next_package,
                )
                next_record = self.segment_executions.list_for_package(
                    task.task_id,
                    active.parent_package_fingerprint,
                )[next_index]
                self.segment_executions.save(
                    self._record_submitted(
                        next_record,
                        active.context.execution_id,
                        next_handle,
                        next_request.request_id,
                        continuity_input_path=str(final_frame),
                    )
                )
            except Exception as exc:
                return self._fail_segmented(
                    active,
                    task,
                    next_index + 1,
                    f"Next segment submission failed: {str(exc) or exc.__class__.__name__}",
                )

            active.current_segment_index = next_index
            active.handle = next_handle
            progress = next_index / segment_count
            parent_handle = self._parent_handle(
                next_handle,
                execution_id=active.context.execution_id,
                provider_job_id=active.parent_provider_job_id,
                state=ProviderExecutionState.RUNNING,
                progress=progress,
                segment_count=segment_count,
            )
            self.execution_jobs.observe(active.context.execution_id, parent_handle)
            result = ProductionExecutionResult(
                candidate=active.candidate,
                state=self._state(next_handle.state),
                provider_id=active.provider_id,
                execution_id=active.context.execution_id,
                provider_job_id=next_handle.provider_job_id,
                progress=progress,
                media_output_directory=self.managed_media_directory,
                message=(
                    f"SEG-{current_number:03d} completed; submitted "
                    f"SEG-{next_index + 1:03d}/{segment_count} with previous final-frame continuity."
                ),
            )
            self._latest[task.task_id] = result
            return result

        try:
            records = self.segment_executions.list_for_package(
                task.task_id,
                active.parent_package_fingerprint,
            )
            if len(records) != segment_count or any(
                record.state != "COMPLETED" for record in records
            ):
                raise ProductionExecutionError(
                    "Segment assembly requires every planned segment to be COMPLETED."
                )
            segment_paths = tuple(Path(record.output_path or "") for record in records)
            source_root = self._require_comfyui_output_directory()
            assembly_path = (
                source_root
                / "vscs-segmented"
                / task.production_id
                / active.context.execution_id
                / f"{task.task_id}.mp4"
            )
            plan = active.parent_package["provider_execution_plan"]
            expected_frames = int(plan["governed_frame_count"])
            expected_fps = int(plan["frames_per_second"])
            assembly = SegmentMediaRuntime().assemble(
                segment_paths,
                destination=assembly_path,
                expected_frame_count=expected_frames,
                expected_frames_per_second=expected_fps,
            )
        except Exception as exc:
            return self._fail_segmented(
                active,
                task,
                current_number,
                f"Segment assembly failed: {str(exc) or exc.__class__.__name__}",
            )

        completed_queue = active.service.runtime.complete(
            active.queue,
            active.candidate.queue_entry_id,
            active.lease_id,
        )
        active.queue = completed_queue
        completed_parent = self._parent_handle(
            refreshed,
            execution_id=active.context.execution_id,
            provider_job_id=active.parent_provider_job_id,
            state=ProviderExecutionState.COMPLETED,
            progress=1.0,
            segment_count=segment_count,
        )
        execution_job = self.execution_jobs.observe(active.context.execution_id, completed_parent)
        relative_output = assembly.output_path.relative_to(
            self._require_comfyui_output_directory()
        ).as_posix()
        provider_output = ProviderExecutionOutput(
            output_id=f"PEO-SEGMENT-ASSEMBLY-{active.context.execution_id}",
            relative_path=relative_output,
            media_kind="production_video",
            source_output_id=f"SEGMENT-ASSEMBLY-{active.context.execution_id}",
            metadata=(
                ("segmented_execution", "true"),
                ("segment_count", str(segment_count)),
                ("governed_frame_count", str(assembly.frame_count)),
                ("governed_fps", str(int(assembly.frames_per_second))),
                ("parent_package_fingerprint", active.parent_package_fingerprint),
            ),
        )
        ingestion = GeneratedMediaIngestionService(
            self.media,
            LocalGeneratedMediaFileStore(
                source_root=self._require_comfyui_output_directory(),
                project_root=self.project_directory,
                managed_relative_root=self.managed_media_directory,
            ),
        )
        ingested = ingestion.ingest_execution_outputs(execution_job, task, (provider_output,))
        result = ProductionExecutionResult(
            candidate=active.candidate,
            state=ProductionExecutionState.COMPLETED,
            provider_id=active.provider_id,
            execution_id=active.context.execution_id,
            provider_job_id=active.parent_provider_job_id,
            progress=1.0,
            generated_media_ids=tuple(item.media.media_id for item in ingested),
            media_output_directory=self.managed_media_directory,
            message=(
                f"All {segment_count} LTX provider segments completed, final-frame continuity was "
                f"applied, and one {assembly.frame_count}-frame Generated Media artifact was assembled."
            ),
        )
        self._segmented_active.pop(task.task_id, None)
        self._active.pop(task.task_id, None)
        self._latest[task.task_id] = result
        return result

    def _resolve_parent_package(
        self,
        task: object,
        profile: str,
        production_package: Path | None,
    ) -> Path:
        try:
            if production_package is None:
                current = self.package_compilation.require_current(task, profile=profile)  # type: ignore[arg-type]
                assert current.path is not None
                return current.path
            package = Path(production_package).expanduser().resolve(strict=False)
            self.package_compilation.validate_file(task, package)  # type: ignore[arg-type]
            payload_profile = self._package_profile(package)
            if payload_profile != profile:
                raise ProductionExecutionError(
                    f"Production Package profile {payload_profile!r} does not match selected "
                    f"profile {profile!r}."
                )
            return package
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def _submit_segment(
        self,
        *,
        adapter: RenderProviderExecutionAdapter,
        service: object,
        context: ProviderExecutionContext,
        task: object,
        parent: dict[str, Any],
        segment: dict[str, Any],
        package_path: Path,
    ) -> tuple[ProviderExecutionHandle, RenderRequest]:
        segment_id = str(segment["segment_id"])
        frame_count = int(segment["frame_count"])
        seed = int(segment["seed"])
        base_request = self._render_request(task)  # type: ignore[arg-type]
        render = replace(
            base_request.render,
            width=int(parent.get("width", base_request.render.width)),
            height=int(parent.get("height", base_request.render.height)),
            frames_per_second=int(
                parent.get("frames_per_second", base_request.render.frames_per_second)
            ),
            frame_count=frame_count,
            seed=seed,
        )
        output = replace(
            base_request.output, filename_stem=f"{base_request.output.filename_stem}-{segment_id}"
        )
        metadata = dict(base_request.metadata)
        metadata["production_package"] = str(package_path.resolve(strict=False))
        metadata["provider_segment_id"] = segment_id
        request = replace(
            base_request,
            request_id=f"{base_request.request_id}-{segment_id}",
            render=render,
            output=output,
            metadata=metadata,
        )
        execution_request = service.compiler.compile(context, request, adapter.adapter)
        validation = adapter.validate(execution_request)
        if not validation.passed:
            raise ProductionExecutionError("; ".join(validation.messages))
        return adapter.submit(execution_request), request

    def _segment_video_output(
        self,
        outputs: tuple[ProviderExecutionOutput, ...],
    ) -> tuple[ProviderExecutionOutput, Path]:
        videos = tuple(output for output in outputs if output.media_kind.casefold() in _VIDEO_KINDS)
        if len(videos) != 1:
            raise ProductionExecutionError(
                "Each provider segment must produce exactly one video output before continuity capture."
            )
        output = videos[0]
        root = self._require_comfyui_output_directory().resolve(strict=False)
        path = (root / output.relative_path).resolve(strict=False)
        if path != root and root not in path.parents:
            raise ProductionExecutionError(
                "Provider segment output escapes the configured ComfyUI output root."
            )
        if not path.is_file():
            raise ProductionExecutionError(f"Provider segment video does not exist: {path}")
        return output, path

    def _current_segment_record(self, active: _ActiveSegmentedExecution) -> SegmentExecutionRecord:
        records = self.segment_executions.list_for_package(
            active.context.task_id,
            active.parent_package_fingerprint,
        )
        try:
            return records[active.current_segment_index]
        except IndexError as exc:
            raise ProductionExecutionError("Durable segment execution record is missing.") from exc

    def _record_submitted(
        self,
        record: SegmentExecutionRecord,
        execution_id: str,
        handle: ProviderExecutionHandle,
        request_id: str,
        *,
        continuity_input_path: str | None,
    ) -> SegmentExecutionRecord:
        metadata = dict(handle.metadata)
        return record.with_state(
            "RUNNING",
            provider_execution_id=execution_id,
            provider_prompt_id=handle.provider_job_id,
            render_job_id=metadata.get("render_job_id"),
            render_request_id=request_id,
            submitted_at=handle.submitted_at.isoformat(),
            continuity_input_path=continuity_input_path,
            error_message=None,
        )

    def _fail_segmented(
        self,
        active: _ActiveSegmentedExecution,
        task: object,
        segment_number: int,
        message: str,
    ) -> ProductionExecutionResult:
        with contextlib.suppress(Exception):
            active.service.runtime.fail(
                active.queue,
                active.candidate.queue_entry_id,
                active.lease_id,
                message,
            )
        failed_parent = self._parent_handle(
            active.handle,
            execution_id=active.context.execution_id,
            provider_job_id=active.parent_provider_job_id,
            state=ProviderExecutionState.FAILED,
            progress=min(0.999, active.current_segment_index / len(active.segments)),
            segment_count=len(active.segments),
            failure_reason=message,
        )
        with contextlib.suppress(Exception):
            self.execution_jobs.observe(active.context.execution_id, failed_parent)
        records = self.segment_executions.list_for_package(
            active.context.task_id,
            active.parent_package_fingerprint,
        )
        index = max(0, min(segment_number - 1, len(records) - 1))
        if records:
            self.segment_executions.save(records[index].with_state("FAILED", error_message=message))
        result = ProductionExecutionResult(
            candidate=active.candidate,
            state=ProductionExecutionState.FAILED,
            provider_id=active.provider_id,
            execution_id=active.context.execution_id,
            provider_job_id=active.handle.provider_job_id,
            progress=min(0.999, active.current_segment_index / len(active.segments)),
            media_output_directory=self.managed_media_directory,
            message=f"SEG-{segment_number:03d} failed: {message}",
        )
        self._segmented_active.pop(active.context.task_id, None)
        self._active.pop(active.context.task_id, None)
        self._latest[active.context.task_id] = result
        return result

    @staticmethod
    def _parent_handle(
        source: ProviderExecutionHandle,
        *,
        execution_id: str,
        provider_job_id: str,
        state: ProviderExecutionState,
        progress: float,
        segment_count: int,
        failure_reason: str | None = None,
    ) -> ProviderExecutionHandle:
        return ProviderExecutionHandle(
            execution_id=execution_id,
            provider_id=source.provider_id,
            provider_job_id=provider_job_id,
            state=state,
            submitted_at=source.submitted_at,
            progress=progress,
            failure_reason=failure_reason,
            metadata=(("segmented", "true"), ("segment_count", str(segment_count))),
        )
