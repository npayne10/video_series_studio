"""Asset-aware migration for Canonical Asset Repository (CAR) v2.0.

The migrator consumes :mod:`vscs.application.car.scanner` as its discovery and
classification layer. It is safe by default: existing files are never
overwritten, moved, renamed, or deleted.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .scanner import (
    AssetClass,
    AssetRepositoryInfo,
    CarRepositoryScanner,
    CarScanError,
    InvalidCarRootError as ScannerInvalidCarRootError,
    RepositoryScanResult,
)

VISUAL_DIRECTORIES = (
    "canon",
    "metadata",
    "prompts",
    "thumbnails",
    "candidates",
    "rejected",
)
VISUAL_METADATA_TEMPLATES = (
    "cap.json",
    "knowledge.json",
    "provenance.json",
    "evaluation.json",
    "history.json",
)

CONFIGURATION_FILES = (
    "profile.json",
    "description.md",
)

BEHAVIOUR_DIRECTORIES = (
    "prompts",
    "tests",
)
BEHAVIOUR_FILES = (
    "behaviour.json",
)


class CarMigrationError(RuntimeError):
    """Base error raised by the CAR repository migrator."""


class InvalidCarRootError(CarMigrationError):
    """Raised when the selected repository root is invalid."""


@dataclass(frozen=True, slots=True)
class MigrationAction:
    """One planned or completed migration action."""

    action: str
    path: str
    status: str
    detail: str = ""
    asset_id: str = ""
    asset_class: str = ""


@dataclass(slots=True)
class MigrationReport:
    """Complete result of one CAR migration run."""

    root: str
    applied: bool
    started_at: str
    completed_at: str = ""
    assets_scanned: int = 0
    visual_assets: int = 0
    configuration_assets: int = 0
    behaviour_assets: int = 0
    unknown_assets: int = 0
    directories_created: int = 0
    files_created: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    actions: list[MigrationAction] = field(default_factory=list)

    def finish(self) -> None:
        """Mark the migration report as complete."""
        self.completed_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable report."""
        payload = asdict(self)
        payload["actions"] = [asdict(action) for action in self.actions]
        return payload


class CarRepositoryMigrator:
    """Create an asset-class-aware CAR v2 repository structure."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.scanner = CarRepositoryScanner(self.root)

    def migrate(self, *, apply: bool = False) -> MigrationReport:
        """Plan or apply the repository migration.

        Existing files are never overwritten, renamed, moved, or deleted.
        """
        report = MigrationReport(
            root=str(self.root),
            applied=apply,
            started_at=datetime.now(UTC).isoformat(),
        )

        try:
            scan_result = self.scanner.scan()
        except ScannerInvalidCarRootError as error:
            raise InvalidCarRootError(str(error)) from error
        except CarScanError as error:
            raise CarMigrationError(str(error)) from error

        self._copy_scan_issues(scan_result, report)

        for asset in scan_result.assets:
            report.assets_scanned += 1
            self._increment_class_count(asset.asset_class, report)
            self._prepare_asset(asset, report, apply=apply)

        report.finish()
        return report

    def write_report(self, report: MigrationReport, path: Path | None = None) -> Path:
        """Write a migration report to disk and return its path."""
        target = path or self.root / "car_migration_report.json"
        target = target.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return target

    def _prepare_asset(
        self,
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        if asset.asset_class is AssetClass.VISUAL:
            self._prepare_visual_asset(asset, report, apply=apply)
            return
        if asset.asset_class is AssetClass.CONFIGURATION:
            self._prepare_configuration_asset(asset, report, apply=apply)
            return
        if asset.asset_class is AssetClass.BEHAVIOUR:
            self._prepare_behaviour_asset(asset, report, apply=apply)
            return

        warning = (
            f"Unknown asset class; no migration template applied: "
            f"{asset.relative_path}"
        )
        report.warnings.append(warning)
        report.actions.append(
            MigrationAction(
                action="skip_asset",
                path=str(asset.relative_path),
                status="skipped",
                detail="Unknown asset class",
                asset_id=asset.asset_id,
                asset_class=asset.asset_class.value,
            )
        )
        report.skipped += 1

    def _prepare_visual_asset(
        self,
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        if not asset.has_manifest:
            report.warnings.append(f"Missing manifest: {asset.relative_path / 'manifest.json'}")

        for directory_name in VISUAL_DIRECTORIES:
            self._ensure_directory(
                asset.path / directory_name,
                asset,
                report,
                apply=apply,
            )

        context = self._template_context(asset)
        metadata_directory = asset.path / "metadata"
        for filename in VISUAL_METADATA_TEMPLATES:
            self._ensure_json_file(
                metadata_directory / filename,
                self._visual_metadata_template(filename, context),
                asset,
                report,
                apply=apply,
            )

    def _prepare_configuration_asset(
        self,
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        context = self._template_context(asset)
        profile_payload = self._configuration_profile_template(context)
        description = self._configuration_description_template(context)

        self._ensure_json_file(
            asset.path / CONFIGURATION_FILES[0],
            profile_payload,
            asset,
            report,
            apply=apply,
        )
        self._ensure_text_file(
            asset.path / CONFIGURATION_FILES[1],
            description,
            asset,
            report,
            apply=apply,
        )

    def _prepare_behaviour_asset(
        self,
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        for directory_name in BEHAVIOUR_DIRECTORIES:
            self._ensure_directory(
                asset.path / directory_name,
                asset,
                report,
                apply=apply,
            )

        context = self._template_context(asset)
        behaviour_path = asset.path / BEHAVIOUR_FILES[0]
        self._ensure_json_file(
            behaviour_path,
            self._behaviour_template(context),
            asset,
            report,
            apply=apply,
        )

    def _ensure_directory(
        self,
        path: Path,
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        relative_path = str(path.relative_to(self.root))
        if path.exists():
            if not path.is_dir():
                message = f"Expected directory but found file: {relative_path}"
                report.errors.append(message)
                report.actions.append(
                    self._action("create_directory", relative_path, "conflict", asset, message)
                )
                return
            report.skipped += 1
            report.actions.append(
                self._action("create_directory", relative_path, "exists", asset)
            )
            return

        if apply:
            path.mkdir(parents=True, exist_ok=False)
        report.directories_created += 1
        report.actions.append(
            self._action(
                "create_directory",
                relative_path,
                "created" if apply else "planned",
                asset,
            )
        )

    def _ensure_json_file(
        self,
        path: Path,
        payload: Mapping[str, Any],
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        content = json.dumps(dict(payload), indent=2) + "\n"
        self._ensure_text_file(
            path,
            content,
            asset,
            report,
            apply=apply,
            action="create_file",
        )

    def _ensure_text_file(
        self,
        path: Path,
        content: str,
        asset: AssetRepositoryInfo,
        report: MigrationReport,
        *,
        apply: bool,
        action: str = "create_file",
    ) -> None:
        relative_path = str(path.relative_to(self.root))
        if path.exists():
            if not path.is_file():
                message = f"Expected file but found directory: {relative_path}"
                report.errors.append(message)
                report.actions.append(
                    self._action(action, relative_path, "conflict", asset, message)
                )
                return
            report.skipped += 1
            report.actions.append(self._action(action, relative_path, "exists", asset))
            return

        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        report.files_created += 1
        report.actions.append(
            self._action(
                action,
                relative_path,
                "created" if apply else "planned",
                asset,
            )
        )

    @staticmethod
    def _action(
        action: str,
        path: str,
        status: str,
        asset: AssetRepositoryInfo,
        detail: str = "",
    ) -> MigrationAction:
        return MigrationAction(
            action=action,
            path=path,
            status=status,
            detail=detail,
            asset_id=asset.asset_id,
            asset_class=asset.asset_class.value,
        )

    @staticmethod
    def _template_context(asset: AssetRepositoryInfo) -> dict[str, str]:
        return {
            "asset_id": asset.asset_id,
            "name": asset.name,
            "category": asset.category,
            "asset_class": asset.asset_class.value,
            "repository_version": "2.0",
            "source_manifest": "../manifest.json",
        }

    @staticmethod
    def _visual_metadata_template(
        filename: str,
        context: Mapping[str, str],
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        common = {
            "schema_version": "2.0",
            "repository_version": context["repository_version"],
            "asset_id": context["asset_id"],
            "asset_class": context["asset_class"],
        }
        if filename == "cap.json":
            return {
                **common,
                "name": context["name"],
                "category": context["category"],
                "status": "migration_pending",
                "current_version": "1.0",
                "source_manifest": context["source_manifest"],
            }
        if filename == "knowledge.json":
            return {**common, "tags": [], "materials": [], "design_rules": []}
        if filename == "provenance.json":
            return {**common, "created_by": "", "source": "existing_repository"}
        if filename == "evaluation.json":
            return {**common, "status": "not_evaluated", "evaluations": []}
        if filename == "history.json":
            return {
                **common,
                "events": [
                    {
                        "event": "car_v2_structure_created",
                        "timestamp": now,
                        "version": "2.0",
                    }
                ],
            }
        raise ValueError(f"Unsupported visual metadata template: {filename}")

    @staticmethod
    def _configuration_profile_template(context: Mapping[str, str]) -> dict[str, Any]:
        return {
            "schema_version": "2.0",
            "repository_version": context["repository_version"],
            "asset_id": context["asset_id"],
            "asset_class": context["asset_class"],
            "name": context["name"],
            "category": context["category"],
            "status": "migration_pending",
            "parameters": {},
            "notes": "",
        }

    @staticmethod
    def _configuration_description_template(context: Mapping[str, str]) -> str:
        return (
            f"# {context['asset_id']} — {context['name']}\n\n"
            f"- Asset class: `{context['asset_class']}`\n"
            f"- Category: `{context['category']}`\n"
            f"- Repository version: `{context['repository_version']}`\n\n"
            "Configuration description pending.\n"
        )

    @staticmethod
    def _behaviour_template(context: Mapping[str, str]) -> dict[str, Any]:
        return {
            "schema_version": "2.0",
            "repository_version": context["repository_version"],
            "asset_id": context["asset_id"],
            "asset_class": context["asset_class"],
            "name": context["name"],
            "category": context["category"],
            "status": "migration_pending",
            "inputs": {},
            "parameters": {},
            "outputs": {},
            "constraints": [],
        }

    @staticmethod
    def _increment_class_count(
        asset_class: AssetClass,
        report: MigrationReport,
    ) -> None:
        if asset_class is AssetClass.VISUAL:
            report.visual_assets += 1
        elif asset_class is AssetClass.CONFIGURATION:
            report.configuration_assets += 1
        elif asset_class is AssetClass.BEHAVIOUR:
            report.behaviour_assets += 1
        else:
            report.unknown_assets += 1

    @staticmethod
    def _copy_scan_issues(
        scan_result: RepositoryScanResult,
        report: MigrationReport,
    ) -> None:
        all_issues = list(scan_result.issues)
        for asset in scan_result.assets:
            all_issues.extend(asset.issues)

        for issue in all_issues:
            location = f" ({issue.path})" if issue.path else ""
            message = f"[{issue.code}] {issue.message}{location}"
            if issue.severity.casefold() == "error":
                report.errors.append(message)
            else:
                report.warnings.append(message)


def build_parser() -> argparse.ArgumentParser:
    """Build the CAR migrator command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Create an asset-class-aware CAR v2 repository structure without "
            "moving or overwriting existing content."
        )
    )
    parser.add_argument("root", type=Path, help="Canonical asset repository root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create folders and template files. Without this flag, preview only.",
    )
    parser.add_argument("--report", type=Path, help="Optional report output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CAR repository migrator command-line interface."""
    arguments = build_parser().parse_args(argv)
    migrator = CarRepositoryMigrator(arguments.root)
    try:
        report = migrator.migrate(apply=arguments.apply)
    except CarMigrationError as error:
        print(f"CAR migration failed: {error}")
        return 1

    report_path = migrator.write_report(report, arguments.report)
    mode = "APPLIED" if arguments.apply else "DRY RUN"
    print(
        f"CAR migration {mode}: {report.assets_scanned} assets "
        f"({report.visual_assets} visual, "
        f"{report.configuration_assets} configuration, "
        f"{report.behaviour_assets} behaviour, "
        f"{report.unknown_assets} unknown), "
        f"{report.directories_created} directories, "
        f"{report.files_created} files, "
        f"{len(report.warnings)} warnings, "
        f"{len(report.errors)} errors."
    )
    print(f"Report: {report_path}")
    return 2 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
