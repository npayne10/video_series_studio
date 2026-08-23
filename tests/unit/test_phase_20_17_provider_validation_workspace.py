from vscs.domain.provider_capability_validation import ValidationOutcome


def test_provider_validation_outcomes_include_partial() -> None:
    assert ValidationOutcome.PARTIAL.value == "partial"
    assert [item.value for item in ValidationOutcome] == [
        "not_run",
        "pass",
        "partial",
        "fail",
        "blocked",
    ]
