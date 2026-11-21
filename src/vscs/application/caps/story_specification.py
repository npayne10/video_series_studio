"""Governed Story-to-CAP specification proposals using existing CAP generation.

A provider-generated proposal is advisory, not Story Canon or CAP approval.
The operator must review suggested identity and variants before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from vscs.application.caps.category_identity import category_identity_issues
from vscs.application.caps.context_preparation import CAPContextManifest
from vscs.application.caps.design_quality import (
    DesignQualityIssue,
    assess_design_grounding,
    assess_design_quality,
)
from vscs.application.caps.detail_expansion import CanonicalDetailExpansion, expand_details
from vscs.application.caps.generator import CAPGeneratorService
from vscs.application.caps.provider_design_expansion import (
    CAPDesignExpansionProvider,
    ProposedDesignField,
    validate_design_expansion,
)
from vscs.application.caps.story_field_grounding import (
    CAPFieldOrigin,
    CAPFieldProvenance,
    reconcile_grounded_fields,
)
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    CAPStructuredSpecificationService,
)
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.domain.caps.generation import CAPGenerationRequest, GeneratedCAPDraft
from vscs.infrastructure.ai.provider import CAPGenerationProvider

_CATEGORY_KEYS: dict[AssetCategory, str] = {
    AssetCategory.CHARACTER: "anatomy",
    AssetCategory.LOCATION: "architecture",
    AssetCategory.SHIP: "silhouette",
    AssetCategory.VEHICLE: "silhouette",
    AssetCategory.PROP: "geometry",
    AssetCategory.TECHNOLOGY: "geometry",
    AssetCategory.ENVIRONMENT: "geography",
    AssetCategory.PLANET: "geography",
    AssetCategory.UNIFORM: "materials",
}


@dataclass(frozen=True)
class StoryCAPProposal:
    """Read-only specification and unverified assumptions to review."""

    specification: CAPStructuredSpecification
    suggested_attribute_key: str
    limitations: tuple[str, ...]
    detail_expansion: CanonicalDetailExpansion | None = None
    design_suggestions: tuple[ProposedDesignField, ...] = ()
    quality_issues: tuple[DesignQualityIssue, ...] = ()
    field_provenance: tuple[CAPFieldProvenance, ...] = ()

    def ground_against_story(self, asset: Asset, context: CAPContextManifest) -> StoryCAPProposal:
        """Offline Story field mapping; preserve cached human edits verbatim."""
        proposed, evidence, findings = reconcile_grounded_fields(
            self.specification, asset.name, context, self.design_suggestions
        )
        existing = {item.field: item for item in self.field_provenance}
        evidence = tuple(
            existing[item.field]
            if item.field in existing
            and existing[item.field].origin is CAPFieldOrigin.OPERATOR_EDITED
            and existing[item.field].value == item.value
            and existing[item.field].context_fingerprint == context.fingerprint
            else item
            for item in evidence
        )
        quality = tuple(dict.fromkeys((*self.quality_issues, *findings)))
        return replace(
            self, specification=proposed, field_provenance=evidence, quality_issues=quality
        )

    def with_operator_edits(self, reviewed: CAPStructuredSpecification) -> StoryCAPProposal:
        """Never mislabel a local text edit as provider or Story-derived authority."""
        if (
            reviewed.asset_id != self.specification.asset_id
            or reviewed.category != self.specification.category
        ):
            raise ValueError("Reviewed CAP identity differs from the source proposal")
        previous = {item.field: item for item in self.field_provenance}
        for field, value in reviewed.canonical_attributes.items():
            if value == self.specification.canonical_attributes.get(field):
                continue
            source = previous.get(field)
            previous[field] = CAPFieldProvenance(
                field=field,
                value=value,
                origin=CAPFieldOrigin.OPERATOR_EDITED,
                source_record_id=source.source_record_id if source else "",
                source_field=source.source_field if source else "",
                source_fingerprint=source.source_fingerprint if source else "",
                context_fingerprint=source.context_fingerprint if source else "",
                excerpt=source.excerpt if source else "",
                shot_authority=source.shot_authority if source else "",
                shot_record_id=source.shot_record_id if source else "",
                shot_field=source.shot_field if source else "",
                shot_fingerprint=source.shot_fingerprint if source else "",
                shot_excerpt=source.shot_excerpt if source else "",
                note="Human-edited proposal; prior source is context, not proof of this new wording.",
            )
        return replace(self, specification=reviewed, field_provenance=tuple(previous.values()))

    def to_cache(self) -> dict[str, Any]:
        """Serialize all review data, never an approval decision."""
        return {
            "specification": self.specification.model_dump(mode="json"),
            "suggested_attribute_key": self.suggested_attribute_key,
            "limitations": list(self.limitations),
            "detail_expansion": None
            if self.detail_expansion is None
            else {
                "candidates": [
                    {
                        "field": item.field,
                        "value": item.value,
                        "authority": item.authority.value,
                        "evidence": item.evidence,
                    }
                    for item in self.detail_expansion.candidates
                ],
                "missing": list(self.detail_expansion.missing),
            },
            "design_suggestions": [
                item.model_dump(mode="json") for item in self.design_suggestions
            ],
            "quality_issues": [
                {"field": item.field, "code": item.code, "message": item.message}
                for item in self.quality_issues
            ],
            "field_provenance": [item.model_dump(mode="json") for item in self.field_provenance],
        }

    @classmethod
    def from_cache(cls, raw: dict[str, Any]) -> StoryCAPProposal:
        """Rehydrate a cache record using the same validation as a new Draft."""
        from vscs.application.caps.detail_expansion import (
            CanonicalDetailCandidate,
            DetailAuthority,
        )

        spec = CAPStructuredSpecification.model_validate(raw["specification"])
        spec.validate_category_contract()
        details = raw.get("detail_expansion")
        expansion = (
            None
            if details is None
            else CanonicalDetailExpansion(
                tuple(
                    CanonicalDetailCandidate(
                        field=item["field"],
                        value=item["value"],
                        authority=DetailAuthority(item["authority"]),
                        evidence=item["evidence"],
                    )
                    for item in details["candidates"]
                ),
                tuple(details["missing"]),
            )
        )
        return cls(
            spec,
            str(raw["suggested_attribute_key"]),
            tuple(raw["limitations"]),
            expansion,
            tuple(ProposedDesignField.model_validate(item) for item in raw["design_suggestions"]),
            tuple(DesignQualityIssue(**item) for item in raw["quality_issues"]),
            tuple(
                CAPFieldProvenance.model_validate(item) for item in raw.get("field_provenance", ())
            ),
        )


class StoryCAPSpecificationService:
    """Adapt existing CAP-generation providers to structured, review-first Drafts."""

    def __init__(
        self,
        generator: CAPGeneratorService,
        specifications: CAPStructuredSpecificationService,
    ) -> None:
        self.generator = generator
        self.specifications = specifications

    def propose(self, asset_id: str, approved_story_context: str) -> StoryCAPProposal:
        if not approved_story_context.strip():
            raise ValueError("Approved Story context is required")
        asset = self.generator.assets.get(asset_id)
        draft = self.generator.generate_draft(asset_id, approved_story_context)
        return self.proposal_from_draft(
            asset, approved_story_context, draft, self.generator.provider
        )

    @staticmethod
    def generate_from_snapshot(
        asset: Asset,
        approved_story_context: str,
        provider: CAPGenerationProvider,
        *,
        grounding_context: str | None = None,
    ) -> StoryCAPProposal:
        """Provider-only generation from an immutable snapshot, safe for a worker thread.

        Never access project repositories or Qt widgets from this operation.
        It returns advisory material only; governance, cache and persistence
        remain with the UI-thread caller.
        """
        if not approved_story_context.strip():
            raise ValueError("Approved Story context is required")
        request = CAPGenerationRequest(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            asset_category=asset.category.value,
            asset_description=asset.description,
            story_context=approved_story_context,
        )
        draft: GeneratedCAPDraft = provider.generate_cap(request)
        return StoryCAPSpecificationService.proposal_from_draft(
            asset, approved_story_context, draft, provider, grounding_context=grounding_context
        )

    @staticmethod
    def proposal_from_draft(
        asset: Asset,
        approved_story_context: str,
        draft: GeneratedCAPDraft,
        provider: CAPGenerationProvider,
        *,
        grounding_context: str | None = None,
    ) -> StoryCAPProposal:
        """Pure proposal assembly; the provider may run paid design expansion."""
        approved_grounding = grounding_context or approved_story_context
        key = _CATEGORY_KEYS.get(asset.category, "identity")
        identity = draft.visual_identity.strip() or draft.canonical_description.strip()
        if not identity:
            raise ValueError("Provider returned no reviewable visual identity")
        description = draft.canonical_description.strip() or identity
        identity_issues = category_identity_issues(asset.category, asset.name, identity)
        if identity_issues:
            raise ValueError(
                "CAP category identity gate must be corrected before review: "
                + "; ".join(identity_issues)
            )
        # The provider output is a *proposed* visual anchor; no story entailment claimed.
        prompt = (
            f"Canonical reference image of {asset.name}. {description}. "
            f"Preserve identity: {identity}. Photorealistic, physically plausible, "
            "consistent geometry and materials; clear complete subject."
        )
        proposed = CAPStructuredSpecification(
            asset_id=asset.asset_id,
            category=asset.category,
            design_intent=description,
            canonical_attributes={key: identity},
            master_prompt=prompt,
            continuity_rules=draft.continuity_rules,
            source_description=(
                "Approved Story plus labelled Shot supporting context; "
                "provider draft (not verified canon)"
            ),
            origin="story_intelligence_proposal",
        )
        proposed.validate_category_contract()
        suggestions: tuple[ProposedDesignField, ...] = ()
        if isinstance(provider, CAPDesignExpansionProvider):
            response = provider.expand_cap_design(proposed, approved_grounding)
            verified = validate_design_expansion(proposed, response)
            suggestions = tuple(verified.values())
            grounding_issues = assess_design_grounding(approved_grounding, suggestions)
            if grounding_issues:
                raise ValueError(
                    "Design-expansion grounding must be corrected before review: "
                    + "; ".join(f"{issue.field}: {issue.code}" for issue in grounding_issues)
                )
        return StoryCAPProposal(
            proposed,
            key,
            (
                "Confirm that every canonical attribute is supported by the approved Story.",
                "Provider-inferred appearances and dimensions are proposals, not established canon.",
                "Review missing dependencies, variants, and prompt fidelity before saving.",
            ),
            expand_details(proposed, draft, approved_grounding),
            suggestions,
            assess_design_quality(asset.category, suggestions),
        )

    def save_reviewed(
        self, specification: CAPStructuredSpecification
    ) -> CAPStructuredSpecification:
        if specification.origin != "story_intelligence_proposal":
            raise ValueError("Only Story-to-CAP proposals are accepted by this workflow")
        if self.specifications.get(specification.asset_id) is not None:
            raise ValueError("A structured CAP already exists; revision review is required")
        return self.specifications.save_draft(specification)
