"""Phase B.5.10: deterministic spatial containment without AI/provider calls."""

import pytest
from pydantic import ValidationError

from vscs.application.caps.geometry_contract import (
    CAPGeometry,
    check_containment,
)


def _geometry(
    size: tuple[float, float, float],
    origin: tuple[float, float, float] = (0, 0, 0),
    frame: str = "room-001",
) -> CAPGeometry:
    return CAPGeometry.model_validate(
        {
            "frame_id": frame,
            "size_mm": dict(zip(("x", "y", "z"), size, strict=True)),
            "origin_mm": dict(zip(("x", "y", "z"), origin, strict=True)),
        }
    )


def test_console_inside_room_with_clearance_is_compatible():
    room = _geometry((8000, 5000, 2600))
    console = _geometry((1500, 700, 950), (2000, 1500, 400))
    assert check_containment(room, console, 300) == ()


def test_console_overlaps_wall_is_out_of_bounds():
    room = _geometry((8000, 5000, 2600))
    console = _geometry((2000, 700, 950), (7000, 1500, 400))
    assert check_containment(room, console)[0].code == "out_of_bounds"


def test_clearance_violation_is_detected():
    room = _geometry((8000, 5000, 2600))
    console = _geometry((1500, 700, 950), (200, 1500, 400))
    assert check_containment(room, console, 300)[0].code == "out_of_bounds"


def test_mismatched_frames_cannot_be_compared():
    assert check_containment(
        _geometry((8000, 5000, 2600)),
        _geometry((1000, 500, 1000), frame="ship-002"),
    )[0].code == "frame_mismatch"


def test_invalid_dimensions_and_duplicate_anchors_rejected():
    with pytest.raises(ValidationError):
        _geometry((0, 5000, 2600))
    with pytest.raises(ValidationError):
        CAPGeometry.model_validate(
            {
                "frame_id": "room-001",
                "size_mm": {"x": 8000, "y": 5000, "z": 2600},
                "origin_mm": {"x": 0, "y": 0, "z": 0},
                "anchors": [
                    {"name": "Console", "position_mm": {"x": 1, "y": 1, "z": 1}},
                    {"name": "console", "position_mm": {"x": 2, "y": 2, "z": 2}},
                ],
            }
        )
