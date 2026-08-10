"""Prompt package discovery for behaviour assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .constants import (
    PROMPT_PACKAGE_MANIFEST_NAMES,
    PROMPT_PACKAGE_README_NAMES,
    PROMPT_PACKAGE_REQUIRED_DIRECTORIES,
)


@dataclass(frozen=True, slots=True)
class PromptPackage:
    """Discovered prompt package and its structural state."""

    name: str
    path: Path
    manifest_path: Path | None
    readme_path: Path | None
    directories: dict[str, Path]
    missing_directories: tuple[str, ...] = ()
    empty_directories: tuple[str, ...] = ()
    extra_directories: tuple[str, ...] = ()
    manifest_candidates: tuple[Path, ...] = ()

    @property
    def structurally_valid(self) -> bool:
        """Return whether all mandatory package elements were discovered."""
        return (
            self.manifest_path is not None
            and self.readme_path is not None
            and not self.missing_directories
            and len(self.manifest_candidates) == 1
        )


@dataclass(slots=True)
class PromptPackageDiscoveryResult:
    """Prompt package discovery output for one behaviour asset."""

    root: Path
    packages: list[PromptPackage] = field(default_factory=list)
    ignored_entries: list[Path] = field(default_factory=list)

    @property
    def package_count(self) -> int:
        return len(self.packages)

    @property
    def valid_package_count(self) -> int:
        return sum(package.structurally_valid for package in self.packages)

    @property
    def missing_manifest_count(self) -> int:
        return sum(package.manifest_path is None for package in self.packages)

    @property
    def missing_readme_count(self) -> int:
        return sum(package.readme_path is None for package in self.packages)


class PromptPackageDiscoverer:
    """Discover immediate child prompt packages without parsing their content."""

    def discover(self, root: Path) -> PromptPackageDiscoveryResult:
        """Discover packages beneath ``root`` in deterministic name order."""
        result = PromptPackageDiscoveryResult(root=root)
        if not root.is_dir():
            return result

        for entry in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
            if not self._is_package_candidate(entry):
                result.ignored_entries.append(entry)
                continue
            result.packages.append(self._inspect_package(entry))
        return result

    def _is_package_candidate(self, path: Path) -> bool:
        if path.name.startswith(".") or not path.is_dir():
            return False
        recognised_files = (*PROMPT_PACKAGE_MANIFEST_NAMES, *PROMPT_PACKAGE_README_NAMES)
        if any((path / name).is_file() for name in recognised_files):
            return True
        return any((path / name).is_dir() for name in PROMPT_PACKAGE_REQUIRED_DIRECTORIES)

    def _inspect_package(self, package_path: Path) -> PromptPackage:
        directories = {name: package_path / name for name in PROMPT_PACKAGE_REQUIRED_DIRECTORIES}
        missing = tuple(name for name, path in directories.items() if not path.is_dir())
        empty = tuple(
            name for name, path in directories.items() if path.is_dir() and not any(path.iterdir())
        )
        expected = set(PROMPT_PACKAGE_REQUIRED_DIRECTORIES)
        extra = tuple(
            path.name
            for path in sorted(package_path.iterdir(), key=lambda item: item.name.casefold())
            if path.is_dir() and path.name not in expected
        )
        manifests = tuple(
            package_path / name
            for name in PROMPT_PACKAGE_MANIFEST_NAMES
            if (package_path / name).is_file()
        )
        readme = next(
            (
                package_path / name
                for name in PROMPT_PACKAGE_README_NAMES
                if (package_path / name).is_file()
            ),
            None,
        )
        return PromptPackage(
            name=package_path.name,
            path=package_path,
            manifest_path=manifests[0] if len(manifests) == 1 else None,
            readme_path=readme,
            directories=directories,
            missing_directories=missing,
            empty_directories=empty,
            extra_directories=extra,
            manifest_candidates=manifests,
        )
