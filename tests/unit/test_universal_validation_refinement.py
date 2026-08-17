from vscs.application.universal_validation_refinement import _action_runtime_seconds


def test_action_runtime_seconds_reads_timing_notes():
    assert _action_runtime_seconds({"timing_notes": "Target runtime: 20 seconds"}) == 20.0
