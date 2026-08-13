from vscs.application.universal_production_description_compiler import UniversalProductionDescriptionCompilerService
from vscs.application.universal_validation_refinement import install_universal_validation_refinement


def test_installed_refinement_adds_runtime_and_missing_performer_findings():
    install_universal_validation_refinement()
    description = {
        "shot": {"target_runtime_seconds": 15},
        "action_performance": {
            "temporal_narrative": "James approaches Cheryl.",
            "spoken_content": "James: Hello.",
            "timing_notes": "Target runtime: 20 seconds",
        },
        "assets": [
            {
                "asset_id": "CAP-CHR-001",
                "category": "character",
                "requirement": "James is visible",
                "canonical_reference": "james.png",
            }
        ],
        "environment": {},
        "continuity": {},
    }
    findings = UniversalProductionDescriptionCompilerService._consistency_findings(description)
    assert any("target runtime is 15 seconds" in item for item in findings)
    assert any("Cheryl" in item and "canonical references" in item for item in findings)
