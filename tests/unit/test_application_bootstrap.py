"""Tests for Phase 16.1 application startup and dependency injection."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import (
    CanonicalReferenceRepository,
    CanonicalReferenceService,
    CAPGeneratorService,
    CAPRepository,
    CAPService,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.infrastructure.configuration import ConfigurationService, EnvironmentManager
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.plugins import PluginManager
from vscs.presentation.windows.main_window import MainWindow


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


def test_bootstrap_registers_complete_frontend_dependency_graph(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))

    required = (
        ConfigurationService,
        EnvironmentManager,
        DatabaseManager,
        ProjectService,
        AssetRepository,
        AssetService,
        CAPRepository,
        CAPService,
        CanonicalReferenceRepository,
        CanonicalReferenceService,
        CAPGeneratorService,
        PluginManager,
    )
    assert all(context.services.contains(service_type) for service_type in required)
    assert context.services.require(ProjectService).database is context.database

    context.shutdown()


def test_bootstrap_creates_real_main_window_without_event_loop(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))

    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert isinstance(window, MainWindow)
    assert window.services is context.services
    assert window.navigation.count() == 8
    assert window.navigation.currentItem().text() == "Dashboard"
    assert window.content_stack.count() == 8
    assert window.statusBar().currentMessage() == "No project open"
    assert not window.save_project_action.isEnabled()

    context.shutdown()


def test_project_created_through_injected_service_updates_frontend(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    projects = context.services.require(ProjectService)

    projects.create(tmp_path / "Demo Production", name="Demo Production")
    window._update_project_state()

    assert "Demo Production" in window.windowTitle()
    assert window.navigation_dock.windowTitle() == "Demo Production"
    assert window.save_project_action.isEnabled()
    assert window.asset_manager.add_button.isEnabled()
    assert window.cap_manager.add_button.isEnabled()

    context.shutdown()


def test_shutdown_is_idempotent_and_clears_services(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))

    context.shutdown()
    context.shutdown()

    assert len(context.services) == 0
    assert context._shutdown is True


def test_context_manager_releases_application_services(tmp_path: Path) -> None:
    with build_application_context(_options(tmp_path)) as context:
        services = context.services
        assert len(services) > 0

    assert len(services) == 0
