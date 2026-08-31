"""Provider-neutral Universal Production Description compilation for Phase 19.4.8."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.governed_reference_plan_source import (
    GovernedReferencePlanSource,
    PersistedGovernedReferencePlanSource,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageService,
    ProductionPackageStatus,
)
from vscs.application.projects import ProjectNotOpenError, ProjectService


class UniversalProductionDescriptionCompilerError(RuntimeError):
    """Raised when Universal Production Description authority cannot be processed safely."""


class UniversalProductionDescriptionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class UniversalProductionDescriptionDraft:
    shot_id: str
    source_package_id: str
    dependency_fingerprint: str
    description: dict[str, Any] | None = None
    production_notes: str = ""
    status: UniversalProductionDescriptionStatus = UniversalProductionDescriptionStatus.DRAFT

    def description_value(self) -> dict[str, Any]:
        return dict(self.description or {})


class UniversalProductionDescriptionCompilerService:
    """Compile all governed Shot authority into one provider-neutral production description."""

    FILE_NAME = "universal_production_description_compilation.json"
    SCHEMA_VERSION = "1.4"
    REQUIRED_UPSTREAM = (
        ("action_performance_complete", "Action & Performance"),
        ("assets_complete", "Assets"),
        ("camera_complete", "Camera"),
        ("lighting_complete", "Lighting"),
        ("continuity_complete", "Continuity"),
        ("style_complete", "Style"),
    )
    _INTERIOR_TERMS = (
        "bridge",
        "corridor",
        "cabin",
        "room",
        "interior",
        "inside",
        "viewport",
        "deck",
        "quarters",
        "hangar",
        "laboratory",
        "lab",
    )
    _INTERIOR_ATMOSPHERES = frozenset({"controlled", "pressurized", "pressurised"})
    _CHARACTER_ASSET_CATEGORIES = frozenset({"character", "person", "performer", "actor"})
    _STOPWORDS = frozenset(
        {
            "a",
            "an",
            "and",
            "at",
            "be",
            "comes",
            "from",
            "in",
            "into",
            "is",
            "of",
            "on",
            "out",
            "the",
            "to",
            "with",
        }
    )

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        reference_plans: GovernedReferencePlanSource | None = None,
    ) -> None:
        self.projects = projects
        self.packages = packages
        self.reference_plans = reference_plans or PersistedGovernedReferencePlanSource(projects)

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[UniversalProductionDescriptionDraft, ...]:
        if not self.draft_file.is_file():
            return ()
        try:
            raw = json.loads(self.draft_file.read_text(encoding="utf-8"))
            drafts = tuple(
                self._from_dict(item)
                for item in raw.get("universal_production_description_compilation", [])
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise UniversalProductionDescriptionCompilerError(
                f"Unable to load Universal Production Description drafts: {exc}"
            ) from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> UniversalProductionDescriptionDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise UniversalProductionDescriptionCompilerError(
                f"Universal Production Description compilation already exists for {normalized}"
            )
        package = self.packages.current_package(normalized) or self.packages.materialize(normalized)
        draft = UniversalProductionDescriptionDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            dependency_fingerprint=self._dependency_fingerprint(package),
            description=self._build_description(package),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Ready Universal Production Description must return to Draft before refreshing"
            )
        package = self.packages.require_current_package(current.shot_id)
        fingerprint = self._dependency_fingerprint(package)
        if fingerprint == current.dependency_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            dependency_fingerprint=fingerprint,
            description=self._build_description(package),
        )
        self._replace(updated)
        return updated

    def save_notes(
        self, shot_id: str, production_notes: str
    ) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Ready Universal Production Description must return to Draft before editing"
            )
        if not self.is_current(current):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale against current production authority"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale against current production authority"
            )
        self._require_upstream_ready(current.shot_id)
        self._require_consistent(current.description_value())
        self._validate(current.description_value())
        ready = replace(current, status=UniversalProductionDescriptionStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        draft = replace(
            self._require_draft(shot_id), status=UniversalProductionDescriptionStatus.DRAFT
        )
        self._replace(draft)
        return draft

    def is_current(self, draft: UniversalProductionDescriptionDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        return package is not None and draft.dependency_fingerprint == self._dependency_fingerprint(
            package
        )

    def missing_prerequisites(self, shot_id: str) -> tuple[str, ...]:
        package = self.packages.current_package(shot_id.strip().upper())
        if package is None:
            return tuple(label for _key, label in self.REQUIRED_UPSTREAM)
        return tuple(
            label
            for key, label in self.REQUIRED_UPSTREAM
            if package.validation.get(key) is not True
        )

    def consistency_findings(self, shot_id: str) -> tuple[str, ...]:
        draft = self.draft(shot_id)
        if draft is None:
            package = self.packages.current_package(shot_id.strip().upper())
            if package is None:
                return ()
            return self._consistency_findings(self._build_description(package))
        return self._consistency_findings(draft.description_value())

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Only Ready Universal Production Description may be compiled"
            )
        if not self.is_current(draft):
            draft = self._refresh_ready_reference_dependency(draft)
        if not self.is_current(draft):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale and cannot be compiled"
            )
        self._require_upstream_ready(draft.shot_id)
        description = draft.description_value()
        self._require_consistent(description)
        self._validate(description)
        return self._derive(
            draft.shot_id,
            self._compile_description(description),
            production_notes=draft.production_notes,
        )

    def _refresh_ready_reference_dependency(
        self, draft: UniversalProductionDescriptionDraft
    ) -> UniversalProductionDescriptionDraft:
        """Refresh a READY UPD only when governed references are the sole changed dependency."""
        package = self.packages.require_current_package(draft.shot_id)
        refreshed_description = self._build_description(package)
        if not self._same_reviewed_authority(draft.description_value(), refreshed_description):
            raise UniversalProductionDescriptionCompilerError(
                "Ready Universal Production Description is stale against changed production "
                "authority and must return to Draft before refreshing"
            )
        updated = replace(
            draft,
            source_package_id=package.package_id,
            dependency_fingerprint=self._dependency_fingerprint(package),
            description=refreshed_description,
        )
        self._replace(updated)
        return updated

    @classmethod
    def _same_reviewed_authority(
        cls, previous: dict[str, Any], refreshed: dict[str, Any]
    ) -> bool:
        """Compare reviewed UPD authority while excluding governed-reference dependency data."""
        return cls._without_reference_dependency(previous) == cls._without_reference_dependency(
            refreshed
        )

    @classmethod
    def _without_reference_dependency(cls, value: dict[str, Any]) -> dict[str, Any]:
        detached = cls._detached(value)
        detached.pop("reference_plan", None)
        return detached

    def _require_upstream_ready(self, shot_id: str) -> None:
        missing = self.missing_prerequisites(shot_id)
        if missing:
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description cannot be finalized until upstream authority is Ready: "
                + ", ".join(missing)
            )

    def _require_consistent(self, description: dict[str, Any]) -> None:
        findings = self._consistency_findings(description)
        if findings:
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description has unresolved cross-authority inconsistencies:\n- "
                + "\n- ".join(findings)
            )

    def _derive(
        self, shot_id: str, compiled: dict[str, Any], *, production_notes: str = ""
    ) -> ProductionPackage:
        current = self.packages.require_current_package(shot_id)
        if (
            current.universal_description == compiled
            and current.validation.get("universal_description_complete") is True
        ):
            return current
        data = asdict(current)
        data.pop("package_id", None)
        data.pop("package_fingerprint", None)
        data["universal_description"] = dict(compiled)
        validation = dict(current.validation)
        validation["universal_description_complete"] = True
        validation["cross_authority_consistent"] = True
        if production_notes.strip():
            validation["universal_description_review_notes"] = production_notes.strip()
        else:
            validation.pop("universal_description_review_notes", None)
        data["validation"] = validation
        data["status"] = ProductionPackageStatus.COMPILING.value
        append_derived: Any = self.packages._append_derived
        derived: ProductionPackage = append_derived(current, data)
        return derived

    def _build_description(self, package: ProductionPackage) -> dict[str, Any]:
        action = self._section(package.action_performance)
        camera = self._section(package.camera)
        lighting = self._section(package.lighting)
        continuity = self._section(package.continuity)
        style = self._section(package.style)
        assets = [self._section(item) for item in package.assets]
        description = {
            "current_shot_id": package.shot_id,
            "story_context": self._detached(package.story_context),
            "shot": self._detached(package.shot),
            "action_performance": action,
            "assets": assets,
            "camera": camera,
            "lighting": lighting,
            "environment": self._detached(package.environment),
            "continuity": continuity,
            "style": style,
            "dialogue": [dict(item) for item in package.dialogue],
            "effects": [dict(item) for item in package.effects],
            "canonical_references": [dict(item) for item in package.references],
            "source_policy": "approved-production-authority-only",
            "provider_neutral": True,
        }
        reference_plan = self.reference_plans.reference_plan_for_shot(package.shot_id)
        if reference_plan is not None:
            description["reference_plan"] = self._detached(reference_plan)
        description["consistency_findings"] = list(self._consistency_findings(description))
        description["universal_text"] = self._universal_text(description)
        return description

    @classmethod
    def _compile_description(cls, description: dict[str, Any]) -> dict[str, Any]:
        governed = cls._detached(description)
        production = {
            "current_shot_id": governed.get("current_shot_id", ""),
            "universal_text": governed.get("universal_text", ""),
            "story_context": governed.get("story_context", {}),
            "shot": governed.get("shot", {}),
            "action_performance": governed.get("action_performance", {}),
            "assets": governed.get("assets", []),
            "camera": governed.get("camera", {}),
            "lighting": governed.get("lighting", {}),
            "environment": governed.get("environment", {}),
            "continuity": governed.get("continuity", {}),
            "style": governed.get("style", {}),
            "dialogue": governed.get("dialogue", []),
            "effects": governed.get("effects", []),
            "canonical_references": governed.get("canonical_references", []),
            "consistency_findings": governed.get("consistency_findings", []),
            "source_policy": governed.get("source_policy", ""),
            "provider_neutral": True,
        }
        reference_plan = governed.get("reference_plan")
        if isinstance(reference_plan, dict):
            production["reference_plan"] = cls._detached(reference_plan)
        return {"governed": governed, "production": production}

    @staticmethod
    def _validate(value: dict[str, Any]) -> None:
        if not str(value.get("current_shot_id", "")).strip():
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is missing the current Shot identity"
            )
        if value.get("provider_neutral") is not True:
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description must remain provider-neutral"
            )
        if not str(value.get("universal_text", "")).strip():
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description has no governed production content"
            )

    def _dependency_fingerprint(self, package: ProductionPackage) -> str:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "story_context": self._detached(package.story_context),
            "shot": self._detached(package.shot),
            "action_performance": self._detached(package.action_performance),
            "assets": [self._detached(item) for item in package.assets],
            "camera": self._detached(package.camera),
            "lighting": self._detached(package.lighting),
            "environment": self._detached(package.environment),
            "continuity": self._detached(package.continuity),
            "style": self._detached(package.style),
            "dialogue": [dict(item) for item in package.dialogue],
            "effects": [dict(item) for item in package.effects],
            "references": [dict(item) for item in package.references],
            "reference_plan": self.reference_plans.reference_plan_for_shot(package.shot_id),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _consistency_findings(cls, description: dict[str, Any]) -> tuple[str, ...]:
        findings: list[str] = []
        shot = cls._dict_value(description.get("shot"))
        action = cls._dict_value(description.get("action_performance"))
        environment = cls._dict_value(description.get("environment"))
        continuity = cls._dict_value(description.get("continuity"))
        assets_raw = description.get("assets", [])
        assets = [cls._dict_value(item) for item in assets_raw if isinstance(item, dict)]

        action_text = " ".join(
            str(action.get(key, ""))
            for key in (
                "temporal_narrative",
                "spoken_content",
                "performance_direction",
                "opening_state",
                "closing_state",
            )
        ).lower()
        interior = any(term in action_text for term in cls._INTERIOR_TERMS)
        environment_context = str(environment.get("environment_context", "")).strip().lower()
        atmosphere = str(environment.get("atmosphere_state", "")).strip().lower()
        surface_state = str(environment.get("surface_state", "")).strip().lower()
        pressure = environment.get("pressure_kpa")
        zero_or_negative_pressure = isinstance(pressure, int | float) and pressure <= 0
        declared_interior = (
            environment_context == "interior"
            or "interior" in surface_state
            or atmosphere in cls._INTERIOR_ATMOSPHERES
        )
        explicit_vacuum = atmosphere == "vacuum" or environment_context == "orbital_space"

        if interior and explicit_vacuum:
            findings.append(
                "Action & Performance places performers in an interior location, but Environment authority explicitly describes vacuum/orbital space."
            )
        if declared_interior and zero_or_negative_pressure:
            findings.append(
                "Environment authority declares a controlled/interior space, but Pressure Kpa is 0 or below."
            )

        constraints_raw = environment.get("environment_constraints", [])
        constraints: tuple[str, ...]
        if isinstance(constraints_raw, str):
            constraints = (constraints_raw,)
        elif isinstance(constraints_raw, list | tuple):
            constraints = tuple(str(item) for item in constraints_raw)
        else:
            constraints = ()
        if declared_interior and any("vacuum" in item.lower() for item in constraints):
            findings.append(
                "Environment authority declares a controlled/interior space, but Environment Constraints still contain vacuum-specific instructions."
            )

        categories = {str(item.get("category", "")).strip().lower() for item in assets}
        spoken = str(action.get("spoken_content", "")).strip()
        character_assets = tuple(
            item
            for item in assets
            if str(item.get("category", "")).strip().lower() in cls._CHARACTER_ASSET_CATEGORIES
        )
        if spoken and not character_assets:
            findings.append(
                "Action & Performance contains spoken content, but no governed character asset binding exists for this Shot."
            )
        character_assets_without_references = sorted(
            cls._governed_asset_label(item)
            for item in character_assets
            if not cls._asset_has_canonical_reference(item)
        )
        if character_assets_without_references:
            findings.append(
                "Governed character asset bindings lack canonical references: "
                + ", ".join(character_assets_without_references)
                + "."
            )
        if interior and not categories.intersection({"environment", "location", "set"}):
            findings.append(
                "Action & Performance requires an interior production location, but no environment/location asset is governed for this Shot."
            )

        continuity_ids = continuity.get("asset_ids") or continuity.get("current_asset_ids") or []
        if isinstance(continuity_ids, str):
            continuity_ids = [continuity_ids]
        governed_ids = cls._governed_asset_ids(assets)
        if isinstance(continuity_ids, list | tuple):
            missing_ids = [
                str(item).strip()
                for item in continuity_ids
                if str(item).strip() and str(item).strip().upper() not in governed_ids
            ]
            if missing_ids:
                findings.append(
                    "Continuity references assets that are absent from current Asset authority: "
                    + ", ".join(missing_ids)
                    + "."
                )

        dialogue_requirement = str(shot.get("dialogue_requirement", "")).strip()
        if dialogue_requirement and dialogue_requirement.lower() not in spoken.lower():
            findings.append(
                "Shot dialogue requirement is not represented in Action & Performance spoken content."
            )

        required_action = str(shot.get("required_action", "")).strip()
        temporal = str(action.get("temporal_narrative", "")).strip()
        if required_action and temporal:
            required_tokens = cls._meaningful_tokens(required_action)
            temporal_tokens = cls._meaningful_tokens(temporal)
            if required_tokens and not required_tokens.intersection(temporal_tokens):
                findings.append(
                    "Shot required action is not represented in the Action & Performance temporal narrative."
                )

        return tuple(findings)

    @classmethod
    def _governed_asset_ids(cls, assets: list[dict[str, Any]]) -> set[str]:
        governed_ids: set[str] = set()
        for item in assets:
            candidates: list[Any] = [item.get("asset_id")]
            for section_name in ("production", "resolution", "binding", "governed"):
                section = item.get(section_name)
                if isinstance(section, dict):
                    candidates.append(section.get("asset_id"))
            for candidate in candidates:
                value = str(candidate or "").strip().upper()
                if value:
                    governed_ids.add(value)
        return governed_ids

    @classmethod
    def _governed_asset_label(cls, asset: dict[str, Any]) -> str:
        asset_id = cls._governed_asset_id(asset)
        role = str(asset.get("role", "")).strip()
        if role and asset_id:
            return f"{role} ({asset_id})"
        return asset_id or role or "unidentified governed character asset"

    @staticmethod
    def _governed_asset_id(asset: dict[str, Any]) -> str:
        direct = str(asset.get("asset_id", "")).strip().upper()
        if direct:
            return direct
        for section_name in ("production", "resolution", "binding", "governed"):
            section = asset.get(section_name)
            if isinstance(section, dict):
                value = str(section.get("asset_id", "")).strip().upper()
                if value:
                    return value
        return ""

    @staticmethod
    def _asset_has_canonical_reference(asset: dict[str, Any]) -> bool:
        def has_reference(value: dict[str, Any]) -> bool:
            if str(value.get("canonical_reference", "") or "").strip():
                return True
            references = value.get("canonical_references")
            if not isinstance(references, list | tuple):
                references = value.get("references")
            if not isinstance(references, list | tuple):
                return False
            return any(
                isinstance(item, dict)
                and bool(
                    str(item.get("file_path") or item.get("canonical_reference") or "").strip()
                )
                for item in references
            )

        if has_reference(asset):
            return True
        for section_name in ("production", "resolution", "governed"):
            section = asset.get(section_name)
            if isinstance(section, dict) and has_reference(section):
                return True
        return False

    @classmethod
    def _meaningful_tokens(cls, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if len(token) > 2 and token not in cls._STOPWORDS
        }

    @staticmethod
    def _dict_value(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _universal_text(cls, description: dict[str, Any]) -> str:
        sections: list[str] = []
        for label, key in (
            ("SHOT", "shot"),
            ("ACTION & PERFORMANCE", "action_performance"),
            ("ASSETS", "assets"),
            ("CAMERA", "camera"),
            ("LIGHTING", "lighting"),
            ("ENVIRONMENT", "environment"),
            ("CONTINUITY", "continuity"),
            ("STYLE", "style"),
            ("DIALOGUE", "dialogue"),
            ("EFFECTS", "effects"),
            ("CANONICAL REFERENCES", "canonical_references"),
            ("CONSISTENCY FINDINGS", "consistency_findings"),
        ):
            value = description.get(key)
            if value in (None, "", {}, []):
                continue
            rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            sections.append(f"{label}: {rendered}")
        return "\n".join(sections)

    @staticmethod
    def _section(value: dict[str, Any]) -> dict[str, Any]:
        for name in ("production", "governed"):
            nested = value.get(name)
            if isinstance(nested, dict):
                return dict(nested)
        return dict(value)

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description value is not a JSON object"
            )
        return dict(decoded)

    def _require_draft(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise UniversalProductionDescriptionCompilerError(
                f"No Universal Production Description exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: UniversalProductionDescriptionDraft) -> None:
        self._write(
            tuple(
                updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
            )
        )

    def _write(self, drafts: tuple[UniversalProductionDescriptionDraft, ...]) -> None:
        self.draft_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "universal_production_description_compilation": [
                self._to_dict(item) for item in drafts
            ],
        }
        temporary = self.draft_file.with_suffix(self.draft_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.draft_file)

    @staticmethod
    def _to_dict(draft: UniversalProductionDescriptionDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> UniversalProductionDescriptionDraft:
        description = data.get("description", {})
        if not isinstance(description, dict):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description draft payload is invalid"
            )
        return UniversalProductionDescriptionDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            dependency_fingerprint=str(data["dependency_fingerprint"]),
            description=dict(description),
            production_notes=str(data.get("production_notes", "")),
            status=UniversalProductionDescriptionStatus(str(data.get("status", "draft"))),
        )