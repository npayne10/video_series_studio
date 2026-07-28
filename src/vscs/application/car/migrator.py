"""Safe repository structure migration for Canonical Asset Repository v2.0."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

ASSET_DIRECTORY_PATTERN = re.compile(r"^CAP-[A-Z]{3}-\d{3}(?:_.+)?$")
CAR_DIRECTORIES = (
    "canon",
    "metadata",
    "prompts",
    "thumbnails",
    "candidates",
    "rejected",
)
METADATA_TEMPLATES = (
    "cap.json",
    "knowledge.json",
    "provenance.json",
    "evaluation.json",
    "history.json",
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


@dataclass(slots=True)
class MigrationReport:
    """Complete result of one CAR migration run."""

    root: str
    applied: bool
    started_at: str
    completed_at: str = ""
    assets_scanned: int = 0
    directories_created: int = 0
    files_created: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
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
    """Create the CAR v2 directory and metadata skeleton without moving media."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def migrate(self, *, apply: bool = False) -> MigrationReport:
        """Plan or apply the repository migration.

        Existing files are never overwritten, renamed, moved, or deleted.
        """
        self._validate_root()
        report = MigrationReport(
            root=str(self.root),
            applied=apply,
            started_at=datetime.now(UTC).isoformat(),
        )

        for asset_directory in self._asset_directories():
            report.assets_scanned += 1
            self._prepare_asset(asset_directory, report, apply=apply)

        report.finish()
        return report

    def write_report(self, report: MigrationReport, path: Path | None = None) -> Path:
        """Write a migration report to disk and return its path."""
        target = path or self.root / "car_migration_report.json"
        target = target.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return target

    def _validate_root(self) -> None:
        if not self.root.exists():
            raise InvalidCarRootError(f"CAR root does not exist: {self.root}")
        if not self.root.is_dir():
            raise InvalidCarRootError(f"CAR root is not a directory: {self.root}")

    def _asset_directories(self) -> Iterable[Path]:
        for category in sorted(path for path in self.root.iterdir() if path.is_dir()):
            for candidate in sorted(path for path in category.iterdir() if path.is_dir()):
                if ASSET_DIRECTORY_PATTERN.match(candidate.name):
                    yield candidate

    def _prepare_asset(
        self,
        asset_directory: Path,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        manifest = self._read_manifest(asset_directory, report)
        asset_id = self._asset_id(asset_directory, manifest)
        asset_name = self._asset_name(asset_directory, manifest)
        category = asset_directory.parent.name

        for directory_name in CAR_DIRECTORIES:
            self._ensure_directory(asset_directory / directory_name, report, apply=apply)

        metadata_directory = asset_directory / "metadata"
        template_context = {
            "asset_id": asset_id,
            "name": asset_name,
            "category": category,
            "source_manifest": "../manifest.json",
        }
        for filename in METADATA_TEMPLATES:
            payload = self._metadata_template(filename, template_context)
            self._ensure_json_file(
                metadata_directory / filename,
                payload,
                report,
                apply=apply,
            )

    def _ensure_directory(
        self,
        path: Path,
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        relative_path = str(path.relative_to(self.root))
        if path.exists():
            report.skipped += 1
            report.actions.append(MigrationAction("create_directory", relative_path, "exists"))
            return
        if apply:
            path.mkdir(parents=True, exist_ok=False)
        report.directories_created += 1
        report.actions.append(
            MigrationAction(
                "create_directory",
                relative_path,
                "created" if apply else "planned",
            )
        )

    def _ensure_json_file(
        self,
        path: Path,
        payload: dict[str, Any],
        report: MigrationReport,
        *,
        apply: bool,
    ) -> None:
        relative_path = str(path.relative_to(self.root))
        if path.exists():
            report.skipped += 1
            report.actions.append(MigrationAction("create_file", relative_path, "exists"))
            return
        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        report.files_created += 1
        report.actions.append(
            MigrationAction("create_file", relative_path, "created" if apply else "planned")
        )

    def _read_manifest(
        self,
        asset_directory: Path,
        report: MigrationReport,
    ) -> dict[str, Any]:
        manifest_path = asset_directory / "manifest.json"
        if not manifest_path.exists():
            report.warnings.append(f"Missing manifest: {manifest_path.relative_to(self.root)}")
            return {}
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            report.warnings.append(
                f"Unreadable manifest {manifest_path.relative_to(self.root)}: {error}"
            )
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _asset_id(asset_directory: Path, manifest: dict[str, Any]) -> str:
        manifest_id = manifest.get("asset_id")
        if isinstance(manifest_id, str) and manifest_id.strip():
            return manifest_id.strip().upper()
        return asset_directory.name.split("_", maxsplit=1)[0].upper()

    @staticmethod
    def _asset_name(asset_directory: Path, manifest: dict[str, Any]) -> str:
        manifest_name = manifest.get("name") or manifest.get("asset_name")
        if isinstance(manifest_name, str) and manifest_name.strip():
            return manifest_name.strip()
        parts = asset_directory.name.split("_", maxsplit=1)
        return parts[1].replace("_", " ") if len(parts) == 2 else parts[0]

    @staticmethod
    def _metadata_template(filename: str, context: dict[str, str]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        common = {
            "schema_version": "2.0",
            "asset_id": context["asset_id"],
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
                        "version": "1.0",
                    }
                ],
            }
        raise ValueError(f"Unsupported metadata template: {filename}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CAR migrator command-line parser."""
    parser = argparse.ArgumentParser(
        description="Create the CAR v2 repository structure without moving existing media."
    )
    parser.add_argument("root", type=Path, help="Canonical asset repository root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create folders and template files. Without this flag, only preview changes.",
    )
    parser.add_argument("--report", type=Path, help="Optional report output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CAR repository migrator command line interface."""
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
        f"CAR migration {mode}: {report.assets_scanned} assets, "
        f"{report.directories_created} directories, {report.files_created} files."
    )
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
