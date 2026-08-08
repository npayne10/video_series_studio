"""Integration coverage for the Phase 18.2.11.2.5a ComfyUI derived-reference pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import (
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
)
from vscs.infrastructure.ai.comfyui_derived_reference_provider import (
    ComfyUIDerivedReferenceConfiguration,
    ComfyUIDerivedReferenceProvider,
)


class _ComfyClient:
    def __init__(self) -> None:
        self.prompt: dict[str, Any] | None = None

    def healthcheck(self) -> None:
        return None

    def validate_nodes(self, prompt: dict[str, Any]) -> None:
        return None

    def submit(self, prompt: dict[str, Any]) -> str:
        self.prompt = prompt
        return "derived-1"

    def wait(self, prompt_id: str, timeout_seconds: float = 3600.0) -> dict[str, Any]:
        assert prompt_id == "derived-1"
        assert self.prompt is not None
        queue_path = Path(self.prompt["171"]["inputs"]["queue_file"])
        job = json.loads(queue_path.read_text(encoding="utf-8"))[0]
        output = Path(job["directory"]) / str(job["filename"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"generated-png")
        return {"status": {"completed": True}}


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_comfyui_output_enters_governed_candidate_lifecycle(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "references" / "master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-SHP-920",
            name="Comfy Test Ship",
            category=AssetCategory.SHIP,
            description="A canonical test ship.",
        ),
        Path("references/master.png"),
        confirmed_chatgpt_master=True,
    )

    provider = ComfyUIDerivedReferenceProvider(
        ComfyUIDerivedReferenceConfiguration(),
        client=_ComfyClient(),  # type: ignore[arg-type]
    )
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(provider)
    service = DerivedReferenceGenerationService(references, library, registry)

    created = service.generate(
        "CAP-SHP-920",
        (CanonicalReferenceView.FRONT,),
        provider_name=provider.name,
        seed=77,
        actor="Neill",
    )

    assert len(created) == 1
    reference = references.get(created[0])
    assert reference.file_path.suffix == ".png"
    assert (project / reference.file_path).read_bytes() == b"generated-png"
    entry = library.get(created[0])
    assert entry.view is CanonicalReferenceView.FRONT
    assert entry.origin is CanonicalReferenceOrigin.VSCS_DERIVED
    assert entry.lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    assert entry.generator == provider.name
    assert entry.parent_reference_id is not None
    context.shutdown()
