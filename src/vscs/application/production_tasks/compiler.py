"""Deterministic provider-neutral ProductionTask compilation for Phase 19.6.2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from vscs.application.production_package import ProductionPackageService
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionStatus,
)

from .governance import ProductionTaskGovernanceService
from .models import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)


class ProductionTaskCompilationError(RuntimeError):
    """Raised when governed UPD authority cannot be compiled safely into tasks."""


@dataclass(frozen=True, slots=True)
class ProductionTaskCompilationContext:
    """Explicit governed scope needed because legacy UPD storage does not yet own it."""

    production_id: str
    episode_id: str
    approved_by: str
    authority_revision: int
    scene_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("production_id", self.production_id),
            ("episode_id", self.episode_id),
            ("approved_by", self.approved_by),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be blank")
        if self.authority_revision < 1:
            raise ValueError("authority_revision must be at least 1")


class ProductionTaskCompilerService:
    """Compile current approved UPD shot authority into immutable ProductionTasks.

    Phase 19.6.2 intentionally compiles only the primary shot VIDEO_GENERATION task.
    Voice, lip-sync, audio, QC, repair and assembly decomposition remain later governed
    compilation work rather than being inferred speculatively from legacy UPD fields.
    """

    def __init__(
        self,
        universal: UniversalProductionDescriptionCompilerService,
        packages: ProductionPackageService,
        governance: ProductionTaskGovernanceService | None = None,
    ) -> None:
        self.universal = universal
        self.packages = packages
        self.governance = governance or ProductionTaskGovernanceService()

    def compile_shot(
        self,
        shot_id: str,
        context: ProductionTaskCompilationContext,
    ) -> tuple[ProductionTask, ...]:
        shot = shot_id.strip().upper()
        if not shot:
            raise ProductionTaskCompilationError("shot_id cannot be blank")

        draft = self.universal.draft(shot)
        if draft is None:
            raise ProductionTaskCompilationError(f"No Universal Production Description exists for {shot}")
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise ProductionTaskCompilationError(
                f"Universal Production Description for {shot} is not Ready"
            )
        if not self.universal.is_current(draft):
            raise ProductionTaskCompilationError(
                f"Universal Production Description for {shot} is stale"
            )

        package = self.packages.require_current_package(shot)
        if package.validation.get("universal_description_complete") is not True:
            raise ProductionTaskCompilationError(
                f"Universal Production Description authority for {shot} is not compiled"
            )
        if package.validation.get("cross_authority_consistent") is not True:
            raise ProductionTaskCompilationError(
                f"Universal Production Description authority for {shot} is not cross-authority consistent"
            )

        authority_fingerprint = self._fingerprint(package.universal_description)
        authority = ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{shot}",
            revision=context.authority_revision,
            fingerprint=authority_fingerprint,
            approved=True,
            approved_by=context.approved_by.strip(),
        )
        task = ProductionTask(
            task_id=self._task_id(
                authority_id=authority.authority_id,
                authority_revision=authority.revision,
                authority_fingerprint=authority.fingerprint,
                task_type=ProductionTaskType.VIDEO_GENERATION,
            ),
            production_id=context.production_id.strip(),
            episode_id=context.episode_id.strip(),
            scene_id=self._optional_text(context.scene_id),
            shot_id=shot,
            task_type=ProductionTaskType.VIDEO_GENERATION,
            authority=authority,
            capabilities=(ProductionCapability.VIDEO_GENERATION,),
            required_inputs=self._required_inputs(package.universal_description),
            expected_outputs=("video/shot",),
            state=ProductionTaskState.PLANNED,
            provenance=(
                ("source_authority", "universal-production-description"),
                ("source_package_id", package.package_id),
            ),
            metadata=(("compiler_phase", "19.6.2"),),
        )
        self.governance.require_valid(task)
        return (task,)

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _task_id(
        cls,
        *,
        authority_id: str,
        authority_revision: int,
        authority_fingerprint: str,
        task_type: ProductionTaskType,
    ) -> str:
        payload = {
            "authority_id": authority_id,
            "authority_revision": authority_revision,
            "authority_fingerprint": authority_fingerprint,
            "task_type": task_type.value,
        }
        digest = cls._fingerprint(payload)[:16].upper()
        return f"PT-{task_type.value.upper().replace('_', '-')}-{digest}"

    @classmethod
    def _required_inputs(cls, universal_description: dict[str, Any]) -> tuple[str, ...]:
        production = universal_description.get("production")
        view = production if isinstance(production, dict) else universal_description
        references = view.get("canonical_references", []) if isinstance(view, dict) else []
        inputs: list[str] = []
        if isinstance(references, list):
            for item in references:
                if not isinstance(item, dict):
                    continue
                asset_id = str(item.get("asset_id", "")).strip().upper()
                reference = str(item.get("canonical_reference", "")).strip()
                if asset_id and reference:
                    inputs.append(f"canonical-reference:{asset_id}:{reference}")
                elif asset_id:
                    inputs.append(f"canonical-asset:{asset_id}")
        return tuple(dict.fromkeys(inputs))

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
