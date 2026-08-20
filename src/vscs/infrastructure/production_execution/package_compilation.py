"""Local production package compilation and ComfyUI v7.1.4 input assurance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.production_execution.package_compilation import (
    CompiledProductionPackage,
    ProductionPackageCompilationError,
    ProductionPackageCompilationState,
    ProductionPackageCompilerService,
    ProductionPackageStatus,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus as CanonicalProductionPackageStatus,
)
from vscs.application.production_tasks import ProductionTask


class LocalProductionPackageCompilationError(ProductionPackageCompilationError):
    """Raised when local canonical or compiled package storage is invalid."""


@dataclass(frozen=True, slots=True)
class ComfyUIInputTrace:
    """Trace one governed package value into the production workflow."""

    name: str
    package_field: str
    loader_output_index: int
    consumer_class_type: str
    consumer_input: str


@dataclass(frozen=True, slots=True)
class ComfyUIInputAssuranceReport:
    """Static assurance result for the committed production workflow."""

    passed: bool
    traces: tuple[ComfyUIInputTrace, ...]
    issues: tuple[str, ...] = ()


class LocalProductionPackageCompilationService:
    """Resolve approved authority, compile it, persist it, and reject stale artifacts."""

    SOURCE_FILE = Path("production") / "production_packages.json"
    COMPILED_ROOT = Path("production") / "compiled"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.compiler = ProductionPackageCompilerService()

    def status(self, task: ProductionTask, *, profile: str = "production") -> ProductionPackageStatus:
        path = self._package_path(task, profile)
        if not path.is_file():
            return ProductionPackageStatus(
                task_id=task.task_id,
                state=ProductionPackageCompilationState.NOT_COMPILED,
                profile=profile,
                path=path,
                authority_fingerprint=task.authority.fingerprint,
                message="Production Package has not been compiled for the current authority.",
            )
        try:
            raw = self._read_json(path)
            manifest = self._manifest(raw)
            stored_authority = str(manifest.get("authority_fingerprint", ""))
            package_fingerprint = str(manifest.get("package_fingerprint", ""))
            source_package_id = str(manifest.get("source_package_id", ""))
            if stored_authority != task.authority.fingerprint:
                return ProductionPackageStatus(
                    task_id=task.task_id,
                    state=ProductionPackageCompilationState.STALE,
                    profile=profile,
                    path=path,
                    authority_fingerprint=stored_authority or None,
                    package_fingerprint=package_fingerprint or None,
                    source_package_id=source_package_id or None,
                    message="Compiled Production Package is stale against current approved authority.",
                )
            self.validate_file(task, path)
            return ProductionPackageStatus(
                task_id=task.task_id,
                state=ProductionPackageCompilationState.COMPILED,
                profile=profile,
                path=path,
                authority_fingerprint=stored_authority,
                package_fingerprint=package_fingerprint,
                source_package_id=source_package_id,
                message="Compiled Production Package matches current approved authority.",
            )
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
            LocalProductionPackageCompilationError,
        ) as exc:
            return ProductionPackageStatus(
                task_id=task.task_id,
                state=ProductionPackageCompilationState.INVALID,
                profile=profile,
                path=path,
                authority_fingerprint=task.authority.fingerprint,
                message=f"Compiled Production Package is invalid: {exc}",
            )

    def compile(self, task: ProductionTask, *, profile: str = "production") -> ProductionPackageStatus:
        source = self._authority_source(task)
        compiled = self.compiler.compile(task, source, profile=profile)
        path = self._package_path(task, compiled.profile)
        payload = self._comfyui_payload(compiled)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        result = self.status(task, profile=compiled.profile)
        if not result.executable:
            raise LocalProductionPackageCompilationError(result.message)
        return result

    def require_current(
        self,
        task: ProductionTask,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        result = self.status(task, profile=profile)
        if not result.executable:
            raise LocalProductionPackageCompilationError(
                result.message
                + " Compile or recompile the Production Package before starting production."
            )
        return result

    def validate_file(self, task: ProductionTask, path: Path) -> None:
        raw = self._read_json(path)
        manifest = self._manifest(raw)
        if str(manifest.get("task_id", "")) != task.task_id:
            raise LocalProductionPackageCompilationError(
                "Production Package task identity does not match selected ProductionTask"
            )
        if str(manifest.get("authority_fingerprint", "")) != task.authority.fingerprint:
            raise LocalProductionPackageCompilationError(
                "Production Package authority fingerprint does not match selected ProductionTask"
            )
        expected = str(manifest.get("package_fingerprint", ""))
        if not expected:
            raise LocalProductionPackageCompilationError(
                "Production Package has no package fingerprint"
            )
        content = dict(raw)
        content.pop("_vscs_manifest", None)
        actual = self._fingerprint(content)
        if actual != expected:
            raise LocalProductionPackageCompilationError(
                "Production Package fingerprint does not match its content"
            )
        required = (
            "target_description",
            "shot_prompt",
            "negative_prompt",
            "filename_prefix",
            "width",
            "height",
            "frame_count",
            "fps",
            "cfg",
            "ic_lora_strength",
            "seed",
            "composition_plan",
            "production_authority",
        )
        missing = tuple(key for key in required if key not in raw)
        if missing:
            raise LocalProductionPackageCompilationError(
                "Production Package is missing required loader inputs: " + ", ".join(missing)
            )

    def _authority_source(self, task: ProductionTask) -> ProductionPackage:
        if task.shot_id is None:
            raise LocalProductionPackageCompilationError(
                "VIDEO_GENERATION ProductionTask has no Shot identity"
            )
        path = self.project_directory / self.SOURCE_FILE
        if not path.is_file():
            raise LocalProductionPackageCompilationError(
                f"Canonical Production Package storage does not exist: {path}"
            )
        root = self._read_json(path)
        raw_packages = root.get("production_packages", [])
        if not isinstance(raw_packages, list):
            raise LocalProductionPackageCompilationError(
                "Canonical Production Package storage is invalid"
            )
        for raw in reversed(raw_packages):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("shot_id", "")).strip().upper() != task.shot_id.strip().upper():
                continue
            source = self._canonical_from_dict(raw)
            if self.compiler.authority_fingerprint(source) == task.authority.fingerprint:
                return source
        raise LocalProductionPackageCompilationError(
            "No canonical Production Package matches the ProductionTask approved authority fingerprint"
        )

    def _package_path(self, task: ProductionTask, profile: str) -> Path:
        normalized = profile.strip().lower() or "production"
        return (
            self.project_directory
            / self.COMPILED_ROOT
            / normalized
            / task.task_id
            / "production_package.json"
        )

    @classmethod
    def _comfyui_payload(cls, compiled: CompiledProductionPackage) -> dict[str, Any]:
        """Translate provider-neutral execution authority into the v7.1.4 loader contract."""
        content: dict[str, Any] = {
            "schema_version": "7.1.4-vscs-1",
            "profile": compiled.profile,
            "target_description": compiled.universal_text,
            "shot_prompt": compiled.positive_prompt,
            "negative_prompt": compiled.negative_prompt,
            "previous_approved_final_frame": compiled.previous_approved_final_frame or "",
            "filename_prefix": compiled.filename_prefix,
            "width": compiled.width,
            "height": compiled.height,
            "frame_count": compiled.frame_count,
            "fps": compiled.frames_per_second,
            "cfg": compiled.cfg,
            "ic_lora_strength": compiled.ic_lora_strength,
            "seed": compiled.seed,
            "composition_plan": compiled.composition_plan,
            "production_authority": compiled.production_authority,
        }
        fingerprint = cls._fingerprint(content)
        content["_vscs_manifest"] = {
            "task_id": compiled.task_id,
            "production_id": compiled.production_id,
            "episode_id": compiled.episode_id,
            "scene_id": compiled.scene_id,
            "shot_id": compiled.shot_id,
            "authority_id": compiled.authority_id,
            "authority_revision": compiled.authority_revision,
            "authority_fingerprint": compiled.authority_fingerprint,
            "approved_by": compiled.approved_by,
            "source_package_id": compiled.source_package_id,
            "source_package_fingerprint": compiled.source_package_fingerprint,
            "source_schema_version": compiled.source_schema_version,
            "package_fingerprint": fingerprint,
            "compiler": "VSCS Phase 20.15.1",
        }
        return content

    @staticmethod
    def _manifest(raw: dict[str, Any]) -> dict[str, Any]:
        manifest = raw.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise LocalProductionPackageCompilationError(
                "Production Package has no VSCS compilation manifest"
            )
        return manifest

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise LocalProductionPackageCompilationError("Production Package JSON root is not an object")
        return raw

    @staticmethod
    def _canonical_from_dict(data: dict[str, Any]) -> ProductionPackage:
        provenance_raw = data.get("provenance")
        if not isinstance(provenance_raw, dict):
            raise LocalProductionPackageCompilationError(
                "Canonical Production Package provenance is invalid"
            )
        return ProductionPackage(
            package_id=str(data["package_id"]),
            shot_id=str(data["shot_id"]),
            schema_version=str(data["schema_version"]),
            source_fingerprint=str(data["source_fingerprint"]),
            package_fingerprint=str(data["package_fingerprint"]),
            provenance=ProductionPackageProvenance(
                integrated_package_id=str(provenance_raw["integrated_package_id"]),
                integrated_package_fingerprint=str(
                    provenance_raw["integrated_package_fingerprint"]
                ),
                planning_review_id=str(provenance_raw["planning_review_id"]),
                planning_review_fingerprint=str(provenance_raw["planning_review_fingerprint"]),
            ),
            story_context=dict(data.get("story_context", {})),
            shot=dict(data.get("shot", {})),
            assets=tuple(dict(item) for item in data.get("assets", [])),
            camera=dict(data.get("camera", {})),
            lighting=dict(data.get("lighting", {})),
            environment=dict(data.get("environment", {})),
            action_performance=dict(data.get("action_performance", {})),
            continuity=dict(data.get("continuity", {})),
            style=dict(data.get("style", {})),
            dialogue=tuple(dict(item) for item in data.get("dialogue", [])),
            effects=tuple(dict(item) for item in data.get("effects", [])),
            references=tuple(dict(item) for item in data.get("references", [])),
            universal_description=dict(data.get("universal_description", {})),
            provider_outputs=dict(data.get("provider_outputs", {})),
            validation=dict(data.get("validation", {})),
            status=CanonicalProductionPackageStatus(
                str(data.get("status", CanonicalProductionPackageStatus.FOUNDATION.value))
            ),
        )

    @staticmethod
    def _fingerprint(value: object) -> str:
        canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ComfyUIV714InputAssurance:
    """Prove that governed production-package outputs are wired into the committed workflow."""

    LOADER_CLASS = "XorixProductionPackageLoaderV714"
    LOADER_TITLE = "Xorix Production Package — Canonical Composition v7.1.4"
    EXPECTED: tuple[tuple[str, str, int, str, str], ...] = (
        ("target_description", "target_description", 4, "XorixCanonicalCompositionBuilderV714", "target_description"),
        ("shot_prompt", "shot_prompt", 5, "CLIPTextEncode", "text"),
        ("negative_prompt", "negative_prompt", 6, "CLIPTextEncode", "text"),
        (
            "previous_approved_final_frame",
            "previous_approved_final_frame",
            7,
            "XorixOptionalImageLoaderV60",
            "image_path",
        ),
        ("filename_prefix", "filename_prefix", 8, "SaveVideo", "filename_prefix"),
        ("width", "width", 9, "EmptyLTXVLatentVideo", "width"),
        ("height", "height", 10, "EmptyLTXVLatentVideo", "height"),
        ("frame_count", "frame_count", 11, "EmptyLTXVLatentVideo", "length"),
        ("fps", "fps", 13, "LTXVConditioning", "frame_rate"),
        ("cfg", "cfg", 14, "CFGGuider", "cfg"),
        ("ic_lora_strength", "ic_lora_strength", 15, "LTXICLoRALoaderModelOnly", "strength_model"),
        (
            "composition_plan",
            "composition_plan",
            20,
            "XorixCanonicalCompositionBuilderV714",
            "composition_plan_json",
        ),
    )

    def inspect(self, workflow_path: Path) -> ComfyUIInputAssuranceReport:
        raw = LocalProductionPackageCompilationService._read_json(workflow_path)
        loaders = [
            (node_id, node)
            for node_id, node in raw.items()
            if isinstance(node, dict)
            and node.get("class_type") == self.LOADER_CLASS
            and isinstance(node.get("_meta"), dict)
            and node["_meta"].get("title") == self.LOADER_TITLE
        ]
        if len(loaders) != 1:
            return ComfyUIInputAssuranceReport(
                passed=False,
                traces=(),
                issues=(
                    "Production package loader must resolve to exactly one semantic workflow node.",
                ),
            )
        loader_id = loaders[0][0]
        traces: list[ComfyUIInputTrace] = []
        issues: list[str] = []
        for name, package_field, index, class_type, input_name in self.EXPECTED:
            consumers = []
            for node in raw.values():
                if not isinstance(node, dict) or node.get("class_type") != class_type:
                    continue
                inputs = node.get("inputs")
                if not isinstance(inputs, dict):
                    continue
                value = inputs.get(input_name)
                if value == [loader_id, index]:
                    consumers.append(node)
            if not consumers:
                issues.append(
                    f"{name} loader output {index} is not wired to {class_type}.{input_name}"
                )
                continue
            traces.append(
                ComfyUIInputTrace(
                    name=name,
                    package_field=package_field,
                    loader_output_index=index,
                    consumer_class_type=class_type,
                    consumer_input=input_name,
                )
            )
        return ComfyUIInputAssuranceReport(
            passed=not issues,
            traces=tuple(traces),
            issues=tuple(issues),
        )
