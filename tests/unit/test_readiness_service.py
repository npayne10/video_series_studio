"""Unit tests for deterministic CAP readiness evaluation."""

from types import SimpleNamespace

from vscs.application.caps.readiness_service import CAPReadinessService
from vscs.domain.assets import AssetCategory
from vscs.domain.caps import (
    CanonicalReferenceLifecycle,
    CanonicalReferenceView,
    CategoryReferenceTemplate,
    CAPStatus,
    ReadinessState,
)


class _Assets:
    def __init__(self, asset: object) -> None:
        self.asset = asset

    def get(self, asset_id: str) -> object:
        assert asset_id == "CAP-LOC-001"
        return self.asset


class _Caps:
    def __init__(self, cap: object, asset: object) -> None:
        self.cap = cap
        self.assets = _Assets(asset)

    def get(self, asset_id: str) -> object:
        assert asset_id == "CAP-LOC-001"
        return self.cap

    def list(self) -> tuple[object, ...]:
        return (self.cap,)


class _Library:
    def __init__(self, entries: tuple[object, ...]) -> None:
        self.entries = entries

    def list_for_cap(self, asset_id: str) -> tuple[object, ...]:
        assert asset_id == "CAP-LOC-001"
        return self.entries


class _Templates:
    def template_for(self, asset_id: str) -> CategoryReferenceTemplate:
        assert asset_id == "CAP-LOC-001"
        return CategoryReferenceTemplate(
            category=AssetCategory.LOCATION,
            required_views=(CanonicalReferenceView.MASTER,),
        )


def test_ready_location_with_locked_master_has_generation_readiness() -> None:
    asset = SimpleNamespace(asset_id="CAP-LOC-001", category=AssetCategory.LOCATION)
    cap = SimpleNamespace(
        asset_id="CAP-LOC-001",
        title="Docking Bay",
        status=CAPStatus.APPROVED,
        canonical_description="Canonical docking bay.",
        visual_identity="Industrial Guild architecture.",
        production_notes="Maintain canonical dimensions and lighting logic.",
    )
    master = SimpleNamespace(
        view=CanonicalReferenceView.MASTER,
        lifecycle=CanonicalReferenceLifecycle.LOCKED,
    )
    service = CAPReadinessService.__new__(CAPReadinessService)
    service.caps = _Caps(cap, asset)
    service.references = SimpleNamespace()
    service.library = _Library((master,))
    service.templates = _Templates()

    report = service.evaluate("CAP-LOC-001")

    assert report.identity.state is ReadinessState.READY
    assert report.references.state is ReadinessState.READY
    assert report.generation.state is ReadinessState.READY
    assert report.production.state is ReadinessState.READY
    assert report.overall_score == 100
    assert service.overall_percentage("CAP-LOC-001") == 100
    assert service.blocking_gaps("CAP-LOC-001") == ()
