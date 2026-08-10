"""Append-only production audit ledger and provenance snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from vscs.application.acpp import ProductionBundle

from .executors import ExecutionResult, WorkerIdentity


class AuditEventType(StrEnum):
    PROVENANCE_CAPTURED = "provenance_captured"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    RECOVERY_APPLIED = "recovery_applied"
    QUALITY_CONTROL = "quality_control"


@dataclass(frozen=True, slots=True)
class VersionedComponent:
    component_type: str
    component_id: str
    version: str
    checksum: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactProvenance:
    story_version: str
    ssie_version: str
    acpp_version: str
    bundle_schema_version: str
    package_checksum: str
    prompt_checksum: str
    render_job_checksum: str
    bundle_checksum: str
    asset_ids: tuple[str, ...] = ()
    reference_ids: tuple[str, ...] = ()
    prompt_package_ids: tuple[str, ...] = ()
    components: tuple[VersionedComponent, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderProvenance:
    executor_id: str
    worker_id: str
    seed_policy: str
    fixed_seed: int | None
    width: int
    height: int
    frames_per_second: int
    frame_count: int
    quality_mode: str
    output_paths: tuple[str, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    succeeded: bool | None = None
    error_code: str | None = None
    error_message: str | None = None
    machine_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionProvenance:
    production_id: str
    episode_id: str
    clip_id: str
    job_id: str
    captured_at: datetime
    artifacts: ArtifactProvenance
    render: RenderProvenance
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionAuditEntry:
    entry_id: str
    event_type: AuditEventType
    occurred_at: datetime
    actor_id: str
    message: str
    provenance: ProductionProvenance
    previous_checksum: str | None
    checksum: str
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionAuditLedger:
    ledger_id: str
    production_id: str
    entries: tuple[ProductionAuditEntry, ...] = ()
    schema_version: str = "1.0"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditValidationIssue:
    code: str
    message: str
    entry_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditValidationResult:
    issues: tuple[AuditValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.issues


class ProductionAuditError(ValueError):
    """Raised for invalid audit operations or serialized payloads."""


class ProductionAuditService:
    """Capture provenance and maintain an append-only checksum chain."""

    def capture(
        self,
        bundle: ProductionBundle,
        *,
        production_id: str,
        episode_id: str,
        worker: WorkerIdentity,
        story_version: str,
        ssie_version: str,
        components: tuple[VersionedComponent, ...] = (),
        execution: ExecutionResult | None = None,
        machine_metadata: tuple[tuple[str, str], ...] = (),
        captured_at: datetime | None = None,
    ) -> ProductionProvenance:
        package = bundle.package
        job = bundle.render_job
        return ProductionProvenance(
            production_id=production_id,
            episode_id=episode_id,
            clip_id=package.identity.clip_id,
            job_id=job.job_id,
            captured_at=captured_at or datetime.now(UTC),
            artifacts=ArtifactProvenance(
                story_version=story_version,
                ssie_version=ssie_version,
                acpp_version=package.schema_version,
                bundle_schema_version=bundle.schema_version,
                package_checksum=bundle.package_checksum,
                prompt_checksum=bundle.prompt_checksum,
                render_job_checksum=bundle.render_job_checksum,
                bundle_checksum=bundle.aggregate_checksum,
                asset_ids=tuple(dict.fromkeys(item.asset_id for item in package.assets)),
                reference_ids=tuple(
                    dict.fromkeys(item.reference_id for item in job.input_references)
                ),
                prompt_package_ids=bundle.prompt.prompt_package_ids,
                components=components,
            ),
            render=RenderProvenance(
                executor_id=worker.executor_id,
                worker_id=worker.worker_id,
                seed_policy=job.seed_policy.value,
                fixed_seed=job.fixed_seed,
                width=job.width,
                height=job.height,
                frames_per_second=job.frames_per_second,
                frame_count=job.frame_count,
                quality_mode=job.quality_mode.value,
                output_paths=() if execution is None else execution.output_paths,
                started_at=None if execution is None else execution.started_at,
                completed_at=None if execution is None else execution.completed_at,
                duration_seconds=_duration(execution),
                succeeded=None if execution is None else execution.succeeded,
                error_code=_error_code(execution),
                error_message=None if execution is None else execution.error_message,
                machine_metadata=machine_metadata,
            ),
        )

    def append(
        self,
        ledger: ProductionAuditLedger,
        *,
        event_type: AuditEventType,
        actor_id: str,
        message: str,
        provenance: ProductionProvenance,
        occurred_at: datetime | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> ProductionAuditLedger:
        if provenance.production_id != ledger.production_id:
            raise ProductionAuditError("Provenance production ID does not match ledger")
        if not actor_id.strip():
            raise ProductionAuditError("actor_id must not be empty")
        current = occurred_at or datetime.now(UTC)
        previous = ledger.entries[-1].checksum if ledger.entries else None
        entry_id = f"AUDIT-{len(ledger.entries) + 1:08d}"
        checksum = self.entry_checksum(
            entry_id,
            event_type,
            current,
            actor_id,
            message,
            provenance,
            previous,
            metadata,
        )
        entry = ProductionAuditEntry(
            entry_id=entry_id,
            event_type=event_type,
            occurred_at=current,
            actor_id=actor_id,
            message=message,
            provenance=provenance,
            previous_checksum=previous,
            checksum=checksum,
            metadata=metadata,
        )
        return replace(ledger, entries=(*ledger.entries, entry))

    @staticmethod
    def query(
        ledger: ProductionAuditLedger,
        *,
        clip_id: str | None = None,
        job_id: str | None = None,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
    ) -> tuple[ProductionAuditEntry, ...]:
        return tuple(
            entry
            for entry in ledger.entries
            if (clip_id is None or entry.provenance.clip_id == clip_id)
            and (job_id is None or entry.provenance.job_id == job_id)
            and (event_type is None or entry.event_type is event_type)
            and (actor_id is None or entry.actor_id == actor_id)
        )

    @staticmethod
    def report(ledger: ProductionAuditLedger) -> str:
        validation = ProductionAuditValidator().validate(ledger)
        clips = {entry.provenance.clip_id for entry in ledger.entries}
        failures = sum(
            entry.event_type is AuditEventType.EXECUTION_FAILED for entry in ledger.entries
        )
        head = ledger.entries[-1].checksum if ledger.entries else "none"
        return "\n".join(
            (
                f"Production Audit Ledger: {ledger.ledger_id}",
                f"Production: {ledger.production_id}",
                f"Schema: {ledger.schema_version}",
                f"Entries: {len(ledger.entries)}",
                f"Clips: {len(clips)}",
                f"Execution failures: {failures}",
                f"Integrity: {'PASSED' if validation.passed else 'FAILED'}",
                f"Head checksum: {head}",
            )
        )

    @staticmethod
    def entry_checksum(
        entry_id: str,
        event_type: AuditEventType,
        occurred_at: datetime,
        actor_id: str,
        message: str,
        provenance: ProductionProvenance,
        previous_checksum: str | None,
        metadata: tuple[tuple[str, str], ...],
    ) -> str:
        payload = {
            "entry_id": entry_id,
            "event_type": event_type.value,
            "occurred_at": occurred_at.isoformat(),
            "actor_id": actor_id,
            "message": message,
            "provenance": ProductionAuditSerializer.provenance_to_dict(provenance),
            "previous_checksum": previous_checksum,
            "metadata": [list(item) for item in metadata],
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ProductionAuditValidator:
    """Validate identity, sequence, and checksum-chain integrity."""

    def validate(self, ledger: ProductionAuditLedger) -> AuditValidationResult:
        issues: list[AuditValidationIssue] = []
        previous: str | None = None
        seen: set[str] = set()
        if not ledger.ledger_id.strip():
            issues.append(AuditValidationIssue("EMPTY_LEDGER_ID", "Ledger ID is empty"))
        if not ledger.production_id.strip():
            issues.append(AuditValidationIssue("EMPTY_PRODUCTION_ID", "Production ID is empty"))
        for index, entry in enumerate(ledger.entries, start=1):
            expected_id = f"AUDIT-{index:08d}"
            if entry.entry_id in seen:
                issues.append(_issue("DUPLICATE_ENTRY_ID", "Duplicate entry ID", entry))
            seen.add(entry.entry_id)
            if entry.entry_id != expected_id:
                issues.append(
                    _issue(
                        "ENTRY_SEQUENCE_MISMATCH",
                        f"Expected {expected_id}, found {entry.entry_id}",
                        entry,
                    )
                )
            if entry.provenance.production_id != ledger.production_id:
                issues.append(
                    _issue(
                        "PRODUCTION_ID_MISMATCH",
                        "Entry provenance does not match ledger production",
                        entry,
                    )
                )
            if entry.previous_checksum != previous:
                issues.append(
                    _issue(
                        "CHAIN_LINK_MISMATCH",
                        "Previous checksum does not match prior entry",
                        entry,
                    )
                )
            expected = ProductionAuditService.entry_checksum(
                entry.entry_id,
                entry.event_type,
                entry.occurred_at,
                entry.actor_id,
                entry.message,
                entry.provenance,
                entry.previous_checksum,
                entry.metadata,
            )
            if entry.checksum != expected:
                issues.append(
                    _issue(
                        "ENTRY_CHECKSUM_MISMATCH",
                        "Entry checksum does not match entry content",
                        entry,
                    )
                )
            previous = entry.checksum
        return AuditValidationResult(tuple(issues))


class ProductionAuditSerializer:
    """Stable JSON serialization for production audit ledgers."""

    def dumps(self, ledger: ProductionAuditLedger) -> str:
        self._require_valid(ledger)
        return json.dumps(self.to_dict(ledger), indent=2, sort_keys=True) + "\n"

    def loads(self, payload: str) -> ProductionAuditLedger:
        try:
            ledger = self.from_dict(json.loads(payload))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ProductionAuditError(f"Invalid production audit payload: {exc}") from exc
        self._require_valid(ledger)
        return ledger

    @staticmethod
    def to_dict(ledger: ProductionAuditLedger) -> dict[str, Any]:
        return {
            "ledger_id": ledger.ledger_id,
            "production_id": ledger.production_id,
            "schema_version": ledger.schema_version,
            "entries": [ProductionAuditSerializer.entry_to_dict(item) for item in ledger.entries],
            "metadata": dict(ledger.metadata),
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> ProductionAuditLedger:
        return ProductionAuditLedger(
            ledger_id=str(raw["ledger_id"]),
            production_id=str(raw["production_id"]),
            entries=tuple(
                ProductionAuditSerializer.entry_from_dict(item) for item in raw.get("entries", [])
            ),
            schema_version=str(raw.get("schema_version", "1.0")),
            metadata={str(key): str(value) for key, value in raw.get("metadata", {}).items()},
        )

    @staticmethod
    def entry_to_dict(entry: ProductionAuditEntry) -> dict[str, Any]:
        return {
            "entry_id": entry.entry_id,
            "event_type": entry.event_type.value,
            "occurred_at": entry.occurred_at.isoformat(),
            "actor_id": entry.actor_id,
            "message": entry.message,
            "provenance": ProductionAuditSerializer.provenance_to_dict(entry.provenance),
            "previous_checksum": entry.previous_checksum,
            "checksum": entry.checksum,
            "metadata": [list(item) for item in entry.metadata],
        }

    @staticmethod
    def entry_from_dict(raw: dict[str, Any]) -> ProductionAuditEntry:
        return ProductionAuditEntry(
            entry_id=str(raw["entry_id"]),
            event_type=AuditEventType(str(raw["event_type"])),
            occurred_at=datetime.fromisoformat(str(raw["occurred_at"])),
            actor_id=str(raw["actor_id"]),
            message=str(raw["message"]),
            provenance=ProductionAuditSerializer.provenance_from_dict(raw["provenance"]),
            previous_checksum=_optional_text(raw.get("previous_checksum")),
            checksum=str(raw["checksum"]),
            metadata=_metadata(raw.get("metadata", [])),
        )

    @staticmethod
    def provenance_to_dict(value: ProductionProvenance) -> dict[str, Any]:
        return {
            "production_id": value.production_id,
            "episode_id": value.episode_id,
            "clip_id": value.clip_id,
            "job_id": value.job_id,
            "captured_at": value.captured_at.isoformat(),
            "artifacts": {
                **_artifact_scalars(value.artifacts),
                "asset_ids": list(value.artifacts.asset_ids),
                "reference_ids": list(value.artifacts.reference_ids),
                "prompt_package_ids": list(value.artifacts.prompt_package_ids),
                "components": [_component_to_dict(item) for item in value.artifacts.components],
            },
            "render": {
                **_render_scalars(value.render),
                "output_paths": list(value.render.output_paths),
                "started_at": _datetime_text(value.render.started_at),
                "completed_at": _datetime_text(value.render.completed_at),
                "machine_metadata": [list(item) for item in value.render.machine_metadata],
            },
            "metadata": [list(item) for item in value.metadata],
        }

    @staticmethod
    def provenance_from_dict(raw: dict[str, Any]) -> ProductionProvenance:
        artifacts = raw["artifacts"]
        render = raw["render"]
        return ProductionProvenance(
            production_id=str(raw["production_id"]),
            episode_id=str(raw["episode_id"]),
            clip_id=str(raw["clip_id"]),
            job_id=str(raw["job_id"]),
            captured_at=datetime.fromisoformat(str(raw["captured_at"])),
            artifacts=_artifact_from_dict(artifacts),
            render=_render_from_dict(render),
            metadata=_metadata(raw.get("metadata", [])),
        )

    @staticmethod
    def _require_valid(ledger: ProductionAuditLedger) -> None:
        result = ProductionAuditValidator().validate(ledger)
        if not result.passed:
            raise ProductionAuditError("; ".join(item.message for item in result.issues))


def _artifact_scalars(value: ArtifactProvenance) -> dict[str, str]:
    return {
        "story_version": value.story_version,
        "ssie_version": value.ssie_version,
        "acpp_version": value.acpp_version,
        "bundle_schema_version": value.bundle_schema_version,
        "package_checksum": value.package_checksum,
        "prompt_checksum": value.prompt_checksum,
        "render_job_checksum": value.render_job_checksum,
        "bundle_checksum": value.bundle_checksum,
    }


def _render_scalars(value: RenderProvenance) -> dict[str, Any]:
    return {
        "executor_id": value.executor_id,
        "worker_id": value.worker_id,
        "seed_policy": value.seed_policy,
        "fixed_seed": value.fixed_seed,
        "width": value.width,
        "height": value.height,
        "frames_per_second": value.frames_per_second,
        "frame_count": value.frame_count,
        "quality_mode": value.quality_mode,
        "duration_seconds": value.duration_seconds,
        "succeeded": value.succeeded,
        "error_code": value.error_code,
        "error_message": value.error_message,
    }


def _component_to_dict(value: VersionedComponent) -> dict[str, Any]:
    return {
        "component_type": value.component_type,
        "component_id": value.component_id,
        "version": value.version,
        "checksum": value.checksum,
        "metadata": [list(item) for item in value.metadata],
    }


def _artifact_from_dict(raw: dict[str, Any]) -> ArtifactProvenance:
    return ArtifactProvenance(
        story_version=str(raw["story_version"]),
        ssie_version=str(raw["ssie_version"]),
        acpp_version=str(raw["acpp_version"]),
        bundle_schema_version=str(raw["bundle_schema_version"]),
        package_checksum=str(raw["package_checksum"]),
        prompt_checksum=str(raw["prompt_checksum"]),
        render_job_checksum=str(raw["render_job_checksum"]),
        bundle_checksum=str(raw["bundle_checksum"]),
        asset_ids=tuple(str(item) for item in raw.get("asset_ids", [])),
        reference_ids=tuple(str(item) for item in raw.get("reference_ids", [])),
        prompt_package_ids=tuple(str(item) for item in raw.get("prompt_package_ids", [])),
        components=tuple(
            VersionedComponent(
                component_type=str(item["component_type"]),
                component_id=str(item["component_id"]),
                version=str(item["version"]),
                checksum=_optional_text(item.get("checksum")),
                metadata=_metadata(item.get("metadata", [])),
            )
            for item in raw.get("components", [])
        ),
    )


def _render_from_dict(raw: dict[str, Any]) -> RenderProvenance:
    return RenderProvenance(
        executor_id=str(raw["executor_id"]),
        worker_id=str(raw["worker_id"]),
        seed_policy=str(raw["seed_policy"]),
        fixed_seed=None if raw.get("fixed_seed") is None else int(raw["fixed_seed"]),
        width=int(raw["width"]),
        height=int(raw["height"]),
        frames_per_second=int(raw["frames_per_second"]),
        frame_count=int(raw["frame_count"]),
        quality_mode=str(raw["quality_mode"]),
        output_paths=tuple(str(item) for item in raw.get("output_paths", [])),
        started_at=_optional_datetime(raw.get("started_at")),
        completed_at=_optional_datetime(raw.get("completed_at")),
        duration_seconds=(
            None if raw.get("duration_seconds") is None else float(raw["duration_seconds"])
        ),
        succeeded=None if raw.get("succeeded") is None else bool(raw["succeeded"]),
        error_code=_optional_text(raw.get("error_code")),
        error_message=_optional_text(raw.get("error_message")),
        machine_metadata=_metadata(raw.get("machine_metadata", [])),
    )


def _issue(code: str, message: str, entry: ProductionAuditEntry) -> AuditValidationIssue:
    return AuditValidationIssue(code, message, entry.entry_id)


def _duration(execution: ExecutionResult | None) -> float | None:
    if execution is None:
        return None
    return max(0.0, (execution.completed_at - execution.started_at).total_seconds())


def _error_code(execution: ExecutionResult | None) -> str | None:
    if execution is None or execution.error_code is None:
        return None
    return execution.error_code.value


def _metadata(value: Any) -> tuple[tuple[str, str], ...]:
    return tuple((str(key), str(item)) for key, item in value)


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _datetime_text(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else datetime.fromisoformat(str(value))
