"""Governed Shot-to-Asset resolution for Phase 19.3.4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.asset_resolution import (
    AssetBrowserFilter,
    AssetBrowserService,
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionService,
    AssetResolutionStatus,
)
from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.domain.assets import AssetCategory

from .shot_planning import GovernedShotPlanningService, ShotPlan


class GovernedAssetResolutionError(RuntimeError):
    """Raised when governed Shot asset resolution cannot be processed safely."""


class AssetBindingStatus(StrEnum):
    """Governance state for one Shot asset requirement."""

    DRAFT = "draft"
    READY = "ready"


SPECIALIST_CATEGORIES = frozenset(
    {
        AssetCategory.CAMERA,
        AssetCategory.LIGHTING,
        AssetCategory.REFERENCE,
    }
)


@dataclass(frozen=True, slots=True)
class ShotAssetBinding:
    """One governed production requirement bound to an authoritative project asset."""

    binding_id: str
    shot_id: str
    sequence_number: int
    role: str
    requirement: str
    expected_category: AssetCategory
    asset_id: str = ""
    notes: str = ""
    shot_contract_hash: str = ""
    asset_dependency_hash: str = ""
    status: AssetBindingStatus = AssetBindingStatus.DRAFT


class GovernedAssetResolutionService:
    """Bind Ready governed Shots to approved XPD/CAP production assets."""

    FILE_NAME = "asset_resolutions.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        shots: GovernedShotPlanningService,
        resolver: AssetResolutionService,
        browser: AssetBrowserService,
    ) -> None:
        self.projects = projects
        self.shots = shots
        self.resolver = resolver
        self.browser = browser

    @property
    def planning_file(self) -> Path:
        """Return the active project's authoritative Shot asset-resolution file."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_bindings(self, *, shot_id: str | None = None) -> tuple[ShotAssetBinding, ...]:
        """Load governed asset bindings in deterministic Shot/sequence order."""
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            bindings = tuple(self._from_dict(item) for item in raw.get("bindings", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise GovernedAssetResolutionError(
                f"Unable to load governed asset resolutions: {exc}"
            ) from exc
        if shot_id is not None:
            normalized = shot_id.strip().upper()
            bindings = tuple(binding for binding in bindings if binding.shot_id == normalized)
        return tuple(
            sorted(
                bindings,
                key=lambda binding: (
                    binding.shot_id,
                    binding.sequence_number,
                    binding.binding_id,
                ),
            )
        )

    def binding(self, binding_id: str) -> ShotAssetBinding | None:
        """Return one governed asset binding by stable identity."""
        normalized = binding_id.strip().upper()
        return next(
            (binding for binding in self.list_bindings() if binding.binding_id == normalized),
            None,
        )

    def next_sequence_number(self, shot_id: str) -> int:
        """Return the next requirement sequence number within one Shot."""
        return (
            max(
                (binding.sequence_number for binding in self.list_bindings(shot_id=shot_id)),
                default=0,
            )
            + 1
        )

    def available_assets(self, category: AssetCategory) -> tuple[tuple[str, str], ...]:
        """Return deterministic project asset choices for one production category."""
        self._validate_category(category)
        result = self.browser.browse(AssetBrowserFilter(categories=frozenset({category})))
        return tuple((item.asset_id, item.name) for item in result.items)

    def resolution(self, binding: ShotAssetBinding) -> AssetResolutionResult | None:
        """Resolve the binding's selected asset against current XPD/CAP truth."""
        if not binding.asset_id:
            return None
        return self.resolver.resolve(
            AssetResolutionRequest(
                binding.asset_id,
                expected_category=binding.expected_category,
                require_approved_asset=True,
                require_cap=True,
                require_approved_cap=True,
                require_approved_references=True,
            )
        )

    def is_upstream_current(self, binding: ShotAssetBinding) -> bool:
        """Return whether the binding still matches its authoritative Shot contract."""
        shot = self.shots.plan(binding.shot_id)
        return shot is not None and binding.shot_contract_hash == self._shot_contract_hash(shot)

    def is_asset_current(self, binding: ShotAssetBinding) -> bool:
        """Return whether the bound asset/CAP/reference dependency fingerprint is current."""
        resolution = self.resolution(binding)
        return (
            resolution is not None
            and resolution.status is AssetResolutionStatus.RESOLVED
            and resolution.fingerprint is not None
            and binding.asset_dependency_hash == resolution.fingerprint.checksum
        )

    def is_production_ready(self, binding: ShotAssetBinding) -> bool:
        """Return whether downstream specialist planners may consume this binding."""
        shot = self.shots.plan(binding.shot_id)
        return (
            binding.status is AssetBindingStatus.READY
            and shot is not None
            and self.shots.is_production_ready(shot)
            and self.is_upstream_current(binding)
            and self.is_asset_current(binding)
        )

    def create(
        self,
        *,
        shot_id: str,
        sequence_number: int,
        role: str,
        requirement: str,
        expected_category: AssetCategory,
        asset_id: str = "",
        notes: str = "",
    ) -> ShotAssetBinding:
        """Create one Draft asset requirement beneath a current Ready Shot."""
        shot = self._require_ready_shot(shot_id)
        if sequence_number < 1:
            raise GovernedAssetResolutionError("Asset requirement sequence must be at least 1")
        self._validate_category(expected_category)
        binding_id = self._binding_id(shot.shot_id, sequence_number)
        if self.binding(binding_id) is not None:
            raise GovernedAssetResolutionError(f"Asset binding already exists: {binding_id}")
        selected_asset = asset_id.strip().upper()
        binding = ShotAssetBinding(
            binding_id=binding_id,
            shot_id=shot.shot_id,
            sequence_number=sequence_number,
            role=self._required(role, "Production role"),
            requirement=self._required(requirement, "Asset requirement"),
            expected_category=expected_category,
            asset_id=selected_asset,
            notes=notes.strip(),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_dependency_hash=self._dependency_hash(selected_asset, expected_category),
        )
        self._write((*self.list_bindings(), binding))
        return binding

    def update(
        self,
        binding_id: str,
        *,
        role: str,
        requirement: str,
        expected_category: AssetCategory,
        asset_id: str,
        notes: str,
    ) -> ShotAssetBinding:
        """Update a Draft binding and refresh both upstream fingerprints."""
        current = self._require_binding(binding_id)
        if current.status is not AssetBindingStatus.DRAFT:
            raise GovernedAssetResolutionError(
                "Ready asset bindings must return to Draft before editing"
            )
        shot = self._require_ready_shot(current.shot_id)
        self._validate_category(expected_category)
        selected_asset = asset_id.strip().upper()
        updated = replace(
            current,
            role=self._required(role, "Production role"),
            requirement=self._required(requirement, "Asset requirement"),
            expected_category=expected_category,
            asset_id=selected_asset,
            notes=notes.strip(),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_dependency_hash=self._dependency_hash(selected_asset, expected_category),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, binding_id: str) -> ShotAssetBinding:
        """Approve one current fully resolved Shot asset binding for production."""
        current = self._require_binding(binding_id)
        if current.status is AssetBindingStatus.READY:
            if self.is_production_ready(current):
                return current
            raise GovernedAssetResolutionError(
                "Ready asset bindings must return to Draft before re-approval"
            )
        shot = self._require_ready_shot(current.shot_id)
        if current.shot_contract_hash != self._shot_contract_hash(shot):
            raise GovernedAssetResolutionError(
                "Asset binding is stale because the Shot contract changed; edit and save it before marking Ready"
            )
        if not current.asset_id:
            raise GovernedAssetResolutionError(
                "A project asset must be selected before marking Ready"
            )
        resolution = self.resolution(current)
        if resolution is None or resolution.status is not AssetResolutionStatus.RESOLVED:
            message = self._resolution_message(resolution)
            raise GovernedAssetResolutionError(f"Selected asset is not production-ready: {message}")
        if resolution.fingerprint is None:
            raise GovernedAssetResolutionError(
                "Selected asset has no dependency fingerprint and cannot be approved"
            )
        updated = replace(
            current,
            asset_dependency_hash=resolution.fingerprint.checksum,
            status=AssetBindingStatus.READY,
        )
        self._replace(updated)
        return updated

    def return_to_draft(self, binding_id: str) -> ShotAssetBinding:
        """Return a Ready asset binding to editable Draft state."""
        current = self._require_binding(binding_id)
        updated = replace(current, status=AssetBindingStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, binding_id: str) -> bool:
        """Delete only a Draft governed asset binding."""
        current = self.binding(binding_id)
        if current is None:
            return False
        if current.status is not AssetBindingStatus.DRAFT:
            raise GovernedAssetResolutionError(
                "Ready asset bindings must return to Draft before deletion"
            )
        remaining = tuple(
            binding for binding in self.list_bindings() if binding.binding_id != current.binding_id
        )
        self._write(remaining)
        return True

    def reorder_shot(
        self,
        shot_id: str,
        ordered_binding_ids: tuple[str, ...],
    ) -> tuple[ShotAssetBinding, ...]:
        """Persist explicit asset-requirement order within one Shot."""
        current = self.list_bindings(shot_id=shot_id)
        by_id = {binding.binding_id: binding for binding in current}
        if len(ordered_binding_ids) != len(by_id) or set(ordered_binding_ids) != set(by_id):
            raise GovernedAssetResolutionError(
                "Reorder must include every governed asset binding in the Shot exactly once"
            )
        replacements = {
            binding_id: replace(by_id[binding_id], sequence_number=index)
            for index, binding_id in enumerate(ordered_binding_ids, start=1)
        }
        all_bindings = tuple(
            replacements.get(binding.binding_id, binding) for binding in self.list_bindings()
        )
        self._write(all_bindings)
        return self.list_bindings(shot_id=shot_id)

    def shot_ready(self, shot_id: str) -> bool:
        """Return whether every declared asset requirement for a Shot is production-ready."""
        bindings = self.list_bindings(shot_id=shot_id)
        return bool(bindings) and all(self.is_production_ready(binding) for binding in bindings)

    def _dependency_hash(self, asset_id: str, category: AssetCategory) -> str:
        if not asset_id:
            return ""
        result = self.resolver.resolve(
            AssetResolutionRequest(
                asset_id,
                expected_category=category,
                require_approved_asset=True,
                require_cap=True,
                require_approved_cap=True,
                require_approved_references=True,
            )
        )
        return result.fingerprint.checksum if result.fingerprint is not None else ""

    def _require_ready_shot(self, shot_id: str) -> ShotPlan:
        shot = self.shots.plan(shot_id)
        if shot is None:
            raise GovernedAssetResolutionError(f"Shot Plan not found: {shot_id}")
        if not self.shots.is_production_ready(shot):
            raise GovernedAssetResolutionError(
                "Asset Resolution requires a current Ready governed Shot Plan"
            )
        return shot

    def _require_binding(self, binding_id: str) -> ShotAssetBinding:
        binding = self.binding(binding_id)
        if binding is None:
            raise GovernedAssetResolutionError(f"Asset binding not found: {binding_id}")
        return binding

    def _replace(self, updated: ShotAssetBinding) -> None:
        bindings = tuple(
            updated if binding.binding_id == updated.binding_id else binding
            for binding in self.list_bindings()
        )
        self._write(bindings)

    def _write(self, bindings: tuple[ShotAssetBinding, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            bindings,
            key=lambda binding: (
                binding.shot_id,
                binding.sequence_number,
                binding.binding_id,
            ),
        )
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "bindings": [self._to_dict(binding) for binding in ordered],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise GovernedAssetResolutionError(
                f"Unable to save governed asset resolutions: {exc}"
            ) from exc

    @staticmethod
    def _to_dict(binding: ShotAssetBinding) -> dict[str, Any]:
        raw = asdict(binding)
        raw["expected_category"] = binding.expected_category.value
        raw["status"] = binding.status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> ShotAssetBinding:
        return ShotAssetBinding(
            binding_id=str(raw["binding_id"]).strip().upper(),
            shot_id=str(raw["shot_id"]).strip().upper(),
            sequence_number=int(raw["sequence_number"]),
            role=str(raw["role"]),
            requirement=str(raw["requirement"]),
            expected_category=AssetCategory(str(raw["expected_category"])),
            asset_id=str(raw.get("asset_id", "")).strip().upper(),
            notes=str(raw.get("notes", "")),
            shot_contract_hash=str(raw.get("shot_contract_hash", "")),
            asset_dependency_hash=str(raw.get("asset_dependency_hash", "")),
            status=AssetBindingStatus(str(raw.get("status", AssetBindingStatus.DRAFT.value))),
        )

    @classmethod
    def _shot_contract_hash(cls, shot: ShotPlan) -> str:
        payload = {
            "shot_id": shot.shot_id,
            "scene_id": shot.scene_id,
            "sequence_number": shot.sequence_number,
            "title": shot.title,
            "narrative_purpose": shot.narrative_purpose,
            "production_objective": shot.production_objective,
            "target_runtime_seconds": shot.target_runtime_seconds,
            "required_action": shot.required_action,
            "dialogue_requirement": shot.dialogue_requirement,
            "continuity_in": shot.continuity_in,
            "continuity_out": shot.continuity_out,
            "shot_constraints": list(shot.shot_constraints),
            "scene_contract_hash": shot.scene_contract_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _binding_id(shot_id: str, sequence_number: int) -> str:
        return f"{shot_id}-AST-{sequence_number:03d}"

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise GovernedAssetResolutionError(f"{label} is required")
        return normalized

    @staticmethod
    def _validate_category(category: AssetCategory) -> None:
        if category in SPECIALIST_CATEGORIES:
            owner = {
                AssetCategory.CAMERA: "Phase 19.3.5 Camera Planner",
                AssetCategory.LIGHTING: "Phase 19.3.6 Lighting Planner",
                AssetCategory.REFERENCE: "canonical-reference resolution",
            }[category]
            raise GovernedAssetResolutionError(
                f"{category.value.title()} assets are not authored by Phase 19.3.4; use {owner}"
            )

    @staticmethod
    def _resolution_message(result: AssetResolutionResult | None) -> str:
        if result is None:
            return "no asset is selected"
        if not result.diagnostics:
            return result.status.value
        return "; ".join(diagnostic.message for diagnostic in result.diagnostics)
