"""Append-only production audit ledger and provenance snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from vscs.application.acpp import ProductionBundle

from .executors import ExecutionResult, WorkerIdentity


class AuditEventType(StrEnum):
    """Stable production audit event categories."""

    PROVENANCE_CAPTURED = "provenance_captured"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    RECOVERY_APPLIED = "recovery_applied"
    QUALITY_CONTROL = "quality_control"


@dataclass(frozen=True, slots=True)
class VersionedComponent:
    """Versioned model, workflow, LoRA, application, or other component."""

    component_type: str
    component_id: str
    version: str
    checksum: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactProvenance:
    """Immutable provenance for the compiled production artifacts."""

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
    """Runtime provenance for one render execution."""

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
    """Complete traceability record for one production clip."""

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
    """One append-only, hash-chained production audit entry."""

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
    """Versioned append-only production audit ledger."""

    ledger_id: str
    production_id: str
    entries: tuple[ProductionAuditEntry, ...] = ()
    schema_version: str = "1.0"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditValidationIssue:
    """One audit-ledger integrity finding."""

    code: str
    message: str
    entry_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditValidationResult:
    """Result of validating an audit ledger."""

    issues: tuple[AuditValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.issues


class ProductionAuditError(ValueError):
    """Raised for invalid production audit operations or payloads."""


class ProductionAuditService:
    """Capture provenance, append audit entries, query, and report."""

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
        """Create one complete provenance snapshot from a production bundle."""
        current = captured_at or datetime.now(UTC)
        package = bundle.package
        job = bundle.render_job
        asset_ids = tuple(
            dict.fromkeys(binding.asset_id for binding in package.asset_bindings)
        )
        reference_ids = tuple(
            dict.fromkeys(item.reference_id for item in job.input_references)
        )
        render = RenderProvenance(
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
            duration_seconds=self._duration(execution),
            succeeded=None if execution is None else execution.succeeded,
            error_code=(
                None
                if execution is None or execution.error_code is None
                else execution.error_code.value
            ),
            error_message=None if execution is None else execution.error_message,
            machine_metadata=machine_metadata,
        )
        return ProductionProvenance(
            production_id=production_id,
            episode_id=episode_id,
            clip_id=package.identity.clip_id,
            job_id=job.job_id,
            captured_at=current,
            artifacts=ArtifactProvenance(
                story_version=story_version,
                ssie_version=ssie_version,
                acpp_version=package.schema_version,
                bundle_schema_version=bundle.schema_version,
                package_checksum=bundle.package_checksum,
                prompt_checksum=bundle.prompt_checksum,
                render_job_checksum=bundle.render_job_checksum,
                bundle_checksum=bundle.aggregate_checksum,
                asset_ids=asset_ids,
                reference_ids=reference_ids,
                prompt_package_ids=bundle.prompt.prompt_package_ids,
                components=components,
            ),
            render=render,
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
        """Append one checksum-linked entry to a ledger."""
        if provenance.production_id != ledger.production_id:
            raise ProductionAuditError("Provenance production ID does not match ledger")
        if not actor_id.strip():
            raise ProductionAuditError("actor_id must not be empty")
        current = occurred_at or datetime.now(UTC)
        previous = ledger.entries[-1].checksum if ledger.entries else None
        entry_id = f"AUDIT-{len(ledger.entries) + 1:08d}"
        checksum = self.entry_checksum(
            entry_id=entry_id,
            event_type=event_type,
            occurred_at=current,
            actor_id=actor_id,
            message=message,
            provenance=provenance,
            previous_checksum=previous,
            metadata=metadata,
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
        return ProductionAuditLedger(
            ledger_id=ledger.ledger_id,
            production_id=ledger.production_id,
            entries=(*ledger.entries, entry),
            schema_version=ledger.schema_version,
            metadata=dict(ledger.metadata),
        )

    @staticmethod
    def query(
        ledger: ProductionAuditLedger,
        *,
        clip_id: str | None = None,
        job_id: str | None = None,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
    ) -> tuple[ProductionAuditEntry, ...]:
        """Return audit entries matching all supplied filters."""
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
        """Build a concise human-readable audit summary."""
        validation = ProductionAuditValidator().validate(ledger)
        clips = {entry.provenance.clip_id for entry in ledger.entries}
        failures = sum(
            entry.event_type is AuditEventType.EXECUTION_FAILED
            for entry in ledger.entries
        )
        return "\n".join(
            (
                f"Production Audit Ledger: {ledger.ledger_id}",
                f"Production: {ledger.production_id}",
                f"Schema: {ledger.schema_version}",
                f"Entries: {len(ledger.entries)}",
                f"Clips: {len(clips)}",
                f"Execution failures: {failures}",
                f"Integrity: {'PASSED' if validation.passed else 'FAILED'}",
                f"Head checksum: {ledger.entries[-1].checksum if ledger.entries else 'none'}",
            )
        )

    @staticmethod
    def entry_checksum(
        *,
        entry_id: str,
        event_type: AuditEventType,
        occurred_at: datetime,
        actor_id: str,
        message: str,
        provenance: ProductionProvenance,
        previous_checksum: str | None,
        metadata: tuple[tuple[str, str], ...],
    ) -> str:
        """Return the deterministic checksum for one audit entry."""
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

    @staticmethod
    def _duration(execution: ExecutionResult | None) -> float | None:
        if execution is None:
            return None
        return max(
            0.0,
            (execution.completed_at - execution.started_at).total_seconds(),
        )


class ProductionAuditValidator:
    """Validate audit identity, ordering, and checksum-chain integrity."""

    def validate(self, ledger: ProductionAuditLedger) -> AuditValidationResult:
        """Validate one complete production audit ledger."""
        issues: list[AuditValidationIssue] = []
        if not ledger.ledger_id.strip():
            issues.append(AuditValidationIssue("EMPTY_LEDGER_ID", "Ledger ID is empty"))
        if not ledger.production_id.strip():
            issues.append(
                AuditValidationIssue("EMPTY_PRODUCTION_ID", "Production ID is empty")
            )
        previous: str | None = None
        seen: set[str] = set()
        for index, entry in enumerate(ledger.entries, start=1):
            if entry.entry_id in seen:
                issues.append(
                    AuditValidationIssue(
                        "DUPLICATE_ENTRY_ID",
                        f"Duplicate audit entry ID: {entry.entry_id}",
                        entry.entry_id,
                    )
                )
            seen.add(entry.entry_id)
            expected_id = f"AUDIT-{index:08d}"
            if entry.entry_id != expected_id:
                issues.append(
                    AuditValidationIssue(
                        "ENTRY_SEQUENCE_MISMATCH",
                        f"Expected {expected_id}, found {entry.entry_id}",
                        entry.entry_id,
                    )
                )
            if entry.provenance.production_id != ledger.production_id:
                issues.append(
                    AuditValidationIssue(
                        "PRODUCTION_ID_MISMATCH",
                        "Entry provenance does not match ledger production",
                        entry.entry_id,
                    )
                )
            if entry.previous_checksum != previous:
                issues.append(
                    AuditValidationIssue(
                        "CHAIN_LINK_MISMATCH",
                        "Previous checksum does not match prior entry",
                        entry.entry_id,
                    )
                )
            expected_checksum = ProductionAuditService.entry_checksum(
                entry_id=entry.entry_id,
                event_type=entry.event_type,
                occurred_at=entry.occurred_at,
                actor_id=entry.actor_id,
                message=entry.message,
                provenance=entry.provenance,
                previous_checksum=entry.previous_checksum,
                metadata=entry.metadata,
            )
            if entry.checksum != expected_checksum:
                issues.append(
                    AuditValidationIssue(
                        "ENTRY_CHECKSUM_MISMATCH",
                        "Entry checksum does not match entry content",
                        entry.entry_id,
                    )
                )
            previous = entry.checksum
        return AuditValidationResult(tuple(issues))


class ProductionAuditSerializer:
    """Stable JSON serialization for production audit ledgers."""

    def dumps(self, ledger: ProductionAuditLedger) -> str:
        """Serialize a valid audit ledger to stable JSON."""
        self._require_valid(ledger)
        return json.dumps(
            self.to_dict(ledger), indent=2, sort_keys=True, ensure_ascii=False
        ) + "\n"

    def loads(self, payload: str) -> ProductionAuditLedger:
        """Restore and validate an audit ledger from JSON."""
        try:
            raw = json.loads(payload)
            ledger = self.from_dict(raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ProductionAuditError(f"Invalid production audit payload: {exc}") from exc
        self._require_valid(ledger)
        return ledger

    @staticmethod
    def to_dict(ledger: ProductionAuditLedger) -> dict[str, Any]:
        return {
            "schema_version": ledger.schema_version,
            "ledger_id": ledger.ledger_id,
            "production_id": ledger.production_id,
            "entries": [ProductionAuditSerializer.entry_to_dict(item) for item in ledger.entries],
            "metadata": dict(ledger.metadata),
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> ProductionAuditLedger:
        return ProductionAuditLedger(
            ledger_id=str(raw["ledger_id"]),
            production_id=str(raw["production_id"]),
            entries=tuple(
                ProductionAuditSerializer.entry_from_dict(item)
                for item in raw.get("entries", [])
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
            previous_checksum=(
                None
                if raw.get("previous_checksum") is None
                else str(raw["previous_checksum"])
            ),
            checksum=str(raw["checksum"]),
            metadata=tuple((str(key), str(value)) for key, value in raw.get("metadata", [])),
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
                "story_version": value.artifacts.story_version,
                "ssie_version": value.artifacts.ssie_version,
                "acpp_version": value.artifacts.acpp_version,
                "bundle_schema_version": value.artifacts.bundle_schema_version,
                "package_checksum": value.artifacts.package_checksum,
                "prompt_checksum": value.artifacts.prompt_checksum,
                "render_job_checksum": value.artifacts.render_job_checksum,
                "bundle_checksum": value.artifacts.bundle_checksum,
                "asset_ids": list(value.artifacts.asset_ids),
                "reference_ids": list(value.artifacts.reference_ids),
                "prompt_package_ids": list(value.artifacts.prompt_package_ids),
                "components": [
                    {
                        "component_type": item.component_type,
                        "component_id": item.component_id,
                        "version": item.version,
                        "checksum": item.checksum,
                        "metadata": [list(pair) for pair in item.metadata],
                    }
                    for item in value.artifacts.components
                ],
            },
            "render": {
                "executor_id": value.render.executor_id,
                "worker_id": value.render.worker_id,
                "seed_policy": value.render.seed_policy,
                "fixed_seed": value.render.fixed_seed,
                "width": value.render.width,
                "height": value.render.height,
                "frames_per_second": value.render.frames_per_second,
                "frame_count": value.render.frame_count,
                "quality_mode": value.render.quality_mode,
                "output_paths": list(value.render.output_paths),
                "started_at": _datetime_text(value.render.started_at),
                "completed_at": _datetime_text(value.render.completed_at),
                "duration_seconds": value.render.duration_seconds,
                "succeeded": value.render.succeeded,
                "error_code": value.render.error_code,
                "error_message": value.render.error_message,
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
            artifacts=ArtifactProvenance(
                story_version=str(artifacts["story_version"]),
                ssie_version=str(artifacts["ssie_version"]),
                acpp_version=str(artifacts["acpp_version"]),
                bundle_schema_version=str(artifacts["bundle_schema_version"]),
                package_checksum=str(artifacts["package_checksum"]),
                prompt_checksum=str(artifacts["prompt_checksum"]),
                render_job_checksum=str(artifacts["render_job_checksum"]),
                bundle_checksum=str(artifacts["bundle_checksum"]),
                asset_ids=tuple(str(item) for item in artifacts.get("asset_ids", [])),
                reference_ids=tuple(str(item) for item in artifacts.get("reference_ids", [])),
                prompt_package_ids=tuple(
                    str(item) for item in artifacts.get("prompt_package_ids", [])
                ),
                components=tuple(
                    VersionedComponent(
                        component_type=str(item["component_type"]),
                        component_id=str(item["component_id"]),
                        version=str(item["version"]),
                        checksum=(
                            None if item.get("checksum") is None else str(item["checksum"])
                        ),
                        metadata=tuple(
                            (str(key), str(value))
                            for key, value in item.get("metadata", [])
                        ),
                    )
                    for item in artifacts.get("components", [])
                ),
            ),
            render=RenderProvenance(
                executor_id=str(render["executor_id"]),
                worker_id=str(render["worker_id"]),
                seed_policy=str(render["seed_policy"]),
                fixed_seed=(
                    None if render.get("fixed_seed") is None else int(render["fixed_seed"])
                ),
                width=int(render["width"]),
                height=int(render["height"]),
                frames_per_second=int(render["frames_per_second"]),
                frame_count=int(render["frame_count"]),
                quality_mode=str(render["quality_mode"]),
                output_paths=tuple(str(item) for item in render.get("output_paths", [])),
                started_at=_optional_datetime(render.get("started_at")),
                completed_at=_optional_datetime(render.get("completed_at")),
                duration_seconds=(
                    None
                    if render.get("duration_seconds") is None
                    else float(render["duration_seconds"])
                ),
                succeeded=(
                    None if render.get("succeeded") is None else bool(render["succeeded"])
                ),
                error_code=(
                    None if render.get("error_code") is None else str(render["error_code"])
                ),
                error_message=(
                    None
                    if render.get("error_message") is None
                    else str(render["error_message"])
                ),
                machine_metadata=tuple(
                    (str(key), str(value))
                    for key, value in render.get("machine_metadata", [])
                ),
            ),
            metadata=tuple((str(key), str(value)) for key, value in raw.get("metadata", [])),
        )

    @staticmethod
    def _require_valid(ledger: ProductionAuditLedger) -> None:
        result = ProductionAuditValidator().validate(ledger)
        if not result.passed:
            summary = "; ".join(issue.message for issue in result.issues)
            raise ProductionAuditError(summary)


def _datetime_text(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else datetime.fromisoformat(str(value))
