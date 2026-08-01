"""Versioned validation and serialization for complete ACPP production bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .models import ClipProductionPackage, RenderQualityMode, SeedPolicy
from .prompt_compiler import CompiledProductionPrompt, CompiledPromptSection
from .render_jobs import RenderCapability, RenderInputReference, RenderJob, RetryPolicy
from .resolution import (
    ACPPResolutionResult,
    ResolutionDiagnostic,
    ResolutionProvenance,
    ResolutionSeverity,
)
from .serialization import ACPPSerializationError, ACPPSerializer


class BundleValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class BundleValidationIssue:
    severity: BundleValidationSeverity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class BundleValidationResult:
    issues: tuple[BundleValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(
            issue.severity is BundleValidationSeverity.ERROR
            for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class ProductionBundle:
    package: ClipProductionPackage
    resolution: ACPPResolutionResult
    prompt: CompiledProductionPrompt
    render_job: RenderJob
    package_checksum: str
    prompt_checksum: str
    render_job_checksum: str
    aggregate_checksum: str
    schema_version: str = "1.0"
    metadata: dict[str, str] = field(default_factory=dict)


class ProductionBundleValidationError(ValueError):
    def __init__(self, result: BundleValidationResult) -> None:
        self.result = result
        summary = "; ".join(issue.message for issue in result.issues)
        super().__init__(summary or "Production bundle validation failed")


class ProductionBundleValidator:
    def __init__(self, package_serializer: ACPPSerializer | None = None) -> None:
        self.package_serializer = package_serializer or ACPPSerializer()

    def validate(self, bundle: ProductionBundle) -> BundleValidationResult:
        issues: list[BundleValidationIssue] = []
        clip_id = bundle.package.identity.clip_id
        identities = {
            bundle.resolution.package.identity.clip_id,
            bundle.prompt.clip_id,
            bundle.render_job.clip_id,
        }
        if identities != {clip_id}:
            self._error(issues, "CLIP_ID_MISMATCH", "All bundle clip IDs must match.")
        if bundle.resolution.package != bundle.package:
            self._error(
                issues,
                "RESOLVED_PACKAGE_MISMATCH",
                "Resolution result does not contain the bundle package.",
            )
        if not bundle.resolution.passed:
            self._error(
                issues,
                "RESOURCE_RESOLUTION_FAILED",
                "Production bundles require successful resource resolution.",
            )
        expected_package = self.package_serializer.checksum(bundle.package)
        if bundle.package_checksum != expected_package:
            self._error(
                issues,
                "PACKAGE_CHECKSUM_MISMATCH",
                "Stored package checksum does not match package content.",
            )
        if bundle.prompt_checksum != bundle.prompt.checksum:
            self._error(
                issues,
                "PROMPT_CHECKSUM_MISMATCH",
                "Stored prompt checksum does not match the compiled prompt.",
            )
        if bundle.render_job.package_checksum != bundle.package_checksum:
            self._error(
                issues,
                "RENDER_PACKAGE_CHECKSUM_MISMATCH",
                "Render job references a different package checksum.",
            )
        if bundle.render_job.prompt_checksum != bundle.prompt_checksum:
            self._error(
                issues,
                "RENDER_PROMPT_CHECKSUM_MISMATCH",
                "Render job references a different prompt checksum.",
            )
        dependencies = bundle.render_job.dependencies
        if bundle.render_job.clip_id in dependencies:
            self._error(
                issues,
                "SELF_DEPENDENCY",
                "Render job may not depend on its own clip.",
            )
        if len(set(dependencies)) != len(dependencies):
            self._error(
                issues,
                "DUPLICATE_DEPENDENCY",
                "Render-job dependencies must be unique.",
            )
        if dependencies != bundle.package.dependencies:
            self._error(
                issues,
                "DEPENDENCY_MISMATCH",
                "Render-job dependencies must match ACPP dependencies.",
            )
        expected_aggregate = ProductionBundleSerializer.aggregate_checksum(
            bundle.package_checksum,
            bundle.prompt_checksum,
            bundle.render_job_checksum,
            bundle.schema_version,
        )
        if bundle.aggregate_checksum != expected_aggregate:
            self._error(
                issues,
                "AGGREGATE_CHECKSUM_MISMATCH",
                "Aggregate checksum does not match component checksums.",
            )
        return BundleValidationResult(tuple(issues))

    @staticmethod
    def _error(
        issues: list[BundleValidationIssue], code: str, message: str
    ) -> None:
        issues.append(
            BundleValidationIssue(BundleValidationSeverity.ERROR, code, message)
        )


class ProductionBundleSerializer:
    def __init__(self, package_serializer: ACPPSerializer | None = None) -> None:
        self.package_serializer = package_serializer or ACPPSerializer()
        self.validator = ProductionBundleValidator(self.package_serializer)

    def build(
        self,
        resolution: ACPPResolutionResult,
        prompt: CompiledProductionPrompt,
        render_job: RenderJob,
        *,
        render_job_checksum: str,
        schema_version: str = "1.0",
        metadata: dict[str, str] | None = None,
    ) -> ProductionBundle:
        package_checksum = self.package_serializer.checksum(resolution.package)
        aggregate = self.aggregate_checksum(
            package_checksum,
            prompt.checksum,
            render_job_checksum,
            schema_version,
        )
        bundle = ProductionBundle(
            package=resolution.package,
            resolution=resolution,
            prompt=prompt,
            render_job=render_job,
            package_checksum=package_checksum,
            prompt_checksum=prompt.checksum,
            render_job_checksum=render_job_checksum,
            aggregate_checksum=aggregate,
            schema_version=schema_version,
            metadata={} if metadata is None else dict(metadata),
        )
        self._require_valid(bundle)
        return bundle

    def dumps(self, bundle: ProductionBundle) -> str:
        self._require_valid(bundle)
        return json.dumps(
            self.to_dict(bundle), indent=2, sort_keys=True, ensure_ascii=False
        ) + "\n"

    def loads(self, payload: str) -> ProductionBundle:
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ACPPSerializationError(f"Invalid production bundle JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ACPPSerializationError("Production bundle JSON root must be an object")
        try:
            bundle = self.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise ACPPSerializationError(f"Invalid production bundle payload: {exc}") from exc
        self._require_valid(bundle)
        return bundle

    def to_dict(self, bundle: ProductionBundle) -> dict[str, Any]:
        return {
            "schema_version": bundle.schema_version,
            "package": self.package_serializer.to_dict(bundle.package),
            "resolution": self._resolution_to_dict(bundle.resolution),
            "prompt": self._prompt_to_dict(bundle.prompt),
            "render_job": self._render_job_to_dict(bundle.render_job),
            "checksums": {
                "package": bundle.package_checksum,
                "prompt": bundle.prompt_checksum,
                "render_job": bundle.render_job_checksum,
                "aggregate": bundle.aggregate_checksum,
            },
            "metadata": dict(bundle.metadata),
        }

    def from_dict(self, raw: dict[str, Any]) -> ProductionBundle:
        package = self.package_serializer.from_dict(raw["package"])
        checksums = raw["checksums"]
        return ProductionBundle(
            package=package,
            resolution=self._resolution_from_dict(raw["resolution"], package),
            prompt=self._prompt_from_dict(raw["prompt"]),
            render_job=self._render_job_from_dict(raw["render_job"]),
            package_checksum=str(checksums["package"]),
            prompt_checksum=str(checksums["prompt"]),
            render_job_checksum=str(checksums["render_job"]),
            aggregate_checksum=str(checksums["aggregate"]),
            schema_version=str(raw.get("schema_version", "1.0")),
            metadata={
                str(key): str(value)
                for key, value in raw.get("metadata", {}).items()
            },
        )

    def report(self, bundle: ProductionBundle) -> str:
        validation = self.validator.validate(bundle)
        status = "PASSED" if validation.passed else "FAILED"
        lines = [
            f"Production Bundle: {bundle.package.identity.clip_id}",
            f"Status: {status}",
            f"Schema: {bundle.schema_version}",
            f"Output: {bundle.render_job.output_path}",
            f"Dependencies: {len(bundle.render_job.dependencies)}",
            f"References: {len(bundle.render_job.input_references)}",
            f"Capabilities: {len(bundle.render_job.required_capabilities)}",
            f"Aggregate checksum: {bundle.aggregate_checksum}",
        ]
        lines.extend(
            f"{issue.severity.value.upper()} {issue.code}: {issue.message}"
            for issue in validation.issues
        )
        return "\n".join(lines)

    @staticmethod
    def aggregate_checksum(
        package_checksum: str,
        prompt_checksum: str,
        render_job_checksum: str,
        schema_version: str,
    ) -> str:
        payload = "|".join(
            (schema_version, package_checksum, prompt_checksum, render_job_checksum)
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _require_valid(self, bundle: ProductionBundle) -> None:
        result = self.validator.validate(bundle)
        if not result.passed:
            raise ProductionBundleValidationError(result)

    @staticmethod
    def _resolution_to_dict(result: ACPPResolutionResult) -> dict[str, Any]:
        return {
            "diagnostics": [
                {
                    "severity": item.severity.value,
                    "code": item.code,
                    "message": item.message,
                    "resource_id": item.resource_id,
                }
                for item in result.diagnostics
            ],
            "provenance": _provenance_to_dict(result.provenance),
            "resolved_dependencies": list(result.resolved_dependencies),
        }

    @staticmethod
    def _resolution_from_dict(
        raw: dict[str, Any], package: ClipProductionPackage
    ) -> ACPPResolutionResult:
        return ACPPResolutionResult(
            package=package,
            diagnostics=tuple(
                ResolutionDiagnostic(
                    severity=ResolutionSeverity(str(item["severity"])),
                    code=str(item["code"]),
                    message=str(item["message"]),
                    resource_id=str(item["resource_id"]),
                )
                for item in raw.get("diagnostics", [])
            ),
            provenance=_provenance_from_dict(raw.get("provenance", [])),
            resolved_dependencies=tuple(
                str(value) for value in raw.get("resolved_dependencies", [])
            ),
        )

    @staticmethod
    def _prompt_to_dict(prompt: CompiledProductionPrompt) -> dict[str, Any]:
        return {
            "clip_id": prompt.clip_id,
            "schema_version": prompt.schema_version,
            "positive_prompt": prompt.positive_prompt,
            "negative_prompt": prompt.negative_prompt,
            "sections": [
                {"name": section.name, "content": section.content}
                for section in prompt.sections
            ],
            "canonical_reference_ids": list(prompt.canonical_reference_ids),
            "prompt_package_ids": list(prompt.prompt_package_ids),
            "start_reference_id": prompt.start_reference_id,
            "end_reference_id": prompt.end_reference_id,
            "provenance": _provenance_to_dict(prompt.provenance),
            "checksum": prompt.checksum,
        }

    @staticmethod
    def _prompt_from_dict(raw: dict[str, Any]) -> CompiledProductionPrompt:
        return CompiledProductionPrompt(
            clip_id=str(raw["clip_id"]),
            schema_version=str(raw["schema_version"]),
            positive_prompt=str(raw["positive_prompt"]),
            negative_prompt=str(raw["negative_prompt"]),
            sections=tuple(
                CompiledPromptSection(str(item["name"]), str(item["content"]))
                for item in raw.get("sections", [])
            ),
            canonical_reference_ids=tuple(
                str(value) for value in raw.get("canonical_reference_ids", [])
            ),
            prompt_package_ids=tuple(
                str(value) for value in raw.get("prompt_package_ids", [])
            ),
            start_reference_id=_optional_text(raw.get("start_reference_id")),
            end_reference_id=_optional_text(raw.get("end_reference_id")),
            provenance=_provenance_from_dict(raw.get("provenance", [])),
            checksum=str(raw["checksum"]),
        )

    @staticmethod
    def _render_job_to_dict(job: RenderJob) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "clip_id": job.clip_id,
            "width": job.width,
            "height": job.height,
            "frames_per_second": job.frames_per_second,
            "frame_count": job.frame_count,
            "quality_mode": job.quality_mode.value,
            "seed_policy": job.seed_policy.value,
            "fixed_seed": job.fixed_seed,
            "positive_prompt": job.positive_prompt,
            "negative_prompt": job.negative_prompt,
            "input_references": [
                {"reference_id": item.reference_id, "role": item.role}
                for item in job.input_references
            ],
            "start_reference_id": job.start_reference_id,
            "end_reference_id": job.end_reference_id,
            "output_path": job.output_path,
            "dependencies": list(job.dependencies),
            "retry_policy": {
                "maximum_attempts": job.retry_policy.maximum_attempts,
                "backoff_seconds": job.retry_policy.backoff_seconds,
                "retry_on_timeout": job.retry_policy.retry_on_timeout,
                "retry_on_provider_error": job.retry_policy.retry_on_provider_error,
            },
            "required_capabilities": [
                item.value for item in job.required_capabilities
            ],
            "package_checksum": job.package_checksum,
            "prompt_checksum": job.prompt_checksum,
            "schema_version": job.schema_version,
            "metadata": [list(item) for item in job.metadata],
        }

    @staticmethod
    def _render_job_from_dict(raw: dict[str, Any]) -> RenderJob:
        retry = raw["retry_policy"]
        return RenderJob(
            job_id=str(raw["job_id"]),
            clip_id=str(raw["clip_id"]),
            width=int(raw["width"]),
            height=int(raw["height"]),
            frames_per_second=int(raw["frames_per_second"]),
            frame_count=int(raw["frame_count"]),
            quality_mode=RenderQualityMode(str(raw["quality_mode"])),
            seed_policy=SeedPolicy(str(raw["seed_policy"])),
            fixed_seed=(
                None if raw.get("fixed_seed") is None else int(raw["fixed_seed"])
            ),
            positive_prompt=str(raw["positive_prompt"]),
            negative_prompt=str(raw["negative_prompt"]),
            input_references=tuple(
                RenderInputReference(str(item["reference_id"]), str(item["role"]))
                for item in raw.get("input_references", [])
            ),
            start_reference_id=_optional_text(raw.get("start_reference_id")),
            end_reference_id=_optional_text(raw.get("end_reference_id")),
            output_path=str(raw["output_path"]),
            dependencies=tuple(
                str(value) for value in raw.get("dependencies", [])
            ),
            retry_policy=RetryPolicy(
                maximum_attempts=int(retry["maximum_attempts"]),
                backoff_seconds=float(retry["backoff_seconds"]),
                retry_on_timeout=bool(retry["retry_on_timeout"]),
                retry_on_provider_error=bool(retry["retry_on_provider_error"]),
            ),
            required_capabilities=tuple(
                RenderCapability(str(value))
                for value in raw.get("required_capabilities", [])
            ),
            package_checksum=str(raw["package_checksum"]),
            prompt_checksum=str(raw["prompt_checksum"]),
            schema_version=str(raw.get("schema_version", "1.0")),
            metadata=tuple(
                (str(item[0]), str(item[1]))
                for item in raw.get("metadata", [])
            ),
        )


def _provenance_to_dict(
    provenance: tuple[ResolutionProvenance, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "resource_id": item.resource_id,
            "resource_type": item.resource_type,
            "version": item.version,
            "source": item.source,
            "checksum": item.checksum,
            "related_ids": list(item.related_ids),
        }
        for item in provenance
    ]


def _provenance_from_dict(
    values: list[dict[str, Any]],
) -> tuple[ResolutionProvenance, ...]:
    return tuple(
        ResolutionProvenance(
            resource_id=str(item["resource_id"]),
            resource_type=str(item["resource_type"]),
            version=str(item["version"]),
            source=str(item["source"]),
            checksum=(
                None if item.get("checksum") is None else str(item["checksum"])
            ),
            related_ids=tuple(
                str(value) for value in item.get("related_ids", [])
            ),
        )
        for item in values
    )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
