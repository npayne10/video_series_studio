"""Current-authority guard for Phase 20.18.2 Preview/XPC compilation.

The legacy local package compiler resolved a ProductionTask by scanning canonical
ProductionPackage history backwards until *any* historical package matched the
immutable task authority fingerprint.  That behavior is unsafe once a READY UPD
acquires a newer governed ReferencePlan: an old task can silently select an old
UPD-bearing package and produce a seemingly READY Preview package.

This module makes current READY UPD authority the only executable source.  A
reference-only READY-UPD dependency change is refreshed through the existing UPD
compiler.  If that produces authority different from the immutable scheduled
ProductionTask, compilation is blocked and the task must be recompiled/rescheduled.
Historical package fallback is never used.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilationState,
    ProductionPackageStatus,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.production_tasks import ProductionTask
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionStatus,
)

from .ltx23_v721_backend import (
    LocalComfyUIProductionExecutionBackend as _LTX23V721Backend,
)
from .ltx23_v721_backend import (
    LocalLTX23V721ProductionPackageCompilationService,
)
from .package_compilation import LocalProductionPackageCompilationError


class _ProjectDirectoryView:
    """Minimal ProjectService-compatible view needed by the UPD compiler."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory


class _CurrentProductionPackageStore:
    """File-backed current-package adapter used only for governed UPD refresh.

    ProductionPackage history remains append-only.  The last record for the shot
    is treated as current execution authority; older records remain readable but
    are never selected for execution merely because they match an old task hash.
    """

    SOURCE_FILE = Path("production") / "production_packages.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self.path = project_directory / self.SOURCE_FILE

    def current_package(self, shot_id: str) -> ProductionPackage | None:
        normalized = shot_id.strip().upper()
        for raw in reversed(self._raw_packages()):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("shot_id", "")).strip().upper() == normalized:
                return LocalLTX23V721ProductionPackageCompilationService._canonical_from_dict(raw)
        return None

    def materialize(self, shot_id: str) -> ProductionPackage:
        package = self.current_package(shot_id)
        if package is None:
            raise LocalProductionPackageCompilationError(
                f"No current Production Package exists for {shot_id.strip().upper()}"
            )
        return package

    def require_current_package(self, shot_id: str) -> ProductionPackage:
        return self.materialize(shot_id)

    def _append_derived(
        self, current: ProductionPackage, data: dict[str, Any]
    ) -> ProductionPackage:
        payload = dict(data)
        payload.pop("package_id", None)
        payload.pop("package_fingerprint", None)
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        package_id = f"PP-{current.shot_id}-{fingerprint[:12].upper()}"

        raw_packages = self._raw_packages()
        for raw in reversed(raw_packages):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("shot_id", "")).strip().upper() != current.shot_id.strip().upper():
                continue
            if str(raw.get("package_fingerprint", "")) == fingerprint:
                return LocalLTX23V721ProductionPackageCompilationService._canonical_from_dict(raw)

        payload["package_id"] = package_id
        payload["package_fingerprint"] = fingerprint
        derived = LocalLTX23V721ProductionPackageCompilationService._canonical_from_dict(payload)
        self._write((*raw_packages, payload))
        return derived

    def _raw_packages(self) -> tuple[dict[str, Any], ...]:
        if not self.path.is_file():
            return ()
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LocalProductionPackageCompilationError(
                f"Cannot read canonical Production Package storage: {exc}"
            ) from exc
        raw = root.get("production_packages", []) if isinstance(root, dict) else None
        if not isinstance(raw, list):
            raise LocalProductionPackageCompilationError(
                "Canonical Production Package storage is invalid"
            )
        return tuple(dict(item) for item in raw if isinstance(item, dict))

    def _write(self, packages: tuple[dict[str, Any], ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "production_packages": list(packages),
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class CurrentAuthorityLTX23V721ProductionPackageCompilationService(
    LocalLTX23V721ProductionPackageCompilationService
):
    """Compile only from the current READY UPD and never from matching history."""

    def _authority_source(self, task: ProductionTask) -> ProductionPackage:
        source = self._refresh_current_ready_upd(task)
        current_fingerprint = self.compiler.authority_fingerprint(source)
        if current_fingerprint != task.authority.fingerprint:
            raise LocalProductionPackageCompilationError(
                "ProductionTask approved UPD authority is stale against the current READY UPD. "
                f"Current source package is {source.package_id}. Recompile and reschedule the "
                "ProductionTask from current READY UPD authority; historical ProductionPackage "
                "fallback is prohibited."
            )
        return source

    def _refresh_current_ready_upd(self, task: ProductionTask) -> ProductionPackage:
        if task.shot_id is None:
            raise LocalProductionPackageCompilationError(
                "VIDEO_GENERATION ProductionTask has no Shot identity"
            )
        projects = _ProjectDirectoryView(self.project_directory)
        packages = _CurrentProductionPackageStore(self.project_directory)
        universal = UniversalProductionDescriptionCompilerService(
            projects,  # type: ignore[arg-type]
            packages,  # type: ignore[arg-type]
        )
        draft = universal.draft(task.shot_id)
        if draft is None:
            raise LocalProductionPackageCompilationError(
                f"No Universal Production Description exists for {task.shot_id.strip().upper()}"
            )
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise LocalProductionPackageCompilationError(
                f"Universal Production Description for {task.shot_id.strip().upper()} is not Ready"
            )
        try:
            return universal.compile(task.shot_id)
        except UniversalProductionDescriptionCompilerError as exc:
            raise LocalProductionPackageCompilationError(
                f"Current READY UPD cannot be refreshed for execution: {exc}"
            ) from exc

    def status(
        self,
        task: ProductionTask,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        base = super().status(task, profile=profile)
        try:
            source = self._authority_source(task)
        except LocalProductionPackageCompilationError as exc:
            return ProductionPackageStatus(
                task_id=task.task_id,
                state=ProductionPackageCompilationState.STALE,
                profile=profile,
                path=base.path,
                authority_fingerprint=task.authority.fingerprint,
                package_fingerprint=base.package_fingerprint,
                source_package_id=base.source_package_id,
                message=str(exc),
            )
        if base.executable and base.source_package_id != source.package_id:
            return ProductionPackageStatus(
                task_id=task.task_id,
                state=ProductionPackageCompilationState.STALE,
                profile=profile,
                path=base.path,
                authority_fingerprint=task.authority.fingerprint,
                package_fingerprint=base.package_fingerprint,
                source_package_id=base.source_package_id,
                message=(
                    "Compiled Production Package was built from an older ProductionPackage "
                    f"revision ({base.source_package_id}); current READY UPD source is "
                    f"{source.package_id}. Recompile before execution."
                ),
            )
        return base

    def validate_file(self, task: ProductionTask, path: Path) -> None:
        self._authority_source(task)
        super().validate_file(task, path)


class LocalComfyUIProductionExecutionBackend(_LTX23V721Backend):
    """LTX v7.2.1 backend with current-UPD-only Preview/XPC authority selection."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            project_directory,
            endpoint=endpoint,
            comfyui_output_directory=comfyui_output_directory,
            managed_media_directory=managed_media_directory,
            lease_duration_seconds=lease_duration_seconds,
        )
        self.package_compilation = CurrentAuthorityLTX23V721ProductionPackageCompilationService(
            self.project_directory
        )
