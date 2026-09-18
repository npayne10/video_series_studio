"""Phase 20.18.2.1 provider reference capacity resolution regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.acpp.reference_roles import ReferencePriority
from vscs.application.governed_reference_suitability_review import (
    suggested_reference_priority,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)
from vscs.infrastructure.production_execution.provider_reference_helper import (
    GovernedProviderReferenceHelperBuilder,
)


@pytest.mark.parametrize(
    ("category", "semantic_role", "expected"),
    (
        ("character", "Dialogue Speaker", ReferencePriority.REQUIRED),
        ("character", "Supporting Character", ReferencePriority.REQUIRED),
        ("location", "Location", ReferencePriority.REQUIRED),
        ("set", "Primary Set", ReferencePriority.REQUIRED),
        ("environment", "Environment Context", ReferencePriority.PREFERRED),
        ("planet", "Visible Planet", ReferencePriority.REQUIRED),
        ("ship", "Vehicle/Ship", ReferencePriority.PREFERRED),
        ("prop", "Hero critical prop", ReferencePriority.REQUIRED),
        ("prop", "Background prop", ReferencePriority.PREFERRED),
    ),
)
def test_semantic_priority_suggestions(
    category: str,
    semantic_role: str,
    expected: ReferencePriority,
) -> None:
    assert suggested_reference_priority(category, semantic_role) is expected


def _binding(
    reference_id: str,
    role: str,
    *,
    priority: str,
    provider_ready: bool = True,
) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "asset_id": reference_id.replace("REF-", "ASSET-"),
        "role": role,
        "required": priority == "required",
        "vscs_priority": priority,
        "provider_ready": provider_ready,
        "path": f"/provider/{reference_id}.png",
        "file_checksum": f"checksum-{reference_id}",
        "reference_fingerprint": f"fingerprint-{reference_id}",
    }


def _plan(*bindings: dict[str, object]) -> dict[str, object]:
    return {
        "bindings": list(bindings),
        "references": [
            {
                "reference_id": binding["reference_id"],
                "role": binding["role"],
                "reference_class": "canonical_master",
            }
            for binding in bindings
        ],
    }


def test_required_references_fill_first_then_preferred_provider_ready_reference(
    tmp_path: Path,
) -> None:
    builder = GovernedProviderReferenceHelperBuilder(tmp_path)
    plan = _plan(
        _binding("REF-PRIMARY", "primary_identity", priority="required"),
        _binding("REF-SECONDARY", "secondary_identity", priority="required"),
        _binding("REF-ENV", "environment_reference", priority="preferred"),
        _binding("REF-BACKGROUND", "background_identity", priority="preferred"),
        _binding("REF-OPTIONAL", "background_identity", priority="optional"),
    )

    enriched = builder.ensure_helper(plan)
    multi = enriched["provider_multi_reference"]
    assert isinstance(multi, dict)
    refs = multi["references"]
    assert isinstance(refs, list)

    assert [item["reference_id"] for item in refs] == [
        "REF-PRIMARY",
        "REF-SECONDARY",
        "REF-ENV",
    ]
    assert [item["required"] for item in refs] == [True, True, False]
    assert [item["vscs_priority"] for item in refs] == [
        "required",
        "required",
        "preferred",
    ]
    assert multi["provider_capacity"] == 3
    assert multi["required_reference_count"] == 2
    assert multi["preferred_reference_count"] == 2
    assert multi["reference_count"] == 3

    bindings = enriched["bindings"]
    assert isinstance(bindings, list)
    assert len(bindings) == 5


def test_non_provider_ready_preferred_reference_does_not_consume_capacity(
    tmp_path: Path,
) -> None:
    builder = GovernedProviderReferenceHelperBuilder(tmp_path)
    enriched = builder.ensure_helper(
        _plan(
            _binding("REF-PRIMARY", "primary_identity", priority="required"),
            _binding(
                "REF-ENV-NOT-READY",
                "environment_reference",
                priority="preferred",
                provider_ready=False,
            ),
            _binding("REF-SHIP", "background_identity", priority="preferred"),
        )
    )
    multi = enriched["provider_multi_reference"]
    assert isinstance(multi, dict)
    refs = multi["references"]
    assert isinstance(refs, list)

    assert [item["reference_id"] for item in refs] == [
        "REF-PRIMARY",
        "REF-SHIP",
    ]
    assert multi["reference_count"] == 2


def test_more_than_three_required_visual_references_are_blocked_with_details(
    tmp_path: Path,
) -> None:
    builder = GovernedProviderReferenceHelperBuilder(tmp_path)
    plan = _plan(
        _binding("REF-PRIMARY", "primary_identity", priority="required"),
        _binding("REF-SECONDARY", "secondary_identity", priority="required"),
        _binding("REF-ENV", "environment_reference", priority="required"),
        _binding("REF-SHIP", "background_identity", priority="required"),
    )

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match=r"at most three required governed references per shot; received 4",
    ) as exc_info:
        builder.ensure_helper(plan)

    message = str(exc_info.value)
    assert "REF-PRIMARY" in message
    assert "REF-SECONDARY" in message
    assert "REF-ENV" in message
    assert "REF-SHIP" in message


def test_continuity_reference_does_not_consume_direct_visual_capacity(
    tmp_path: Path,
) -> None:
    builder = GovernedProviderReferenceHelperBuilder(tmp_path)
    enriched = builder.ensure_helper(
        _plan(
            _binding("REF-PRIMARY", "primary_identity", priority="required"),
            _binding("REF-CONTINUITY", "start_frame_reference", priority="required"),
            _binding("REF-ENV", "environment_reference", priority="preferred"),
        )
    )
    multi = enriched["provider_multi_reference"]
    assert isinstance(multi, dict)
    refs = multi["references"]
    assert isinstance(refs, list)

    assert [item["reference_id"] for item in refs] == [
        "REF-PRIMARY",
        "REF-ENV",
    ]
    continuity = multi["continuity"]
    assert isinstance(continuity, dict)
    assert continuity["path"] == "/provider/REF-CONTINUITY.png"
