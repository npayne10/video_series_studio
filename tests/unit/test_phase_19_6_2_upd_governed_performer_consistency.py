from __future__ import annotations

from typing import Any

from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)


def _description(*, assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "shot": {},
        "action_performance": {
            "temporal_narrative": (
                "Sandra reports something unusual to James while Iron Horizon remains on course. "
                "Establish the Iron Horizon context without changing the performance blocking."
            ),
            "spoken_content": (
                'Sandra reports to James: "Commander, I have something unusual."\n'
                'James may respond: "How unusual?"'
            ),
            "performance_direction": (
                "Sandra remains controlled while James shifts attention toward her report."
            ),
            "opening_state": "Iron Horizon remains on course.",
            "closing_state": "James is focused on Sandra's report.",
        },
        "assets": assets,
        "environment": {},
        "continuity": {},
    }


def _character(asset_id: str, role: str, *, reference: str = "") -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "role": role,
        "category": "character",
        "canonical_reference": reference,
    }


def test_prose_capitalisation_cannot_manufacture_performers() -> None:
    description = _description(
        assets=[
            _character("CAP-CHR-SANDRA", "Sandra Crawford", reference="refs/sandra.png"),
            _character("CAP-CHR-JAMES", "Commander James Spence", reference="refs/james.png"),
            {
                "asset_id": "CAP-SHP-IRON-HORIZON",
                "role": "Iron Horizon",
                "category": "ship",
                "canonical_reference": "refs/iron-horizon.png",
            },
        ]
    )

    findings = UniversalProductionDescriptionCompilerService._consistency_findings(description)

    assert not findings
    rendered = "\n".join(findings)
    assert "Sandra reports to James" not in rendered
    assert "Establish" not in rendered
    assert "The Iron" not in rendered
    assert "Horizon" not in rendered


def test_missing_reference_is_reported_only_from_governed_character_binding() -> None:
    description = _description(
        assets=[
            _character("CAP-CHR-SANDRA", "Sandra Crawford"),
            _character("CAP-CHR-JAMES", "Commander James Spence", reference="refs/james.png"),
            {
                "asset_id": "CAP-SHP-IRON-HORIZON",
                "role": "Iron Horizon",
                "category": "ship",
            },
        ]
    )

    findings = UniversalProductionDescriptionCompilerService._consistency_findings(description)

    assert findings == (
        "Governed character asset bindings lack canonical references: "
        "Sandra Crawford (CAP-CHR-SANDRA).",
    )
    assert "Iron Horizon" not in findings[0]
    assert "Establish" not in findings[0]


def test_spoken_content_without_character_binding_reports_generic_governance_gap() -> None:
    description = _description(
        assets=[
            {
                "asset_id": "CAP-SHP-IRON-HORIZON",
                "role": "Iron Horizon",
                "category": "ship",
                "canonical_reference": "refs/iron-horizon.png",
            }
        ]
    )

    findings = UniversalProductionDescriptionCompilerService._consistency_findings(description)

    assert findings == (
        "Action & Performance contains spoken content, but no governed character asset binding "
        "exists for this Shot.",
    )
    assert "Sandra reports to James" not in findings[0]
    assert "Iron Horizon" not in findings[0]
