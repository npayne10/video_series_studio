"""Tests for the VSCS configuration service."""

from pathlib import Path

from vscs.infrastructure.configuration import ConfigurationService, Theme


def test_load_creates_default_settings_file(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.yaml"
    service = ConfigurationService(config_path)

    settings = service.load()

    assert config_path.exists()
    assert settings.theme is Theme.SYSTEM
    assert settings.workspace.default_workspace == "Dashboard"


def test_settings_round_trip_through_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.yaml"
    service = ConfigurationService(config_path)
    service.load()
    service.settings.theme = Theme.DARK
    service.settings.workspace.default_workspace = "Assets"
    service.save()

    reloaded = ConfigurationService(config_path)
    settings = reloaded.load()

    assert settings.theme is Theme.DARK
    assert settings.workspace.default_workspace == "Assets"


def test_recent_projects_are_unique_and_limited(tmp_path: Path) -> None:
    service = ConfigurationService(tmp_path / "settings.yaml")
    service.load()
    service.settings.maximum_recent_projects = 2

    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"

    service.add_recent_project(first)
    service.add_recent_project(second)
    service.add_recent_project(first)
    service.add_recent_project(third)

    assert service.settings.recent_projects == [third.resolve(), first.resolve()]
