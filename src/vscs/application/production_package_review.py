"""Phase 19.4.10 Production Package Review and Validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService
from vscs.application.provider_compiler import (
    ProviderCompilationStatus,
    ProviderCompilerFrameworkService,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionStatus,
)


class ReviewStatus(StrEnum):
    """Human-governed final production review lifecycle."""

    REVIEW_REQUIRED = "review-required"
    VALIDATION_FAILED = "validation-failed"
    APPROVED = "approved-for-production"
    CHANGES_REQUIRED = "changes-required"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One deterministic final production-readiness finding."""

    code: str
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class ProductionPackageReview:
    """Review snapshot persisted only after an explicit human decision."""

    shot_id: str
    provider_id: str
    status: ReviewStatus
    validation_passed: bool
    findings: tuple[ValidationFinding, ...]
    dependency_fingerprint: str
    canonical_reference_count: int
    asset_count: int
    provider_contract: str
    provider_execution: str
    reviewed_at: str
    reviewed_by: str = ""
    review_notes: str = ""


class ProductionPackageReviewService:
    """Final deterministic validation and explicit human production-approval gate."""

    REQUIRED_VALIDATION = (
        ("action_performance_complete", "Action & Performance"),
        ("assets_complete", "Assets"),
        ("camera_complete", "Camera"),
        ("lighting_complete", "Lighting"),
        ("continuity_complete", "Continuity"),
        ("style_complete", "Style"),
        ("universal_description_complete", "Universal Production Description"),
        ("cross_authority_consistent", "Cross-authority consistency"),
    )

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        universal: UniversalProductionDescriptionCompilerService,
        provider: ProviderCompilerFrameworkService,
    ) -> None:
        self.projects = projects
        self.packages = packages
        self.universal = universal
        self.provider = provider
        self._validated_fingerprints: dict[tuple[str, str], str] = {}

    def inspect(self, shot_id: str, provider_id: str = "comfyui") -> ProductionPackageReview:
        """Inspect current readiness without recording an explicit validation action."""
        shot = shot_id.strip().upper()
        selected_provider = provider_id.strip().lower()
        findings: list[ValidationFinding] = []
        package = self.packages.current_package(shot)
        universal = self.universal.draft(shot)
        provider = self.provider.draft(shot, selected_provider)

        if package is None:
            findings.append(
                ValidationFinding(
                    "package.missing",
                    "error",
                    "No current Production Package exists for this Shot.",
                )
            )
        else:
            for key, label in self.REQUIRED_VALIDATION:
                if package.validation.get(key) is not True:
                    findings.append(
                        ValidationFinding(
                            f"authority.{key}",
                            "error",
                            f"{label} authority is not complete in the current Production Package.",
                        )
                    )
            provider_key = f"provider_{selected_provider}_complete"
            if package.validation.get(provider_key) is not True:
                findings.append(
                    ValidationFinding(
                        f"authority.{provider_key}",
                        "error",
                        f"{selected_provider.title()} Provider authority is not complete in the current Production Package.",
                    )
                )

        if universal is None:
            findings.append(
                ValidationFinding(
                    "universal.missing",
                    "error",
                    "Universal Production Description does not exist.",
                )
            )
        elif universal.status is not UniversalProductionDescriptionStatus.READY:
            findings.append(
                ValidationFinding(
                    "universal.not_ready",
                    "error",
                    "Universal Production Description has not been approved Ready.",
                )
            )
        elif not self.universal.is_current(universal):
            findings.append(
                ValidationFinding(
                    "universal.stale",
                    "error",
                    "Universal Production Description is stale against current production authority.",
                )
            )

        consistency = self.universal.consistency_findings(shot)
        findings.extend(
            ValidationFinding("universal.consistency", "error", message)
            for message in consistency
        )

        output: dict[str, Any] = {}
        if provider is None:
            findings.append(
                ValidationFinding(
                    "provider.missing",
                    "error",
                    f"No {selected_provider.title()} Provider compilation exists.",
                )
            )
        else:
            output = provider.output_value()
            if provider.status is not ProviderCompilationStatus.READY:
                findings.append(
                    ValidationFinding(
                        "provider.not_ready",
                        "error",
                        "Provider output has not been approved Ready.",
                    )
                )
            elif not self.provider.is_current(provider):
                findings.append(
                    ValidationFinding(
                        "provider.stale",
                        "error",
                        "Provider output is stale against approved Universal authority.",
                    )
                )
            if output.get("provider_id") != selected_provider:
                findings.append(
                    ValidationFinding(
                        "provider.identity",
                        "error",
                        "Provider output identity does not match the selected provider.",
                    )
                )
            if not str(output.get("contract", "")).strip():
                findings.append(
                    ValidationFinding(
                        "provider.contract",
                        "error",
                        "Provider output has no contract identity.",
                    )
                )
            if output.get("execution") != "not-submitted":
                findings.append(
                    ValidationFinding(
                        "provider.execution",
                        "error",
                        "Provider execution must remain not-submitted until final human approval.",
                    )
                )

        production = self._production_view(
            package.universal_description if package is not None else {}
        )
        universal_references = self._reference_keys(
            production.get("canonical_references", [])
        )
        provider_references = self._reference_keys(
            output.get("canonical_references", [])
        )
        missing_references = sorted(universal_references - provider_references)
        if missing_references:
            findings.append(
                ValidationFinding(
                    "canonical.provider_coverage",
                    "error",
                    "Provider output is missing governed canonical reference coverage for: "
                    + ", ".join(missing_references),
                )
            )

        assets = production.get("assets", [])
        asset_count = len(assets) if isinstance(assets, list) else 0
        passed = not any(item.severity == "error" for item in findings)
        fingerprint = self._fingerprint(package, universal, provider)
        return ProductionPackageReview(
            shot_id=shot,
            provider_id=selected_provider,
            status=(
                ReviewStatus.REVIEW_REQUIRED
                if passed
                else ReviewStatus.VALIDATION_FAILED
            ),
            validation_passed=passed,
            findings=tuple(findings),
            dependency_fingerprint=fingerprint,
            canonical_reference_count=len(provider_references),
            asset_count=asset_count,
            provider_contract=str(output.get("contract", "")),
            provider_execution=str(output.get("execution", "")),
            reviewed_at=datetime.now(UTC).isoformat(),
        )

    def validate(
        self, shot_id: str, provider_id: str = "comfyui"
    ) -> ProductionPackageReview:
        """Explicitly validate current authority and record the validated fingerprint."""
        review = self.inspect(shot_id, provider_id)
        key = (review.shot_id, review.provider_id)
        if review.validation_passed:
            self._validated_fingerprints[key] = review.dependency_fingerprint
        else:
            self._validated_fingerprints.pop(key, None)
        return review

    def validation_confirmed(
        self, shot_id: str, provider_id: str = "comfyui"
    ) -> bool:
        """Return whether this exact current dependency set was explicitly validated."""
        review = self.inspect(shot_id, provider_id)
        key = (review.shot_id, review.provider_id)
        return (
            review.validation_passed
            and self._validated_fingerprints.get(key) == review.dependency_fingerprint
        )

    def approve(
        self,
        shot_id: str,
        *,
        reviewed_by: str,
        notes: str = "",
        provider_id: str = "comfyui",
    ) -> ProductionPackageReview:
        """Persist explicit human approval only after explicit current validation."""
        review = self.inspect(shot_id, provider_id)
        key = (review.shot_id, review.provider_id)
        if self._validated_fingerprints.get(key) != review.dependency_fingerprint:
            raise ValueError(
                "Validate Package must complete successfully before production approval."
            )
        reviewer = reviewed_by.strip()
        if not review.validation_passed:
            raise ValueError(
                "Production Package cannot be approved while validation errors remain."
            )
        if not reviewer:
            raise ValueError(
                "Human reviewer identity is required for production approval."
            )
        approved = replace(
            review,
            status=ReviewStatus.APPROVED,
            reviewed_by=reviewer,
            review_notes=notes.strip(),
            reviewed_at=datetime.now(UTC).isoformat(),
        )
        self._write(approved)
        return approved

    def require_changes(
        self,
        shot_id: str,
        *,
        reviewed_by: str,
        notes: str,
        provider_id: str = "comfyui",
    ) -> ProductionPackageReview:
        """Persist an explicit human request for upstream production changes."""
        reviewer = reviewed_by.strip()
        review_notes = notes.strip()
        if not reviewer:
            raise ValueError(
                "Human reviewer identity is required to request changes."
            )
        if not review_notes:
            raise ValueError("Review notes are required when requesting changes.")
        review = self.inspect(shot_id, provider_id)
        self._validated_fingerprints.pop((review.shot_id, review.provider_id), None)
        changed = replace(
            review,
            status=ReviewStatus.CHANGES_REQUIRED,
            reviewed_by=reviewer,
            review_notes=review_notes,
            reviewed_at=datetime.now(UTC).isoformat(),
        )
        self._write(changed)
        return changed

    def current_review(
        self, shot_id: str, provider_id: str = "comfyui"
    ) -> ProductionPackageReview | None:
        """Return persisted human decision, marking it stale if authority changed."""
        path = self._path(shot_id, provider_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            findings = tuple(
                ValidationFinding(**item) for item in raw.pop("findings", [])
            )
            raw["status"] = ReviewStatus(str(raw["status"]))
            review = ProductionPackageReview(findings=findings, **raw)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Unable to load Production Package review: {exc}"
            ) from exc
        fresh = self.inspect(shot_id, provider_id)
        if review.dependency_fingerprint == fresh.dependency_fingerprint:
            return review
        self._validated_fingerprints.pop((fresh.shot_id, fresh.provider_id), None)
        return replace(
            review,
            status=ReviewStatus.STALE,
            validation_passed=False,
        )

    def execution_authorized(
        self, shot_id: str, provider_id: str = "comfyui"
    ) -> bool:
        """Return whether current provider execution has final human authorization."""
        review = self.current_review(shot_id, provider_id)
        return review is not None and review.status is ReviewStatus.APPROVED

    @staticmethod
    def _production_view(value: dict[str, Any]) -> dict[str, Any]:
        production = value.get("production")
        if isinstance(production, dict):
            return dict(production)
        governed = value.get("governed")
        if isinstance(governed, dict):
            return dict(governed)
        return dict(value)

    @staticmethod
    def _reference_keys(value: Any) -> set[str]:
        if not isinstance(value, list):
            return set()
        keys: set[str] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id", "")).strip()
            reference = str(item.get("canonical_reference", "")).strip()
            if asset_id and reference:
                keys.add(asset_id)
        return keys

    @staticmethod
    def _fingerprint(package: Any, universal: Any, provider: Any) -> str:
        payload = {
            "package_fingerprint": getattr(package, "package_fingerprint", ""),
            "universal_dependency": getattr(universal, "dependency_fingerprint", ""),
            "universal_status": str(getattr(universal, "status", "")),
            "provider_dependency": getattr(provider, "dependency_fingerprint", ""),
            "provider_status": str(getattr(provider, "status", "")),
            "provider_output": (
                provider.output_value() if provider is not None else {}
            ),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _path(self, shot_id: str, provider_id: str) -> Path:
        root = self.projects.project_directory
        if root is None:
            raise RuntimeError(
                "A project must be open before reviewing a Production Package."
            )
        directory = root / "production" / "reviews"
        directory.mkdir(parents=True, exist_ok=True)
        name = (
            f"{shot_id.strip().upper()}--{provider_id.strip().lower()}.review.json"
        )
        return directory / name

    def _write(self, review: ProductionPackageReview) -> None:
        path = self._path(review.shot_id, review.provider_id)
        temporary = path.with_suffix(path.suffix + ".tmp")
        payload = asdict(review)
        payload["status"] = review.status.value
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
