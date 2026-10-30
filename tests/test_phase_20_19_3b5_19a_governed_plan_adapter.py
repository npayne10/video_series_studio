"""CAP governed adapter uses Story Workspace source services, never duplicate records."""

from types import SimpleNamespace

import pytest

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.governed_plan_adapter import GovernedProductionPlanAdapter
from vscs.application.shots.models import ProductionShot
from vscs.application.shots.service import ShotPlanningService
from vscs.application.story.service import StoryService


def _project(tmp_path):
    project = SimpleNamespace(project_directory=tmp_path)
    return StoryService(project), ShotPlanningService(project)


def test_missing_scenes_reports_active_source_without_creating_files(tmp_path):
    scenes, shots = _project(tmp_path)
    report = GovernedProductionPlanAdapter(tmp_path, scenes, shots).diagnostics()
    assert report.scene_count == 0
    assert report.scene_source == tmp_path / "story" / "scenes.json"
    assert report.shot_source == tmp_path / "story" / "shots.json"
    assert not (tmp_path / "story").exists()


def test_orphan_shots_are_rejected_without_autocreating_scenes(tmp_path):
    scenes, shots = _project(tmp_path)
    shot = ProductionShot(
        shot_id="SCN-001-SHT-001",
        scene_id="SCN-001",
        sequence_number=1,
        title="Console",
        description="Diagnostic Console inside Engineering Control Room.",
    )
    shots.save_shot(shot)
    adapter = GovernedProductionPlanAdapter(tmp_path, scenes, shots)
    assert adapter.diagnostics().orphan_shot_ids == (shot.shot_id,)
    with pytest.raises(ShotTextAuthorityError, match="missing Scenes"):
        adapter.verified_snapshot("STORY-001", "digest")
    assert not scenes.story_file.exists()
