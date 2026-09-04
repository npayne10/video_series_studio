from __future__ import annotations

from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)
from vscs.infrastructure.production_execution.provider_reference_helper import (
    GovernedProviderReferenceHelperBuilder,
)


def _binding(reference_id: str, asset_id: str, role: str, path: Path) -> dict:
    path.write_bytes(reference_id.encode())
    return {
        "reference_id": reference_id,
        "asset_id": asset_id,
        "role": role,
        "path": str(path),
        "required": True,
        "provider_ready": True,
        "file_checksum": f"checksum-{reference_id}",
        "reference_fingerprint": f"fp-{reference_id}",
    }


def _plan(tmp_path: Path) -> dict:
    return {
        "schema_version": "2.0",
        "provider": "ltx-2.3",
        "references": [],
        "bindings": [
            _binding(
                "LIVE-PRIMARY_IDENTITY-CAP-CHR-001",
                "CAP-CHR-001",
                "primary_identity",
                tmp_path / "james.png",
            ),
            _binding(
                "LIVE-SECONDARY_IDENTITY-CAP-CHR-003",
                "CAP-CHR-003",
                "secondary_identity",
                tmp_path / "sandra.png",
            ),
            _binding(
                "LIVE-ENVIRONMENT-CAP-PLN-002",
                "CAP-PLN-002",
                "environment_reference",
                tmp_path / "xorix.png",
            ),
        ],
    }


def test_multiple_required_references_remain_separate_and_emit_provider_contract(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)

    result = GovernedProviderReferenceHelperBuilder(tmp_path).ensure_helper(plan)

    assert [item["role"] for item in result["bindings"]] == [
        "primary_identity",
        "secondary_identity",
        "environment_reference",
    ]
    assert not any(item.get("role") == "scene_composition_anchor" for item in result["bindings"])
    assert "provider_helper" not in result
    contract = result["provider_multi_reference"]
    assert contract["enabled"] is True
    assert contract["mode"] == "ltx_ingredients_iclora"
    assert contract["collapsed_scene_anchor"] is False
    assert contract["reference_count"] == 3
    assert [item["slot"] for item in contract["references"]] == [1, 2, 3]
    assert [item["role"] for item in contract["references"]] == [
        "primary_identity",
        "secondary_identity",
        "environment_reference",
    ]
    assert contract["continuity"] is None
    assert not (tmp_path / "production" / "provider_reference_helpers").exists()


def test_legacy_contact_sheet_binding_is_removed_without_dropping_governed_sources(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    plan["bindings"].append(
        {
            "reference_id": "LEGACY-HELPER",
            "role": "scene_composition_anchor",
            "path": str(tmp_path / "legacy-helper.png"),
            "required": True,
        }
    )

    result = GovernedProviderReferenceHelperBuilder(tmp_path).ensure_helper(plan)

    assert len(result["bindings"]) == 3
    assert result["provider_multi_reference"]["reference_count"] == 3


def test_single_required_reference_still_uses_explicit_provider_contract(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan["bindings"] = plan["bindings"][:1]

    result = GovernedProviderReferenceHelperBuilder(tmp_path).ensure_helper(plan)

    assert result["provider_multi_reference"]["reference_count"] == 1
    assert result["provider_multi_reference"]["references"][0]["role"] == "primary_identity"


def test_more_than_three_required_references_are_rejected(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan["bindings"].append(
        _binding("REF-FOUR", "CAP-FOUR", "prop_reference", tmp_path / "four.png")
    )

    with pytest.raises(LocalProductionPackageCompilationError, match="at most three"):
        GovernedProviderReferenceHelperBuilder(tmp_path).ensure_helper(plan)
