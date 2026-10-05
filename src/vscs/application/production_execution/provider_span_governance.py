"""Provider-neutral span metadata governance for Phase 20.18.2.3.6.4f.1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.production_execution.provider_temporal_span_execution import (
    ProviderTemporalSpanExecutionCompiler,
    ProviderTemporalSpanExecutionError,
)


class ProviderSpanGovernanceError(ValueError):
    """Raised when provider-span metadata cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class ProviderSpanGovernance:
    """Provider-neutral execution facts for one governed internal render span."""

    span_id: str
    sequence_number: int
    global_start_frame: int
    global_through_frame: int
    local_start_frame: int
    local_through_frame: int
    local_frame_count: int
    active_asset_ids: tuple[str, ...]
    active_character_asset_ids: tuple[str, ...]
    introduced_asset_ids: tuple[str, ...]
    introduced_character_asset_ids: tuple[str, ...]
    future_asset_ids: tuple[str, ...]
    future_character_asset_ids: tuple[str, ...]
    exact_active_character_count: int
    has_character_introduction: bool
    source_execution_id: str
    source_execution_plan_fingerprint: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        span_id = self.span_id.strip()
        if not span_id:
            raise ProviderSpanGovernanceError("Provider-span governance requires span_id")
        object.__setattr__(self, "span_id", span_id)

        if self.schema_version != "1.0":
            raise ProviderSpanGovernanceError(
                "Provider-span governance requires schema version 1.0"
            )
        if self.sequence_number <= 0:
            raise ProviderSpanGovernanceError("Provider-span governance sequence must be positive")
        if self.global_start_frame < 0 or self.global_through_frame < self.global_start_frame:
            raise ProviderSpanGovernanceError(
                "Provider-span governance has an invalid global frame interval"
            )
        if self.local_start_frame != 0:
            raise ProviderSpanGovernanceError(
                "Provider-span governance local frame authority must begin at zero"
            )
        if self.local_frame_count <= 0 or self.local_through_frame != self.local_frame_count - 1:
            raise ProviderSpanGovernanceError(
                "Provider-span governance local frame interval is inconsistent"
            )
        if self.local_frame_count != self.global_through_frame - self.global_start_frame + 1:
            raise ProviderSpanGovernanceError(
                "Provider-span governance local and global frame counts differ"
            )

        for field_name in (
            "active_asset_ids",
            "active_character_asset_ids",
            "introduced_asset_ids",
            "introduced_character_asset_ids",
            "future_asset_ids",
            "future_character_asset_ids",
        ):
            values = tuple(str(value).strip().upper() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise ProviderSpanGovernanceError(
                    f"Provider-span governance {field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise ProviderSpanGovernanceError(
                    f"Provider-span governance {field_name} cannot contain duplicates"
                )
            object.__setattr__(self, field_name, values)

        active = set(self.active_asset_ids)
        active_characters = set(self.active_character_asset_ids)
        introduced = set(self.introduced_asset_ids)
        introduced_characters = set(self.introduced_character_asset_ids)
        future = set(self.future_asset_ids)
        future_characters = set(self.future_character_asset_ids)

        if not active_characters.issubset(active):
            raise ProviderSpanGovernanceError("Active character assets must be active in the span")
        if not introduced.issubset(active):
            raise ProviderSpanGovernanceError(
                "Introduced assets must be active in their target span"
            )
        if not introduced_characters.issubset(introduced & active_characters):
            raise ProviderSpanGovernanceError(
                "Introduced character assets must be introduced active characters"
            )
        if not future_characters.issubset(future):
            raise ProviderSpanGovernanceError("Future character assets must be future assets")
        if active & future:
            raise ProviderSpanGovernanceError(
                "Future assets must be structurally absent from the active span"
            )
        if self.exact_active_character_count != len(self.active_character_asset_ids):
            raise ProviderSpanGovernanceError(
                "Exact active character count does not match active character assets"
            )
        if self.has_character_introduction != bool(self.introduced_character_asset_ids):
            raise ProviderSpanGovernanceError(
                "Character introduction flag does not match introduced character assets"
            )

        execution_id = self.source_execution_id.strip()
        fingerprint = self.source_execution_plan_fingerprint.strip().lower()
        if not execution_id or not fingerprint:
            raise ProviderSpanGovernanceError(
                "Provider-span governance requires source execution identity and fingerprint"
            )
        object.__setattr__(self, "source_execution_id", execution_id)
        object.__setattr__(self, "source_execution_plan_fingerprint", fingerprint)

    @property
    def governance_id(self) -> str:
        return (
            f"PSG-{self.sequence_number:03d}-{_fingerprint(self._authority_payload())[:12].upper()}"
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "global_start_frame": self.global_start_frame,
            "global_through_frame": self.global_through_frame,
            "local_start_frame": self.local_start_frame,
            "local_through_frame": self.local_through_frame,
            "local_frame_count": self.local_frame_count,
            "active_asset_ids": list(self.active_asset_ids),
            "active_character_asset_ids": list(self.active_character_asset_ids),
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "introduced_character_asset_ids": list(self.introduced_character_asset_ids),
            "future_asset_ids": list(self.future_asset_ids),
            "future_character_asset_ids": list(self.future_character_asset_ids),
            "exact_active_character_count": self.exact_active_character_count,
            "has_character_introduction": self.has_character_introduction,
            "source_execution_id": self.source_execution_id,
            "source_execution_plan_fingerprint": (self.source_execution_plan_fingerprint),
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["governance_id"] = self.governance_id
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ProviderSpanGovernance:
        item = cls(
            span_id=str(raw.get("span_id") or ""),
            sequence_number=_required_int(raw, "sequence_number"),
            global_start_frame=_required_int(raw, "global_start_frame"),
            global_through_frame=_required_int(raw, "global_through_frame"),
            local_start_frame=_required_int(raw, "local_start_frame"),
            local_through_frame=_required_int(raw, "local_through_frame"),
            local_frame_count=_required_int(raw, "local_frame_count"),
            active_asset_ids=_string_tuple(raw, "active_asset_ids"),
            active_character_asset_ids=_string_tuple(raw, "active_character_asset_ids"),
            introduced_asset_ids=_string_tuple(raw, "introduced_asset_ids"),
            introduced_character_asset_ids=_string_tuple(raw, "introduced_character_asset_ids"),
            future_asset_ids=_string_tuple(raw, "future_asset_ids"),
            future_character_asset_ids=_string_tuple(raw, "future_character_asset_ids"),
            exact_active_character_count=_required_int(raw, "exact_active_character_count"),
            has_character_introduction=_required_bool(raw, "has_character_introduction"),
            source_execution_id=str(raw.get("source_execution_id") or ""),
            source_execution_plan_fingerprint=str(
                raw.get("source_execution_plan_fingerprint") or ""
            ),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied_id = str(raw.get("governance_id") or "").strip()
        if supplied_id and supplied_id != item.governance_id:
            raise ProviderSpanGovernanceError(
                "Provider-span governance identity does not match governed content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != item.fingerprint:
            raise ProviderSpanGovernanceError(
                "Provider-span governance fingerprint does not match governed content"
            )
        return item


@dataclass(frozen=True, slots=True)
class ProviderSpanGovernancePlan:
    """Complete provider-neutral span metadata governance for one Shot."""

    shot_id: str
    source_package_fingerprint: str
    source_execution_plan_fingerprint: str
    spans: tuple[ProviderSpanGovernance, ...]
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise ProviderSpanGovernanceError("Provider-span governance plan requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        if self.schema_version != "1.0" or self.provider_neutral is not True:
            raise ProviderSpanGovernanceError(
                "Provider-span governance plan must remain provider-neutral schema 1.0"
            )

        package_fingerprint = self.source_package_fingerprint.strip().lower()
        execution_fingerprint = self.source_execution_plan_fingerprint.strip().lower()
        if not package_fingerprint or not execution_fingerprint:
            raise ProviderSpanGovernanceError(
                "Provider-span governance plan requires source fingerprints"
            )
        object.__setattr__(self, "source_package_fingerprint", package_fingerprint)
        object.__setattr__(self, "source_execution_plan_fingerprint", execution_fingerprint)

        if not self.spans:
            raise ProviderSpanGovernanceError(
                "Provider-span governance plan requires at least one span"
            )
        expected_global_start = 0
        for index, span in enumerate(self.spans, start=1):
            if span.sequence_number != index:
                raise ProviderSpanGovernanceError(
                    "Provider-span governance sequence is not contiguous"
                )
            if span.global_start_frame != expected_global_start:
                raise ProviderSpanGovernanceError(
                    "Provider-span governance contains a global gap or overlap"
                )
            if span.source_execution_plan_fingerprint != self.source_execution_plan_fingerprint:
                raise ProviderSpanGovernanceError(
                    "Provider-span governance source execution fingerprint is inconsistent"
                )
            expected_global_start = span.global_through_frame + 1

    @property
    def plan_id(self) -> str:
        return f"PSGPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_neutral": self.provider_neutral,
            "shot_id": self.shot_id,
            "source_package_fingerprint": self.source_package_fingerprint,
            "source_execution_plan_fingerprint": (self.source_execution_plan_fingerprint),
            "spans": [span.to_dict() for span in self.spans],
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ProviderSpanGovernancePlan:
        spans_raw = raw.get("spans")
        if not isinstance(spans_raw, list):
            raise ProviderSpanGovernanceError(
                "Provider-span governance plan spans must be an array"
            )
        spans = tuple(
            ProviderSpanGovernance.from_dict(dict(item))
            for item in spans_raw
            if isinstance(item, dict)
        )
        if len(spans) != len(spans_raw):
            raise ProviderSpanGovernanceError(
                "Every provider-span governance entry must be an object"
            )
        provider_neutral = raw.get("provider_neutral", True)
        if not isinstance(provider_neutral, bool):
            raise ProviderSpanGovernanceError("provider_neutral must be a boolean")
        plan = cls(
            shot_id=str(raw.get("shot_id") or ""),
            source_package_fingerprint=str(raw.get("source_package_fingerprint") or ""),
            source_execution_plan_fingerprint=str(
                raw.get("source_execution_plan_fingerprint") or ""
            ),
            spans=spans,
            schema_version=str(raw.get("schema_version") or "1.0"),
            provider_neutral=provider_neutral,
        )
        supplied_id = str(raw.get("plan_id") or "").strip()
        if supplied_id and supplied_id != plan.plan_id:
            raise ProviderSpanGovernanceError(
                "Provider-span governance plan identity does not match governed content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != plan.fingerprint:
            raise ProviderSpanGovernanceError(
                "Provider-span governance plan fingerprint does not match governed content"
            )
        return plan

    def require_source(self, compiled: CompiledProductionPackage) -> None:
        if compiled.package_fingerprint.strip().lower() != self.source_package_fingerprint:
            raise ProviderSpanGovernanceError(
                "Provider-span governance source package fingerprint changed"
            )
        expected = ProviderSpanGovernanceCompiler().compile(compiled)
        if expected.fingerprint != self.fingerprint:
            raise ProviderSpanGovernanceError(
                "Provider-span governance no longer matches compiled sources"
            )


class ProviderSpanGovernanceCompiler:
    """Compile provider-neutral metadata facts from governed temporal authority."""

    def compile(
        self,
        compiled: CompiledProductionPackage,
    ) -> ProviderSpanGovernancePlan:
        try:
            execution_plan = ProviderTemporalSpanExecutionCompiler().compile(compiled)
        except ProviderTemporalSpanExecutionError as exc:
            raise ProviderSpanGovernanceError(
                f"Provider-span governance source authority is invalid: {exc}"
            ) from exc

        asset_kinds = self._asset_kinds(compiled)
        reference_assets = self._reference_asset_map(compiled.reference_plan)

        spans: list[ProviderSpanGovernance] = []
        for execution in execution_plan.executions:
            introduced_asset_ids = self._assets_for_references(
                execution.introduced_reference_ids,
                reference_assets,
            )
            future_asset_ids = self._assets_for_references(
                execution.future_reference_ids,
                reference_assets,
            )
            active_character_ids = self._characters(
                execution.active_asset_ids,
                asset_kinds,
            )
            introduced_character_ids = self._characters(
                introduced_asset_ids,
                asset_kinds,
            )
            future_character_ids = self._characters(
                future_asset_ids,
                asset_kinds,
            )
            spans.append(
                ProviderSpanGovernance(
                    span_id=execution.span_id,
                    sequence_number=execution.sequence_number,
                    global_start_frame=execution.global_start_frame,
                    global_through_frame=execution.global_through_frame,
                    local_start_frame=0,
                    local_through_frame=execution.governed_frame_count - 1,
                    local_frame_count=execution.governed_frame_count,
                    active_asset_ids=execution.active_asset_ids,
                    active_character_asset_ids=active_character_ids,
                    introduced_asset_ids=introduced_asset_ids,
                    introduced_character_asset_ids=introduced_character_ids,
                    future_asset_ids=future_asset_ids,
                    future_character_asset_ids=future_character_ids,
                    exact_active_character_count=len(active_character_ids),
                    has_character_introduction=bool(introduced_character_ids),
                    source_execution_id=execution.execution_id,
                    source_execution_plan_fingerprint=execution_plan.fingerprint,
                )
            )

        return ProviderSpanGovernancePlan(
            shot_id=compiled.shot_id,
            source_package_fingerprint=compiled.package_fingerprint,
            source_execution_plan_fingerprint=execution_plan.fingerprint,
            spans=tuple(spans),
        )

    @staticmethod
    def _asset_kinds(compiled: CompiledProductionPackage) -> dict[str, str]:
        raw = compiled.timed_asset_presence
        if not isinstance(raw, dict):
            raise ProviderSpanGovernanceError(
                "Provider-span governance requires Timed Asset Presence authority"
            )
        presences = raw.get("presences")
        if not isinstance(presences, list):
            raise ProviderSpanGovernanceError("Timed Asset Presence records must be an array")

        kinds: dict[str, str] = {}
        for presence in presences:
            if not isinstance(presence, dict):
                continue
            asset_id = str(presence.get("asset_id") or "").strip().upper()
            asset_kind = str(presence.get("asset_kind") or "").strip().casefold()
            if asset_id and asset_kind:
                kinds[asset_id] = asset_kind
        return kinds

    @staticmethod
    def _reference_asset_map(
        reference_plan: dict[str, Any] | None,
    ) -> dict[str, str]:
        if not isinstance(reference_plan, dict):
            raise ProviderSpanGovernanceError(
                "Provider-span governance requires a governed ReferencePlan"
            )
        raw = reference_plan.get("references")
        if not isinstance(raw, list):
            raise ProviderSpanGovernanceError("Governed ReferencePlan references must be an array")

        result: dict[str, str] = {}
        for reference in raw:
            if not isinstance(reference, dict):
                raise ProviderSpanGovernanceError("Every governed reference must be an object")
            reference_id = str(reference.get("reference_id") or "").strip()
            asset_id = str(reference.get("asset_id") or "").strip().upper()
            if not reference_id or not asset_id:
                continue
            if reference_id in result and result[reference_id] != asset_id:
                raise ProviderSpanGovernanceError(
                    f"Governed reference {reference_id} maps to multiple assets"
                )
            result[reference_id] = asset_id
        return result

    @staticmethod
    def _assets_for_references(
        reference_ids: tuple[str, ...],
        reference_assets: dict[str, str],
    ) -> tuple[str, ...]:
        assets: list[str] = []
        for reference_id in reference_ids:
            asset_id = reference_assets.get(reference_id)
            if not asset_id:
                raise ProviderSpanGovernanceError(
                    f"Governed reference {reference_id} has no asset mapping"
                )
            if asset_id not in assets:
                assets.append(asset_id)
        return tuple(assets)

    @staticmethod
    def _characters(
        asset_ids: tuple[str, ...],
        asset_kinds: dict[str, str],
    ) -> tuple[str, ...]:
        characters: list[str] = []
        for asset_id in asset_ids:
            kind = asset_kinds.get(asset_id)
            if kind is None:
                raise ProviderSpanGovernanceError(
                    f"Active provider asset {asset_id} has no Timed Asset Presence kind"
                )
            if kind == "character":
                characters.append(asset_id)
        return tuple(characters)


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool):
        raise ProviderSpanGovernanceError(f"{key} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ProviderSpanGovernanceError(f"{key} must be an integer") from exc
    raise ProviderSpanGovernanceError(f"{key} must be an integer")


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ProviderSpanGovernanceError(f"{key} must be a boolean")
    return value


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ProviderSpanGovernanceError(f"{key} must be an array")
    return tuple(str(item) for item in value)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
