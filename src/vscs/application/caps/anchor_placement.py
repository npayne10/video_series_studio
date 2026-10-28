"""Local, deterministic anchor translations and axis-aligned collision checks."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.caps.geometry_contract import CAPGeometry, Vector3MM


class AnchorPlacement(BaseModel):
    """Place a child's local anchor at a parent anchor plus an explicit offset."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    parent_anchor: str = Field(min_length=1)
    child_anchor: str = Field(min_length=1)
    offset_mm: Vector3MM = Field(default_factory=lambda: Vector3MM(x=0, y=0, z=0))


@dataclass(frozen=True)
class PlacementFinding:
    code: str
    message: str


def place_at_anchor(
    parent: CAPGeometry, child: CAPGeometry, placement: AnchorPlacement
) -> tuple[CAPGeometry | None, tuple[PlacementFinding, ...]]:
    """Resolve a translation only; rotations and scale changes are unsupported."""
    parent_anchor = next(
        (item for item in parent.anchors if item.name == placement.parent_anchor), None
    )
    child_anchor = next(
        (item for item in child.anchors if item.name == placement.child_anchor), None
    )
    if parent_anchor is None or child_anchor is None:
        return None, (
            PlacementFinding("missing_anchor", "Named parent or child anchor does not exist"),
        )
    position = Vector3MM(
        x=parent_anchor.position_mm.x + placement.offset_mm.x - child_anchor.position_mm.x,
        y=parent_anchor.position_mm.y + placement.offset_mm.y - child_anchor.position_mm.y,
        z=parent_anchor.position_mm.z + placement.offset_mm.z - child_anchor.position_mm.z,
    )
    return (
        child.model_copy(update={"frame_id": parent.frame_id, "origin_mm": position}),
        (),
    )


def check_collision(first: CAPGeometry, second: CAPGeometry) -> tuple[PlacementFinding, ...]:
    """Strict AABB overlap; touching surfaces are not colliding."""
    if first.frame_id != second.frame_id:
        return (PlacementFinding("frame_mismatch", "Collision frames do not match"),)
    for axis in ("x", "y", "z"):
        first_min = getattr(first.origin_mm, axis)
        second_min = getattr(second.origin_mm, axis)
        first_max = first_min + getattr(first.size_mm, axis)
        second_max = second_min + getattr(second.size_mm, axis)
        if first_max <= second_min or second_max <= first_min:
            return ()
    return (PlacementFinding("collision", "Axis-aligned occupied bounds overlap"),)
