"""Governed Shot Composition Keyframe authority for Phase 20.18.2.2g."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class GovernedShotKeyframeError(RuntimeError):
    """Raised when governed keyframe authority is missing, stale, or unsafe."""


KEYFRAME_ACCEPTANCE_CRITERIA = (
    "exactly_two_visible_people",
    "james_identity_present",
    "sandra_identity_present",
    "no_extra_crew",
    "correct_iron_horizon_bridge",
    "xorix_visible_in_correct_place",
    "sandra_at_control_station",
    "james_at_forward_display",
    "wide_static_eye_level_composition",
)


@dataclass(frozen=True, slots=True)
class GovernedShotKeyframe:
    """One explicitly human-approved Shot Composition Keyframe."""

    shot_id: str
    image_path: str
    image_sha256: str
    approved_by: str
    approved_at: str
    acceptance_criteria: tuple[str, ...]
    status: str = "approved"
    schema_version: str = "1.0"

    @property
    def approved(self) -> bool:
        return self.status == "approved" and bool(self.approved_by.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "shot_id": self.shot_id,
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "acceptance_criteria": list(self.acceptance_criteria),
            "status": self.status,
        }


class GovernedShotKeyframeStore:
    """Persist and verify human-approved keyframes without weakening Shot authority."""

    RELATIVE_PATH = Path(".vscs") / "governed_keyframes.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def get(self, shot_id: str) -> GovernedShotKeyframe | None:
        normalized = shot_id.strip().upper()
        for raw in self._records():
            if str(raw.get("shot_id") or "").strip().upper() != normalized:
                continue
            return self._from_dict(raw)
        return None

    def require_approved(self, shot_id: str) -> GovernedShotKeyframe:
        record = self.get(shot_id)
        if record is None:
            raise GovernedShotKeyframeError(
                f"No governed Shot Composition Keyframe is registered for {shot_id.strip().upper()}."
            )
        if not record.approved:
            raise GovernedShotKeyframeError(
                f"Governed Shot Composition Keyframe for {shot_id.strip().upper()} is not approved."
            )
        required = set(KEYFRAME_ACCEPTANCE_CRITERIA)
        actual = set(record.acceptance_criteria)
        missing = sorted(required - actual)
        if missing:
            raise GovernedShotKeyframeError(
                "Governed Shot Composition Keyframe approval does not cover: " + ", ".join(missing)
            )
        image = self._resolve_image(record.image_path)
        if not image.is_file():
            raise GovernedShotKeyframeError(f"Governed keyframe image does not exist: {image}")
        actual_sha = self._sha256(image)
        if actual_sha != record.image_sha256:
            raise GovernedShotKeyframeError(
                "Governed keyframe image checksum no longer matches approved authority."
            )
        return record

    def save(self, record: GovernedShotKeyframe) -> GovernedShotKeyframe:
        image = self._resolve_image(record.image_path)
        if not image.is_file():
            raise GovernedShotKeyframeError(f"Governed keyframe image does not exist: {image}")
        if self._sha256(image) != record.image_sha256:
            raise GovernedShotKeyframeError(
                "Governed keyframe checksum does not match the image being registered."
            )
        records = [
            raw
            for raw in self._records()
            if str(raw.get("shot_id") or "").strip().upper() != record.shot_id.strip().upper()
        ]
        records.append(record.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {"schema_version": "1.0", "keyframes": records},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return self.require_approved(record.shot_id)

    def image_path(self, record: GovernedShotKeyframe) -> Path:
        return self._resolve_image(record.image_path)

    def _records(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GovernedShotKeyframeError(f"Cannot read governed keyframe authority: {exc}") from exc
        raw = root.get("keyframes", []) if isinstance(root, dict) else None
        if not isinstance(raw, list):
            raise GovernedShotKeyframeError("Governed keyframe authority store is invalid.")
        return [dict(item) for item in raw if isinstance(item, dict)]

    def _resolve_image(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        return path.resolve(strict=False)

    @staticmethod
    def _from_dict(raw: dict[str, object]) -> GovernedShotKeyframe:
        criteria = raw.get("acceptance_criteria", [])
        if not isinstance(criteria, list):
            criteria = []
        return GovernedShotKeyframe(
            shot_id=str(raw.get("shot_id") or "").strip().upper(),
            image_path=str(raw.get("image_path") or "").strip(),
            image_sha256=str(raw.get("image_sha256") or "").strip().lower(),
            approved_by=str(raw.get("approved_by") or "").strip(),
            approved_at=str(raw.get("approved_at") or "").strip(),
            acceptance_criteria=tuple(str(item).strip() for item in criteria if str(item).strip()),
            status=str(raw.get("status") or "").strip().lower(),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
