from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.acpp import (
    ProviderReadyReferenceResolver,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePriority,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)
from vscs.application.governed_reference_plan_persistence import (
    GovernedReferencePlanPersistenceService,
)
from vscs.application.governed_reference_plan_source import (
    PersistedGovernedReferencePlanSource,
)

SHOT_ID = "EP-001-SCN-001-SHT-001"
DEFAULT_TASK_ID = "PT-VIDEO-GENERATION-8B0A1D6874693AED"
PROFILE_ID = "production-video-16x9"
PROVIDER_ID = "ltx23-local"
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720


@dataclass
class _Projects:
    project_directory: Path


class _Catalog:
    def __init__(self, references: tuple[ShotReference, ...]) -> None:
        self.references = references

    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        return tuple(item for item in self.references if item.asset_id == asset_id)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if not header.startswith(b"\x89PNG\r\n\x1a\n") or len(header) < 24:
        raise RuntimeError(f"Only PNG references are supported by this migration utility: {path}")
    return struct.unpack(">II", header[16:24])


def _legacy_plan(project: Path, task_id: str) -> dict[str, Any]:
    package = (
        project / "production" / "compiled" / "production" / task_id / "production_package.json"
    )
    if not package.is_file():
        raise RuntimeError(f"Legacy Production package not found: {package}")
    payload = json.loads(package.read_text(encoding="utf-8"))
    plan = payload.get("reference_plan")
    if not isinstance(plan, dict) or str(plan.get("schema_version") or "") != "1.1":
        raise RuntimeError(
            "Expected legacy reference_plan schema 1.1 in the current Production package"
        )
    return plan


def _template_records(project: Path, legacy: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    identities = legacy.get("identity_references", [])
    if not isinstance(identities, list):
        identities = []
    for index, item in enumerate(identities):
        if not isinstance(item, dict):
            continue
        image = Path(str(item.get("image") or ""))
        if not image.is_absolute():
            image = project / image
        if not image.is_file():
            raise RuntimeError(f"Legacy identity reference does not exist: {image}")
        width, height = _png_dimensions(image)
        role = "primary_identity" if index == 0 else "secondary_identity"
        records.append(
            {
                "reference_id": f"LIVE-{role.upper()}-{item.get('asset_id') or index + 1}",
                "asset_id": str(item.get("asset_id") or ""),
                "role": role,
                "reference_class": "canonical_master",
                "subject_type": "character",
                "source_path": str(image),
                "canonical_source_id": str(item.get("asset_id") or ""),
                "label": f"Live {role} reference",
                "width": width,
                "height": height,
                "file_checksum": _sha256(image),
                "provider_ready": False,
                "provider_profiles": [],
                "coverage": {
                    "framing_type": "REVIEW_REQUIRED",
                    "coverage": "REVIEW_REQUIRED",
                    "required_features_visible": False,
                    "identity_visible": False,
                    "full_required_asset_visible": False,
                },
                "review_note": (
                    "Explicit operator review required. If this canonical image is unsuitable, "
                    "replace source_path with the approved provider-ready derivative and set "
                    "reference_class to provider_ready_derivative."
                ),
            }
        )

    metadata = legacy.get("metadata_assets", [])
    if not isinstance(metadata, list):
        metadata = []
    for item in metadata:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").lower()
        if category not in {"planet", "location", "environment", "set"}:
            continue
        image = Path(str(item.get("image") or ""))
        if not image.is_absolute():
            image = project / image
        if not image.is_file():
            raise RuntimeError(f"Legacy environment reference does not exist: {image}")
        width, height = _png_dimensions(image)
        records.append(
            {
                "reference_id": f"LIVE-ENVIRONMENT-{item.get('asset_id') or 'REFERENCE'}",
                "asset_id": str(item.get("asset_id") or ""),
                "role": "environment_reference",
                "reference_class": "canonical_master",
                "subject_type": "environment",
                "source_path": str(image),
                "canonical_source_id": str(item.get("asset_id") or ""),
                "label": "Live governed environment reference",
                "width": width,
                "height": height,
                "file_checksum": _sha256(image),
                "provider_ready": False,
                "provider_profiles": [],
                "coverage": {
                    "framing_type": "REVIEW_REQUIRED",
                    "coverage": "REVIEW_REQUIRED",
                    "required_features_visible": False,
                    "identity_visible": True,
                    "full_required_asset_visible": False,
                },
                "review_note": (
                    "Explicit operator review required. If this canonical image is unsuitable, "
                    "replace source_path with the approved provider-ready derivative and set "
                    "reference_class to provider_ready_derivative."
                ),
            }
        )
    return records


def _write_template(project: Path, task_id: str) -> Path:
    legacy = _legacy_plan(project, task_id)
    records = _template_records(project, legacy)
    if not records:
        raise RuntimeError("No James/Sandra/Xorix legacy references were found")
    path = project / "production" / "governed_reference_suitability_EP-001-SCN-001-SHT-001.json"
    payload = {
        "schema_version": "1.0",
        "shot_id": SHOT_ID,
        "target": {
            "width": TARGET_WIDTH,
            "height": TARGET_HEIGHT,
            "profile_id": PROFILE_ID,
            "provider_id": PROVIDER_ID,
        },
        "instructions": (
            "Review each image visually. Do not approve a canonical master merely because it exists. "
            "For every required reference, set provider_ready=true only when the image is suitable "
            "for the target profile; set coverage facts explicitly. Replace source_path with a "
            "provider-ready derivative when needed."
        ),
        "references": records,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _reference(raw: dict[str, Any]) -> ShotReference:
    path = Path(str(raw.get("source_path") or ""))
    if not path.is_file():
        raise RuntimeError(f"Suitability reference file does not exist: {path}")
    width, height = _png_dimensions(path)
    declared_width = int(raw.get("width") or 0)
    declared_height = int(raw.get("height") or 0)
    if (declared_width, declared_height) != (width, height):
        raise RuntimeError(
            f"Suitability dimensions are stale for {path}: declared "
            f"{declared_width}x{declared_height}, actual {width}x{height}"
        )
    checksum = _sha256(path)
    declared_checksum = str(raw.get("file_checksum") or "")
    if declared_checksum and declared_checksum != checksum:
        raise RuntimeError(f"Suitability checksum is stale for {path}")
    coverage = raw.get("coverage")
    if not isinstance(coverage, dict):
        raise RuntimeError(f"Coverage declaration is missing for {path}")
    return ShotReference(
        reference_id=str(raw["reference_id"]),
        asset_id=str(raw.get("asset_id") or "") or None,
        role=ReferenceRole(str(raw["role"])),
        reference_class=ReferenceClass(str(raw["reference_class"])),
        priority=ReferencePriority.REQUIRED,
        subject_type=ReferenceSubjectType(str(raw["subject_type"])),
        source_path=str(path),
        canonical_source_id=str(raw.get("canonical_source_id") or "") or None,
        label=str(raw.get("label") or ""),
        width=width,
        height=height,
        provider_ready=raw.get("provider_ready") is True,
        provider_profiles=tuple(str(item) for item in raw.get("provider_profiles", [])),
        coverage=ReferenceCoverage(
            framing_type=str(coverage.get("framing_type") or "unknown"),
            coverage=str(coverage.get("coverage") or "unknown"),
            required_features_visible=coverage.get("required_features_visible") is True,
            identity_visible=coverage.get("identity_visible") is True,
            full_required_asset_visible=coverage.get("full_required_asset_visible") is True,
        ),
        file_checksum=checksum,
    )


def _apply(project: Path, suitability_path: Path) -> int:
    raw = json.loads(suitability_path.read_text(encoding="utf-8"))
    if str(raw.get("shot_id") or "").upper() != SHOT_ID:
        raise RuntimeError(f"Suitability file does not govern {SHOT_ID}")
    entries = raw.get("references")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Suitability file contains no references")
    references = tuple(_reference(item) for item in entries if isinstance(item, dict))
    requests = tuple(
        ReferenceRoleRequest(
            role=item.role,
            priority=ReferencePriority.REQUIRED,
            asset_id=item.asset_id,
            preferred_reference_id=item.reference_id,
        )
        for item in references
    )
    store = PersistedGovernedReferencePlanSource(_Projects(project))  # type: ignore[arg-type]
    service = GovernedReferencePlanPersistenceService(
        ProviderReadyReferenceResolver(_Catalog(references)),
        store,
    )
    resolution = service.resolve_and_persist(
        shot_id=SHOT_ID,
        target=ReferenceTarget(
            width=TARGET_WIDTH,
            height=TARGET_HEIGHT,
            profile_id=PROFILE_ID,
            provider_id=PROVIDER_ID,
        ),
        requests=requests,
        supplied_references=references,
        provenance={
            "source": "live-explicit-suitability-migration",
            "legacy_task_id": DEFAULT_TASK_ID,
            "suitability_file": str(suitability_path),
        },
    )
    output = store.store_file
    print(f"Governed reference plan written: {output}")
    print(f"Status: {'PASSED' if resolution.passed else 'FAILED'}")
    for diagnostic in resolution.diagnostics:
        print(f"{diagnostic.severity.value.upper()} {diagnostic.code}: {diagnostic.message}")
    return 0 if resolution.passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 20.18.2 live James/Sandra/Xorix governed reference migration"
    )
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init-suitability", action="store_true")
    mode.add_argument("--apply", type=Path)
    args = parser.parse_args()
    project = args.project.expanduser().resolve()
    if args.init_suitability:
        path = _write_template(project, args.task_id)
        print(f"Suitability template written: {path}")
        print("Review and explicitly approve/replace every required reference before --apply.")
        return 0
    return _apply(project, args.apply.expanduser().resolve())


if __name__ == "__main__":
    raise SystemExit(main())
