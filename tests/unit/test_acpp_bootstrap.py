"""Bootstrap regression for the Phase 17.3 ACPP Editor service."""

from __future__ import annotations

from pathlib import Path

from vscs.application.acpp import ACPPEditorService
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_acpp_editor_service(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    service = context.services.require(ACPPEditorService)
    assert service.stories is context.services.require(StoryService)
    context.shutdown()
