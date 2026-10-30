"""Read-only adapter for the production hierarchy shown in Story Workspace.

Story Workspace uses StoryService for scenes and ShotPlanningService for Shots.
A projection never creates a second Scene/Shot store.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.authoritative_shot_text import (
    AuthoritativeShotSnapshot,
    ShotTextAuthorityError,
    assert_shot_text_fresh,
    capture_authoritative_shot_text,
)
from vscs.application.caps.story_scene_authority import StorySceneAuthority
from vscs.application.shots.service import ShotPlanningService
from vscs.application.story.service import StoryService


@dataclass(frozen=True)
class GovernedPlanDiagnostics:
    scene_source: Path
    shot_source: Path
    scene_count: int
    shot_count: int
    scene_ids: tuple[str, ...]
    orphan_shot_ids: tuple[str, ...]


class GovernedProductionPlanAdapter:
    """Use precisely the persisted planning services underpinning Story Workspace."""

    def __init__(self, root: Path, scenes: StoryService, shots: ShotPlanningService) -> None:
        self.root = root
        self.scenes = scenes
        self.shots = shots

    def diagnostics(self) -> GovernedPlanDiagnostics:
        scenes = self.scenes.list_scenes()
        shots = self.shots.list_shots()
        ids = tuple(scene.scene_id for scene in scenes)
        registered = set(ids)
        return GovernedPlanDiagnostics(
            scene_source=self.scenes.story_file,
            shot_source=self.shots.shot_file,
            scene_count=len(scenes),
            shot_count=len(shots),
            scene_ids=ids,
            orphan_shot_ids=tuple(
                shot.shot_id for shot in shots if shot.scene_id not in registered
            ),
        )

    def verified_snapshot(
        self, story_id: str, approved_fingerprint: str
    ) -> AuthoritativeShotSnapshot:
        """Require explicit ownership and exact current persisted Shot content."""
        report = self.diagnostics()
        if report.orphan_shot_ids:
            raise ShotTextAuthorityError(
                "Persisted Shots reference missing Scenes: " + ", ".join(report.orphan_shot_ids)
            )
        scope = StorySceneAuthority(self.root, self.scenes).verify(story_id, approved_fingerprint)
        snapshot = capture_authoritative_shot_text(self.shots, scope, approved_fingerprint)
        assert_shot_text_fresh(snapshot, self.shots, scope, approved_fingerprint)
        return snapshot
