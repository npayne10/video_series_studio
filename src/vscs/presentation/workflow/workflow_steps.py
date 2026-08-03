"""Reusable workflow-step models for guided VSCS editors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """Describe one ordered task in an editor workflow."""

    step_id: str
    label: str
    recommendation: str
    topic_id: str
    optional: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowStepState:
    """Pair a workflow step with its current completion state."""

    step: WorkflowStep
    completed: bool


SCENE_WORKFLOW_STEPS = (
    WorkflowStep(
        "production_type",
        "Select production type",
        "Choose whether this scene belongs to an episode, trailer or another production.",
        "scene.production_type",
    ),
    WorkflowStep(
        "container_id",
        "Confirm container ID",
        "Confirm the canonical production container ID.",
        "scene.container_id",
    ),
    WorkflowStep(
        "scene_identity",
        "Name and identify the scene",
        "Enter a short scene name and screenplay heading.",
        "scene.name",
    ),
    WorkflowStep(
        "location",
        "Choose primary location",
        "Select the canonical location where the scene occurs.",
        "scene.location",
    ),
    WorkflowStep(
        "summary",
        "Describe the story event",
        "Summarise what happens and what changes in the scene.",
        "scene.summary",
    ),
    WorkflowStep(
        "participants",
        "Select participants",
        "Select every character who appears or speaks in the scene.",
        "scene.participants",
        optional=True,
    ),
    WorkflowStep(
        "required_assets",
        "Select required assets",
        "Select the ships, props, technology and effects required for production.",
        "scene.required_assets",
        optional=True,
    ),
    WorkflowStep(
        "dialogue",
        "Add dialogue",
        "Add and order spoken lines when the scene contains dialogue.",
        "scene.dialogue",
        optional=True,
    ),
    WorkflowStep(
        "production",
        "Review production settings",
        "Review time, transition and estimated scene duration.",
        "scene.duration",
    ),
    WorkflowStep(
        "validation",
        "Resolve validation issues",
        "Resolve all blocking issues so the scene is ready to save.",
        "scene.summary",
    ),
)
