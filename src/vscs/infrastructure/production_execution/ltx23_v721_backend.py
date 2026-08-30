"""LTX-2.3 Production Engine v7.2.1 integration for Phase 20.18.2."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from vscs.application.production_execution import (
    CompiledProductionPackage,
    ProductionExecutionError,
    ProductionPackageStatus,
)
from vscs.application.production_tasks import ProductionTask
from vscs.application.rendering import RenderRequest
from vscs.application.rendering.workflows import (
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.infrastructure.rendering import (
    ComfyUIWorkflowCompiler,
    ProductionPackageComfyUIAdapter,
)

from .package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)
from .stale_reconciliation_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase20182ProductionExecutionBackend,
)

LTX23_V721_WORKFLOW_ID = "ltx23_production_v1"
LTX23_V721_WORKFLOW_FILE = "workflows/ltx23_production_v1_api.json"
LTX23_V721_MANIFEST_FILE = "ltx23_production_v1.json"
LTX23_V721_PACKAGE_SCHEMA = "7.2.1-vscs-1"
LTX23_V721_PACKAGE_LOADER_CLASS = "VSCSProductionPackageLoaderV720"
LTX23_V721_PACKAGE_LOADER_TITLE = "VSCS Production Package — Governed References v7.2.1"
LTX23_V721_REFERENCE_RESOLVER_CLASS = "VSCSReferenceResolverV720"
LTX23_V721_REFERENCE_RESOLVER_TITLE = "VSCS Governed Reference Resolver v7.2.0"
_IDENTITY_ROLES = frozenset({"primary_identity", "secondary_identity", "group_identity"})


@dataclass(frozen=True, slots=True)
class LTX23V721DeploymentAssurance:
    """Verify the checked-in v7.2.1 provider workflow before live package compilation."""

    workflow_root: Path

    def inspect(self) -> tuple[str, ...]:
        root = self.workflow_root.resolve(strict=False)
        workflow_path = (root / LTX23_V721_WORKFLOW_FILE).resolve(strict=False)
        if workflow_path != root and root not in workflow_path.parents:
            return ("LTX-2.3 v7.2.1 workflow path escapes the configured workflow root",)
        if not workflow_path.is_file():
            return (f"LTX-2.3 v7.2.1 workflow is not installed at {workflow_path}",)
        try:
            raw = json.loads(workflow_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return (f"LTX-2.3 v7.2.1 workflow cannot be read as API JSON: {exc}",)
        if not isinstance(raw, dict) or not raw:
            return ("LTX-2.3 v7.2.1 API workflow must be a non-empty object",)

        issues: list[str] = []
        self._inspect_semantic_node(
            raw,
            class_type=LTX23_V721_PACKAGE_LOADER_CLASS,
            title=LTX23_V721_PACKAGE_LOADER_TITLE,
            label="production package loader",
            issues=issues,
        )
        self._inspect_semantic_node(
            raw,
            class_type=LTX23_V721_REFERENCE_RESOLVER_CLASS,
            title=LTX23_V721_REFERENCE_RESOLVER_TITLE,
            label="governed reference resolver",
            issues=issues,
        )

        loader = self._matching_node(
            raw,
            LTX23_V721_PACKAGE_LOADER_CLASS,
            LTX23_V721_PACKAGE_LOADER_TITLE,
        )
        if loader is not None:
            inputs = loader.get("inputs")
            if not isinstance(inputs, dict):
                issues.append("v7.2.1 production package loader inputs must be an object")
            else:
                if inputs.get("production_package") != "":
                    issues.append(
                        "v7.2.1 production package path must remain blank in the checked-in workflow"
                    )
                if inputs.get("profile_override") != "from_package":
                    issues.append(
                        "v7.2.1 profile override must be sourced from the production package"
                    )
                if inputs.get("strict_validation") is not True:
                    issues.append(
                        "v7.2.1 production package loader strict validation must remain enabled"
                    )

        resolver = self._matching_node(
            raw,
            LTX23_V721_REFERENCE_RESOLVER_CLASS,
            LTX23_V721_REFERENCE_RESOLVER_TITLE,
        )
        if resolver is not None:
            inputs = resolver.get("inputs")
            if not isinstance(inputs, dict):
                issues.append("v7.2.1 governed reference resolver inputs must be an object")
            elif inputs.get("strict_validation") is not True:
                issues.append(
                    "v7.2.1 governed reference resolver strict validation must remain enabled"
                )
        return tuple(issues)

    @classmethod
    def _inspect_semantic_node(
        cls,
        workflow: dict[str, object],
        *,
        class_type: str,
        title: str,
        label: str,
        issues: list[str],
    ) -> None:
        matches = [
            node
            for node in workflow.values()
            if isinstance(node, dict)
            and node.get("class_type") == class_type
            and isinstance(node.get("_meta"), dict)
            and node["_meta"].get("title") == title
        ]
        if len(matches) != 1:
            issues.append(f"v7.2.1 {label} must resolve to exactly one semantic workflow node")

    @staticmethod
    def _matching_node(
        workflow: dict[str, object],
        class_type: str,
        title: str,
    ) -> dict[str, object] | None:
        matches = [
            node
            for node in workflow.values()
            if isinstance(node, dict)
            and node.get("class_type") == class_type
            and isinstance(node.get("_meta"), dict)
            and node["_meta"].get("title") == title
        ]
        return matches[0] if len(matches) == 1 else None


class LocalLTX23V721ProductionPackageCompilationService(LocalProductionPackageCompilationService):
    """Emit the v7.2.1 package contract without weakening governed reference authority."""

    def validate_file(self, task: ProductionTask, path: Path) -> None:
        super().validate_file(task, path)
        raw = self._read_json(path)
        schema_version = str(raw.get("schema_version") or "")
        if schema_version != LTX23_V721_PACKAGE_SCHEMA:
            raise LocalProductionPackageCompilationError(
                "Production Package is not compiled for LTX-2.3 v7.2.1; "
                "recompile it before starting production"
            )

    def _comfyui_payload(self, compiled: CompiledProductionPackage) -> dict[str, Any]:
        content = super()._comfyui_payload(compiled)
        content["schema_version"] = LTX23_V721_PACKAGE_SCHEMA
        content["status"] = "READY"
        content["positive_prompt"] = compiled.positive_prompt
        content["acpp"] = {
            "metadata": {"id": compiled.source_package_id},
            "timing": {
                "frames": compiled.frame_count,
                "fps": compiled.frames_per_second,
            },
            "generation": {
                "render_profile": compiled.profile,
                "width": compiled.width,
                "height": compiled.height,
                "cfg": compiled.cfg,
                "ic_lora_model_strength": compiled.ic_lora_strength,
                "reference_guide_strength": compiled.ic_lora_strength,
                "seed": compiled.seed,
                "audio_mode": "generated_reference",
            },
            "prompts": {
                "positive": compiled.positive_prompt,
                "negative": compiled.negative_prompt,
            },
            "story": {
                "opening_state": "",
                "primary_action": compiled.universal_text,
                "performance": "",
                "environmental_motion": "",
                "ending_state": "",
            },
            "output": {"filename_prefix": compiled.filename_prefix},
        }
        if compiled.reference_plan is not None:
            content["reference_plan"] = self._provider_reference_plan(compiled.reference_plan)
        self._refresh_manifest_fingerprint(content)
        return content

    def _provider_reference_plan(self, raw_plan: object) -> dict[str, Any]:
        if not isinstance(raw_plan, dict):
            raise LocalProductionPackageCompilationError(
                "Governed ReferencePlan must be an object before v7.2.1 provider binding"
            )
        references = raw_plan.get("references")
        if not isinstance(references, list) or not references:
            raise LocalProductionPackageCompilationError(
                "Governed ReferencePlan has no references for v7.2.1 provider binding"
            )
        plan = dict(raw_plan)
        plan["schema_version"] = "2.0"
        plan["provider"] = "ltx-2.3"
        plan["legacy_synthesized"] = False
        plan["bindings"] = [self._provider_reference_binding(item) for item in references]
        return plan

    def _provider_reference_binding(self, raw: object) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise LocalProductionPackageCompilationError(
                "Governed ReferencePlan reference entries must be objects"
            )
        reference_id = str(raw.get("reference_id") or "").strip()
        source_path = str(raw.get("source_path") or "").strip()
        if not reference_id or not source_path:
            raise LocalProductionPackageCompilationError(
                "Governed reference requires reference_id and source_path for v7.2.1 binding"
            )
        path = Path(source_path).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        path = path.resolve(strict=False)
        if not path.is_file():
            raise LocalProductionPackageCompilationError(
                f"Governed provider reference file does not exist: {path}"
            )

        role = str(raw.get("role") or "").strip()
        required = str(raw.get("priority") or "").strip().lower() == "required"
        coverage_raw = raw.get("coverage")
        coverage_detail = dict(coverage_raw) if isinstance(coverage_raw, dict) else {}
        coverage: list[str] = []
        if coverage_detail.get("required_features_visible") is True:
            coverage.append("required_features")
        if coverage_detail.get("full_required_asset_visible") is True:
            coverage.append("full_required_asset")
        if coverage_detail.get("identity_visible") is True:
            coverage.append("identity")

        required_coverage: list[str] = []
        if required:
            required_coverage.extend(("required_features", "full_required_asset"))
            if role in _IDENTITY_ROLES:
                required_coverage.append("identity")

        return {
            "reference_id": reference_id,
            "asset_id": str(raw.get("asset_id") or ""),
            "role": role,
            "path": str(path),
            "required": required,
            "provider_ready": raw.get("provider_ready"),
            "coverage": coverage,
            "required_coverage": required_coverage,
            "canonical_source": str(raw.get("canonical_source_id") or ""),
            "derivative_type": str(raw.get("reference_class") or ""),
            "notes": str(raw.get("label") or ""),
            "reference_fingerprint": raw.get("reference_fingerprint"),
            "file_checksum": raw.get("file_checksum"),
            "width": raw.get("width"),
            "height": raw.get("height"),
            "vscs_priority": raw.get("priority"),
            "vscs_coverage": coverage_detail,
        }

    @classmethod
    def _refresh_manifest_fingerprint(cls, content: dict[str, Any]) -> None:
        manifest = content.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise LocalProductionPackageCompilationError(
                "Production Package has no VSCS compilation manifest"
            )
        payload = dict(content)
        payload.pop("_vscs_manifest", None)
        manifest["package_fingerprint"] = cls._fingerprint(payload)
        manifest["compiler"] = "VSCS Phase 20.18.2 / LTX-2.3 v7.2.1"


class LocalComfyUIProductionExecutionBackend(_Phase20182ProductionExecutionBackend):
    """Execute governed Production Packages through the approved LTX v7.2.1 workflow."""

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
        self.package_compilation = LocalLTX23V721ProductionPackageCompilationService(
            self.project_directory
        )

    @staticmethod
    def _workflow_root() -> Path:
        return Path(__file__).resolve().parents[4] / "resources" / "workflows"

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        task = self._require_task(task_id)
        issues = LTX23V721DeploymentAssurance(self._workflow_root()).inspect()
        if issues:
            raise ProductionExecutionError(
                "LTX-2.3 v7.2.1 production workflow assurance failed: " + "; ".join(issues)
            )
        try:
            return self.package_compilation.compile(task, profile=profile)
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def _workflow_foundation(self) -> ProductionPackageComfyUIAdapter:
        workflow_root = self._workflow_root()
        manifest_path = workflow_root / "manifests" / LTX23_V721_MANIFEST_FILE
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProductionExecutionError(
                f"Cannot load LTX-2.3 v7.2.1 workflow manifest: {exc}"
            ) from exc
        registry = WorkflowRegistry()
        registry.register(WorkflowManifest.from_dict(raw))
        return ProductionPackageComfyUIAdapter(
            registry,
            WorkflowCompatibilityValidator(),
            ComfyUIWorkflowCompiler(workflow_root),
            production_package_class_type=LTX23_V721_PACKAGE_LOADER_CLASS,
            production_package_title=LTX23_V721_PACKAGE_LOADER_TITLE,
        )

    def _render_request(self, task: ProductionTask) -> RenderRequest:
        request = super()._render_request(task)
        return replace(request, workflow_id=LTX23_V721_WORKFLOW_ID)
