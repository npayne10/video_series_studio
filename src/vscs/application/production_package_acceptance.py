"""Phase 19.4.11 Integration & Acceptance boundary for Production Planning.

This service is the read-only hand-off contract between the completed Phase 19.4
compiler/review pipeline and later provider execution.  It never submits provider
work and never invents or edits production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from vscs.application.production_package import ProductionPackageService
from vscs.application.production_package_review import (
    ProductionPackageReviewService,
    ReviewStatus,
)


class ProductionPackageAcceptanceError(RuntimeError):
    """Raised when a Production Package is requested before final acceptance."""


class AcceptanceStatus(StrEnum):
    """Final Phase 19.4 integration state."""

    ACCEPTED = "accepted"
    NOT_READY = "not-ready"


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    """One final integration/acceptance assertion."""

    code: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class ProductionPackageAcceptanceReport:
    """Read-only final hand-off report for one Shot/provider pair."""

    shot_id: str
    provider_id: str
    status: AcceptanceStatus
    package_id: str
    package_fingerprint: str
    checks: tuple[AcceptanceCheck, ...]

    @property
    def accepted(self) -> bool:
        return self.status is AcceptanceStatus.ACCEPTED


class ProductionPackageAcceptanceService:
    """Verify the complete Phase 19.4 chain before later provider execution."""

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
        packages: ProductionPackageService,
        reviews: ProductionPackageReviewService,
    ) -> None:
        self.packages = packages
        self.reviews = reviews

    def assess(
        self,
        shot_id: str,
        provider_id: str = "comfyui",
    ) -> ProductionPackageAcceptanceReport:
        """Assess final current authority without mutating or submitting anything."""
        shot = shot_id.strip().upper()
        provider = provider_id.strip().lower()
        checks: list[AcceptanceCheck] = []
        package = self.packages.current_package(shot)

        if package is None:
            checks.append(
                AcceptanceCheck(
                    "package.current",
                    False,
                    "A current Production Package is required.",
                )
            )
            return ProductionPackageAcceptanceReport(
                shot_id=shot,
                provider_id=provider,
                status=AcceptanceStatus.NOT_READY,
                package_id="",
                package_fingerprint="",
                checks=tuple(checks),
            )

        checks.append(
            AcceptanceCheck(
                "package.current",
                True,
                "Current Production Package resolved.",
            )
        )
        for key, label in self.REQUIRED_VALIDATION:
            passed = package.validation.get(key) is True
            checks.append(
                AcceptanceCheck(
                    f"authority.{key}",
                    passed,
                    f"{label} authority is {'complete' if passed else 'not complete'}.",
                )
            )

        provider_key = f"provider_{provider}_complete"
        provider_complete = package.validation.get(provider_key) is True
        checks.append(
            AcceptanceCheck(
                f"authority.{provider_key}",
                provider_complete,
                f"{provider.title()} Provider authority is "
                + ("complete." if provider_complete else "not complete."),
            )
        )

        output_record = package.provider_outputs.get(provider, {})
        output_record = output_record if isinstance(output_record, dict) else {}
        governed = output_record.get("governed", {})
        governed = governed if isinstance(governed, dict) else {}
        provider_ready = output_record.get("status") == "ready"
        checks.append(
            AcceptanceCheck(
                "provider.ready",
                provider_ready,
                "Provider output is approved Ready."
                if provider_ready
                else "Provider output is not approved Ready.",
            )
        )
        execution_safe = governed.get("execution") == "not-submitted"
        checks.append(
            AcceptanceCheck(
                "provider.not_submitted",
                execution_safe,
                "Provider execution remains not-submitted."
                if execution_safe
                else "Provider execution state is not safely held at not-submitted.",
            )
        )
        contract_present = bool(str(governed.get("contract", "")).strip())
        checks.append(
            AcceptanceCheck(
                "provider.contract",
                contract_present,
                "Provider contract identity is present."
                if contract_present
                else "Provider contract identity is missing.",
            )
        )

        universal_refs = self._reference_keys(
            self._production_view(package.universal_description).get(
                "canonical_references", []
            )
        )
        provider_refs = self._reference_keys(governed.get("canonical_references", []))
        references_match = universal_refs <= provider_refs
        checks.append(
            AcceptanceCheck(
                "canonical.provider_coverage",
                references_match,
                "Provider output covers all governed canonical references."
                if references_match
                else "Provider output is missing governed canonical references.",
            )
        )

        review = self.reviews.current_review(shot, provider)
        review_current = review is not None and review.status is not ReviewStatus.STALE
        checks.append(
            AcceptanceCheck(
                "review.current",
                review_current,
                "Final human review is current."
                if review_current
                else "Final human review is missing or stale.",
            )
        )
        human_approved = review is not None and review.status is ReviewStatus.APPROVED
        checks.append(
            AcceptanceCheck(
                "review.approved",
                human_approved,
                "Final human approval is recorded."
                if human_approved
                else "Final human approval is not recorded.",
            )
        )
        execution_authorized = self.reviews.execution_authorized(shot, provider)
        checks.append(
            AcceptanceCheck(
                "review.execution_authorized",
                execution_authorized,
                "Current human review authorizes later provider execution."
                if execution_authorized
                else "Current human review does not authorize provider execution.",
            )
        )

        accepted = all(check.passed for check in checks)
        return ProductionPackageAcceptanceReport(
            shot_id=shot,
            provider_id=provider,
            status=AcceptanceStatus.ACCEPTED if accepted else AcceptanceStatus.NOT_READY,
            package_id=package.package_id,
            package_fingerprint=package.package_fingerprint,
            checks=tuple(checks),
        )

    def require_accepted(
        self,
        shot_id: str,
        provider_id: str = "comfyui",
    ) -> ProductionPackageAcceptanceReport:
        """Return the final hand-off report or raise with all failed checks."""
        report = self.assess(shot_id, provider_id)
        if report.accepted:
            return report
        failed = "; ".join(check.message for check in report.checks if not check.passed)
        raise ProductionPackageAcceptanceError(
            f"Production Package {report.shot_id} is not accepted: {failed}"
        )

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
