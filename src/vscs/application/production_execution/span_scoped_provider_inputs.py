"""Span-scoped provider prompt and reference compilation for Phase 20.18.2.3.6.4b."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.production_execution.provider_temporal_span_execution import (
    ProviderTemporalSpanExecution,
    ProviderTemporalSpanExecutionCompiler,
    ProviderTemporalSpanExecutionError,
    ProviderTemporalSpanExecutionPlan,
)


class SpanScopedProviderCompilationError(ValueError):
    """Raised when span-scoped provider inputs cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class SpanReferenceSlot:
    """One deterministic provider picture slot for an active canonical reference."""

    picture_index: int
    picture_tag: str
    reference_id: str
    asset_id: str
    role: str
    source_path: str
    semantic_label: str

    def __post_init__(self) -> None:
        if self.picture_index <= 0:
            raise SpanScopedProviderCompilationError("Picture slot index must be positive")
        expected_tag = f"<Picture {self.picture_index}>"
        if self.picture_tag != expected_tag:
            raise SpanScopedProviderCompilationError(
                "Picture slot tag does not match its deterministic index"
            )
        for field_name in (
            "reference_id",
            "asset_id",
            "role",
            "source_path",
            "semantic_label",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise SpanScopedProviderCompilationError(
                    f"Picture slot requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

    def to_dict(self) -> dict[str, object]:
        return {
            "picture_index": self.picture_index,
            "picture_tag": self.picture_tag,
            "reference_id": self.reference_id,
            "asset_id": self.asset_id,
            "role": self.role,
            "source_path": self.source_path,
            "semantic_label": self.semantic_label,
        }


@dataclass(frozen=True, slots=True)
class SpanScopedProviderInputs:
    """Provider-facing prompt and reference authority for one temporal execution span."""

    span_id: str
    sequence_number: int
    positive_prompt: str
    negative_prompt: str
    motion_prompt: str
    reference_slots: tuple[SpanReferenceSlot, ...]
    active_asset_ids: tuple[str, ...]
    active_reference_ids: tuple[str, ...]
    omitted_future_aliases: tuple[str, ...]
    source_execution_id: str
    source_execution_plan_fingerprint: str
    compiler: str = "span-scoped-provider-v1"

    def __post_init__(self) -> None:
        if not self.span_id.strip():
            raise SpanScopedProviderCompilationError("Span-scoped inputs require span_id")
        if self.sequence_number <= 0:
            raise SpanScopedProviderCompilationError(
                "Span-scoped inputs require a positive sequence number"
            )
        for field_name in (
            "positive_prompt",
            "negative_prompt",
            "motion_prompt",
            "source_execution_id",
            "source_execution_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise SpanScopedProviderCompilationError(
                    f"Span-scoped inputs require {field_name}"
                )
            object.__setattr__(self, field_name, value)

        for field_name in (
            "active_asset_ids",
            "active_reference_ids",
            "omitted_future_aliases",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise SpanScopedProviderCompilationError(
                    f"Span-scoped inputs {field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise SpanScopedProviderCompilationError(
                    f"Span-scoped inputs {field_name} cannot contain duplicates"
                )
            object.__setattr__(self, field_name, values)

        slot_reference_ids = tuple(slot.reference_id for slot in self.reference_slots)
        if slot_reference_ids != self.active_reference_ids:
            raise SpanScopedProviderCompilationError(
                "Picture slots must exactly match active references in deterministic order"
            )
        if tuple(slot.picture_index for slot in self.reference_slots) != tuple(
            range(1, len(self.reference_slots) + 1)
        ):
            raise SpanScopedProviderCompilationError(
                "Picture slots must be contiguous from Picture 1"
            )

    @property
    def input_id(self) -> str:
        return f"SSPI-{self.span_id}-{_fingerprint(self._authority_payload())[:12].upper()}"

    @property
    def reference_slot_fingerprint(self) -> str:
        return _fingerprint([slot.to_dict() for slot in self.reference_slots])

    @property
    def prompt_fingerprint(self) -> str:
        return _fingerprint(
            {
                "positive_prompt": self.positive_prompt,
                "negative_prompt": self.negative_prompt,
                "motion_prompt": self.motion_prompt,
            }
        )

    def _authority_payload(self) -> dict[str, object]:
        return {
            "compiler": self.compiler,
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "motion_prompt": self.motion_prompt,
            "reference_slots": [slot.to_dict() for slot in self.reference_slots],
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "omitted_future_aliases": list(self.omitted_future_aliases),
            "source_execution_id": self.source_execution_id,
            "source_execution_plan_fingerprint": self.source_execution_plan_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["input_id"] = self.input_id
        payload["reference_slot_fingerprint"] = self.reference_slot_fingerprint
        payload["prompt_fingerprint"] = self.prompt_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class SpanScopedProviderInputPlan:
    """Complete span-scoped provider inputs for one editorial Shot."""

    shot_id: str
    source_package_fingerprint: str
    source_execution_plan_fingerprint: str
    spans: tuple[SpanScopedProviderInputs, ...]
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise SpanScopedProviderCompilationError(
                "Span-scoped input plan requires shot_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        if self.schema_version != "1.0" or self.provider_neutral is not True:
            raise SpanScopedProviderCompilationError(
                "Span-scoped input plan must remain provider-neutral schema 1.0"
            )
        if not self.spans:
            raise SpanScopedProviderCompilationError(
                "Span-scoped input plan requires at least one span"
            )
        for field_name in (
            "source_package_fingerprint",
            "source_execution_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise SpanScopedProviderCompilationError(
                    f"Span-scoped input plan requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

        for index, span in enumerate(self.spans, start=1):
            if span.sequence_number != index:
                raise SpanScopedProviderCompilationError(
                    "Span-scoped input sequence is not contiguous"
                )
            if span.source_execution_plan_fingerprint != self.source_execution_plan_fingerprint:
                raise SpanScopedProviderCompilationError(
                    "Span-scoped input source execution fingerprint is inconsistent"
                )

    @property
    def plan_id(self) -> str:
        return f"SSPIPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_neutral": self.provider_neutral,
            "shot_id": self.shot_id,
            "source_package_fingerprint": self.source_package_fingerprint,
            "source_execution_plan_fingerprint": self.source_execution_plan_fingerprint,
            "spans": [span.to_dict() for span in self.spans],
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload

    def require_source(self, compiled: CompiledProductionPackage) -> None:
        if compiled.package_fingerprint.strip().lower() != self.source_package_fingerprint:
            raise SpanScopedProviderCompilationError(
                "Span-scoped input source package fingerprint changed"
            )
        expected = SpanScopedProviderInputCompiler().compile(compiled)
        if expected.fingerprint != self.fingerprint:
            raise SpanScopedProviderCompilationError(
                "Span-scoped provider inputs no longer match compiled sources"
            )


class SpanScopedProviderInputCompiler:
    """Compile exact reference slots and prompts independently for each governed span."""

    _ASSET_NAME_FIELDS = (
        "name",
        "label",
        "display_name",
        "canonical_name",
        "character_name",
        "title",
    )
    _REFERENCE_LABEL_FIELDS = ("label", "name", "display_name", "canonical_name")
    _ALIAS_STOP_WORDS = frozenset(
        {
            "the",
            "and",
            "for",
            "with",
            "from",
            "into",
            "reference",
            "identity",
            "primary",
            "secondary",
            "environment",
            "character",
            "asset",
        }
    )

    def compile(self, compiled: CompiledProductionPackage) -> SpanScopedProviderInputPlan:
        try:
            execution_plan = ProviderTemporalSpanExecutionCompiler().compile(compiled)
        except ProviderTemporalSpanExecutionError as exc:
            raise SpanScopedProviderCompilationError(
                f"Span-scoped provider compilation source authority is invalid: {exc}"
            ) from exc

        references = self._reference_records(compiled.reference_plan)
        references_by_id = {
            self._required_text(reference, "reference_id"): reference
            for reference in references
        }
        if len(references_by_id) != len(references):
            raise SpanScopedProviderCompilationError(
                "Governed ReferencePlan contains duplicate reference IDs"
            )

        asset_records = self._asset_records(compiled)
        asset_by_id = {
            self._optional_text(asset.get("asset_id")).upper(): asset
            for asset in asset_records
            if self._optional_text(asset.get("asset_id"))
        }

        all_reference_asset_ids = {
            reference_id: self._required_text(reference, "asset_id").upper()
            for reference_id, reference in references_by_id.items()
        }

        compiled_spans: list[SpanScopedProviderInputs] = []
        for execution in execution_plan.executions:
            future_asset_ids = tuple(
                dict.fromkeys(
                    all_reference_asset_ids[reference_id]
                    for reference_id in execution.future_reference_ids
                    if reference_id in all_reference_asset_ids
                )
            )
            future_aliases = self._future_aliases(
                execution,
                future_asset_ids,
                references_by_id,
                asset_by_id,
            )
            slots = self._reference_slots(
                execution,
                references_by_id,
                asset_by_id,
            )
            positive = self._compile_prompt_channel(
                compiled.positive_prompt,
                future_aliases,
                delimiter="sentence",
            )
            negative = self._compile_prompt_channel(
                compiled.negative_prompt,
                future_aliases,
                delimiter="negative",
            )
            motion = self._compile_prompt_channel(
                compiled.motion_prompt or compiled.positive_prompt,
                future_aliases,
                delimiter="sentence",
            )
            declaration = " ".join(
                f"{slot.picture_tag} is the authoritative reference for {slot.semantic_label}."
                for slot in slots
            )
            positive = " ".join(value for value in (declaration, positive) if value).strip()

            if not positive:
                raise SpanScopedProviderCompilationError(
                    f"Span {execution.span_id} has no safe positive provider prompt"
                )
            if not negative:
                negative = "identity swap; duplicated character; merged identity"
            if not motion:
                motion = "Preserve natural motion and the established composition."

            self._require_no_future_semantics(
                execution,
                future_aliases,
                positive,
                negative,
                motion,
                slots,
            )
            compiled_spans.append(
                SpanScopedProviderInputs(
                    span_id=execution.span_id,
                    sequence_number=execution.sequence_number,
                    positive_prompt=positive,
                    negative_prompt=negative,
                    motion_prompt=motion,
                    reference_slots=slots,
                    active_asset_ids=execution.active_asset_ids,
                    active_reference_ids=execution.active_reference_ids,
                    omitted_future_aliases=future_aliases,
                    source_execution_id=execution.execution_id,
                    source_execution_plan_fingerprint=execution_plan.fingerprint,
                )
            )

        return SpanScopedProviderInputPlan(
            shot_id=compiled.shot_id,
            source_package_fingerprint=compiled.package_fingerprint,
            source_execution_plan_fingerprint=execution_plan.fingerprint,
            spans=tuple(compiled_spans),
        )

    def _reference_slots(
        self,
        execution: ProviderTemporalSpanExecution,
        references_by_id: dict[str, dict[str, Any]],
        asset_by_id: dict[str, dict[str, Any]],
    ) -> tuple[SpanReferenceSlot, ...]:
        slots: list[SpanReferenceSlot] = []
        for picture_index, reference_id in enumerate(execution.active_reference_ids, start=1):
            reference = references_by_id.get(reference_id)
            if reference is None:
                raise SpanScopedProviderCompilationError(
                    f"Active reference {reference_id} is absent from the governed ReferencePlan"
                )
            asset_id = self._required_text(reference, "asset_id").upper()
            if asset_id not in execution.active_asset_ids:
                raise SpanScopedProviderCompilationError(
                    f"Active reference {reference_id} belongs to inactive asset {asset_id}"
                )
            semantic_label = self._semantic_label(
                reference,
                asset_by_id.get(asset_id),
                asset_id,
            )
            slots.append(
                SpanReferenceSlot(
                    picture_index=picture_index,
                    picture_tag=f"<Picture {picture_index}>",
                    reference_id=reference_id,
                    asset_id=asset_id,
                    role=self._required_text(reference, "role"),
                    source_path=self._required_text(reference, "source_path"),
                    semantic_label=semantic_label,
                )
            )
        return tuple(slots)

    def _future_aliases(
        self,
        execution: ProviderTemporalSpanExecution,
        future_asset_ids: tuple[str, ...],
        references_by_id: dict[str, dict[str, Any]],
        asset_by_id: dict[str, dict[str, Any]],
    ) -> tuple[str, ...]:
        aliases: list[str] = []
        for asset_id in future_asset_ids:
            aliases.append(asset_id)
            asset = asset_by_id.get(asset_id)
            if asset is not None:
                for field_name in self._ASSET_NAME_FIELDS:
                    self._append_alias(aliases, asset.get(field_name))
            for reference_id in execution.future_reference_ids:
                reference = references_by_id.get(reference_id)
                if reference is None:
                    continue
                reference_asset_id = self._required_text(reference, "asset_id").upper()
                if reference_asset_id != asset_id:
                    continue
                aliases.append(reference_id)
                for field_name in self._REFERENCE_LABEL_FIELDS:
                    self._append_alias(aliases, reference.get(field_name))

        expanded = list(aliases)
        for alias in aliases:
            for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", alias):
                lowered = token.casefold()
                if lowered not in self._ALIAS_STOP_WORDS:
                    expanded.append(token)
        return tuple(dict.fromkeys(value.strip() for value in expanded if value.strip()))

    def _append_alias(self, aliases: list[str], value: object) -> None:
        text = self._optional_text(value)
        if text:
            aliases.append(text)

    def _semantic_label(
        self,
        reference: dict[str, Any],
        asset: dict[str, Any] | None,
        asset_id: str,
    ) -> str:
        for source, fields in (
            (reference, self._REFERENCE_LABEL_FIELDS),
            (asset or {}, self._ASSET_NAME_FIELDS),
        ):
            for field_name in fields:
                value = self._optional_text(source.get(field_name))
                if value:
                    return value
        return asset_id

    def _compile_prompt_channel(
        self,
        text: str,
        future_aliases: tuple[str, ...],
        *,
        delimiter: str,
    ) -> str:
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return ""
        if delimiter == "negative":
            parts = [part.strip() for part in cleaned.split(";") if part.strip()]
            retained = [
                part
                for part in parts
                if not self._contains_any_alias(part, future_aliases)
            ]
            return "; ".join(retained)
        parts = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", cleaned)
            if part.strip()
        ]
        retained = [
            part for part in parts if not self._contains_any_alias(part, future_aliases)
        ]
        return " ".join(retained)

    def _require_no_future_semantics(
        self,
        execution: ProviderTemporalSpanExecution,
        future_aliases: tuple[str, ...],
        positive: str,
        negative: str,
        motion: str,
        slots: tuple[SpanReferenceSlot, ...],
    ) -> None:
        provider_text = " ".join((positive, negative, motion))
        leaking_aliases = tuple(
            alias
            for alias in future_aliases
            if self._contains_alias(provider_text, alias)
        )
        if leaking_aliases:
            raise SpanScopedProviderCompilationError(
                f"Span {execution.span_id} leaks future asset semantics: "
                + ", ".join(leaking_aliases)
            )
        active_reference_ids = {slot.reference_id for slot in slots}
        leaked_references = set(execution.future_reference_ids) & active_reference_ids
        if leaked_references:
            raise SpanScopedProviderCompilationError(
                f"Span {execution.span_id} leaks future canonical references"
            )

    def _contains_any_alias(self, text: str, aliases: tuple[str, ...]) -> bool:
        return any(self._contains_alias(text, alias) for alias in aliases)

    @staticmethod
    def _contains_alias(text: str, alias: str) -> bool:
        candidate = alias.strip()
        if not candidate:
            return False
        escaped = re.escape(candidate)
        return re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None

    @staticmethod
    def _reference_records(reference_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(reference_plan, dict):
            raise SpanScopedProviderCompilationError(
                "Span-scoped provider compilation requires a governed ReferencePlan"
            )
        raw = reference_plan.get("references")
        if not isinstance(raw, list):
            raise SpanScopedProviderCompilationError(
                "Governed ReferencePlan references must be an array"
            )
        if not all(isinstance(item, dict) for item in raw):
            raise SpanScopedProviderCompilationError(
                "Every governed ReferencePlan reference must be an object"
            )
        return [dict(item) for item in raw]

    def _asset_records(self, compiled: CompiledProductionPackage) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for source in (compiled.production_authority, compiled.composition_plan):
            if not isinstance(source, dict):
                continue
            raw = source.get("assets")
            if isinstance(raw, list):
                records.extend(dict(item) for item in raw if isinstance(item, dict))
        return records

    @staticmethod
    def _required_text(raw: dict[str, Any], key: str) -> str:
        value = str(raw.get(key) or "").strip()
        if not value:
            raise SpanScopedProviderCompilationError(
                f"Governed reference requires {key}"
            )
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
