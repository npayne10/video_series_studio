"""Registry for versioned VSCS-managed generation workflow templates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class WorkflowEngine(StrEnum):
    """Supported execution engines for managed workflow templates."""

    COMFYUI = "comfyui"


class WorkflowPurpose(StrEnum):
    """Stable production purpose for a managed workflow."""

    DERIVED_REFERENCE = "derived_reference"
    VIDEO_GENERATION = "video_generation"
    AUDIO_GENERATION = "audio_generation"
    LIPSYNC = "lipsync"
    POSTPRODUCTION = "postproduction"


@dataclass(frozen=True, slots=True)
class ManagedWorkflow:
    """Descriptor for one versioned workflow template shipped with VSCS."""

    workflow_id: str
    purpose: WorkflowPurpose
    engine: WorkflowEngine
    model_family: str
    template_path: Path
    production_capable: bool
    requires: tuple[str, ...] = ()

    def load_text(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(f"VSCS workflow template not found: {self.template_path}")
        return self.template_path.read_text(encoding="utf-8")


class ManagedWorkflowRegistry:
    """Resolve workflow templates by stable ID or production purpose."""

    def __init__(self) -> None:
        self._items: dict[str, ManagedWorkflow] = {}

    def register(self, workflow: ManagedWorkflow) -> None:
        workflow_id = workflow.workflow_id.strip()
        if not workflow_id:
            raise ValueError("Workflow ID is required")
        self._items[workflow_id] = workflow

    def require(self, workflow_id: str) -> ManagedWorkflow:
        try:
            return self._items[workflow_id]
        except KeyError as exc:
            raise KeyError(f"VSCS workflow is not registered: {workflow_id}") from exc

    def for_purpose(self, purpose: WorkflowPurpose) -> tuple[ManagedWorkflow, ...]:
        return tuple(item for item in self._items.values() if item.purpose is purpose)


def default_workflow_registry() -> ManagedWorkflowRegistry:
    """Return the built-in workflow registry shipped with VSCS."""
    package_root = Path(__file__).resolve().parents[2]
    registry = ManagedWorkflowRegistry()
    registry.register(
        ManagedWorkflow(
            workflow_id="qwen.derived-reference.v2.1",
            purpose=WorkflowPurpose.DERIVED_REFERENCE,
            engine=WorkflowEngine.COMFYUI,
            model_family="qwen_image_edit_2511",
            template_path=(
                package_root
                / "workflows"
                / "image"
                / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
            ),
            production_capable=True,
            requires=(
                "master_reference",
                "positive_prompt",
                "negative_prompt",
                "view",
                "seed",
            ),
        )
    )
    return registry
