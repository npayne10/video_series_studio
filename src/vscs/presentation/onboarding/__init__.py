"""Reusable onboarding framework for VSCS presentation workflows."""

from .onboarding_controller import (
    OnboardingController,
    OnboardingOutcome,
    OnboardingState,
)
from .onboarding_steps import OnboardingSequence, OnboardingStep
from .scene_onboarding import SCENE_EDITOR_ONBOARDING
from .welcome_overlay import OnboardingWelcomeOverlay

__all__ = [
    "SCENE_EDITOR_ONBOARDING",
    "OnboardingController",
    "OnboardingOutcome",
    "OnboardingSequence",
    "OnboardingState",
    "OnboardingStep",
    "OnboardingWelcomeOverlay",
]
