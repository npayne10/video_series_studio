"""Unit coverage for Phase 18.2.11.2.5 derived reference generation."""

from pathlib import Path

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
    DerivedReferenceRequest,
)
from vscs.domain.caps import CanonicalReferenceView
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider


def test_generator_registry_is_provider_neutral() -> None:
    registry = DerivedReferenceGeneratorRegistry()
    provider = OfflineDerivedReferencePreviewProvider()
    registry.register(provider)

    assert registry.names() == (provider.name,)
    assert registry.require(provider.name) is provider


def test_offline_provider_requires_and_reads_master(tmp_path: Path) -> None:
    master = tmp_path / "MASTER.png"
    master.write_bytes(b"canonical-master")
    provider = OfflineDerivedReferencePreviewProvider()

    result = provider.generate(
        DerivedReferenceRequest(
            asset_id="CAP-SHP-004",
            title="Guild Tug Ship",
            view=CanonicalReferenceView.TOP,
            master_path=master,
            prompt="Preserve the MASTER and show the top view.",
            negative_prompt="identity drift",
        )
    )

    assert result.provider_name == provider.name
    assert result.media_type == "image/svg+xml"
    assert b"MASTER input: MASTER.png" in result.content
    assert provider.production_capable is False


def test_cardinal_view_prompts_have_unambiguous_camera_orientations() -> None:
    for view, required in (
        (CanonicalReferenceView.FRONT, "no three-quarter angle"),
        (CanonicalReferenceView.REAR, "straight-on rear elevation"),
        (CanonicalReferenceView.LEFT, "asset's own left side"),
        (CanonicalReferenceView.RIGHT, "asset's own right side"),
    ):
        prompt = DerivedReferenceGenerationService._prompt("Console", "Three buttons", view)
        assert required in prompt
        assert "MASTER image as the absolute visual identity authority" in prompt
