"""Provider-selectable production readiness authority for Phase 20.18.2.3.6.6."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum


class ProviderExecutionReadinessState(StrEnum):
    """Operator-visible readiness state for one selected provider/profile."""

    BLOCKED = "blocked"
    READY = "ready"
    QC_REQUIRED = "qc_required"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class ProviderExecutionReadiness:
    """Immutable preflight result for governed provider-selectable span execution."""

    task_id: str
    shot_id: str
    execution_profile: str
    provider_profile_id: str
    provider_profile_fingerprint: str
    execution_adapter_id: str
    package_fingerprint: str
    timed_span_state: str
    span_count: int
    requirement_count: int
    approved_keyframe_count: int
    state: ProviderExecutionReadinessState
    blockers: tuple[str, ...] = ()
    provider_plan_id: str | None = None
    provider_plan_fingerprint: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "task_id",
            "shot_id",
            "execution_profile",
            "provider_profile_id",
            "provider_profile_fingerprint",
            "execution_adapter_id",
            "package_fingerprint",
            "timed_span_state",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"Provider execution readiness requires {field_name}")
            object.__setattr__(self, field_name, value)
        if self.span_count < 0 or self.requirement_count < 0 or self.approved_keyframe_count < 0:
            raise ValueError("Provider execution readiness counts cannot be negative")
        normalized_blockers = tuple(str(item).strip() for item in self.blockers if str(item).strip())
        object.__setattr__(self, "blockers", normalized_blockers)
        if self.state is ProviderExecutionReadinessState.READY and normalized_blockers:
            raise ValueError("Ready provider execution cannot contain blockers")
        if self.state is ProviderExecutionReadinessState.BLOCKED and not normalized_blockers:
            raise ValueError("Blocked provider execution requires at least one blocker")
        if self.schema_version != "1.0":
            raise ValueError("Provider execution readiness requires schema version 1.0")

    @property
    def ready_to_execute(self) -> bool:
        return self.state is ProviderExecutionReadinessState.READY

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            self._authority_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def readiness_id(self) -> str:
        return f"PER-{self.fingerprint[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "shot_id": self.shot_id,
            "execution_profile": self.execution_profile,
            "provider_profile_id": self.provider_profile_id,
            "provider_profile_fingerprint": self.provider_profile_fingerprint,
            "execution_adapter_id": self.execution_adapter_id,
            "package_fingerprint": self.package_fingerprint,
            "timed_span_state": self.timed_span_state,
            "span_count": self.span_count,
            "requirement_count": self.requirement_count,
            "approved_keyframe_count": self.approved_keyframe_count,
            "state": self.state.value,
            "blockers": list(self.blockers),
            "provider_plan_id": self.provider_plan_id,
            "provider_plan_fingerprint": self.provider_plan_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["readiness_id"] = self.readiness_id
        payload["fingerprint"] = self.fingerprint
        return payload
