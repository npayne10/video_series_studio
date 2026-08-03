"""Reusable, UI-independent onboarding step and sequence models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnboardingStep:
    """Describe one ordered step in an application onboarding guide."""

    step_id: str
    title: str
    description: str
    topic_id: str | None = None
    target_id: str | None = None

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("Onboarding step ID cannot be empty")
        if not self.title.strip():
            raise ValueError("Onboarding step title cannot be empty")
        if not self.description.strip():
            raise ValueError("Onboarding step description cannot be empty")


@dataclass(frozen=True, slots=True)
class OnboardingSequence:
    """Define one complete, versioned onboarding guide."""

    guide_id: str
    title: str
    steps: tuple[OnboardingStep, ...]
    version: int = 1

    def __post_init__(self) -> None:
        if not self.guide_id.strip():
            raise ValueError("Onboarding guide ID cannot be empty")
        if not self.title.strip():
            raise ValueError("Onboarding guide title cannot be empty")
        if self.version < 1:
            raise ValueError("Onboarding guide version must be at least 1")
        if not self.steps:
            raise ValueError("Onboarding sequence must contain at least one step")
        step_ids = tuple(step.step_id for step in self.steps)
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Onboarding step IDs must be unique within a sequence")

    @property
    def total_steps(self) -> int:
        """Return the number of steps in this guide."""
        return len(self.steps)

    def step(self, index: int) -> OnboardingStep:
        """Return the step at a zero-based index."""
        if index < 0 or index >= self.total_steps:
            raise IndexError("Onboarding step index is out of range")
        return self.steps[index]
