from __future__ import annotations

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


def test_ready_stale_draft_must_return_to_draft_before_rebase(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")
    packages.value = replace(
        packages.value, package_id="PP-SHT-001-BBBB", source_fingerprint="source-2"
    )

    with pytest.raises(ActionPerformanceError, match="return to Draft"):
        service.rebase_to_current_package("SHT-001")
