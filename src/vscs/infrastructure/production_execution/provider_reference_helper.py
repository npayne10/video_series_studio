"""Deterministic governed provider helper generation for one-image LTX workflows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from .package_compilation import LocalProductionPackageCompilationError

_HELPER_ROLES = frozenset({"scene_composition_anchor", "provider_helper_reference"})


class GovernedProviderReferenceHelperBuilder:
    """Build a deterministic provider-specific helper without replacing source authority."""

    ROOT = Path("production") / "provider_reference_helpers"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)

    def ensure_helper(self, plan: dict[str, Any]) -> dict[str, Any]:
        bindings_raw = plan.get("bindings")
        if not isinstance(bindings_raw, list):
            raise LocalProductionPackageCompilationError(
                "Provider ReferencePlan bindings must be a JSON array"
            )
        bindings = [dict(item) for item in bindings_raw if isinstance(item, dict)]
        required = [
            item
            for item in bindings
            if item.get("required") is True and str(item.get("role") or "") not in _HELPER_ROLES
        ]
        if len(required) <= 1:
            return plan

        existing = next(
            (item for item in bindings if str(item.get("role") or "") in _HELPER_ROLES),
            None,
        )
        if existing is not None:
            self._validate_existing_helper(existing, plan)
            enriched = dict(plan)
            enriched["provider_helper"] = self._helper_status(existing, required, generated=False)
            return enriched

        target = plan.get("target")
        if not isinstance(target, dict):
            raise LocalProductionPackageCompilationError(
                "Multi-reference provider helper requires a governed ReferencePlan target"
            )
        width = self._positive_int(target.get("width"), "target width")
        height = self._positive_int(target.get("height"), "target height")

        helper = self._build_helper(required, width=width, height=height)
        enriched = dict(plan)
        enriched_bindings = [*bindings, helper]
        enriched["bindings"] = enriched_bindings

        references_raw = enriched.get("references")
        references = [dict(item) for item in references_raw if isinstance(item, dict)] if isinstance(references_raw, list) else []
        references.append(self._reference_record(helper, required))
        enriched["references"] = references
        enriched["provider_helper"] = self._helper_status(helper, required, generated=True)
        return enriched

    def _build_helper(
        self,
        required: list[dict[str, Any]],
        *,
        width: int,
        height: int,
    ) -> dict[str, Any]:
        sources = [self._source_record(item) for item in required]
        fingerprint_payload = {
            "target": [width, height],
            "sources": sources,
            "layout": "deterministic-horizontal-contact-sheet-v1",
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        reference_id = f"LTX23-PROVIDER-HELPER-{fingerprint[:16].upper()}"
        path = (self.project_directory / self.ROOT / f"{reference_id}.png").resolve(strict=False)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.is_file():
            image = QImage(width, height, QImage.Format.Format_RGB32)
            image.fill(QColor(8, 8, 8))
            painter = QPainter(image)
            try:
                count = len(required)
                for index, binding in enumerate(required):
                    source_path = Path(str(binding.get("path") or "")).expanduser().resolve(strict=False)
                    source = QImage(str(source_path))
                    if source.isNull():
                        raise LocalProductionPackageCompilationError(
                            f"Cannot read governed reference image for provider helper: {source_path}"
                        )
                    left = round(index * width / count)
                    right = round((index + 1) * width / count)
                    cell = QRect(left, 0, max(right - left, 1), height)
                    scaled = source.scaled(
                        cell.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    x = cell.x() + (cell.width() - scaled.width()) // 2
                    y = cell.y() + (cell.height() - scaled.height()) // 2
                    painter.drawImage(x, y, scaled)
            finally:
                painter.end()
            if not image.save(str(path), "PNG"):
                raise LocalProductionPackageCompilationError(
                    f"Cannot persist governed provider helper image: {path}"
                )

        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        source_reference_ids = [str(item.get("reference_id") or "") for item in required]
        source_asset_ids = [str(item.get("asset_id") or "") for item in required]
        source_checksums = [str(item.get("file_checksum") or "") for item in required]
        return {
            "reference_id": reference_id,
            "asset_id": "",
            "role": "scene_composition_anchor",
            "path": str(path),
            "required": True,
            "provider_ready": True,
            "coverage": ["required_features", "full_required_asset", "identity"],
            "required_coverage": ["required_features", "full_required_asset", "identity"],
            "canonical_source": "",
            "derivative_type": "provider_specific_helper",
            "notes": (
                "Deterministic LTX one-image provider helper derived from governed required "
                "references; source references remain authoritative provenance."
            ),
            "reference_fingerprint": fingerprint,
            "file_checksum": checksum,
            "width": width,
            "height": height,
            "vscs_priority": "required",
            "vscs_coverage": {
                "framing_type": "provider_multi_reference_helper",
                "coverage": "full_required_scene",
                "required_features_visible": True,
                "identity_visible": True,
                "full_required_asset_visible": True,
            },
            "source_reference_ids": source_reference_ids,
            "source_asset_ids": source_asset_ids,
            "source_checksums": source_checksums,
            "helper_layout": "deterministic-horizontal-contact-sheet-v1",
        }

    def _validate_existing_helper(self, helper: dict[str, Any], plan: dict[str, Any]) -> None:
        path = Path(str(helper.get("path") or "")).expanduser().resolve(strict=False)
        if not path.is_file():
            raise LocalProductionPackageCompilationError(
                f"Governed provider helper file does not exist: {path}"
            )
        if helper.get("provider_ready") is not True:
            raise LocalProductionPackageCompilationError(
                "Governed provider helper is not approved as provider-ready"
            )
        target = plan.get("target")
        if isinstance(target, dict):
            width = self._positive_int(target.get("width"), "target width")
            height = self._positive_int(target.get("height"), "target height")
            if helper.get("width") != width or helper.get("height") != height:
                raise LocalProductionPackageCompilationError(
                    "Governed scene composition helper must match target dimensions exactly"
                )

    @staticmethod
    def _reference_record(
        helper: dict[str, Any], required: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "reference_id": helper["reference_id"],
            "role": "scene_composition_anchor",
            "reference_class": "provider_specific_helper",
            "priority": "required",
            "subject_type": "multi_subject_scene",
            "source_path": helper["path"],
            "canonical_source_id": None,
            "asset_id": None,
            "label": "Governed LTX multi-reference provider helper",
            "width": helper["width"],
            "height": helper["height"],
            "provider_ready": True,
            "provider_profiles": ["production-video-16x9"],
            "coverage": dict(helper["vscs_coverage"]),
            "reference_fingerprint": helper["reference_fingerprint"],
            "file_checksum": helper["file_checksum"],
            "contains_subjects": [
                str(item.get("asset_id") or "")
                for item in required
                if "identity" in str(item.get("role") or "")
            ],
            "contains_props": [],
            "contains_environments": [
                str(item.get("asset_id") or "")
                for item in required
                if str(item.get("role") or "") == "environment_reference"
            ],
            "source_reference_ids": list(helper["source_reference_ids"]),
            "source_checksums": list(helper["source_checksums"]),
        }

    @staticmethod
    def _helper_status(
        helper: dict[str, Any], required: list[dict[str, Any]], *, generated: bool
    ) -> dict[str, Any]:
        return {
            "status": "generated" if generated else "governed_existing",
            "reference_id": helper.get("reference_id"),
            "path": helper.get("path"),
            "role": helper.get("role"),
            "derivative_type": helper.get("derivative_type"),
            "source_reference_ids": [str(item.get("reference_id") or "") for item in required],
            "source_count": len(required),
        }

    @staticmethod
    def _source_record(binding: dict[str, Any]) -> dict[str, Any]:
        return {
            "reference_id": str(binding.get("reference_id") or ""),
            "asset_id": str(binding.get("asset_id") or ""),
            "role": str(binding.get("role") or ""),
            "path": str(binding.get("path") or ""),
            "reference_fingerprint": str(binding.get("reference_fingerprint") or ""),
            "file_checksum": str(binding.get("file_checksum") or ""),
        }

    @staticmethod
    def _positive_int(value: object, label: str) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        raise LocalProductionPackageCompilationError(
            f"Governed provider helper requires a positive {label}"
        )
