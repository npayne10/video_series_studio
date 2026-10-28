"""Typed Draft-only AABB geometry and deterministic local continuity checks.

All units are millimetres. Coordinates use a shared, operator-defined local
frame: x right, y forward, z up. No implied canonical approval.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Vector3MM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    z: float


class DimensionsMM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(gt=0)
    y: float = Field(gt=0)
    z: float = Field(gt=0)


class SpatialAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1)
    position_mm: Vector3MM


class CAPGeometry(BaseModel):
    """Axis-aligned occupied bounds in a declared project-local frame."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    frame_id: str = Field(min_length=1)
    size_mm: DimensionsMM
    origin_mm: Vector3MM
    anchors: tuple[SpatialAnchor, ...] = ()

    @model_validator(mode="after")
    def unique_anchors(self) -> CAPGeometry:
        names = [anchor.name.casefold() for anchor in self.anchors]
        if len(names) != len(set(names)):
            raise ValueError("Geometry anchor names must be unique")
        return self


@dataclass(frozen=True)
class GeometryFinding:
    code: str
    message: str


def check_containment(
    container: CAPGeometry,
    target: CAPGeometry,
    minimum_clearance_mm: float | None = None,
) -> tuple[GeometryFinding, ...]:
    """Check two AABBs in the same frame; rotation and obstacles are out of scope."""
    if container.frame_id != target.frame_id:
        return (GeometryFinding("frame_mismatch", "Geometry frames do not match"),)
    clearance = 0.0 if minimum_clearance_mm is None else minimum_clearance_mm
    if clearance < 0:
        raise ValueError("Minimum clearance cannot be negative")
    for axis in ("x", "y", "z"):
        c_min = getattr(container.origin_mm, axis)
        c_max = c_min + getattr(container.size_mm, axis)
        t_min = getattr(target.origin_mm, axis)
        t_max = t_min + getattr(target.size_mm, axis)
        if t_min < c_min + clearance or t_max > c_max - clearance:
            return (
                GeometryFinding(
                    "out_of_bounds",
                    f"Target bounds violate container {axis}-axis clearance of {clearance:g} mm",
                ),
            )
    return ()
