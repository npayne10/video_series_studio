from pathlib import Path
from types import SimpleNamespace

from vscs.infrastructure.production_execution.provider_ready_package import (
    ProviderReadyProductionPackageResolver,
)


def test_missing_declared_continuity_frame_falls_back_to_empty_latent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    resolver = ProviderReadyProductionPackageResolver(project)
    compiled = SimpleNamespace(previous_approved_final_frame="continuity/SHT-000-final.png")

    contract = resolver._continuity_contract(compiled)  # type: ignore[arg-type]

    assert contract["declared_start_frame"] == "continuity/SHT-000-final.png"
    assert contract["start_frame"] == ""
    assert contract["unavailable_start_frame"].endswith("continuity\\SHT-000-final.png") or contract[
        "unavailable_start_frame"
    ].endswith("continuity/SHT-000-final.png")
    assert contract["delivery"] == "empty_latent"
    assert contract["temporal_start_policy"]["mode"] == "empty_latent"
    assert contract["temporal_start_policy"]["has_explicit_start_frame"] is False
