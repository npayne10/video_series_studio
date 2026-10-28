"""Phase B.5.11 deterministic named anchors and AABB collision safety."""

from vscs.application.caps.anchor_placement import (
    AnchorPlacement,
    check_collision,
    place_at_anchor,
)
from vscs.application.caps.geometry_contract import CAPGeometry


def _geometry(frame: str, origin: int, size: int, name: str) -> CAPGeometry:
    return CAPGeometry.model_validate(
        {
            "frame_id": frame,
            "origin_mm": {"x": origin, "y": 0, "z": 0},
            "size_mm": {"x": size, "y": size, "z": size},
            "anchors": [{"name": name, "position_mm": {"x": 400, "y": 400, "z": 400}}],
        }
    )


def test_named_anchor_translation_into_parent_coordinates():
    room = _geometry("room", 0, 2000, "mount")
    console = _geometry("console-local", 0, 200, "base")
    transformed, issues = place_at_anchor(
        room, console, AnchorPlacement(parent_anchor="mount", child_anchor="base")
    )
    assert issues == ()
    assert transformed is not None
    assert transformed.frame_id == "room"
    assert transformed.origin_mm.x == 0


def test_missing_anchor_fails_closed():
    placed, findings = place_at_anchor(
        _geometry("room", 0, 2000, "mount"),
        _geometry("console", 0, 200, "base"),
        AnchorPlacement(parent_anchor="missing", child_anchor="base"),
    )
    assert placed is None
    assert findings[0].code == "missing_anchor"


def test_axis_aligned_collision_and_noncollision():
    room_a = _geometry("room", 0, 300, "a")
    overlap = _geometry("room", 200, 300, "b")
    separated = _geometry("room", 300, 300, "c")
    assert check_collision(room_a, overlap)[0].code == "collision"
    assert check_collision(room_a, separated) == ()


def test_collision_requires_matching_frames():
    assert check_collision(
        _geometry("one", 0, 300, "a"), _geometry("two", 0, 300, "b")
    )[0].code == "frame_mismatch"
