"""Tests for declarative renderer failure decisions."""

import pytest

from vscs.application.rendering import FailureAction, RetryPolicy


def test_retry_policy_selects_retry_abort_and_notify() -> None:
    policy = RetryPolicy(
        maximum_retries=2,
        retryable_error_codes=frozenset({"TIMEOUT"}),
        abort_error_codes=frozenset({"INVALID_WORKFLOW"}),
    )

    assert policy.action_for("TIMEOUT", 0) is FailureAction.RETRY
    assert policy.action_for("TIMEOUT", 2) is FailureAction.NOTIFY
    assert policy.action_for("INVALID_WORKFLOW", 0) is FailureAction.ABORT
    assert policy.action_for("UNKNOWN", 0) is FailureAction.NOTIFY


def test_retry_policy_rejects_conflicting_codes() -> None:
    with pytest.raises(ValueError, match="both retryable and abort-only"):
        RetryPolicy(
            retryable_error_codes=frozenset({"BROKEN"}),
            abort_error_codes=frozenset({"BROKEN"}),
        )
