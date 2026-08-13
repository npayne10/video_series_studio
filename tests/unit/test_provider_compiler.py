"""Phase 19.4.9 Provider Compiler Framework tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.provider_compiler import (
    ComfyUIProviderCompiler,
    ProviderCompilationStatus,
    ProviderCompilerError,
    ProviderCompilerFrameworkService,
    ProviderCompilerRegistry,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        universal = {
            "production": {
                "current_shot_id": "SHT-001",
                "universal_text": "SHOT\nBridge dialogue\nCAMERA\nStatic medium close",
                "shot": {"title": "Bridge Dialogue"},
                "camera": {"movement": "static"},
                "lighting": {"lighting_intent": "practical_motivated"},
                "environment": {"environment_context": "ship_interior"},
                "continuity": {"opening_state": "James enters the bridge."},
                "style": {"provider_neutral": True},
                "canonical_references": [
                    {"asset_id": "CAP-CHR-001", "canonical_reference": "james.png"}
                ],
                "consistency_findings": [],
            }
        }
        self.value = ProductionPackage(
            package_id="PP-SHT-001-UPD",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="fingerprint",
            provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
            story_context={},
            shot={},
            assets=(),
            camera={},
            lighting={},
            environment={},
            action_performance={},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=(),
            universal_description=universal,
            provider_outputs={},
            validation={
                "universal_description_complete": True,
                "cross_authority_consistent": True,
            },
            status=ProductionPackageStatus.COMPILING,
        )
        self.history: list[ProductionPackage] = []

    def current_package(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def _append_derived(self, current: ProductionPackage, data: dict):
        derived = replace(
            current,
            package_id="PP-SHT-001-PROVIDER",
            package_fingerprint="provider-fingerprint",
            provider_outputs=dict(data["provider_outputs"]),
            validation=dict(data["validation"]),
            status=ProductionPackageStatus.COMPILING,
        )
        self.value = derived
        self.history.append(derived)
        return derived


def _service(tmp_path: Path):
    packages = _Packages()
    service = ProviderCompilerFrameworkService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_registry_exposes_comfyui_provider_by_default(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    providers = service.providers()
    assert len(providers) == 1
    assert providers[0].provider_id == "comfyui"
    assert providers[0].display_name == "ComfyUI"


def test_comfyui_provider_compiles_approved_universal_authority_without_execution(
    tmp_path: Path,
) -> None:
    service, _packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-001", "comfyui")
    output = draft.output_value()
    assert output["provider_id"] == "comfyui"
    assert output["contract"] == "vscs.comfyui.production-input.v1"
    assert output["execution"] == "not-submitted"
    assert output["prompt"]["positive"].startswith("SHOT")
    assert output["workflow"]["workflow_id"] is None
    assert output["canonical_references"][0]["asset_id"] == "CAP-CHR-001"


def test_provider_compilation_is_blocked_until_universal_description_is_approved(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(
        packages.value,
        validation={"universal_description_complete": False, "cross_authority_consistent": True},
    )
    with pytest.raises(ProviderCompilerError, match="approved Universal"):
        service.create_from_current_package("SHT-001", "comfyui")


def test_ready_compiles_provider_output_into_new_production_package_revision(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001", "comfyui")
    service.save_notes("SHT-001", "comfyui", "Reviewed provider contract.")
    ready = service.mark_ready("SHT-001", "comfyui")
    assert ready.status is ProviderCompilationStatus.READY
    assert packages.value.provider_outputs["comfyui"]["status"] == "ready"
    assert packages.value.provider_outputs["comfyui"]["governed"]["execution"] == "not-submitted"
    assert packages.value.validation["provider_comfyui_complete"] is True


def test_universal_change_makes_provider_draft_stale_and_refresh_preserves_notes(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001", "comfyui")
    service.save_notes("SHT-001", "comfyui", "Keep this note.")
    changed = dict(packages.value.universal_description)
    changed["production"] = {
        **changed["production"],
        "universal_text": "SHOT\nChanged approved production description",
    }
    packages.value = replace(packages.value, universal_description=changed)
    draft = service.draft("SHT-001", "comfyui")
    assert draft is not None
    assert not service.is_current(draft)
    refreshed = service.rebase_to_current_package("SHT-001", "comfyui")
    assert service.is_current(refreshed)
    assert refreshed.production_notes == "Keep this note."
    assert "Changed approved" in refreshed.output_value()["prompt"]["positive"]


def test_registry_rejects_duplicate_provider_identity() -> None:
    registry = ProviderCompilerRegistry()
    registry.register(ComfyUIProviderCompiler())
    with pytest.raises(ProviderCompilerError, match="already registered"):
        registry.register(ComfyUIProviderCompiler())
