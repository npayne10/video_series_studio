"""Deterministic compilation of prompt graphs into renderer-neutral packages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import PromptGraph, PromptNode, PromptNodeKind
from .snapshot import graph_checksum
from .validation import (
    PromptGraphResourceInventory,
    PromptGraphValidationReport,
    PromptGraphValidator,
)


class PromptSectionKind(StrEnum):
    """Stable renderer-neutral prompt sections."""

    VISUAL_INTENT = "visual_intent"
    SCENE = "scene"
    CHARACTERS = "characters"
    ENVIRONMENT = "environment"
    CAMERA = "camera"
    LIGHTING = "lighting"
    MOVEMENT = "movement"
    CONTINUITY = "continuity"
    EFFECTS = "effects"
    DIALOGUE = "dialogue"
    AUDIO = "audio"
    STYLE = "style"
    QUALITY = "quality"
    RESTRICTIONS = "restrictions"
    NEGATIVE = "negative"
    RENDERER = "renderer"
    OTHER = "other"


_SECTION_ORDER: tuple[PromptSectionKind, ...] = (
    PromptSectionKind.VISUAL_INTENT,
    PromptSectionKind.SCENE,
    PromptSectionKind.CHARACTERS,
    PromptSectionKind.ENVIRONMENT,
    PromptSectionKind.CAMERA,
    PromptSectionKind.LIGHTING,
    PromptSectionKind.MOVEMENT,
    PromptSectionKind.CONTINUITY,
    PromptSectionKind.EFFECTS,
    PromptSectionKind.DIALOGUE,
    PromptSectionKind.AUDIO,
    PromptSectionKind.STYLE,
    PromptSectionKind.QUALITY,
    PromptSectionKind.RESTRICTIONS,
    PromptSectionKind.NEGATIVE,
    PromptSectionKind.RENDERER,
    PromptSectionKind.OTHER,
)


_NODE_SECTION: dict[PromptNodeKind, PromptSectionKind] = {
    PromptNodeKind.VISUAL_INTENT: PromptSectionKind.VISUAL_INTENT,
    PromptNodeKind.SCENE: PromptSectionKind.SCENE,
    PromptNodeKind.SHOT: PromptSectionKind.SCENE,
    PromptNodeKind.CHARACTER: PromptSectionKind.CHARACTERS,
    PromptNodeKind.SHIP: PromptSectionKind.ENVIRONMENT,
    PromptNodeKind.VEHICLE: PromptSectionKind.ENVIRONMENT,
    PromptNodeKind.LOCATION: PromptSectionKind.ENVIRONMENT,
    PromptNodeKind.ENVIRONMENT: PromptSectionKind.ENVIRONMENT,
    PromptNodeKind.PROP: PromptSectionKind.ENVIRONMENT,
    PromptNodeKind.CAMERA: PromptSectionKind.CAMERA,
    PromptNodeKind.LIGHTING: PromptSectionKind.LIGHTING,
    PromptNodeKind.MOVEMENT: PromptSectionKind.MOVEMENT,
    PromptNodeKind.CONTINUITY: PromptSectionKind.CONTINUITY,
    PromptNodeKind.EFFECT: PromptSectionKind.EFFECTS,
    PromptNodeKind.DIALOGUE: PromptSectionKind.DIALOGUE,
    PromptNodeKind.AUDIO: PromptSectionKind.AUDIO,
    PromptNodeKind.STYLE: PromptSectionKind.STYLE,
    PromptNodeKind.QUALITY: PromptSectionKind.QUALITY,
    PromptNodeKind.RESTRICTION: PromptSectionKind.RESTRICTIONS,
    PromptNodeKind.NEGATIVE: PromptSectionKind.NEGATIVE,
    PromptNodeKind.RENDERER: PromptSectionKind.RENDERER,
    PromptNodeKind.OTHER: PromptSectionKind.OTHER,
}


class PromptGraphCompilationError(ValueError):
    """Raised when graph compilation cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class PromptFragment:
    """One traceable node contribution to a compiled section."""

    node_id: str
    label: str
    text: str
    canonical_asset_id: str | None = None
    reference_ids: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    mandatory: bool = False
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class PromptSection:
    """One ordered renderer-neutral prompt section."""

    kind: PromptSectionKind
    fragments: tuple[PromptFragment, ...]

    @property
    def text(self) -> str:
        return "; ".join(fragment.text for fragment in self.fragments if fragment.text)


@dataclass(frozen=True, slots=True)
class PromptPackageProvenance:
    """Traceability from a prompt package back to its graph."""

    graph_id: str
    graph_version: str
    graph_checksum: str
    production_id: str
    container_id: str
    scene_id: str
    shot_id: str
    clip_id: str | None


@dataclass(frozen=True, slots=True)
class PromptPackage:
    """Renderer-neutral compiled prompt package."""

    package_id: str
    sections: tuple[PromptSection, ...]
    positive_prompt: str
    negative_prompt: str
    canonical_asset_ids: tuple[str, ...]
    reference_ids: tuple[str, ...]
    provenance: PromptPackageProvenance
    validation: PromptGraphValidationReport

    def section(self, kind: PromptSectionKind) -> PromptSection | None:
        return next((section for section in self.sections if section.kind is kind), None)


@dataclass(slots=True)
class PromptGraphCompiler:
    """Compile validated graph knowledge into deterministic prompt sections."""

    validator: PromptGraphValidator

    def compile(
        self,
        graph: PromptGraph,
        inventory: PromptGraphResourceInventory | None = None,
        *,
        require_production_ready: bool = True,
    ) -> PromptPackage:
        validation = self.validator.validate(graph, inventory)
        if not validation.passed:
            raise PromptGraphCompilationError(
                "prompt graph contains error-level validation issues"
            )
        if require_production_ready and not validation.completeness.production_ready:
            raise PromptGraphCompilationError(
                "prompt graph does not meet the production-readiness threshold"
            )

        buckets: dict[PromptSectionKind, list[PromptFragment]] = {
            kind: [] for kind in _SECTION_ORDER
        }
        for node in graph.topological_nodes():
            if node.kind is PromptNodeKind.ROOT:
                continue
            section_kind = _NODE_SECTION.get(node.kind, PromptSectionKind.OTHER)
            buckets[section_kind].append(self._fragment(node))

        sections = tuple(
            PromptSection(
                kind,
                tuple(
                    sorted(
                        buckets[kind],
                        key=lambda fragment: (fragment.sequence, fragment.node_id),
                    )
                ),
            )
            for kind in _SECTION_ORDER
            if buckets[kind]
        )
        negative = self._join_sections(
            sections,
            {PromptSectionKind.NEGATIVE, PromptSectionKind.RESTRICTIONS},
        )
        positive = self._join_sections(
            sections,
            set(PromptSectionKind)
            - {PromptSectionKind.NEGATIVE, PromptSectionKind.RESTRICTIONS},
        )
        canonical_asset_ids = tuple(
            sorted(
                {
                    fragment.canonical_asset_id
                    for section in sections
                    for fragment in section.fragments
                    if fragment.canonical_asset_id
                }
            )
        )
        reference_ids = tuple(
            sorted(
                {
                    reference_id
                    for section in sections
                    for fragment in section.fragments
                    for reference_id in fragment.reference_ids
                }
            )
        )
        metadata = graph.metadata
        provenance = PromptPackageProvenance(
            graph_id=metadata.graph_id,
            graph_version=metadata.version,
            graph_checksum=graph_checksum(graph),
            production_id=metadata.production_id,
            container_id=metadata.container_id,
            scene_id=metadata.scene_id,
            shot_id=metadata.shot_id,
            clip_id=metadata.clip_id,
        )
        return PromptPackage(
            package_id=f"{metadata.graph_id}:prompt",
            sections=sections,
            positive_prompt=positive,
            negative_prompt=negative,
            canonical_asset_ids=canonical_asset_ids,
            reference_ids=reference_ids,
            provenance=provenance,
            validation=validation,
        )

    @staticmethod
    def _fragment(node: PromptNode) -> PromptFragment:
        text = node.content.strip() or node.label.strip()
        return PromptFragment(
            node_id=node.node_id,
            label=node.label,
            text=text,
            canonical_asset_id=node.canonical_asset_id,
            reference_ids=node.reference_ids,
            attributes=node.attributes,
            mandatory=node.mandatory,
            sequence=node.sequence,
        )

    @staticmethod
    def _join_sections(
        sections: tuple[PromptSection, ...],
        included: set[PromptSectionKind],
    ) -> str:
        parts = [section.text for section in sections if section.kind in included]
        return ". ".join(part for part in parts if part)
