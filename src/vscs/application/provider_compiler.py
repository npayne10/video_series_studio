"""Provider-specific compilation framework for Phase 19.4.9."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageService,
    ProductionPackageStatus,
)
from vscs.application.projects import ProjectNotOpenError, ProjectService


class ProviderCompilerError(RuntimeError):
    """Raised when provider output cannot be compiled safely."""


class ProviderCompilationStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"


class ProviderCompiler(Protocol):
    """Compile approved universal production authority for one provider."""

    provider_id: str
    display_name: str
    compiler_version: str

    def compile(self, universal: dict[str, Any]) -> dict[str, Any]:
        """Return deterministic provider-specific output without executing it."""
        ...


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    compiler_version: str


class ProviderCompilerRegistry:
    """Runtime registry of provider compilers."""

    def __init__(self) -> None:
        self._compilers: dict[str, ProviderCompiler] = {}

    def register(self, compiler: ProviderCompiler) -> None:
        provider_id = compiler.provider_id.strip().lower()
        if not provider_id:
            raise ProviderCompilerError("Provider compiler id must not be empty")
        if provider_id in self._compilers:
            raise ProviderCompilerError(f"Provider compiler already registered: {provider_id}")
        self._compilers[provider_id] = compiler

    def require(self, provider_id: str) -> ProviderCompiler:
        normalized = provider_id.strip().lower()
        compiler = self._compilers.get(normalized)
        if compiler is None:
            raise ProviderCompilerError(f"Provider compiler is not registered: {normalized}")
        return compiler

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(
            ProviderDescriptor(
                provider_id=item.provider_id,
                display_name=item.display_name,
                compiler_version=item.compiler_version,
            )
            for item in sorted(self._compilers.values(), key=lambda value: value.provider_id)
        )


class ComfyUIProviderCompiler:
    """Compile approved production authority into the VSCS ComfyUI input contract."""

    provider_id = "comfyui"
    display_name = "ComfyUI"
    compiler_version = "1.0"

    def compile(self, universal: dict[str, Any]) -> dict[str, Any]:
        production = _production_view(universal)
        text = str(production.get("universal_text", "")).strip()
        if not text:
            raise ProviderCompilerError("Approved Universal Production Description has no text")
        findings = production.get("consistency_findings", [])
        if isinstance(findings, list) and findings:
            raise ProviderCompilerError(
                "Provider compilation is blocked by Universal Production Description findings"
            )
        references = production.get("canonical_references", [])
        if not isinstance(references, list):
            references = []
        continuity = production.get("continuity", {})
        if not isinstance(continuity, dict):
            continuity = {}
        return {
            "provider_id": self.provider_id,
            "compiler_version": self.compiler_version,
            "contract": "vscs.comfyui.production-input.v1",
            "execution": "not-submitted",
            "prompt": {
                "positive": text,
                "negative": [],
            },
            "canonical_references": [dict(item) for item in references if isinstance(item, dict)],
            "shot": _dict_value(production.get("shot")),
            "camera": _dict_value(production.get("camera")),
            "lighting": _dict_value(production.get("lighting")),
            "environment": _dict_value(production.get("environment")),
            "continuity": _dict_value(continuity),
            "style": _dict_value(production.get("style")),
            "workflow": {
                "workflow_id": None,
                "selection_policy": "downstream-provider-configuration",
            },
            "source_policy": "approved-universal-production-description-only",
        }


@dataclass(frozen=True, slots=True)
class ProviderCompilationDraft:
    shot_id: str
    provider_id: str
    source_package_id: str
    dependency_fingerprint: str
    provider_output: dict[str, Any] | None = None
    production_notes: str = ""
    status: ProviderCompilationStatus = ProviderCompilationStatus.DRAFT

    def output_value(self) -> dict[str, Any]:
        return dict(self.provider_output or {})


class ProviderCompilerFrameworkService:
    """Govern provider-specific compilation without executing provider workflows."""

    FILE_NAME = "provider_compilation.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        registry: ProviderCompilerRegistry | None = None,
    ) -> None:
        self.projects = projects
        self.packages = packages
        self.registry = registry or ProviderCompilerRegistry()
        if not self.registry.descriptors():
            self.registry.register(ComfyUIProviderCompiler())

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def providers(self) -> tuple[ProviderDescriptor, ...]:
        return self.registry.descriptors()

    def list_drafts(self) -> tuple[ProviderCompilationDraft, ...]:
        if not self.draft_file.is_file():
            return ()
        try:
            raw = json.loads(self.draft_file.read_text(encoding="utf-8"))
            drafts = tuple(self._from_dict(item) for item in raw.get("provider_compilation", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ProviderCompilerError(
                f"Unable to load Provider compilation drafts: {exc}"
            ) from exc
        return tuple(sorted(drafts, key=lambda item: (item.shot_id, item.provider_id)))

    def draft(self, shot_id: str, provider_id: str) -> ProviderCompilationDraft | None:
        normalized_shot = shot_id.strip().upper()
        normalized_provider = provider_id.strip().lower()
        return next(
            (
                item
                for item in self.list_drafts()
                if item.shot_id == normalized_shot and item.provider_id == normalized_provider
            ),
            None,
        )

    def create_from_current_package(
        self, shot_id: str, provider_id: str
    ) -> ProviderCompilationDraft:
        shot = shot_id.strip().upper()
        provider = provider_id.strip().lower()
        if self.draft(shot, provider) is not None:
            raise ProviderCompilerError(
                f"Provider compilation already exists for {shot} / {provider}"
            )
        package = self.packages.require_current_package(shot)
        self._require_universal_ready(package)
        compiler = self.registry.require(provider)
        draft = ProviderCompilationDraft(
            shot_id=shot,
            provider_id=provider,
            source_package_id=package.package_id,
            dependency_fingerprint=self._dependency_fingerprint(package, compiler),
            provider_output=compiler.compile(package.universal_description),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str, provider_id: str) -> ProviderCompilationDraft:
        current = self._require_draft(shot_id, provider_id)
        if current.status is ProviderCompilationStatus.READY:
            raise ProviderCompilerError(
                "Ready Provider output must return to Draft before refreshing"
            )
        package = self.packages.require_current_package(current.shot_id)
        self._require_universal_ready(package)
        compiler = self.registry.require(current.provider_id)
        fingerprint = self._dependency_fingerprint(package, compiler)
        if fingerprint == current.dependency_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            dependency_fingerprint=fingerprint,
            provider_output=compiler.compile(package.universal_description),
        )
        self._replace(updated)
        return updated

    def save_notes(self, shot_id: str, provider_id: str, notes: str) -> ProviderCompilationDraft:
        current = self._require_draft(shot_id, provider_id)
        if current.status is ProviderCompilationStatus.READY:
            raise ProviderCompilerError("Ready Provider output must return to Draft before editing")
        if not self.is_current(current):
            raise ProviderCompilerError(
                "Provider output is stale against current universal authority"
            )
        updated = replace(current, production_notes=notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str, provider_id: str) -> ProviderCompilationDraft:
        current = self._require_draft(shot_id, provider_id)
        if not self.is_current(current):
            raise ProviderCompilerError(
                "Provider output is stale against current universal authority"
            )
        package = self.packages.require_current_package(current.shot_id)
        self._require_universal_ready(package)
        self._validate_output(current.output_value(), current.provider_id)
        ready = replace(current, status=ProviderCompilationStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id, ready.provider_id)
        return ready

    def return_to_draft(self, shot_id: str, provider_id: str) -> ProviderCompilationDraft:
        current = self._require_draft(shot_id, provider_id)
        draft = replace(current, status=ProviderCompilationStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: ProviderCompilationDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        if package is None:
            return False
        compiler = self.registry.require(draft.provider_id)
        return draft.dependency_fingerprint == self._dependency_fingerprint(package, compiler)

    def compile(self, shot_id: str, provider_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id, provider_id)
        if draft.status is not ProviderCompilationStatus.READY:
            raise ProviderCompilerError("Only Ready Provider output may be compiled")
        if not self.is_current(draft):
            raise ProviderCompilerError("Provider output is stale and cannot be compiled")
        package = self.packages.require_current_package(draft.shot_id)
        self._require_universal_ready(package)
        output = draft.output_value()
        self._validate_output(output, draft.provider_id)
        data = asdict(package)
        data.pop("package_id", None)
        data.pop("package_fingerprint", None)
        provider_outputs = dict(package.provider_outputs)
        provider_outputs[draft.provider_id] = {
            "governed": output,
            "production_notes": draft.production_notes,
            "status": "ready",
        }
        data["provider_outputs"] = provider_outputs
        validation = dict(package.validation)
        validation[f"provider_{draft.provider_id}_complete"] = True
        data["validation"] = validation
        data["status"] = ProductionPackageStatus.COMPILING.value
        append_derived: Any = self.packages._append_derived
        compiled: ProductionPackage = append_derived(package, data)
        return compiled

    @staticmethod
    def _require_universal_ready(package: ProductionPackage) -> None:
        if package.validation.get("universal_description_complete") is not True:
            raise ProviderCompilerError(
                "Provider compilation requires an approved Universal Production Description"
            )
        if package.validation.get("cross_authority_consistent") is not True:
            raise ProviderCompilerError(
                "Provider compilation requires cross-authority consistency approval"
            )
        production = _production_view(package.universal_description)
        findings = production.get("consistency_findings", [])
        if isinstance(findings, list) and findings:
            raise ProviderCompilerError(
                "Provider compilation is blocked by unresolved Universal Production Description findings"
            )

    @classmethod
    def _dependency_fingerprint(cls, package: ProductionPackage, compiler: ProviderCompiler) -> str:
        payload = {
            "schema_version": cls.SCHEMA_VERSION,
            "provider_id": compiler.provider_id,
            "compiler_version": compiler.compiler_version,
            "universal_description": package.universal_description,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_output(output: dict[str, Any], provider_id: str) -> None:
        if output.get("provider_id") != provider_id:
            raise ProviderCompilerError("Provider output identity does not match selected provider")
        if not str(output.get("contract", "")).strip():
            raise ProviderCompilerError("Provider output has no contract identity")
        if output.get("execution") != "not-submitted":
            raise ProviderCompilerError(
                "Phase 19.4.9 compiles provider output but must not submit execution"
            )

    def _require_draft(self, shot_id: str, provider_id: str) -> ProviderCompilationDraft:
        draft = self.draft(shot_id, provider_id)
        if draft is None:
            raise ProviderCompilerError(
                f"No Provider compilation exists for {shot_id.strip().upper()} / {provider_id.strip().lower()}"
            )
        return draft

    def _replace(self, updated: ProviderCompilationDraft) -> None:
        self._write(
            tuple(
                updated
                if item.shot_id == updated.shot_id and item.provider_id == updated.provider_id
                else item
                for item in self.list_drafts()
            )
        )

    def _write(self, drafts: tuple[ProviderCompilationDraft, ...]) -> None:
        self.draft_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "provider_compilation": [self._to_dict(item) for item in drafts],
        }
        temporary = self.draft_file.with_suffix(self.draft_file.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.draft_file)

    @staticmethod
    def _to_dict(draft: ProviderCompilationDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> ProviderCompilationDraft:
        output = data.get("provider_output", {})
        if not isinstance(output, dict):
            raise ProviderCompilerError("Provider compilation output is invalid")
        return ProviderCompilationDraft(
            shot_id=str(data["shot_id"]),
            provider_id=str(data["provider_id"]),
            source_package_id=str(data["source_package_id"]),
            dependency_fingerprint=str(data["dependency_fingerprint"]),
            provider_output=dict(output),
            production_notes=str(data.get("production_notes", "")),
            status=ProviderCompilationStatus(str(data.get("status", "draft"))),
        )


def _production_view(value: dict[str, Any]) -> dict[str, Any]:
    production = value.get("production")
    if isinstance(production, dict):
        return dict(production)
    governed = value.get("governed")
    if isinstance(governed, dict):
        return dict(governed)
    return dict(value)


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
