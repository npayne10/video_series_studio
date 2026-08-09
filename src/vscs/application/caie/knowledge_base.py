"""Data-driven category and archetype knowledge for CAIE v2.0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from vscs.domain.assets import AssetCategory


class CAIEKnowledgeError(RuntimeError):
    """Raised when CAIE knowledge cannot be loaded or resolved."""


@dataclass(frozen=True, slots=True)
class DesignKnowledge:
    """One resolved category/archetype knowledge package."""

    knowledge_id: str
    name: str
    classification: str
    purpose: tuple[str, ...]
    required_features: tuple[str, ...]
    engineering_principles: tuple[str, ...]
    preferred_language: tuple[str, ...]
    forbidden_features: tuple[str, ...]
    forbidden_archetypes: tuple[str, ...]
    negative_terms: tuple[str, ...]
    required_anchors: tuple[str, ...]
    environment_guidance: str
    composition_guidance: str


@dataclass(frozen=True, slots=True)
class StyleKnowledge:
    """Reusable production style package."""

    style_id: str
    name: str
    positive_language: tuple[str, ...]
    negative_terms: tuple[str, ...]


class CAIEKnowledgeBase:
    """Load and resolve YAML knowledge without embedding design facts in code."""

    STYLE_ALIASES: ClassVar[dict[str, str]] = {
        "grounded_cinematic": "xorix_grounded_scifi",
        "neutral_reference": "xorix_grounded_scifi",
    }

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).with_name("knowledge")
        self._design_cache: dict[str, DesignKnowledge] = {}
        self._style_cache: dict[str, StyleKnowledge] = {}

    def resolve(
        self,
        *,
        category: AssetCategory,
        title: str,
        description: str = "",
        visual_identity: str = "",
    ) -> DesignKnowledge:
        """Resolve the most specific available knowledge package."""
        text = " ".join((title, description, visual_identity)).casefold()
        candidates = self._candidate_ids(category, text)
        for knowledge_id in candidates:
            path = self.root / f"{knowledge_id}.yaml"
            if path.is_file():
                return self.load_design(knowledge_id)
        raise CAIEKnowledgeError(
            f"No CAIE knowledge package is available for category '{category.value}'"
        )

    def load_design(self, knowledge_id: str) -> DesignKnowledge:
        cached = self._design_cache.get(knowledge_id)
        if cached is not None:
            return cached
        data = self._load_yaml(self.root / f"{knowledge_id}.yaml")
        knowledge = DesignKnowledge(
            knowledge_id=knowledge_id,
            name=self._required_text(data, "name"),
            classification=self._required_text(data, "classification"),
            purpose=self._text_tuple(data, "purpose"),
            required_features=self._text_tuple(data, "required_features"),
            engineering_principles=self._text_tuple(data, "engineering_principles"),
            preferred_language=self._text_tuple(data, "preferred_language"),
            forbidden_features=self._text_tuple(data, "forbidden_features"),
            forbidden_archetypes=self._text_tuple(data, "forbidden_archetypes"),
            negative_terms=self._text_tuple(data, "negative_terms"),
            required_anchors=self._text_tuple(data, "required_anchors"),
            environment_guidance=self._required_text(data, "environment_guidance"),
            composition_guidance=self._required_text(data, "composition_guidance"),
        )
        self._design_cache[knowledge_id] = knowledge
        return knowledge

    def load_style(self, style_id: str) -> StyleKnowledge:
        resolved_id = self.STYLE_ALIASES.get(style_id, style_id)
        cached = self._style_cache.get(resolved_id)
        if cached is not None:
            return cached
        path = self.root / "styles" / f"{resolved_id}.yaml"
        data = self._load_yaml(path)
        style = StyleKnowledge(
            style_id=resolved_id,
            name=self._required_text(data, "name"),
            positive_language=self._text_tuple(data, "positive_language"),
            negative_terms=self._text_tuple(data, "negative_terms"),
        )
        self._style_cache[resolved_id] = style
        return style

    @staticmethod
    def _candidate_ids(category: AssetCategory, text: str) -> tuple[str, ...]:
        if category is AssetCategory.SHIP:
            if any(token in text for token in ("tug", "tow craft", "towing craft")):
                return ("ships/orbital_tug", "ships/generic_spacecraft")
            return ("ships/generic_spacecraft",)
        category_defaults: dict[AssetCategory, str] = {
            AssetCategory.CHARACTER: "characters/generic_character",
            AssetCategory.VEHICLE: "vehicles/generic_vehicle",
            AssetCategory.LOCATION: "locations/generic_location",
            AssetCategory.ENVIRONMENT: "environments/generic_environment",
            AssetCategory.PLANET: "planets/generic_planet",
            AssetCategory.PROP: "props/generic_prop",
            AssetCategory.TECHNOLOGY: "technology/generic_technology",
            AssetCategory.UNIFORM: "uniforms/generic_uniform",
            AssetCategory.EFFECT: "effects/generic_effect",
        }
        knowledge_id = category_defaults.get(category, "generic_asset")
        return (knowledge_id, "generic_asset")

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CAIEKnowledgeError(f"Unable to read CAIE knowledge file {path}: {exc}") from exc
        except yaml.YAMLError as exc:
            raise CAIEKnowledgeError(f"Invalid CAIE knowledge YAML {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise CAIEKnowledgeError(f"CAIE knowledge file must contain a mapping: {path}")
        return raw

    @staticmethod
    def _required_text(data: dict[str, Any], key: str) -> str:
        value = str(data.get(key, "")).strip()
        if not value:
            raise CAIEKnowledgeError(f"CAIE knowledge field '{key}' is required")
        return value

    @staticmethod
    def _text_tuple(data: dict[str, Any], key: str) -> tuple[str, ...]:
        value = data.get(key, ())
        if value is None:
            return ()
        if not isinstance(value, list):
            raise CAIEKnowledgeError(f"CAIE knowledge field '{key}' must be a list")
        return tuple(str(item).strip() for item in value if str(item).strip())
