"""Immutable workflow manifest contracts for renderer integrations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from vscs.application.rendering.lip_sync import LipSyncMode
from vscs.application.rendering.models import QualityLevel, RendererKind
from vscs.application.rendering.outputs import RenderOutputKind


class WorkflowInputKind(StrEnum):
    """Renderer-neutral inputs that may be injected into a workflow."""

    POSITIVE_PROMPT = "positive_prompt"
    NEGATIVE_PROMPT = "negative_prompt"
    WIDTH = "width"
    HEIGHT = "height"
    FRAME_COUNT = "frame_count"
    FRAMES_PER_SECOND = "frames_per_second"
    SEED = "seed"
    START_FRAME = "start_frame"
    END_FRAME = "end_frame"
    REFERENCE_IMAGE = "reference_image"
    REFERENCE_IMAGES = "reference_images"
    LORA = "lora"
    AUDIO = "audio"
    OUTPUT_DIRECTORY = "output_directory"
    FILENAME_STEM = "filename_stem"


class WorkflowRequirementKind(StrEnum):
    """External resources required by a workflow."""

    CHECKPOINT = "checkpoint"
    VIDEO_MODEL = "video_model"
    LORA = "lora"
    VAE = "vae"
    CONTROLNET = "controlnet"
    CUSTOM_NODE = "custom_node"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class WorkflowMetadata:
    """Human and version metadata for one workflow manifest."""

    workflow_id: str
    display_name: str
    description: str
    renderer: RendererKind
    workflow_version: str
    manifest_version: str = "1.0"
    author: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("workflow_id", self.workflow_id),
            ("display_name", self.display_name),
            ("workflow_version", self.workflow_version),
            ("manifest_version", self.manifest_version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class WorkflowNodeSelector:
    """Stable selector used to locate a workflow node."""

    logical_name: str
    node_id: str | None = None
    node_title: str | None = None
    class_type: str | None = None

    def __post_init__(self) -> None:
        if not self.logical_name.strip():
            raise ValueError("logical_name is required")
        if not any((self.node_id, self.node_title, self.class_type)):
            raise ValueError(
                "a node selector requires node_id, node_title or class_type"
            )


@dataclass(frozen=True, slots=True)
class WorkflowNodeBinding:
    """Map one VSCS input to a field on a selected workflow node."""

    input_kind: WorkflowInputKind
    selector: WorkflowNodeSelector
    field_path: str
    required: bool = True

    def __post_init__(self) -> None:
        if not self.field_path.strip():
            raise ValueError("field_path is required")


@dataclass(frozen=True, slots=True)
class WorkflowRequirement:
    """One model, file or custom-node dependency."""

    kind: WorkflowRequirementKind
    identifier: str
    version: str | None = None
    optional: bool = False

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("requirement identifier is required")


@dataclass(frozen=True, slots=True)
class WorkflowManifest:
    """Versioned renderer-workflow declaration understood by VSCS."""

    metadata: WorkflowMetadata
    quality_levels: tuple[QualityLevel, ...]
    capabilities: tuple[str, ...] = ()
    bindings: tuple[WorkflowNodeBinding, ...] = ()
    requirements: tuple[WorkflowRequirement, ...] = ()
    output_kinds: tuple[RenderOutputKind, ...] = ()
    lip_sync_modes: tuple[LipSyncMode, ...] = ()
    tags: tuple[str, ...] = ()
    workflow_file: str | None = None
    extra: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.quality_levels:
            raise ValueError("at least one quality level is required")
        if len(self.quality_levels) != len(set(self.quality_levels)):
            raise ValueError("quality levels must be unique")
        input_kinds = [binding.input_kind for binding in self.bindings]
        if len(input_kinds) != len(set(input_kinds)):
            raise ValueError("workflow input bindings must be unique")
        requirement_keys = [
            (requirement.kind, requirement.identifier)
            for requirement in self.requirements
        ]
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("workflow requirements must be unique")
        if self.workflow_file is not None:
            normalized = self.workflow_file.replace("\\", "/")
            if normalized.startswith("/") or ".." in normalized.split("/"):
                raise ValueError("workflow_file must remain project-relative")

    @property
    def workflow_id(self) -> str:
        """Return the stable workflow identity."""
        return self.metadata.workflow_id

    def binding_for(
        self,
        input_kind: WorkflowInputKind,
    ) -> WorkflowNodeBinding | None:
        """Return one binding by renderer-neutral input identity."""
        return next(
            (
                binding
                for binding in self.bindings
                if binding.input_kind is input_kind
            ),
            None,
        )

    def supports_quality(self, quality_level: QualityLevel) -> bool:
        """Return whether this workflow supports a quality level."""
        return quality_level in self.quality_levels

    def to_dict(self) -> dict[str, Any]:
        """Serialize the manifest into JSON-compatible primitives."""
        return _primitive(asdict(self))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowManifest:
        """Construct a validated manifest from JSON-compatible data."""
        metadata_raw = _required_mapping(raw, "metadata")
        metadata = WorkflowMetadata(
            workflow_id=str(metadata_raw.get("workflow_id", "")),
            display_name=str(metadata_raw.get("display_name", "")),
            description=str(metadata_raw.get("description", "")),
            renderer=RendererKind(str(metadata_raw.get("renderer", ""))),
            workflow_version=str(metadata_raw.get("workflow_version", "")),
            manifest_version=str(metadata_raw.get("manifest_version", "1.0")),
            author=str(metadata_raw.get("author", "")),
        )
        bindings = tuple(
            _binding_from_dict(item)
            for item in _mapping_sequence(raw.get("bindings", ()), "bindings")
        )
        requirements = tuple(
            WorkflowRequirement(
                kind=WorkflowRequirementKind(str(item.get("kind", ""))),
                identifier=str(item.get("identifier", "")),
                version=(
                    str(item["version"])
                    if item.get("version") is not None
                    else None
                ),
                optional=bool(item.get("optional", False)),
            )
            for item in _mapping_sequence(
                raw.get("requirements", ()),
                "requirements",
            )
        )
        return cls(
            metadata=metadata,
            quality_levels=tuple(
                QualityLevel(str(value))
                for value in raw.get("quality_levels", ())
            ),
            capabilities=tuple(
                str(value) for value in raw.get("capabilities", ())
            ),
            bindings=bindings,
            requirements=requirements,
            output_kinds=tuple(
                RenderOutputKind(str(value))
                for value in raw.get("output_kinds", ())
            ),
            lip_sync_modes=tuple(
                LipSyncMode(str(value))
                for value in raw.get("lip_sync_modes", ())
            ),
            tags=tuple(str(value) for value in raw.get("tags", ())),
            workflow_file=(
                str(raw["workflow_file"])
                if raw.get("workflow_file") is not None
                else None
            ),
            extra=tuple(
                (str(key), str(value))
                for key, value in _required_pairs(raw.get("extra", ()), "extra")
            ),
        )


def workflow_manifest_schema() -> dict[str, Any]:
    """Return the stable JSON schema for workflow manifest documents."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "VSCS Workflow Manifest",
        "type": "object",
        "required": ["metadata", "quality_levels"],
        "properties": {
            "metadata": {
                "type": "object",
                "required": [
                    "workflow_id",
                    "display_name",
                    "renderer",
                    "workflow_version",
                ],
            },
            "quality_levels": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {
                    "enum": [level.value for level in QualityLevel],
                },
            },
            "bindings": {"type": "array"},
            "requirements": {"type": "array"},
            "capabilities": {"type": "array"},
            "output_kinds": {"type": "array"},
            "lip_sync_modes": {"type": "array"},
        },
        "additionalProperties": True,
    }


def _binding_from_dict(raw: dict[str, Any]) -> WorkflowNodeBinding:
    selector_raw = _required_mapping(raw, "selector")
    return WorkflowNodeBinding(
        input_kind=WorkflowInputKind(str(raw.get("input_kind", ""))),
        selector=WorkflowNodeSelector(
            logical_name=str(selector_raw.get("logical_name", "")),
            node_id=(
                str(selector_raw["node_id"])
                if selector_raw.get("node_id") is not None
                else None
            ),
            node_title=(
                str(selector_raw["node_title"])
                if selector_raw.get("node_title") is not None
                else None
            ),
            class_type=(
                str(selector_raw["class_type"])
                if selector_raw.get("class_type") is not None
                else None
            ),
        ),
        field_path=str(raw.get("field_path", "")),
        required=bool(raw.get("required", True)),
    )


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _mapping_sequence(value: object, name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{name} must be an array")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{name} entries must be objects")
    return tuple(value)


def _required_pairs(
    value: object,
    name: str,
) -> tuple[tuple[object, object], ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{name} must be an array")
    result: list[tuple[object, object]] = []
    for item in value:
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise ValueError(f"{name} entries must contain two values")
        result.append((item[0], item[1]))
    return tuple(result)


def _primitive(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _primitive(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_primitive(item) for item in value]
    return value
