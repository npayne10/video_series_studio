"""Governed Shot-to-Asset resolution for Phase 19.3.4."""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
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


class ShotAssetInferenceSource(StrEnum):
    """Origin of one proposed Shot asset requirement."""

    DETERMINISTIC = "deterministic"
    CANONICAL_MATCH = "canonical_match"
    AI_SEMANTIC = "ai_semantic"


@dataclass(frozen=True, slots=True)
class ShotAssetRequirementProposal:
    """Reviewable proposal; never governed binding authority by itself."""

    proposal_id: str
    shot_id: str
    role: str
    requirement: str
    expected_category: AssetCategory
    matched_asset_id: str = ""
    matched_asset_name: str = ""
    confidence: float = 0.0
    source: ShotAssetInferenceSource = ShotAssetInferenceSource.DETERMINISTIC
    rationale: str = ""
    canonical_status: str = "unresolved"

    @property
    def matched(self) -> bool:
        return bool(self.matched_asset_id)


class ShotAssetSemanticInferenceProvider(ABC):
    """Optional AI boundary for requirements deterministic analysis could not establish."""

    provider_name: str
    model_name: str

    @abstractmethod
    def infer_requirements(
        self,
        *,
        shot: ShotPlan,
        scene_text: str,
        deterministic: tuple[ShotAssetRequirementProposal, ...],
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        """Return proposal-only requirements for unresolved semantic coverage gaps."""


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
        semantic_provider: ShotAssetSemanticInferenceProvider | None = None,
    ) -> None:
        self.projects = projects
        self.shots = shots
        self.resolver = resolver
        self.browser = browser
        self.semantic_provider = semantic_provider

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

    def infer_requirements(
        self,
        shot_id: str,
        *,
        include_ai: bool = True,
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        """Infer reviewable Shot asset requirements without creating governed bindings."""
        shot = self._require_ready_shot(shot_id)
        scene = self.shots.scenes.plan(shot.scene_id)
        scene_text = self._scene_shot_text(shot, scene)
        deterministic = self._deterministic_requirements(shot, scene, scene_text)
        proposals = list(deterministic)

        if (
            include_ai
            and self.semantic_provider is not None
            and self._semantic_inference_needed(shot, deterministic)
        ):
            inferred = self.semantic_provider.infer_requirements(
                shot=shot,
                scene_text=scene_text,
                deterministic=deterministic,
            )
            proposals.extend(
                self._canonicalize_ai_proposal(proposal)
                for proposal in inferred
                if proposal.shot_id.strip().upper() == shot.shot_id
            )

        proposals = list(
            self._enforce_shot_local_character_precedence(
                tuple(proposals),
                shot,
                scene,
            )
        )
        classified = tuple(self._classify_proposal_role(proposal, shot) for proposal in proposals)
        deduplicated = self._deduplicate_proposals(classified)
        without_placeholders = self._suppress_story_placeholders(deduplicated)
        return self._collapse_environment_overlaps(without_placeholders)

    def apply_inferred_requirements(
        self,
        shot_id: str,
        proposals: tuple[ShotAssetRequirementProposal, ...],
    ) -> tuple[ShotAssetBinding, ...]:
        """Human-approved materialization of inference proposals as Draft bindings."""
        shot = self._require_ready_shot(shot_id)
        existing = self.list_bindings(shot_id=shot.shot_id)
        existing_keys = {
            (binding.expected_category, binding.asset_id, binding.requirement.casefold())
            for binding in existing
        }
        created: list[ShotAssetBinding] = []
        sequence = self.next_sequence_number(shot.shot_id)
        for proposal in proposals:
            if proposal.shot_id.strip().upper() != shot.shot_id:
                raise GovernedAssetResolutionError(
                    "Asset requirement proposal belongs to another Shot"
                )
            self._validate_category(proposal.expected_category)
            key = (
                proposal.expected_category,
                proposal.matched_asset_id.strip().upper(),
                proposal.requirement.casefold(),
            )
            if key in existing_keys:
                continue
            binding = self.create(
                shot_id=shot.shot_id,
                sequence_number=sequence,
                role=proposal.role,
                requirement=proposal.requirement,
                expected_category=proposal.expected_category,
                asset_id=proposal.matched_asset_id,
                notes=(
                    f"Inferred via {proposal.source.value}; confidence "
                    f"{proposal.confidence:.2f}. {proposal.rationale}"
                ).strip(),
            )
            created.append(binding)
            existing_keys.add(key)
            sequence += 1
        return tuple(created)

    def _deterministic_requirements(
        self,
        shot: ShotPlan,
        scene: Any,
        scene_text: str,
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        """Extract explicit canonical asset mentions from governed Shot/Scene authority."""
        items = self.browser.browse().items
        proposals: list[ShotAssetRequirementProposal] = []
        normalized_text = self._normalize_text(scene_text)
        shot_text = self._normalize_text(self._shot_only_text(shot))
        for item in items:
            if item.category in SPECIALIST_CATEGORIES:
                continue
            shot_evidence = self._asset_evidence(item, shot_text)
            scene_evidence = self._asset_evidence(item, normalized_text)
            persistent_scene_evidence = (
                scene_evidence
                if item.category is AssetCategory.CHARACTER
                and self._scene_persistently_requires_asset(item, scene)
                else None
            )
            evidence = (
                shot_evidence
                if item.category is AssetCategory.CHARACTER
                else shot_evidence or scene_evidence
            )
            if item.category is AssetCategory.CHARACTER and evidence is None:
                evidence = persistent_scene_evidence
            if evidence is None:
                continue
            confidence, rationale = evidence
            if shot_evidence is None:
                confidence = min(confidence, 0.88)
                if item.category is AssetCategory.CHARACTER:
                    rationale = (
                        "Explicit Scene persistence constraint requires this character in every "
                        f"Shot. {rationale}"
                    )
                else:
                    rationale = f"Scene-context support only. {rationale}"
            strict = self.resolver.resolve(
                AssetResolutionRequest(
                    item.asset_id,
                    expected_category=item.category,
                    require_approved_asset=True,
                    require_cap=True,
                    require_approved_cap=True,
                    require_approved_references=True,
                )
            )
            canonical_status = strict.status.value
            source = (
                ShotAssetInferenceSource.CANONICAL_MATCH
                if strict.status is AssetResolutionStatus.RESOLVED
                else ShotAssetInferenceSource.DETERMINISTIC
            )
            proposals.append(
                ShotAssetRequirementProposal(
                    proposal_id=self._proposal_id(shot.shot_id, item.asset_id, item.category),
                    shot_id=shot.shot_id,
                    role=self._inferred_role(item, shot, shot_evidence is not None),
                    requirement=(
                        f"{item.name} is required by the governed Shot/Scene contract and "
                        "must remain canonically identifiable where visible."
                    ),
                    expected_category=item.category,
                    matched_asset_id=item.asset_id,
                    matched_asset_name=item.name,
                    confidence=confidence,
                    source=source,
                    rationale=rationale,
                    canonical_status=canonical_status,
                )
            )
        return tuple(proposals)

    @classmethod
    def _enforce_shot_local_character_precedence(
        cls,
        proposals: tuple[ShotAssetRequirementProposal, ...],
        shot: ShotPlan,
        scene: Any,
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        """Reject Scene-only character leakage from deterministic or AI inference."""
        kept: list[ShotAssetRequirementProposal] = []
        for proposal in proposals:
            if proposal.expected_category is not AssetCategory.CHARACTER:
                kept.append(proposal)
                continue
            name = proposal.matched_asset_name.strip()
            if name and cls._character_explicit_in_shot(name, shot):
                kept.append(proposal)
                continue
            if name and cls._scene_persistently_requires_name(name, scene):
                kept.append(proposal)
                continue
            if not name and cls._unresolved_character_supported_by_shot(proposal, shot):
                kept.append(proposal)
        return tuple(kept)

    @classmethod
    def _character_explicit_in_shot(cls, name: str, shot: ShotPlan) -> bool:
        aliases = cls._character_aliases(name)
        shot_text = cls._normalize_text(cls._shot_only_text(shot))
        return any(f" {alias} " in f" {shot_text} " for alias in aliases)

    @classmethod
    def _unresolved_character_supported_by_shot(
        cls,
        proposal: ShotAssetRequirementProposal,
        shot: ShotPlan,
    ) -> bool:
        proposal_text = cls._normalize_text(
            " ".join((proposal.role, proposal.requirement, proposal.rationale))
        )
        shot_text = cls._normalize_text(cls._shot_only_text(shot))
        proposal_tokens = {token for token in proposal_text.split() if len(token) >= 4}
        shot_tokens = {token for token in shot_text.split() if len(token) >= 4}
        return bool(proposal_tokens.intersection(shot_tokens))

    @classmethod
    def _scene_persistently_requires_asset(cls, item: Any, scene: Any) -> bool:
        if scene is None:
            return False
        return cls._scene_persistently_requires_name(item.name, scene) or any(
            cls._persistent_constraint_matches(constraint, item.asset_id)
            for constraint in getattr(scene, "scene_constraints", ())
        )

    @classmethod
    def _scene_persistently_requires_name(cls, name: str, scene: Any) -> bool:
        if scene is None:
            return False
        return any(
            cls._persistent_constraint_matches(constraint, name)
            for constraint in getattr(scene, "scene_constraints", ())
        )

    @classmethod
    def _persistent_constraint_matches(cls, constraint: str, subject: str) -> bool:
        normalized = cls._normalize_text(constraint)
        subject_text = cls._normalize_text(subject)
        prefixes = (
            "persistent character ",
            "persistent asset ",
            "always present character ",
            "always present asset ",
        )
        return bool(subject_text) and any(
            normalized.startswith(prefix) and f" {subject_text} " in f" {normalized} "
            for prefix in prefixes
        )

    @staticmethod
    def _semantic_inference_needed(
        shot: ShotPlan,
        deterministic: tuple[ShotAssetRequirementProposal, ...],
    ) -> bool:
        categories = {proposal.expected_category for proposal in deterministic}
        coverage = getattr(getattr(shot, "coverage_role", None), "value", "")
        if not deterministic:
            return True
        if coverage == "dialogue_delivery" and AssetCategory.CHARACTER not in categories:
            return True
        return coverage == "detail_insert" and not categories.intersection(
            {AssetCategory.PROP, AssetCategory.TECHNOLOGY}
        )

    def _canonicalize_ai_proposal(
        self,
        proposal: ShotAssetRequirementProposal,
    ) -> ShotAssetRequirementProposal:
        """Match an AI proposal against current XPD/CAP truth without inventing canon."""
        if proposal.matched_asset_id:
            return proposal
        query = self._normalize_text(
            " ".join(
                value
                for value in (
                    proposal.matched_asset_name,
                    proposal.requirement,
                    proposal.role,
                )
                if value
            )
        )
        candidates = []
        for item in self.browser.browse(
            AssetBrowserFilter(categories=frozenset({proposal.expected_category}))
        ).items:
            evidence = self._asset_evidence(item, query)
            if evidence is not None:
                candidates.append((evidence[0], item))
        if not candidates:
            return proposal
        candidates.sort(key=lambda pair: (-pair[0], pair[1].asset_id))
        top_score, item = candidates[0]
        if len(candidates) > 1 and candidates[1][0] == top_score:
            return proposal
        strict = self.resolver.resolve(
            AssetResolutionRequest(
                item.asset_id,
                expected_category=item.category,
                require_approved_asset=True,
                require_cap=True,
                require_approved_cap=True,
                require_approved_references=True,
            )
        )
        return replace(
            proposal,
            matched_asset_id=item.asset_id,
            matched_asset_name=item.name,
            canonical_status=strict.status.value,
            rationale=(
                proposal.rationale + f" Canonically matched AI requirement to {item.asset_id}."
            ).strip(),
        )

    @staticmethod
    def _shot_only_text(shot: ShotPlan) -> str:
        return " ".join(
            value
            for value in (
                shot.title,
                shot.narrative_purpose,
                shot.production_objective,
                shot.required_action,
                shot.dialogue_requirement,
                shot.continuity_in,
                shot.continuity_out,
                *shot.shot_constraints,
            )
            if value
        )

    @staticmethod
    def _scene_shot_text(shot: ShotPlan, scene: Any) -> str:
        scene_values: tuple[str, ...] = ()
        if scene is not None:
            scene_values = tuple(
                str(value)
                for value in (
                    getattr(scene, "title", ""),
                    getattr(scene, "story_scope", ""),
                    getattr(scene, "production_objective", ""),
                    getattr(scene, "setting_requirement", ""),
                    *getattr(scene, "required_events", ()),
                    *getattr(scene, "scene_constraints", ()),
                )
                if value
            )
        return " ".join(
            value
            for value in (
                shot.title,
                shot.narrative_purpose,
                shot.production_objective,
                shot.required_action,
                shot.dialogue_requirement,
                shot.continuity_in,
                shot.continuity_out,
                *shot.shot_constraints,
                *scene_values,
            )
            if value
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(
            "".join(
                character.casefold() if character.isalnum() else " " for character in value
            ).split()
        )

    def _asset_evidence(
        self,
        item: Any,
        normalized_text: str,
    ) -> tuple[float, str] | None:
        name = self._normalize_text(item.name)
        if name and f" {name} " in f" {normalized_text} ":
            return (
                1.0,
                f"Explicit canonical asset name '{item.name}' occurs in governed Shot text.",
            )

        significant_tags = tuple(
            tag for tag in (self._normalize_text(value) for value in item.tags) if len(tag) >= 4
        )
        matched_tags = tuple(
            tag for tag in significant_tags if f" {tag} " in f" {normalized_text} "
        )
        if matched_tags:
            return (
                0.82,
                "Governed Shot text matches canonical asset tag(s): " + ", ".join(matched_tags),
            )

        asset_tokens = tuple(
            token
            for token in self._normalize_text(item.asset_id).split()
            if len(token) >= 4 and not token.isdigit()
        )
        if asset_tokens and all(
            f" {token} " in f" {normalized_text} " for token in asset_tokens[-2:]
        ):
            return (0.72, f"Governed Shot text matches canonical asset identity {item.asset_id}.")
        return None

    @classmethod
    def _inferred_role(
        cls,
        item: Any,
        shot: ShotPlan,
        explicit_in_shot: bool,
    ) -> str:
        category = item.category
        if category is AssetCategory.CHARACTER:
            return (
                "Dialogue Speaker"
                if cls._character_is_dialogue_speaker(item.name, shot)
                else "Supporting Character"
            )
        if category is AssetCategory.LOCATION:
            return "Location"
        if category is AssetCategory.ENVIRONMENT:
            return "Environment Context"
        if category is AssetCategory.PLANET:
            return "Visible Planet" if explicit_in_shot else "Planetary Context"
        if category in {AssetCategory.SHIP, AssetCategory.VEHICLE}:
            return "Vehicle/Ship"
        if category in {AssetCategory.PROP, AssetCategory.TECHNOLOGY}:
            return "Prop/Technology"
        if category is AssetCategory.UNIFORM:
            return "Wardrobe/Uniform"
        if category is AssetCategory.EFFECT:
            return "Effect"
        if category is AssetCategory.AUDIO:
            return "Audio"
        return "Other Production Asset"

    @classmethod
    def _character_is_dialogue_speaker(cls, name: str, shot: ShotPlan) -> bool:
        if not shot.dialogue_requirement.strip():
            return False
        aliases = cls._character_aliases(name)
        dialogue = cls._normalize_text(shot.dialogue_requirement)
        if any(f" {alias} " in f" {dialogue} " for alias in aliases):
            return True

        speech_verbs = (
            "says",
            "said",
            "asks",
            "asked",
            "reports",
            "reported",
            "states",
            "stated",
            "orders",
            "ordered",
            "replies",
            "replied",
            "answers",
            "answered",
            "tells",
            "told",
            "warns",
            "warned",
            "calls",
            "called",
        )
        for sentence in re.split(r"[.!?]+", shot.required_action):
            normalized = cls._normalize_text(sentence)
            if not normalized:
                continue
            words = normalized.split()
            verb_positions = [
                index for index, word in enumerate(words) if word in speech_verbs
            ]
            if not verb_positions:
                continue
            first_verb = min(verb_positions)
            subject_text = " ".join(words[:first_verb])
            if any(f" {alias} " in f" {subject_text} " for alias in aliases):
                return True
        return False

    @classmethod
    def _character_aliases(cls, name: str) -> tuple[str, ...]:
        title_tokens = {"captain", "commander", "major", "doctor", "dr", "ambassador"}
        tokens = tuple(
            token for token in cls._normalize_text(name).split() if token not in title_tokens
        )
        aliases: list[str] = []
        full = " ".join(tokens)
        if full:
            aliases.append(full)
        for token in tokens:
            if len(token) >= 4 and token not in aliases:
                aliases.append(token)
        return tuple(aliases)

    @staticmethod
    def _proposal_id(
        shot_id: str,
        asset_id: str,
        category: AssetCategory,
    ) -> str:
        digest = hashlib.sha256(f"{shot_id}|{asset_id}|{category.value}".encode()).hexdigest()
        return f"{shot_id}-AIR-{digest[:10].upper()}"

    @staticmethod
    def _deduplicate_proposals(
        proposals: tuple[ShotAssetRequirementProposal, ...],
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        best: dict[tuple[AssetCategory, str, str], ShotAssetRequirementProposal] = {}
        for proposal in proposals:
            key = (
                proposal.expected_category,
                proposal.matched_asset_id.strip().upper(),
                proposal.requirement.casefold(),
            )
            current = best.get(key)
            if current is None or proposal.confidence > current.confidence:
                best[key] = proposal
        return tuple(
            sorted(
                best.values(),
                key=lambda proposal: (
                    proposal.expected_category.value,
                    proposal.matched_asset_name.casefold(),
                    proposal.requirement.casefold(),
                ),
            )
        )

    @classmethod
    def _classify_proposal_role(
        cls,
        proposal: ShotAssetRequirementProposal,
        shot: ShotPlan,
    ) -> ShotAssetRequirementProposal:
        category = proposal.expected_category
        if category is AssetCategory.CHARACTER:
            explicit_speaker = proposal.matched_asset_name and cls._character_is_dialogue_speaker(
                proposal.matched_asset_name, shot
            )
            semantic_speaker = bool(shot.dialogue_requirement.strip()) and any(
                token in proposal.role.casefold() for token in ("speaker", "dialogue", "speaking")
            )
            role = (
                "Dialogue Speaker"
                if explicit_speaker or semantic_speaker
                else "Supporting Character"
            )
        elif category is AssetCategory.LOCATION:
            role = "Location"
        elif category is AssetCategory.ENVIRONMENT:
            role = "Environment Context"
        elif category is AssetCategory.PLANET:
            role = (
                "Visible Planet"
                if proposal.matched_asset_name
                and cls._asset_name_in_shot(proposal.matched_asset_name, shot)
                else "Planetary Context"
            )
        elif category in {AssetCategory.SHIP, AssetCategory.VEHICLE}:
            role = "Vehicle/Ship"
        elif category in {AssetCategory.PROP, AssetCategory.TECHNOLOGY}:
            role = "Prop/Technology"
        elif category is AssetCategory.UNIFORM:
            role = "Wardrobe/Uniform"
        elif category is AssetCategory.EFFECT:
            role = "Effect"
        elif category is AssetCategory.AUDIO:
            role = "Audio"
        else:
            role = "Other Production Asset"
        return replace(proposal, role=role)

    @classmethod
    def _asset_name_in_shot(cls, name: str, shot: ShotPlan) -> bool:
        normalized_name = cls._normalize_text(name)
        normalized_shot = cls._normalize_text(cls._shot_only_text(shot))
        return bool(normalized_name) and f" {normalized_name} " in f" {normalized_shot} "

    @classmethod
    def _suppress_story_placeholders(
        cls,
        proposals: tuple[ShotAssetRequirementProposal, ...],
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        """Drop story-derived placeholders when stronger canonical authority covers the same need."""
        canonical = tuple(
            proposal
            for proposal in proposals
            if proposal.matched_asset_id
            and not cls._is_placeholder_asset_id(proposal.matched_asset_id)
            and proposal.source is ShotAssetInferenceSource.CANONICAL_MATCH
        )
        kept: list[ShotAssetRequirementProposal] = []
        for proposal in proposals:
            if not cls._is_placeholder_asset_id(proposal.matched_asset_id):
                kept.append(proposal)
                continue
            if any(cls._semantically_overlaps(proposal, stronger) for stronger in canonical):
                continue
            kept.append(proposal)
        return tuple(kept)

    @classmethod
    def _collapse_environment_overlaps(
        cls,
        proposals: tuple[ShotAssetRequirementProposal, ...],
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        """Keep the smallest useful location/environment set while preserving distinct production roles."""
        family = {
            AssetCategory.LOCATION,
            AssetCategory.ENVIRONMENT,
            AssetCategory.PLANET,
        }
        non_family = [
            proposal for proposal in proposals if proposal.expected_category not in family
        ]
        family_items = [proposal for proposal in proposals if proposal.expected_category in family]
        selected: list[ShotAssetRequirementProposal] = []

        for proposal in sorted(
            family_items,
            key=lambda item: (
                -cls._proposal_strength(item),
                cls._environment_specificity(item.expected_category),
                item.matched_asset_name.casefold(),
            ),
        ):
            duplicate = next(
                (
                    existing
                    for existing in selected
                    if existing.expected_category is proposal.expected_category
                    and cls._semantically_overlaps(existing, proposal)
                ),
                None,
            )
            if duplicate is None:
                selected.append(proposal)
                continue
            if cls._proposal_strength(proposal) > cls._proposal_strength(duplicate):
                selected.remove(duplicate)
                selected.append(proposal)

        combined = (*non_family, *selected)
        return tuple(
            sorted(
                combined,
                key=lambda proposal: (
                    cls._role_order(proposal.role),
                    proposal.expected_category.value,
                    proposal.matched_asset_name.casefold(),
                    proposal.requirement.casefold(),
                ),
            )
        )

    @staticmethod
    def _environment_specificity(category: AssetCategory) -> int:
        return {
            AssetCategory.LOCATION: 0,
            AssetCategory.ENVIRONMENT: 1,
            AssetCategory.PLANET: 2,
        }.get(category, 9)

    @staticmethod
    def _proposal_strength(proposal: ShotAssetRequirementProposal) -> float:
        status_bonus = 0.25 if proposal.canonical_status == "resolved" else 0.0
        canonical_bonus = (
            0.15 if proposal.source is ShotAssetInferenceSource.CANONICAL_MATCH else 0.0
        )
        placeholder_penalty = (
            0.35
            if GovernedAssetResolutionService._is_placeholder_asset_id(proposal.matched_asset_id)
            else 0.0
        )
        return proposal.confidence + status_bonus + canonical_bonus - placeholder_penalty

    @staticmethod
    def _is_placeholder_asset_id(asset_id: str) -> bool:
        normalized = asset_id.strip().upper()
        return normalized.startswith(("STORY-", "AUTO-", "TEMP-", "TMP-"))

    @classmethod
    def _semantically_overlaps(
        cls,
        left: ShotAssetRequirementProposal,
        right: ShotAssetRequirementProposal,
    ) -> bool:
        left_tokens = cls._semantic_tokens(left.matched_asset_name or left.requirement)
        right_tokens = cls._semantic_tokens(right.matched_asset_name or right.requirement)
        if not left_tokens or not right_tokens:
            return False
        shared = left_tokens.intersection(right_tokens)
        return bool(shared) and (
            len(shared) >= min(len(left_tokens), len(right_tokens))
            or any(len(token) >= 5 for token in shared)
        )

    @classmethod
    def _semantic_tokens(cls, value: str) -> set[str]:
        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "shot",
            "scene",
            "required",
            "visible",
            "context",
            "system",
            "orbit",
            "bridge",
            "environment",
            "location",
        }
        return {
            token
            for token in cls._normalize_text(value).split()
            if len(token) >= 4 and token not in stopwords
        }

    @staticmethod
    def _role_order(role: str) -> int:
        order = {
            "Dialogue Speaker": 0,
            "Supporting Character": 1,
            "Location": 2,
            "Environment Context": 3,
            "Visible Planet": 4,
            "Planetary Context": 5,
            "Vehicle/Ship": 6,
            "Prop/Technology": 7,
            "Wardrobe/Uniform": 8,
            "Effect": 9,
            "Audio": 10,
            "Other Production Asset": 11,
        }
        return order.get(role, 99)

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
            "coverage_role": shot.coverage_role.value,
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
