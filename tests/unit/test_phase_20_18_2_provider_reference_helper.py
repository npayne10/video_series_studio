from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from vscs.infrastructure.production_execution.provider_reference_helper import (
    GovernedProviderReferenceHelperBuilder,
)


def _image(path: Path, color: QColor) -> str:
    image = QImage(320, 180, QImage.Format.Format_RGB32)
    image.fill(color)
    assert image.save(str(path), "PNG")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(reference_id: str, asset_id: str, role: str, path: Path, checksum: str) -> dict:
    return {
        "reference_id": reference_id,
        "asset_id": asset_id,
        "role": role,
        "path": str(path),
        "required": True,
        "provider_ready": True,
        "coverage": ["required_features", "full_required_asset", "identity"],
        "required_coverage": ["required_features", "full_required_asset"],
        "canonical_source": asset_id,
        "derivative_type": "provider_ready_derivative",
        "reference_fingerprint": f"fp-{reference_id}",
        "file_checksum": checksum,
        "width": 320,
        "height": 180,
        "vscs_priority": "required",
        "vscs_coverage": {
            "framing_type": "full_body",
            "coverage": "full_required_asset",
            "required_features_visible": True,
            "identity_visible": True,
            "full_required_asset_visible": True,
        },
    }


def _plan(tmp_path: Path) -> dict:
    james = tmp_path / "james.png"
    sandra = tmp_path / "sandra.png"
    xorix = tmp_path / "xorix.png"
    return {
        "schema_version": "2.0",
        "provider": "ltx-2.3",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
        },
        "references": [],
        "bindings": [
            _binding(
                "LIVE-PRIMARY_IDENTITY-CAP-CHR-001",
                "CAP-CHR-001",
                "primary_identity",
                james,
                _image(james, QColor(80, 20, 20)),
            ),
            _binding(
                "LIVE-SECONDARY_IDENTITY-CAP-CHR-003",
                "CAP-CHR-003",
                "secondary_identity",
                sandra,
                _image(sandra, QColor(20, 80, 20)),
            ),
            _binding(
                "LIVE-ENVIRONMENT-CAP-PLN-002",
                "CAP-PLN-002",
                "environment_reference",
                xorix,
                _image(xorix, QColor(20, 20, 80)),
            ),
        ],
    }


def test_multiple_required_references_generate_one_governed_helper(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    result = GovernedProviderReferenceHelperBuilder(tmp_path).ensure_helper(plan)

    helpers = [
        item for item in result["bindings"] if item.get("role") == "scene_composition_anchor"
    ]
    assert len(helpers) == 1
    helper = helpers[0]
    assert helper["derivative_type"] == "provider_specific_helper"
    assert helper["required"] is True
    assert helper["provider_ready"] is True
    assert helper["width"] == 1280
    assert helper["height"] == 720
    assert Path(helper["path"]).is_file()
    assert helper["source_reference_ids"] == [
        "LIVE-PRIMARY_IDENTITY-CAP-CHR-001",
        "LIVE-SECONDARY_IDENTITY-CAP-CHR-003",
        "LIVE-ENVIRONMENT-CAP-PLN-002",
    ]
    assert len(helper["source_checksums"]) == 3
    assert result["provider_helper"]["status"] == "generated"
    assert result["provider_helper"]["source_count"] == 3


def test_recompilation_reuses_deterministic_helper(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    builder = GovernedProviderReferenceHelperBuilder(tmp_path)
    first = builder.ensure_helper(plan)
    first_helper = next(
        item for item in first["bindings"] if item.get("role") == "scene_composition_anchor"
    )

    second = builder.ensure_helper(first)
    helpers = [
        item for item in second["bindings"] if item.get("role") == "scene_composition_anchor"
    ]
    assert len(helpers) == 1
    assert helpers[0]["reference_id"] == first_helper["reference_id"]
    assert helpers[0]["file_checksum"] == first_helper["file_checksum"]
    assert second["provider_helper"]["status"] == "governed_existing"


def test_single_required_reference_does_not_generate_helper(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan["bindings"] = plan["bindings"][:1]

    result = GovernedProviderReferenceHelperBuilder(tmp_path).ensure_helper(plan)

    assert result == plan
    assert not (tmp_path / "production" / "provider_reference_helpers").exists()
