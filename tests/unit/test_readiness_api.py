"""Public API contract for the Phase 18.2.11.2.7 readiness framework."""

from vscs.application.caps import CAPReadinessService
from vscs.domain.caps import (
    ReadinessAssessment,
    ReadinessDimension,
    ReadinessGap,
    ReadinessReport,
    ReadinessResult,
    ReadinessSeverity,
    ReadinessState,
)


def test_readiness_contract_is_exported_through_public_cap_packages() -> None:
    assert CAPReadinessService is not None
    assert ReadinessAssessment is not None
    assert ReadinessDimension.IDENTITY.value == "identity"
    assert ReadinessSeverity.BLOCKING.value == "blocking"
    assert ReadinessState.READY.value == "ready"
    assert ReadinessResult is ReadinessReport
    assert ReadinessGap is not None
