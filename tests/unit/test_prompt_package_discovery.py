"""Tests for behaviour prompt package discovery."""

from pathlib import Path

from vscs.application.car.validator.prompt_discovery import PromptPackageDiscoverer


def _create_complete_package(root: Path, name: str = "default") -> Path:
    package = root / name
    package.mkdir(parents=True)
    (package / "manifest.json").write_text("{}", encoding="utf-8")
    (package / "README.md").write_text("# Package", encoding="utf-8")
    for directory in ("prompts", "templates", "metadata", "tests"):
        child = package / directory
        child.mkdir()
        (child / ".keep").write_text("keep", encoding="utf-8")
    return package


def test_discovers_complete_prompt_package(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    package_path = _create_complete_package(root)

    result = PromptPackageDiscoverer().discover(root)

    assert result.package_count == 1
    assert result.valid_package_count == 1
    assert result.packages[0].path == package_path
    assert result.packages[0].structurally_valid is True


def test_records_missing_structure(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    package = root / "incomplete"
    package.mkdir(parents=True)
    (package / "prompts").mkdir()

    result = PromptPackageDiscoverer().discover(root)
    discovered = result.packages[0]

    assert discovered.manifest_path is None
    assert discovered.readme_path is None
    assert discovered.missing_directories == ("templates", "metadata", "tests")
    assert result.missing_manifest_count == 1
    assert result.missing_readme_count == 1


def test_multiple_manifests_are_not_selected(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    package = _create_complete_package(root)
    (package / "manifest.yaml").write_text("{}", encoding="utf-8")

    result = PromptPackageDiscoverer().discover(root)
    discovered = result.packages[0]

    assert discovered.manifest_path is None
    assert [path.name for path in discovered.manifest_candidates] == [
        "manifest.json",
        "manifest.yaml",
    ]
    assert discovered.structurally_valid is False


def test_ignores_loose_files_and_hidden_entries(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    root.mkdir()
    (root / "loose.txt").write_text("ignored", encoding="utf-8")
    (root / ".cache").mkdir()
    _create_complete_package(root, "usable")

    result = PromptPackageDiscoverer().discover(root)

    assert [package.name for package in result.packages] == ["usable"]
    assert {path.name for path in result.ignored_entries} == {".cache", "loose.txt"}
