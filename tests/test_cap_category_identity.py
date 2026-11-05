"""B.5.25: physical identity belongs to the declared category, not contained assets."""

import pytest

from vscs.application.caps.category_identity import category_identity_issues
from vscs.domain.assets.models import AssetCategory


@pytest.mark.parametrize(
    ("category", "name", "identity"),
    [
        (
            AssetCategory.SHIP,
            "Unmanned exploration vessel",
            "The diagnostic console has a blue display. "
            "A small indicator is present, but no exterior appearance is established.",
        ),
        (
            AssetCategory.SHIP,
            "Unmanned exploration vessel",
            "The ship contains an engineering control room and a diagnostic console.",
        ),
        (
            AssetCategory.LOCATION,
            "Engineering control room",
            "The diagnostic console has a blue display.",
        ),
        (
            AssetCategory.PROP,
            "Diagnostic console",
            "The engineering control room has a wall and a hatch.",
        ),
    ],
)
def test_category_gate_rejects_cross_asset_identity(category, name, identity):
    assert category_identity_issues(category, name, identity)


@pytest.mark.parametrize(
    ("category", "name", "identity"),
    [
        (
            AssetCategory.SHIP,
            "Unmanned exploration vessel",
            "The vessel's exterior silhouette remains unresolved.",
        ),
        (
            AssetCategory.SHIP,
            "Unmanned exploration vessel",
            "The ship's hull has a compact, faceted silhouette.",
        ),
        (
            AssetCategory.SHIP,
            "Unmanned exploration vessel",
            "The hull has a compact wedge-shaped silhouette.",
        ),
        (
            AssetCategory.LOCATION,
            "Engineering control room",
            "The engineering control room contains a diagnostic console beside a workstation.",
        ),
        (
            AssetCategory.LOCATION,
            "Engineering control room",
            "The room's architecture remains unresolved.",
        ),
        (
            AssetCategory.PROP,
            "Diagnostic console",
            "The diagnostic console has a blue display.",
        ),
        (
            AssetCategory.PROP,
            "Diagnostic console",
            "The console geometry remains unresolved.",
        ),
    ],
)
def test_category_gate_accepts_asset_identity_and_explicit_unknowns(category, name, identity):
    assert category_identity_issues(category, name, identity) == ()


def test_unrelated_categories_remain_unaffected():
    assert (
        category_identity_issues(
            AssetCategory.ENVIRONMENT, "Deep space", "Unspecified deep space environment."
        )
        == ()
    )
