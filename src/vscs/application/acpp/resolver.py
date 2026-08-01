"""Resolve ACPP asset, CAP, canonical-reference, and behaviour dependencies."""

from __future__ import annotations

from dataclasses import replace

from .models import AssetBinding, ClipProductionPackage
from .resolution import (
    ACPPResolutionResult,
    ACPPResolverConfig,
    AssetResolutionCatalog,
    AssetResolutionRecord,
    BehaviourResolutionCatalog,
    BehaviourResolutionRecord,
    ResolutionDiagnostic,
    ResolutionProvenance,
    ResolutionSeverity,
)


class ACPPResolutionError(ValueError):
    """Raised when strict resource resolution fails."""

    def __init__(self, result: ACPPResolutionResult) -> None:
        self.result = result
        errors = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.severity is ResolutionSeverity.ERROR
        ]
        super().__init__("; ".join(errors) or "ACPP resource resolution failed")


class ACPPResourceResolver:
    """Resolve generic ACPP bindings into approved production resources."""

    def __init__(
        self,
        assets: AssetResolutionCatalog,
        behaviours: BehaviourResolutionCatalog,
        config: ACPPResolverConfig | None = None,
    ) -> None:
        self.assets = assets
        self.behaviours = behaviours
        self.config = config or ACPPResolverConfig()

    def resolve(
        self,
        package: ClipProductionPackage,
        *,
        raise_on_error: bool = False,
    ) -> ACPPResolutionResult:
        """Resolve all asset and behaviour bindings for one clip package."""
        diagnostics: list[ResolutionDiagnostic] = []
        provenance: list[ResolutionProvenance] = []
        resolved_dependencies: list[str] = list(package.dependencies)
        resolved_bindings: list[AssetBinding] = []

        for binding in package.assets:
            record = self.assets.resolve_asset(binding.asset_id)
            if record is None:
                diagnostics.append(
                    self._diagnostic(
                        binding,
                        "ASSET_NOT_RESOLVED",
                        f"No CAP resolution record exists for asset '{binding.asset_id}'.",
                    )
                )
                resolved_bindings.append(binding)
                continue

            reference_ids = self._resolve_asset_record(
                binding,
                record,
                diagnostics,
                provenance,
            )
            behaviour_ids = self._resolve_behaviours(
                binding,
                diagnostics,
                provenance,
                resolved_dependencies,
            )
            resolved_bindings.append(
                replace(
                    binding,
                    canonical_reference_ids=reference_ids,
                    behaviour_package_ids=behaviour_ids,
                )
            )

        metadata = dict(package.metadata)
        prefix = self.config.metadata_prefix
        metadata[f"{prefix}.status"] = "resolved" if not any(
            item.severity is ResolutionSeverity.ERROR for item in diagnostics
        ) else "failed"
        metadata[f"{prefix}.asset_count"] = str(len(resolved_bindings))
        metadata[f"{prefix}.provenance_count"] = str(len(provenance))

        resolved_package = replace(
            package,
            assets=tuple(resolved_bindings),
            dependencies=tuple(dict.fromkeys(resolved_dependencies)),
            metadata=metadata,
        )
        result = ACPPResolutionResult(
            package=resolved_package,
            diagnostics=tuple(diagnostics),
            provenance=tuple(provenance),
            resolved_dependencies=tuple(dict.fromkeys(resolved_dependencies)),
        )
        if raise_on_error and not result.passed:
            raise ACPPResolutionError(result)
        return result

    def _resolve_asset_record(
        self,
        binding: AssetBinding,
        record: AssetResolutionRecord,
        diagnostics: list[ResolutionDiagnostic],
        provenance: list[ResolutionProvenance],
    ) -> tuple[str, ...]:
        if self.config.require_approved_caps and not record.cap_approved:
            diagnostics.append(
                self._diagnostic(
                    binding,
                    "CAP_NOT_APPROVED",
                    f"CAP '{record.cap_id}' for asset '{binding.asset_id}' is not approved.",
                )
            )

        approved = tuple(
            reference
            for reference in record.canonical_references
            if reference.approved and reference.locked
        )
        if self.config.require_approved_references and not approved:
            diagnostics.append(
                self._diagnostic(
                    binding,
                    "APPROVED_REFERENCE_MISSING",
                    f"Asset '{binding.asset_id}' has no approved locked canonical reference.",
                )
            )

        primary = tuple(
            reference for reference in approved if reference.role.casefold() == "primary"
        )
        if self.config.require_primary_reference and approved and not primary:
            diagnostics.append(
                self._diagnostic(
                    binding,
                    "PRIMARY_REFERENCE_MISSING",
                    f"Asset '{binding.asset_id}' has no approved primary canonical reference.",
                )
            )

        selected = approved if self.config.include_secondary_references else primary
        reference_ids = tuple(
            dict.fromkeys(
                (*binding.canonical_reference_ids, *(item.reference_id for item in selected))
            )
        )
        provenance.append(
            ResolutionProvenance(
                resource_id=record.cap_id,
                resource_type="cap",
                version=record.cap_version,
                source="asset_catalog",
                checksum=record.checksum,
                related_ids=reference_ids,
            )
        )
        provenance.extend(
            ResolutionProvenance(
                resource_id=reference.reference_id,
                resource_type="canonical_reference",
                version="1",
                source=reference.path,
                checksum=reference.checksum,
                related_ids=(binding.asset_id,),
            )
            for reference in selected
        )
        return reference_ids

    def _resolve_behaviours(
        self,
        binding: AssetBinding,
        diagnostics: list[ResolutionDiagnostic],
        provenance: list[ResolutionProvenance],
        resolved_dependencies: list[str],
    ) -> tuple[str, ...]:
        resolved_ids: list[str] = []
        for package_id in binding.behaviour_package_ids:
            record = self.behaviours.resolve_behaviour(package_id)
            if record is None:
                diagnostics.append(
                    self._diagnostic(
                        binding,
                        "BEHAVIOUR_NOT_RESOLVED",
                        f"Behaviour package '{package_id}' could not be resolved.",
                    )
                )
                continue
            self._record_behaviour(
                binding,
                record,
                diagnostics,
                provenance,
                resolved_dependencies,
            )
            resolved_ids.append(record.package_id)
        return tuple(dict.fromkeys(resolved_ids))

    def _record_behaviour(
        self,
        binding: AssetBinding,
        record: BehaviourResolutionRecord,
        diagnostics: list[ResolutionDiagnostic],
        provenance: list[ResolutionProvenance],
        resolved_dependencies: list[str],
    ) -> None:
        if self.config.require_valid_behaviours and not record.structurally_valid:
            diagnostics.append(
                self._diagnostic(
                    binding,
                    "BEHAVIOUR_INVALID",
                    f"Behaviour package '{record.package_id}' is structurally invalid.",
                )
            )
        provenance.append(
            ResolutionProvenance(
                resource_id=record.package_id,
                resource_type="behaviour_package",
                version=record.version,
                source=record.manifest_path,
                checksum=record.checksum,
                related_ids=record.prompt_package_ids,
            )
        )
        provenance.extend(
            ResolutionProvenance(
                resource_id=prompt_id,
                resource_type="prompt_package",
                version=record.version,
                source=record.manifest_path,
                related_ids=(record.package_id,),
            )
            for prompt_id in record.prompt_package_ids
        )
        resolved_dependencies.extend(record.dependency_ids)

    @staticmethod
    def _diagnostic(
        binding: AssetBinding,
        code: str,
        message: str,
    ) -> ResolutionDiagnostic:
        severity = (
            ResolutionSeverity.ERROR if binding.required else ResolutionSeverity.WARNING
        )
        return ResolutionDiagnostic(
            severity=severity,
            code=code,
            message=message,
            resource_id=binding.asset_id,
        )
