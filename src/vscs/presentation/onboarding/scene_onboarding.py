"""Canonical onboarding sequence for the VSCS Scene Editor."""

from __future__ import annotations

from .onboarding_steps import OnboardingSequence, OnboardingStep


SCENE_EDITOR_ONBOARDING = OnboardingSequence(
    guide_id="scene-editor",
    title="Scene Editor Tour",
    version=1,
    steps=(
        OnboardingStep(
            "welcome",
            "Welcome to the Scene Editor",
            "Learn the scene-creation workflow and the assistance available while you work.",
        ),
        OnboardingStep(
            "production_type",
            "Choose the production type",
            "Choose whether the scene belongs to an episode, trailer, teaser or another container.",
            topic_id="scene.production_type",
            target_id="production_type",
        ),
        OnboardingStep(
            "container_id",
            "Confirm the container ID",
            "Use a stable container ID so scenes remain grouped and traceable.",
            topic_id="scene.container_id",
            target_id="container_id",
        ),
        OnboardingStep(
            "scene_identity",
            "Identify the scene",
            "Enter a concise scene name and a screenplay heading.",
            topic_id="scene.name",
            target_id="scene_identity",
        ),
        OnboardingStep(
            "location",
            "Choose the primary location",
            "Select the canonical Location or Environment asset where the scene occurs.",
            topic_id="scene.location",
            target_id="location",
        ),
        OnboardingStep(
            "participants",
            "Select participants",
            "Add every character who appears or speaks in the scene.",
            topic_id="scene.participants",
            target_id="participants",
        ),
        OnboardingStep(
            "required_assets",
            "Declare required assets",
            "Select the ships, props, technology and effects needed for production.",
            topic_id="scene.required_assets",
            target_id="required_assets",
        ),
        OnboardingStep(
            "dialogue",
            "Add dialogue",
            "Create ordered spoken lines and optional performance notes.",
            topic_id="scene.dialogue",
            target_id="dialogue",
        ),
        OnboardingStep(
            "production",
            "Review production settings",
            "Confirm time of day, transition and estimated scene duration.",
            topic_id="scene.duration",
            target_id="production",
        ),
        OnboardingStep(
            "validation",
            "Resolve validation issues",
            "Use the explanations to complete all information required before saving.",
            topic_id="scene.summary",
            target_id="validation",
        ),
        OnboardingStep(
            "save",
            "Create the scene",
            "Save the completed scene and continue working in the Story Browser.",
            topic_id="scene.summary",
            target_id="validation",
        ),
    ),
)
