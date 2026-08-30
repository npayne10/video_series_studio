"""LTX-2.3 Production Engine v7.2.1 integration for Phase 20.18.2."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from vscs.application.production_execution import (
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

from .package_compilation import LocalProductionPackageCompilationError
from .stale_reconciliation_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase20182ProductionExecutionBackend,
)

LTX23_V721_WORKFLOW_ID = "ltx23_production_v1"
LTX23_V721_WORKFLOW_FILE = "workflows/ltx23_production_v1_api.json"
LTX23_V721_MANIFEST_FILE = "ltx23_production_v1.json"
LTX23_V721_PACKAGE_LOADER_CLASS = "VSCSProductionPackageLoaderV720"
LTX23_V721_PACKAGE_LOADER_TITLE = "VSCS Production Package — Governed References v7.2.1"
LTX23_V721_REFERENCE_RESOLVER_CLASS = "VSCSReferenceResolverV720"
LTX23_V721_REFERENCE_RESOLVER_TITLE = "VSCS Governed Reference Resolver v7.2.0"


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
                    issues.append("v7.2.1 profile override must be sourced from the production package")
                if inputs.get("strict_validation") is not True:
                    issues.append("v7.2.1 production package loader strict validation must remain enabled")

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
                issues.append("v7.2.1 governed reference resolver strict validation must remain enabled")
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


class LocalComfyUIProductionExecutionBackend(_Phase20182ProductionExecutionBackend):
    """Execute governed Production Packages through the approved LTX v7.2.1 workflow."""

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
