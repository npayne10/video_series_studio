"""Provider-neutral resolution of published governed Shot boundary media."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.production_execution.package_compilation import CompiledProductionPackage


class GovernedShotBoundaryError(RuntimeError):
    """Raised when published Shot-boundary authority cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class ResolvedGovernedShotBoundary:
    """One verified published boundary image resolved for a target Shot."""

    boundary_id: str
    source_shot_id: str
    image_path: Path
    image_sha256: str

    def __post_init__(self) -> None:
        boundary_id = self.boundary_id.strip()
        source_shot_id = self.source_shot_id.strip().upper()
        checksum = self.image_sha256.strip().lower()
        if not boundary_id:
            raise GovernedShotBoundaryError("Governed boundary requires boundary_id")
        if not source_shot_id:
            raise GovernedShotBoundaryError("Governed boundary requires source_shot_id")
        if len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
            raise GovernedShotBoundaryError("Governed boundary requires a valid SHA-256")
        object.__setattr__(self, "boundary_id", boundary_id)
        object.__setattr__(self, "source_shot_id", source_shot_id)
        object.__setattr__(self, "image_sha256", checksum)


class GovernedShotBoundaryResolver:
    """Resolve the published previous-Shot boundary declared by continuity authority."""

    STORE_PATH = Path(".vscs") / "governed_shot_boundaries.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)

    def resolve_previous_for(
        self,
        compiled: CompiledProductionPackage,
    ) -> ResolvedGovernedShotBoundary:
        continuity = self._continuity(compiled)
        mode = str(continuity.get("shot_boundary_mode") or "").strip().casefold()
        inheritance = str(continuity.get("inheritance_mode") or "").strip().casefold()
        if mode != "continuous" and inheritance != "previous-shot-closing-state":
            raise GovernedShotBoundaryError(
                "Shot does not declare continuous previous-Shot boundary inheritance"
            )

        previous_shot_id = str(
            continuity.get("previous_shot_id") or continuity.get("source_shot_id") or ""
        ).strip().upper()
        if not previous_shot_id:
            raise GovernedShotBoundaryError(
                "Continuous Shot continuity does not declare previous_shot_id/source_shot_id"
            )

        root = self._read_store()
        raw_boundaries = root.get("boundaries")
        if not isinstance(raw_boundaries, list):
            raise GovernedShotBoundaryError(
                "Governed Shot boundary registry boundaries must be an array"
            )

        matches = [
            dict(item)
            for item in raw_boundaries
            if isinstance(item, dict)
            and str(item.get("shot_id") or "").strip().upper() == previous_shot_id
            and str(item.get("status") or "").strip().casefold() == "published"
        ]
        if len(matches) != 1:
            raise GovernedShotBoundaryError(
                f"Expected exactly one published governed boundary for {previous_shot_id}; "
                f"found {len(matches)}"
            )

        boundary = matches[0]
        boundary_id = str(boundary.get("boundary_id") or "").strip()
        image_path_text = str(boundary.get("image_path") or "").strip()
        image_sha256 = str(boundary.get("image_sha256") or "").strip().lower()
        if not boundary_id or not image_path_text or not image_sha256:
            raise GovernedShotBoundaryError(
                f"Published governed boundary for {previous_shot_id} is incomplete"
            )

        image_path = Path(image_path_text).expanduser()
        if image_path.is_absolute():
            resolved = image_path.resolve(strict=False)
        else:
            resolved = (self.project_directory / image_path).resolve(strict=False)
            try:
                resolved.relative_to(self.project_directory)
            except ValueError as exc:
                raise GovernedShotBoundaryError(
                    "Governed boundary image escapes the project directory"
                ) from exc

        if not resolved.is_file():
            raise GovernedShotBoundaryError(
                f"Governed boundary image does not exist: {resolved}"
            )
        actual_sha256 = _file_sha256(resolved)
        if actual_sha256 != image_sha256:
            raise GovernedShotBoundaryError(
                f"Governed boundary image SHA-256 mismatch for {boundary_id}"
            )

        return ResolvedGovernedShotBoundary(
            boundary_id=boundary_id,
            source_shot_id=previous_shot_id,
            image_path=resolved,
            image_sha256=image_sha256,
        )

    def _read_store(self) -> dict[str, Any]:
        path = self.project_directory / self.STORE_PATH
        if not path.is_file():
            raise GovernedShotBoundaryError(
                f"Governed Shot boundary registry does not exist: {path}"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernedShotBoundaryError(
                f"Unable to read governed Shot boundary registry: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise GovernedShotBoundaryError(
                "Governed Shot boundary registry root must be an object"
            )
        if str(raw.get("schema_version") or "").strip() != "1.0":
            raise GovernedShotBoundaryError(
                "Unsupported governed Shot boundary registry schema"
            )
        return raw

    @staticmethod
    def _continuity(compiled: CompiledProductionPackage) -> dict[str, Any]:
        for source in (compiled.production_authority, compiled.composition_plan):
            if not isinstance(source, dict):
                continue
            continuity = source.get("continuity")
            if isinstance(continuity, dict):
                return dict(continuity)
        raise GovernedShotBoundaryError("Compiled Production Package has no continuity authority")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
