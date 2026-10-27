"""Governed field-level design decisions and draft provenance for CAP specifications."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.caps import CAPStatus, CAPUpdate

DESIGN_REVIEW_KEY = "vscs.cap_design_review.v1"


class DetailDecision(StrEnum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"
    DEFER = "defer"


class DetailOrigin(StrEnum):
    STORY_CANDIDATE = "story_candidate_unverified"
    DESIGN_PROPOSAL = "design_proposal"
    UNRESOLVED = "unresolved"


class DesignFieldReview(BaseModel):
    """An explicit review decision; narrative provenance is not proof of canon."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field: str = Field(min_length=1)
    proposed_value: str = ""
    final_value: str = ""
    decision: DetailDecision
    origin: DetailOrigin
    evidence: str = ""
    rationale: str = ""

    @model_validator(mode="after")
    def check_decision(self) -> DesignFieldReview:
        if self.decision in {DetailDecision.ACCEPT, DetailDecision.EDIT} and not self.final_value:
            raise ValueError("Accepted or edited fields need a final value")
        if self.decision in {DetailDecision.REJECT, DetailDecision.DEFER} and self.final_value:
            raise ValueError("Rejected or deferred fields cannot add canonical values")
        if self.origin is DetailOrigin.UNRESOLVED and self.decision is DetailDecision.ACCEPT:
            raise ValueError("An unresolved field needs an explicit edit or deferral")
        return self


class DesignReviewPackage(BaseModel):
    """Fully reviewed proposal scoped to one current specification fingerprint."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    base_fingerprint: str
    fields: tuple[DesignFieldReview, ...]
    story_fingerprint: str = ""
    reviewer: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_fields(self) -> DesignReviewPackage:
        names = [item.field for item in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("Each attribute requires one review decision")
        return self


def apply_review(
    spec: CAPStructuredSpecification,
    review: DesignReviewPackage,
) -> tuple[CAPStructuredSpecification, str]:
    """Produce reviewed Draft plus stable audit payload; no database writes."""
    if review.asset_id != spec.asset_id or review.base_fingerprint != spec.fingerprint():
        raise ValueError("CAP identity or fingerprint changed; review must be repeated")
    required = REQUIRED_FIELDS.get(spec.category, ("identity",))
    decisions = {item.field: item for item in review.fields}
    if not set(required).issubset(decisions):
        raise ValueError("Every required category field needs an explicit review decision")
    attributes = dict(spec.canonical_attributes)
    for item in review.fields:
        if item.decision in {DetailDecision.ACCEPT, DetailDecision.EDIT}:
            attributes[item.field] = item.final_value
        else:
            attributes.pop(item.field, None)
    updated = CAPStructuredSpecification.model_validate(
        {**spec.model_dump(), "canonical_attributes": attributes}
    )
    updated.validate_category_contract()
    audit = {
        "version": 1,
        "reviewer": review.reviewer,
        "story_fingerprint": review.story_fingerprint,
        "base_fingerprint": review.base_fingerprint,
        "result_fingerprint": updated.fingerprint(),
        "fields": [item.model_dump(mode="json") for item in review.fields],
        "image_authorized": False,
        "canon_approved": False,
    }
    return updated, json.dumps(audit, sort_keys=True, separators=(",", ":"))


def build_reviewed_master_prompt(
    spec: CAPStructuredSpecification, review: DesignReviewPackage
) -> str:
    """Build from accepted decisions only; no inferred canon status."""
    accepted = {
        field.field: field.final_value
        for field in review.fields
        if field.decision in {DetailDecision.ACCEPT, DetailDecision.EDIT}
    }
    if not accepted:
        raise ValueError("No accepted design details")
    details = "; ".join(f"{key}: {accepted[key]}" for key in sorted(accepted))
    digest = hashlib.sha256(details.encode("utf-8")).hexdigest()[:12]
    return (
        f"Canonical {spec.category.value} reference proposal, not approved. "
        f"{spec.design_intent}. Fixed reviewed design: {details}. "
        "Photorealistic, physically plausible, consistent identity and geometry. "
        f"Design fingerprint {digest}."
    )


class DesignReviewPersistence:
    """One metadata update for reviewed Draft and provenance, never approval."""

    def __init__(self, specifications: object) -> None:
        self.specifications = specifications

    def save(
        self, spec: CAPStructuredSpecification, review: DesignReviewPackage
    ) -> CAPStructuredSpecification:
        from vscs.application.caps.structured_specification import (
            SPECIFICATION_METADATA_KEY,
            CAPStructuredSpecificationService,
        )

        service = self.specifications
        if not isinstance(service, CAPStructuredSpecificationService):
            raise TypeError("A project CAP specification service is required")
        reviewed, audit = apply_review(spec, review)
        reviewed = reviewed.model_copy(
            update={"master_prompt": build_reviewed_master_prompt(reviewed, review)}
        )
        cap = service.caps.get(spec.asset_id)
        if cap.status is not CAPStatus.DRAFT or service.get(spec.asset_id) is not None:
            raise ValueError("Only a fresh Draft CAP with no prior specification can be committed")
        asset = service.caps.assets.get(spec.asset_id)
        if asset.category != reviewed.category:
            raise ValueError("Project asset category mismatch")
        metadata = dict(cap.production_metadata)
        metadata[SPECIFICATION_METADATA_KEY] = json.dumps(
            reviewed.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
        )
        metadata[DESIGN_REVIEW_KEY] = audit
        service.caps.update(spec.asset_id, CAPUpdate(production_metadata=metadata))
        return reviewed
