from vscs.application.universal_validation_refinement import _action_runtime_seconds, _missing_performer_coverage


def test_action_runtime_seconds_reads_timing_notes():
    assert _action_runtime_seconds({"timing_notes": "Target runtime: 20 seconds"}) == 20.0


def test_missing_performer_coverage_requires_character_reference():
    assets = [{"category": "character", "requirement": "James is visible", "canonical_reference": "james.png"}]
    assert _missing_performer_coverage(("James", "Cheryl"), assets) == ("Cheryl",)
