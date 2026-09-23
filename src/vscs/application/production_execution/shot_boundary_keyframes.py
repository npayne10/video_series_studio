"""Governed Shot Boundary Keyframe authority for Phase 20.18.2.2i."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class GovernedShotBoundaryError(RuntimeError):
    """Raised when shot-boundary continuity authority is missing, stale, or unsafe."""


class ShotBoundaryContinuityMode(StrEnum):
    """Explicit authority controlling how one shot opens relative to another."""

    CONTINUOUS = "continuous"
    NEW_COMPOSITION = "new_composition"
    SCENE_ENTRY = "scene_entry"
    DISCONTINUITY = "discontinuity"
    MATCH_CUT = "match_cut"
    SPECIAL = "special"

    @property
    def inherits_previous_closing_frame(self) -> bool:
        return self in {
            ShotBoundaryContinuityMode.CONTINUOUS,
            ShotBoundaryContinuityMode.MATCH_CUT,
            ShotBoundaryContinuityMode.SPECIAL,
        }


@dataclass(frozen=True, slots=True)
class GovernedClosingBoundaryFrame:
    """Exact final governed frame published by one human-approved Generated Media video."""

    boundary_id: str
    shot_id: str
    image_path: str
    image_sha256: str
    source_media_id: str
    source_execution_id: str
    source_media_revision: int
    source_media_sha256: str
    frame_index: int
    frame_count: int
    width: int
    height: int
    frame_rate: str
    published_by: str
    published_at: str
    status: str = "published"
    schema_version: str = "1.0"

    @property
    def published(self) -> bool:
        return (
            self.status == "published"
            and bool(self.published_by.strip())
            and self.frame_count > 0
            and self.frame_index == self.frame_count - 1
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "boundary_id": self.boundary_id,
            "shot_id": self.shot_id,
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "source_media_id": self.source_media_id,
            "source_execution_id": self.source_execution_id,
            "source_media_revision": self.source_media_revision,
            "source_media_sha256": self.source_media_sha256,
            "frame_index": self.frame_index,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "published_by": self.published_by,
            "published_at": self.published_at,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class OpeningShotBoundaryAuthority:
    """Resolved opening authority for one target shot."""

    shot_id: str
    mode: ShotBoundaryContinuityMode
    inherited: bool
    source_shot_id: str | None = None
    boundary_id: str | None = None
    image_path: str | None = None
    image_sha256: str | None = None
    source_media_id: str | None = None
    source_media_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "shot_id": self.shot_id,
            "mode": self.mode.value,
            "inherited": self.inherited,
            "source_shot_id": self.source_shot_id,
            "boundary_id": self.boundary_id,
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "source_media_id": self.source_media_id,
            "source_media_sha256": self.source_media_sha256,
        }


@dataclass(frozen=True, slots=True)
class ShotBoundaryAuthorityStatus:
    """Operator-visible opening and closing boundary authority for one shot."""

    shot_id: str
    opening_mode: ShotBoundaryContinuityMode
    opening_state: str
    opening_source_shot_id: str | None = None
    opening_boundary_id: str | None = None
    closing_state: str = "not_published"
    closing_boundary_id: str | None = None
    closing_frame_index: int | None = None
    closing_frame_count: int | None = None
    message: str = ""


class GovernedShotBoundaryStore:
    """Persist closing boundary frames and resolve explicit opening inheritance."""

    RELATIVE_PATH = Path(".vscs") / "governed_shot_boundaries.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def current_closing(self, shot_id: str) -> GovernedClosingBoundaryFrame | None:
        normalized = self._shot_id(shot_id)
        candidates = tuple(
            self._from_dict(raw)
            for raw in self._records()
            if str(raw.get("shot_id") or "").strip().upper() == normalized
        )
        return candidates[-1] if candidates else None

    def require_current_closing(self, shot_id: str) -> GovernedClosingBoundaryFrame:
        record = self.current_closing(shot_id)
        if record is None:
            raise GovernedShotBoundaryError(
                f"No governed closing boundary frame is published for {self._shot_id(shot_id)}."
            )
        if not record.published:
            raise GovernedShotBoundaryError(
                f"Governed closing boundary frame for {record.shot_id} is not published."
            )
        image = self.resolve_image(record.image_path)
        if not image.is_file():
            raise GovernedShotBoundaryError(
                f"Governed closing boundary image does not exist: {image}"
            )
        if self._sha256(image) != record.image_sha256:
            raise GovernedShotBoundaryError(
                "Governed closing boundary image checksum no longer matches published authority."
            )
        return record

    def save(self, record: GovernedClosingBoundaryFrame) -> GovernedClosingBoundaryFrame:
        if not record.published:
            raise GovernedShotBoundaryError(
                "Governed closing boundary must identify the exact final frame before publication."
            )
        image = self.resolve_image(record.image_path)
        if not image.is_file():
            raise GovernedShotBoundaryError(
                f"Governed closing boundary image does not exist: {image}"
            )
        if self._sha256(image) != record.image_sha256:
            raise GovernedShotBoundaryError(
                "Governed closing boundary checksum does not match the image being published."
            )
        records = self._records()
        if any(
            str(raw.get("boundary_id") or "").strip() == record.boundary_id
            for raw in records
        ):
            return self.require_current_closing(record.shot_id)
        records.append(record.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {"schema_version": "1.0", "boundaries": records},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return self.require_current_closing(record.shot_id)

    def resolve_opening(
        self,
        shot_id: str,
        production_authority: dict[str, Any],
    ) -> OpeningShotBoundaryAuthority:
        normalized_shot = self._shot_id(shot_id)
        continuity = production_authority.get("continuity")
        mapping = continuity if isinstance(continuity, dict) else {}
        mode = self._mode(mapping)
        if not mode.inherits_previous_closing_frame:
            return OpeningShotBoundaryAuthority(
                shot_id=normalized_shot,
                mode=mode,
                inherited=False,
            )

        source_shot_id = self._source_shot_id(mapping)
        if source_shot_id is None:
            raise GovernedShotBoundaryError(
                f"{mode.value} opening continuity for {normalized_shot} requires source_shot_id."
            )
        if source_shot_id == normalized_shot:
            raise GovernedShotBoundaryError(
                "A shot cannot inherit its opening boundary from its own closing boundary."
            )
        closing = self.require_current_closing(source_shot_id)
        return OpeningShotBoundaryAuthority(
            shot_id=normalized_shot,
            mode=mode,
            inherited=True,
            source_shot_id=source_shot_id,
            boundary_id=closing.boundary_id,
            image_path=closing.image_path,
            image_sha256=closing.image_sha256,
            source_media_id=closing.source_media_id,
            source_media_sha256=closing.source_media_sha256,
        )

    def validate_compiled_opening(
        self,
        shot_id: str,
        production_authority: dict[str, Any],
        compiled: object,
    ) -> OpeningShotBoundaryAuthority:
        current = self.resolve_opening(shot_id, production_authority)
        if not isinstance(compiled, dict):
            raise GovernedShotBoundaryError(
                "Compiled Production Package has no shot-boundary continuity authority."
            )
        expected = current.to_dict()
        for key in (
            "mode",
            "inherited",
            "source_shot_id",
            "boundary_id",
            "image_sha256",
            "source_media_id",
            "source_media_sha256",
        ):
            if compiled.get(key) != expected.get(key):
                raise GovernedShotBoundaryError(
                    "Compiled opening continuity is stale because its source closing boundary "
                    "authority changed. Recompile the Production Package."
                )
        return current

    def resolve_image(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.project_directory):
            raise GovernedShotBoundaryError(
                "Governed closing boundary image must remain inside the project."
            )
        return resolved

    def _records(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GovernedShotBoundaryError(
                f"Cannot read governed shot-boundary authority: {exc}"
            ) from exc
        raw = root.get("boundaries", []) if isinstance(root, dict) else None
        if not isinstance(raw, list):
            raise GovernedShotBoundaryError("Governed shot-boundary authority store is invalid.")
        return [dict(item) for item in raw if isinstance(item, dict)]

    @staticmethod
    def _from_dict(raw: dict[str, object]) -> GovernedClosingBoundaryFrame:
        return GovernedClosingBoundaryFrame(
            boundary_id=str(raw.get("boundary_id") or "").strip(),
            shot_id=str(raw.get("shot_id") or "").strip().upper(),
            image_path=str(raw.get("image_path") or "").strip(),
            image_sha256=str(raw.get("image_sha256") or "").strip().lower(),
            source_media_id=str(raw.get("source_media_id") or "").strip(),
            source_execution_id=str(raw.get("source_execution_id") or "").strip(),
            source_media_revision=int(raw.get("source_media_revision") or 0),
            source_media_sha256=str(raw.get("source_media_sha256") or "").strip().lower(),
            frame_index=int(raw.get("frame_index") or 0),
            frame_count=int(raw.get("frame_count") or 0),
            width=int(raw.get("width") or 0),
            height=int(raw.get("height") or 0),
            frame_rate=str(raw.get("frame_rate") or "").strip(),
            published_by=str(raw.get("published_by") or "").strip(),
            published_at=str(raw.get("published_at") or "").strip(),
            status=str(raw.get("status") or "").strip().lower(),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )

    @staticmethod
    def _mode(continuity: dict[str, Any]) -> ShotBoundaryContinuityMode:
        raw = next(
            (
                continuity.get(key)
                for key in ("shot_boundary_mode", "boundary_mode", "continuity_mode")
                if continuity.get(key) is not None
            ),
            ShotBoundaryContinuityMode.NEW_COMPOSITION.value,
        )
        normalized = str(raw).strip().casefold().replace("-", "_").replace(" ", "_")
        aliases = {
            "continuous": ShotBoundaryContinuityMode.CONTINUOUS,
            "new_composition": ShotBoundaryContinuityMode.NEW_COMPOSITION,
            "scene_entry": ShotBoundaryContinuityMode.SCENE_ENTRY,
            "discontinuity": ShotBoundaryContinuityMode.DISCONTINUITY,
            "match_cut": ShotBoundaryContinuityMode.MATCH_CUT,
            "special": ShotBoundaryContinuityMode.SPECIAL,
        }
        try:
            return aliases[normalized]
        except KeyError as exc:
            raise GovernedShotBoundaryError(
                f"Unsupported shot-boundary continuity mode: {raw!r}"
            ) from exc

    @classmethod
    def _source_shot_id(cls, continuity: dict[str, Any]) -> str | None:
        raw = next(
            (
                continuity.get(key)
                for key in (
                    "source_shot_id",
                    "previous_shot_id",
                    "continuity_source_shot_id",
                )
                if continuity.get(key) is not None
            ),
            None,
        )
        if raw is None or not str(raw).strip():
            return None
        return cls._shot_id(str(raw))

    @staticmethod
    def _shot_id(value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise GovernedShotBoundaryError("shot_id cannot be blank")
        return normalized

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
