"""Provider-output ingestion into authoritative VSCS Generated Media."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Protocol, runtime_checkable

from vscs.application.production_tasks import ProductionTask
from vscs.application.provider_execution import (
    DurableExecutionJob,
    ProviderExecutionOutput,
    ProviderExecutionState,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
)

from .persistence import GeneratedMediaPersistenceService


class GeneratedMediaIngestionError(RuntimeError):
    """Raised when provider output cannot become authoritative Generated Media safely."""


@runtime_checkable
class GeneratedMediaFileStore(Protocol):
    """Copy provider output bytes into VSCS-managed project media storage."""

    def ingest(
        self,
        source_relative_path: str,
        destination_relative_path: str,
    ) -> GeneratedMediaFile:
        """Ingest one source file and return its managed file metadata."""
        ...


@dataclass(frozen=True, slots=True)
class GeneratedMediaIngestionResult:
    """One idempotent ingestion result for a provider execution output."""

    media: GeneratedMedia
    created: bool


_OUTPUT_KIND_MAP: dict[str, GeneratedMediaKind] = {
    "preview_video": GeneratedMediaKind.VIDEO,
    "production_video": GeneratedMediaKind.VIDEO,
    "lip_sync_video": GeneratedMediaKind.VIDEO,
    "image": GeneratedMediaKind.IMAGE,
    "reference_frame": GeneratedMediaKind.IMAGE,
    "image_sequence": GeneratedMediaKind.IMAGE_SEQUENCE,
    "audio": GeneratedMediaKind.AUDIO,
    "dialogue_audio": GeneratedMediaKind.AUDIO,
    "music": GeneratedMediaKind.AUDIO,
    "effects": GeneratedMediaKind.AUDIO,
    "metadata": GeneratedMediaKind.METADATA,
    "qc_report": GeneratedMediaKind.REPORT,
    "report": GeneratedMediaKind.REPORT,
    "video": GeneratedMediaKind.VIDEO,
}


class GeneratedMediaIngestionService:
    """Promote completed provider artifacts into VSCS-owned Generated Media records."""

    def __init__(
        self,
        persistence: GeneratedMediaPersistenceService,
        file_store: GeneratedMediaFileStore,
    ) -> None:
        self.persistence = persistence
        self.file_store = file_store

    def ingest_execution_outputs(
        self,
        execution: DurableExecutionJob,
        task: ProductionTask,
        outputs: tuple[ProviderExecutionOutput, ...],
    ) -> tuple[GeneratedMediaIngestionResult, ...]:
        """Ingest completed provider outputs deterministically and idempotently."""
        self._validate_execution(execution, task)
        if not outputs:
            raise GeneratedMediaIngestionError(
                "completed execution has no provider outputs to ingest"
            )
        output_ids = tuple(output.output_id for output in outputs)
        if len(set(output_ids)) != len(output_ids):
            raise GeneratedMediaIngestionError(
                "provider outputs contain duplicate output identities"
            )
        ordered = tuple(sorted(outputs, key=lambda output: output.output_id))
        return tuple(self._ingest_one(execution, task, output) for output in ordered)

    def _ingest_one(
        self,
        execution: DurableExecutionJob,
        task: ProductionTask,
        output: ProviderExecutionOutput,
    ) -> GeneratedMediaIngestionResult:
        media_id = self._media_id(execution.execution_id, output.output_id)
        existing = self.persistence.get(media_id)
        if existing is not None:
            self._validate_existing(existing, execution, output)
            return GeneratedMediaIngestionResult(existing, created=False)

        kind = self._media_kind(output.media_kind)
        revision = self._next_revision(task, kind)
        destination = self._destination(task, media_id, output.relative_path)
        managed_file = self.file_store.ingest(output.relative_path, destination)
        media = GeneratedMedia(
            media_id=media_id,
            kind=kind,
            scope=GeneratedMediaScope(
                production_id=task.production_id,
                episode_id=task.episode_id,
                production_task_id=task.task_id,
                scene_id=task.scene_id,
                shot_id=task.shot_id,
            ),
            provenance=GeneratedMediaProvenance(
                execution_id=execution.execution_id,
                provider_id=execution.provider_id,
                provider_job_id=self._provider_job_id(execution),
                render_request_id=execution.render_request_id,
                render_output_id=output.source_output_id,
                workflow_id=execution.workflow_id,
                queue_entry_id=execution.entry_id,
                worker_id=execution.worker_id,
                attributes=self._provenance_attributes(execution, output),
            ),
            file=managed_file,
            revision=revision,
        )
        return GeneratedMediaIngestionResult(self.persistence.register(media), created=True)

    def _next_revision(self, task: ProductionTask, kind: GeneratedMediaKind) -> int:
        candidates = tuple(
            media
            for media in self.persistence.list_for_task(task.task_id)
            if media.scope.production_id == task.production_id
            and media.scope.episode_id == task.episode_id
            and media.kind is kind
        )
        revisions = tuple(media.revision for media in candidates)
        if len(set(revisions)) != len(revisions):
            raise GeneratedMediaIngestionError(
                "existing Generated Media candidates contain duplicate revisions"
            )
        return max(revisions, default=0) + 1

    @staticmethod
    def _validate_execution(execution: DurableExecutionJob, task: ProductionTask) -> None:
        if execution.state is not ProviderExecutionState.COMPLETED:
            raise GeneratedMediaIngestionError(
                "Generated Media ingestion requires a COMPLETED provider execution"
            )
        if execution.provider_job_id is None:
            raise GeneratedMediaIngestionError("completed execution has no provider job identity")
        if execution.production_id != task.production_id or execution.task_id != task.task_id:
            raise GeneratedMediaIngestionError(
                "ProductionTask does not match durable provider execution authority"
            )
        if execution.authority_fingerprint != task.authority.fingerprint:
            raise GeneratedMediaIngestionError(
                "ProductionTask authority fingerprint changed after provider execution"
            )

    @staticmethod
    def _validate_existing(
        media: GeneratedMedia,
        execution: DurableExecutionJob,
        output: ProviderExecutionOutput,
    ) -> None:
        if media.provenance.execution_id != execution.execution_id:
            raise GeneratedMediaIngestionError(
                "deterministic Generated Media identity belongs to another execution"
            )
        if media.provenance.render_output_id != output.source_output_id:
            raise GeneratedMediaIngestionError(
                "deterministic Generated Media identity belongs to another provider output"
            )

    @staticmethod
    def _provider_job_id(execution: DurableExecutionJob) -> str:
        provider_job_id = execution.provider_job_id
        if provider_job_id is None:
            raise GeneratedMediaIngestionError("provider job identity is required for provenance")
        return provider_job_id

    @staticmethod
    def _media_id(execution_id: str, output_id: str) -> str:
        digest = sha256(f"{execution_id}|{output_id}".encode()).hexdigest()[:24].upper()
        return f"GM-{digest}"

    @staticmethod
    def _media_kind(raw_kind: str) -> GeneratedMediaKind:
        normalized = raw_kind.strip().casefold()
        try:
            return _OUTPUT_KIND_MAP[normalized]
        except KeyError as exc:
            raise GeneratedMediaIngestionError(
                f"unsupported provider output media kind: {raw_kind!r}"
            ) from exc

    @staticmethod
    def _destination(task: ProductionTask, media_id: str, source_path: str) -> str:
        suffix = PurePosixPath(source_path.replace("\\", "/")).suffix.casefold()
        filename = f"{media_id}{suffix}"
        return "/".join(
            (
                "generated_media",
                _safe_segment(task.production_id),
                _safe_segment(task.episode_id),
                _safe_segment(task.task_id),
                filename,
            )
        )

    @staticmethod
    def _provenance_attributes(
        execution: DurableExecutionJob,
        output: ProviderExecutionOutput,
    ) -> tuple[tuple[str, str], ...]:
        attributes: list[tuple[str, str]] = [
            ("attempt_number", str(execution.attempt_number)),
            ("resource_id", execution.resource_id),
            ("authority_fingerprint", execution.authority_fingerprint),
            ("provider_output_id", output.output_id),
            ("source_relative_path", output.relative_path),
        ]
        if output.source_output_id is not None:
            attributes.append(("source_output_id", output.source_output_id))
        attributes.extend((f"output.{key}", value) for key, value in output.metadata)
        attributes.extend((f"provider.{key}", value) for key, value in execution.provider_metadata)
        keys = [key for key, _ in attributes]
        if len(set(keys)) != len(keys):
            raise GeneratedMediaIngestionError("ingestion provenance contains duplicate keys")
        return tuple(attributes)


def _safe_segment(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value.strip()
    )
    if not normalized:
        raise GeneratedMediaIngestionError(
            "Generated Media destination contains an empty scope segment"
        )
    return normalized
