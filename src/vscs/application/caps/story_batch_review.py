"""Review-gated CAP creation from project Shot asset requirements and approved Story."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.cross_asset_continuity import validate_dependencies
from vscs.application.caps.design_completion import DesignReviewPackage, DesignReviewPersistence
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.story_batch import StoryBatchError, StoryCAPBatchService
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.caps import CAPCreate, CAPStatus


@dataclass(frozen=True)
class CAPAssetCandidate:
    """Registered asset referenced by a persisted Shot binding."""

    asset_id: str
    name: str
    category: str
    has_cap: bool
    has_specification: bool


class StoryCAPBatchReviewService:
    """Discover without writes; commit only individual explicitly reviewed records."""

    def __init__(self, batch: StoryCAPBatchService) -> None:
        self.batch = batch

    def discover(self) -> tuple[CAPAssetCandidate, ...]:
        assets = self.batch.generator.generator.assets
        root: Path | None = assets.projects.project_directory
        if root is None or not assets.projects.is_project_open:
            raise StoryBatchError("Open a project before discovering asset requirements")
        ledger = root / "planning" / "asset_resolutions.json"
        if not ledger.is_file():
            return ()
        try:
            raw = json.loads(ledger.read_text(encoding="utf-8"))
            bindings = raw["bindings"]
            if not isinstance(bindings, list):
                raise ValueError("Bindings must be a list")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise StoryBatchError("Shot asset-resolution ledger is invalid") from exc
        registered = {asset.asset_id: asset for asset in assets.list()}
        by_id: dict[str, CAPAssetCandidate] = {}
        for binding in bindings:
            if not isinstance(binding, dict):
                raise StoryBatchError("Invalid binding entry")
            asset_id = str(binding.get("asset_id", "")).strip().upper()
            if not asset_id or asset_id in by_id or asset_id not in registered:
                continue
            asset = registered[asset_id]
            expected = str(binding.get("expected_category", "")).strip().lower()
            if expected and expected != asset.category.value:
                raise StoryBatchError(f"{asset_id}: binding category does not match asset")
            caps = self.batch.generator.specifications.caps
            try:
                cap = caps.get(asset_id)
            except Exception as exc:
                from vscs.application.caps.service import CAPNotFoundError

                if not isinstance(exc, CAPNotFoundError):
                    raise
                cap = None
            specification = (
                self.batch.generator.specifications.get(asset_id) if cap is not None else None
            )
            by_id[asset_id] = CAPAssetCandidate(
                asset_id,
                asset.name,
                asset.category.value,
                cap is not None,
                specification is not None,
            )
        return tuple(by_id.values())

    def validate_reviewed_dependencies(
        self, specification: CAPStructuredSpecification
    ) -> tuple[str, ...]:
        """Local preflight for operator-entered relationships, never paid AI."""
        if not specification.dependency_asset_ids and not specification.dependency_constraints:
            return ()
        caps = self.batch.generator.specifications.caps
        findings = validate_dependencies(
            specification,
            specification.dependency_constraints,
            caps.assets,
            self.batch.generator.specifications,
        )
        blockers = {
            "duplicate_relation",
            "unresolved_dependency",
            "self_dependency",
            "undeclared_dependency",
            "missing_asset",
            "invalid_container",
            "invalid_location",
            "target_category_mismatch",
            "out_of_bounds",
            "frame_mismatch",
        }
        errors = [item for item in findings if item.code in blockers]
        if errors:
            raise StoryBatchError(
                "CAP dependency validation failed: "
                + "; ".join(f"{item.target_asset_id}: {item.message}" for item in errors)
            )
        return tuple(
            f"{item.target_asset_id}: {item.message}"
            for item in findings
            if item.code not in blockers
        )

    def save_reviewed(
        self,
        story_id: str,
        specification: CAPStructuredSpecification,
        approved_fingerprint: str,
        review: DesignReviewPackage | None = None,
    ) -> None:
        """Recheck Story authority and current asset/CAP state before persistence."""
        # Revalidate directly from persisted Story, never regenerate a paid AI proposal.
        current_fingerprint = self.batch.current_story_fingerprint(story_id)
        if current_fingerprint != approved_fingerprint:
            raise StoryBatchError("Story changed after proposal; review a new draft")
        try:
            existing_spec = self.batch.generator.specifications.get(specification.asset_id)
        except CAPNotFoundError:
            existing_spec = None
        if existing_spec is not None:
            raise StoryBatchError("A structured CAP already exists; revision review is required")
        caps = self.batch.generator.specifications.caps
        self.validate_reviewed_dependencies(specification)
        asset = caps.assets.get(specification.asset_id)
        if asset.category != specification.category:
            raise StoryBatchError("Asset category changed during review")
        created = False
        try:
            cap = caps.get(specification.asset_id)
        except CAPNotFoundError:
            cap = None
        if cap is None:
            caps.create(
                CAPCreate(
                    asset_id=asset.asset_id,
                    title=asset.name,
                    canonical_description=specification.design_intent,
                    status=CAPStatus.DRAFT,
                )
            )
            created = True
        elif cap.status != CAPStatus.DRAFT:
            raise StoryBatchError("Existing CAP is not Draft")
        try:
            if review is None:
                self.batch.generator.save_reviewed(specification)
            else:
                DesignReviewPersistence(self.batch.generator.specifications).save(
                    specification, review
                )
        except Exception:
            # Avoid destructive rollback of any preexisting CAP. Newly created
            # Draft CAP is removed only if it still has no structured specification.
            if created and self.batch.generator.specifications.get(asset.asset_id) is None:
                caps.delete(asset.asset_id)
            raise
