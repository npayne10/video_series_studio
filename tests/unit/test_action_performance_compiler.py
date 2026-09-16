from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from vscs.application.action_performance import (
    ActionPerformanceCompilerService,
    ActionPerformanceError,
    ActionPerformanceStatus,
)


@dataclass(frozen=True)
class _Package:
    package_id: str = "PP-SHT-001-AAAA"
    shot_id: str = "SHT-001"
    source_fingerprint: str = "source-1"
    shot: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.shot is None:
            object.__setattr__(
                self,
                "shot",
                {
                    "required_action": "James walks to Cheryl at the viewport.",
                    "dialogue_requirement": "James greets Cheryl.",
                    "continuity_in": "James enters from the upper stairs.",
                    "continuity_out": "James stands beside Cheryl.",
                    "target_runtime_seconds": 12,
                },
            )


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        self.value = _Package()
        self.compiled: dict[str, Any] | None = None

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def derive_action_performance(self, _shot_id: str, compiled: dict[str, Any]):
        self.compiled = compiled
        return self.value


def _service(tmp_path: Path):
    packages = _Packages()
    service = ActionPerformanceCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_suggested_draft_preserves_governed_shot_story_without_invention(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-001")

    assert draft.temporal_narrative == "James walks to Cheryl at the viewport."
    assert draft.spoken_content == "James greets Cheryl."
    assert draft.opening_state == "James enters from the upper stairs."
    assert draft.closing_state == "James stands beside Cheryl."
    assert draft.performance_direction == ""
    assert draft.source_authority is not None
    assert draft.source_authority.target_runtime_seconds == "12"
    assert draft.status is ActionPerformanceStatus.DRAFT


def test_ready_action_performance_compiles_into_provider_neutral_package_section(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save(
        "SHT-001",
        temporal_narrative="James walks down the stairs, sees Cheryl, approaches her, and speaks.",
        spoken_content='James: "Hi Cheryl."',
        performance_direction="Natural, restrained familiarity.",
        opening_state="James is on the upper bridge level.",
        closing_state="James stands beside Cheryl at the viewport.",
        timing_notes="Complete within 12 seconds.",
    )
    ready = service.mark_ready("SHT-001")

    assert ready.status is ActionPerformanceStatus.READY
    assert packages.compiled is not None
    assert packages.compiled["temporal_narrative"].startswith("James walks down")
    assert packages.compiled["provider_neutral"] is True
    assert packages.compiled["source"] == "human-reviewed-action-performance"


def test_empty_temporal_narrative_cannot_be_ready(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save(
        "SHT-001",
        temporal_narrative="",
        spoken_content="",
        performance_direction="",
        opening_state="",
        closing_state="",
        timing_notes="",
    )
    with pytest.raises(ActionPerformanceError, match="Temporal narrative"):
        service.mark_ready("SHT-001")


def test_ready_draft_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    with pytest.raises(ActionPerformanceError, match="return to Draft"):
        service.save(
            "SHT-001",
            temporal_narrative="Changed",
            spoken_content="",
            performance_direction="",
            opening_state="",
            closing_state="",
            timing_notes="",
        )

    draft = service.return_to_draft("SHT-001")
    assert draft.status is ActionPerformanceStatus.DRAFT


def test_upstream_production_package_change_makes_action_performance_stale(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-001")
    packages.value = replace(
        packages.value, package_id="PP-SHT-001-BBBB", source_fingerprint="source-2"
    )

    assert not service.is_current(draft)
    with pytest.raises(ActionPerformanceError, match="stale"):
        service.mark_ready("SHT-001")


def test_stale_draft_can_rebase_without_losing_authored_content(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    authored = service.save(
        "SHT-001",
        temporal_narrative="James crosses the bridge, pauses, then speaks to Cheryl.",
        spoken_content='James: "Good morning."',
        performance_direction="Quiet familiarity.",
        opening_state="James enters from the stairs.",
        closing_state="James and Cheryl stand together at the viewport.",
        timing_notes="Complete naturally within 12 seconds.",
    )
    packages.value = replace(
        packages.value, package_id="PP-SHT-001-BBBB", source_fingerprint="source-2"
    )

    assert not service.is_current(authored)
    assert service.structural_changes(authored) == ()
    rebased = service.rebase_to_current_package("SHT-001")

    assert service.is_current(rebased)
    assert rebased.status is ActionPerformanceStatus.DRAFT
    assert rebased.source_package_id == "PP-SHT-001-BBBB"
    assert rebased.source_fingerprint == "source-2"
    assert rebased.temporal_narrative == authored.temporal_narrative
    assert rebased.spoken_content == authored.spoken_content
    assert rebased.performance_direction == authored.performance_direction
    assert rebased.opening_state == authored.opening_state
    assert rebased.closing_state == authored.closing_state
    assert rebased.timing_notes == authored.timing_notes


def test_structural_shot_split_blocks_rebase_and_rebuilds_current_authority(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    old_shot = {
        "required_action": (
            "Establish nine days in the Xorix system. Sandra reports something unusual to James."
        ),
        "dialogue_requirement": (
            'Sandra: "Commander, I have something unusual." James: "How unusual?"'
        ),
        "continuity_in": "The Iron Horizon is in orbit before any anomaly is known.",
        "continuity_out": "James is attending to Sandra's report at her control station.",
        "target_runtime_seconds": 22,
    }
    packages.value = replace(packages.value, shot=old_shot)
    service.create_from_current_package("SHT-001")
    authored = service.save(
        "SHT-001",
        temporal_narrative=old_shot["required_action"],
        spoken_content=old_shot["dialogue_requirement"],
        performance_direction="Keep the opening observational and restrained.",
        opening_state=old_shot["continuity_in"],
        closing_state=old_shot["continuity_out"],
        timing_notes="Target runtime: 22 seconds",
    )

    current_shot = {
        "required_action": "Establish the Iron Horizon in orbit around Xorix after nine days.",
        "dialogue_requirement": "",
        "continuity_in": "The Iron Horizon remains in stable Xorix orbit.",
        "continuity_out": "Sandra looks up from her control station before speaking.",
        "target_runtime_seconds": 6,
    }
    packages.value = replace(
        packages.value,
        package_id="PP-SHT-001-SPLIT",
        source_fingerprint="source-split",
        shot=current_shot,
    )

    changes = service.structural_changes(authored)
    assert {change.field for change in changes} == {
        "required_action",
        "dialogue_requirement",
        "continuity_in",
        "continuity_out",
        "target_runtime_seconds",
    }
    with pytest.raises(ActionPerformanceError, match="Rebase / Preserve is blocked"):
        service.rebase_to_current_package("SHT-001")
    with pytest.raises(ActionPerformanceError, match="stale or structurally unverified"):
        service.save(
            "SHT-001",
            temporal_narrative=authored.temporal_narrative,
            spoken_content=authored.spoken_content,
            performance_direction=authored.performance_direction,
            opening_state=authored.opening_state,
            closing_state=authored.closing_state,
            timing_notes=authored.timing_notes,
        )

    rebuilt = service.rebuild_from_current_package("SHT-001")

    assert rebuilt.status is ActionPerformanceStatus.DRAFT
    assert rebuilt.temporal_narrative == current_shot["required_action"]
    assert rebuilt.spoken_content == ""
    assert rebuilt.opening_state == current_shot["continuity_in"]
    assert rebuilt.closing_state == current_shot["continuity_out"]
    assert rebuilt.timing_notes == "Target runtime: 6 seconds"
    assert rebuilt.performance_direction == "Keep the opening observational and restrained."
    assert service.is_current(rebuilt)


def test_legacy_draft_without_authority_snapshot_cannot_be_silently_current(
    tmp_path: Path,
) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")

    payload = json.loads(service.draft_file.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.0"
    payload["action_performance"][0].pop("source_authority", None)
    service.draft_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    legacy = service.draft("SHT-001")
    assert legacy is not None
    assert legacy.source_authority is None
    assert not service.is_current(legacy)
    changes = service.structural_changes(legacy)
    assert len(changes) == 1
    assert changes[0].field == "source_authority"

    with pytest.raises(ActionPerformanceError, match="Rebase / Preserve is blocked"):
        service.rebase_to_current_package("SHT-001")

    rebuilt = service.rebuild_from_current_package("SHT-001")
    assert rebuilt.source_authority is not None
    assert service.is_current(rebuilt)


def test_ready_stale_draft_must_return_to_draft_before_rebase(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")
    packages.value = replace(
        packages.value, package_id="PP-SHT-001-BBBB", source_fingerprint="source-2"
    )

    with pytest.raises(ActionPerformanceError, match="return to Draft"):
        service.rebase_to_current_package("SHT-001")
