"""Tests for the Phase 17.1 production hierarchy projection."""

from __future__ import annotations

from vscs.application.ssie import Scene, SceneTransition
from vscs.application.story import (
    StoryItemStatus,
    StoryNodeKind,
    build_story_hierarchy,
)


def _scene(
    scene_id: str,
    container_id: str,
    sequence: int,
    *,
    name: str,
    complete: bool = True,
) -> Scene:
    return Scene(
        scene_id=scene_id,
        episode_id=container_id,
        sequence_number=sequence,
        heading="EXT. XORIX ORBIT - DAY" if complete else "",
        location_asset_id="LOC-XORIX-ORBIT" if complete else "",
        summary="The crew arrives at Xorix." if complete else "",
        participant_asset_ids=("CHR-JAMES",),
        dialogue=(),
        required_asset_ids=("SHP-IRON-HORIZON",),
        time_of_day="day",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=20.0,
        scene_name=name,
    )


def test_hierarchy_groups_episodes_and_promotional_containers() -> None:
    hierarchy = build_story_hierarchy(
        (
            _scene("EP-001-SCN-001", "EP-001", 1, name="Arrival"),
            _scene("T01-SCN-001", "T01", 1, name="Trailer Arrival"),
        ),
        {},
        production_name="Xorix",
    )

    production = hierarchy.roots[0]
    assert production.kind is StoryNodeKind.PRODUCTION
    assert production.label == "Xorix"
    assert [child.kind for child in production.children] == [
        StoryNodeKind.SEASON,
        StoryNodeKind.COLLECTION,
    ]
    assert production.children[0].children[0].node_id == "EP-001"
    assert production.children[1].children[0].node_id == "T01"


def test_hierarchy_preserves_scene_order_and_status() -> None:
    hierarchy = build_story_hierarchy(
        (
            _scene("EP-001-SCN-002", "EP-001", 2, name="Second"),
            _scene(
                "EP-001-SCN-001",
                "EP-001",
                1,
                name="First",
                complete=False,
            ),
        ),
        {},
    )

    act = hierarchy.roots[0].children[0].children[0].children[0]
    assert [node.label for node in act.children] == ["First", "Second"]
    assert act.children[0].status is StoryItemStatus.DRAFT
    assert act.children[1].status is StoryItemStatus.READY
    assert act.status is StoryItemStatus.DRAFT


def test_hierarchy_statistics_count_unique_assets() -> None:
    hierarchy = build_story_hierarchy(
        (
            _scene("EP-001-SCN-001", "EP-001", 1, name="First"),
            _scene("EP-001-SCN-002", "EP-001", 2, name="Second"),
        ),
        {},
    )

    stats = hierarchy.statistics
    assert stats.containers == 1
    assert stats.scenes == 2
    assert stats.ready_scenes == 2
    assert stats.draft_scenes == 0
    assert stats.duration_seconds == 40.0
    assert stats.referenced_assets == 3
