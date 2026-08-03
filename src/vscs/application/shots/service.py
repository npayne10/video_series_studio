"""Project-backed persistence and ordering for production shots."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.ssie import (
    CameraMovement,
    LensFamily,
    LightingMood,
    ShotPurpose,
    ShotSize,
)

from .models import ProductionShot, ShotPlanningStatus, build_shot_id


class ShotPlanningError(RuntimeError):
    """Raised when persistent shot planning data cannot be processed."""


class ShotPlanningService:
    """Create, replace, order and delete persistent production shots."""

    FILE_NAME = "shots.json"

    def __init__(self, projects: ProjectService) -> None:
        self.projects = projects

    @property
    def shot_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.FILE_NAME

    def list_shots(
        self,
        scene_id: str | None = None,
    ) -> tuple[ProductionShot, ...]:
        """Load shots in stable scene and sequence order."""
        path = self.shot_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            shots = tuple(
                self._from_dict(item) for item in raw.get("shots", [])
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ShotPlanningError(
                f"Unable to load shot plans: {exc}"
            ) from exc
        if scene_id is not None:
            shots = tuple(
                shot for shot in shots if shot.scene_id == scene_id
            )
        return tuple(
            sorted(
                shots,
                key=lambda shot: (
                    shot.scene_id,
                    shot.sequence_number,
                    shot.shot_id,
                ),
            )
        )

    def shot(self, shot_id: str) -> ProductionShot | None:
        """Return one persistent shot by identity."""
        return next(
            (
                shot
                for shot in self.list_shots()
                if shot.shot_id == shot_id
            ),
            None,
        )

    def next_sequence_number(self, scene_id: str) -> int:
        """Return the next available shot number inside a scene."""
        return (
            max(
                (
                    shot.sequence_number
                    for shot in self.list_shots(scene_id)
                ),
                default=0,
            )
            + 1
        )

    def generate_shot_id(
        self,
        scene_id: str,
        sequence_number: int,
    ) -> str:
        """Generate a unique stable shot ID."""
        base = build_shot_id(scene_id, sequence_number)
        existing = {shot.shot_id for shot in self.list_shots()}
        if base not in existing:
            return base
        suffix = 2
        while f"{base}-{suffix}" in existing:
            suffix += 1
        return f"{base}-{suffix}"

    def save_shot(self, shot: ProductionShot) -> ProductionShot:
        """Create or replace one shot after validating core fields."""
        if not shot.scene_id.strip():
            raise ValueError("Shot scene ID is required")
        if not shot.title.strip():
            raise ValueError("Shot title is required")
        if not shot.description.strip():
            raise ValueError("Shot description is required")
        if shot.estimated_duration_seconds <= 0:
            raise ValueError("Shot duration must be greater than zero")
        shots = {item.shot_id: item for item in self.list_shots()}
        shots[shot.shot_id] = shot
        self._write(tuple(shots.values()))
        return shot

    def delete_shot(self, shot_id: str) -> bool:
        """Delete one shot and retain the remaining sequence values."""
        shots = {item.shot_id: item for item in self.list_shots()}
        removed = shots.pop(shot_id, None)
        if removed is None:
            return False
        self._write(tuple(shots.values()))
        return True

    def reorder_scene(
        self,
        scene_id: str,
        ordered_shot_ids: tuple[str, ...],
    ) -> tuple[ProductionShot, ...]:
        """Persist an explicit sequence order for every shot in a scene."""
        current = self.list_shots(scene_id)
        by_id = {shot.shot_id: shot for shot in current}
        if (
            len(ordered_shot_ids) != len(by_id)
            or set(ordered_shot_ids) != set(by_id)
        ):
            raise ValueError(
                "Reorder must include every shot in the scene exactly once"
            )
        replacements = {
            shot_id: replace(
                by_id[shot_id],
                sequence_number=index,
            )
            for index, shot_id in enumerate(
                ordered_shot_ids,
                start=1,
            )
        }
        all_shots = tuple(
            replacements.get(shot.shot_id, shot)
            for shot in self.list_shots()
        )
        self._write(all_shots)
        return self.list_shots(scene_id)

    def _write(self, shots: tuple[ProductionShot, ...]) -> None:
        path = self.shot_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            shots,
            key=lambda shot: (
                shot.scene_id,
                shot.sequence_number,
                shot.shot_id,
            ),
        )
        payload = {
            "schema_version": "1.0",
            "shots": [self._to_dict(shot) for shot in ordered],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise ShotPlanningError(
                f"Unable to save shot plans: {exc}"
            ) from exc

    @staticmethod
    def _enum_value(value: StrEnum | str) -> str:
        """Serialize enum members and defensive string-backed values uniformly."""
        return value.value if isinstance(value, StrEnum) else str(value)

    @classmethod
    def _to_dict(cls, shot: ProductionShot) -> dict[str, Any]:
        raw = asdict(shot)
        raw["purpose"] = cls._enum_value(shot.purpose)
        raw["shot_size"] = cls._enum_value(shot.shot_size)
        raw["camera_movement"] = cls._enum_value(shot.camera_movement)
        raw["lens_family"] = cls._enum_value(shot.lens_family)
        raw["lighting_mood"] = cls._enum_value(shot.lighting_mood)
        raw["status"] = cls._enum_value(shot.status)
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> ProductionShot:
        return ProductionShot(
            shot_id=str(raw["shot_id"]),
            scene_id=str(raw["scene_id"]),
            sequence_number=int(raw["sequence_number"]),
            title=str(raw["title"]),
            description=str(raw["description"]),
            purpose=ShotPurpose(
                str(raw.get("purpose", ShotPurpose.COVERAGE.value))
            ),
            shot_size=ShotSize(
                str(raw.get("shot_size", ShotSize.MEDIUM.value))
            ),
            camera_movement=CameraMovement(
                str(
                    raw.get(
                        "camera_movement",
                        CameraMovement.STATIC.value,
                    )
                )
            ),
            lens_family=LensFamily(
                str(raw.get("lens_family", LensFamily.NORMAL.value))
            ),
            camera_profile_id=(
                None
                if raw.get("camera_profile_id") is None
                else str(raw["camera_profile_id"])
            ),
            lighting_profile_id=(
                None
                if raw.get("lighting_profile_id") is None
                else str(raw["lighting_profile_id"])
            ),
            lighting_mood=LightingMood(
                str(
                    raw.get(
                        "lighting_mood",
                        LightingMood.NATURALISTIC.value,
                    )
                )
            ),
            estimated_duration_seconds=float(
                raw.get("estimated_duration_seconds", 5.0)
            ),
            continuity_from_shot_id=(
                None
                if raw.get("continuity_from_shot_id") is None
                else str(raw["continuity_from_shot_id"])
            ),
            continuity_notes=str(raw.get("continuity_notes", "")),
            blocking_notes=str(raw.get("blocking_notes", "")),
            storyboard_reference=str(
                raw.get("storyboard_reference", "")
            ),
            dialogue_lines=tuple(
                str(value)
                for value in raw.get("dialogue_lines", [])
            ),
            subject_asset_ids=tuple(
                str(value)
                for value in raw.get("subject_asset_ids", [])
            ),
            required_asset_ids=tuple(
                str(value)
                for value in raw.get("required_asset_ids", [])
            ),
            status=ShotPlanningStatus(
                str(
                    raw.get(
                        "status",
                        ShotPlanningStatus.DRAFT.value,
                    )
                )
            ),
        )
