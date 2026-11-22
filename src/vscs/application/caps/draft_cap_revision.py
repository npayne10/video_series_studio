"""Governed single-field revision of an existing, non-approved Draft CAP.

No AI generation, no image operations and no Canon/MASTER authority.
Only an already-deferred/rejected field may be revised; accepted decisions
and their evidence remain byte-for-byte identical within the review audit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
    build_reviewed_master_prompt,
)
from vscs.application.caps.review_snapshot import load_review_snapshot
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.story_field_grounding import (
    CAPFieldOrigin,
    CAPFieldProvenance,
    reconcile_grounded_fields,
)
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.domain.caps import CAPStatus

REVISION_HISTORY_KEY = "vscs.cap_design_revision_history.v1"


class DraftCAPRevisionError(RuntimeError):
    """The source Draft, context, operator decision or metadata is stale."""


@dataclass(frozen=True, slots=True)
class DraftCAPRevisionSnapshot:
    story_id: str
    asset_id: str
    story_fingerprint: str
    context_fingerprint: str
    expected_metadata: dict[str, str]
    specification: CAPStructuredSpecification
    review: DesignReviewPackage

    @property
    def changed(self) -> bool:
        return False


def prepare_draft_cap_revision(
    service: StoryCAPBatchReviewService, story_id: str, asset_id: str
) -> DraftCAPRevisionSnapshot:
    """Read and attest current project authority; do not write anything."""
    candidates = service.discover(story_id)
    if asset_id not in {
        item.asset_id for item in candidates if item.has_cap and item.has_specification
    }:
        raise DraftCAPRevisionError("Asset is not an existing Story-bound CAP specification")
    current_story = service.batch.current_story_fingerprint(story_id)
    current_context = service.prepare_context(story_id, asset_id).fingerprint
    caps = service.batch.generator.specifications.caps
    cap = caps.get(asset_id)
    if cap.status is not CAPStatus.DRAFT:
        raise DraftCAPRevisionError("Only an unapproved Draft CAP may be revised")
    spec, review, error = load_review_snapshot(cap.production_metadata)
    if spec is None or review is None:
        raise DraftCAPRevisionError(f"Existing CAP review evidence is invalid: {error}")
    if (
        spec.asset_id != asset_id
        or review.story_fingerprint != current_story
        or review.context_fingerprint != current_context
    ):
        raise DraftCAPRevisionError("Stored Story or governed Shot context is stale")
    if not any(
        item.decision in {DetailDecision.DEFER, DetailDecision.REJECT} for item in review.fields
    ):
        raise DraftCAPRevisionError("No deferred or rejected CAP fields are available")
    return DraftCAPRevisionSnapshot(
        story_id=story_id,
        asset_id=asset_id,
        story_fingerprint=current_story,
        context_fingerprint=current_context,
        expected_metadata=dict(cap.production_metadata),
        specification=spec,
        review=review,
    )


def prepare_story_field_revisions(
    service: StoryCAPBatchReviewService,
    snapshot: DraftCAPRevisionSnapshot,
) -> tuple[CAPFieldProvenance, ...]:
    """Inspect source-backed missing fields on the *existing* Draft, without writes.

    Only source text owned by the approved Story may generate a suggestion.
    Previously accepted/edited fields remain outside the revision surface.
    """
    current = prepare_draft_cap_revision(service, snapshot.story_id, snapshot.asset_id)
    if current.expected_metadata != snapshot.expected_metadata:
        raise DraftCAPRevisionError("Draft CAP changed; reopen before reviewing Story suggestions")
    manifest = service.prepare_context(snapshot.story_id, snapshot.asset_id)
    if manifest.fingerprint != snapshot.context_fingerprint:
        raise DraftCAPRevisionError("Story/Shot context changed; reopen Draft CAP review")
    caps = service.batch.generator.specifications.caps
    asset = caps.assets.get(snapshot.asset_id)
    if asset.category != snapshot.specification.category:
        raise DraftCAPRevisionError("Asset category changed before Story field review")
    _, evidence, _ = reconcile_grounded_fields(snapshot.specification, asset.name, manifest, ())
    eligible = {
        field.field
        for field in snapshot.review.fields
        if field.decision in {DetailDecision.DEFER, DetailDecision.REJECT}
        and field.field not in snapshot.specification.canonical_attributes
    }
    return tuple(
        item
        for item in evidence
        if item.field in eligible and item.origin is CAPFieldOrigin.STORY_CANDIDATE
    )


def save_draft_cap_field_revision(
    service: StoryCAPBatchReviewService,
    snapshot: DraftCAPRevisionSnapshot,
    *,
    field: str,
    reviewed_value: str,
    rationale: str,
    reviewer: str,
    story_provenance: CAPFieldProvenance | None = None,
) -> CAPStructuredSpecification:
    """Preserve all other decisions; commit only if Draft metadata is unchanged."""
    value = reviewed_value.strip()
    reason = rationale.strip()
    name = reviewer.strip()
    if not value or not reason or not name:
        raise DraftCAPRevisionError("A reviewed value, rationale and reviewer are required")
    original = next((item for item in snapshot.review.fields if item.field == field), None)
    if original is None or original.decision not in {
        DetailDecision.DEFER,
        DetailDecision.REJECT,
    }:
        raise DraftCAPRevisionError("Only a previously deferred/rejected field is editable")
    if service.batch.current_story_fingerprint(snapshot.story_id) != snapshot.story_fingerprint:
        raise DraftCAPRevisionError("Approved Story changed; reopen Draft CAP review")
    if (
        service.prepare_context(snapshot.story_id, snapshot.asset_id).fingerprint
        != snapshot.context_fingerprint
    ):
        raise DraftCAPRevisionError("Governed CAP context changed; reopen review")
    if story_provenance is not None:
        # Require the exact candidate to be re-derived from CURRENT approved
        # Story evidence, not a client-supplied label or a Draft Shot excerpt.
        current = prepare_story_field_revisions(service, snapshot)
        proven = next((item for item in current if item.field == field), None)
        if (
            proven is None
            or proven != story_provenance
            or story_provenance.origin is not CAPFieldOrigin.STORY_CANDIDATE
            or story_provenance.value != value
        ):
            raise DraftCAPRevisionError("Story-grounded field evidence changed or is unsupported")
    new_field = DesignFieldReview(
        field=original.field,
        proposed_value=(story_provenance.value if story_provenance else original.proposed_value),
        final_value=value,
        decision=DetailDecision.EDIT,
        origin=(
            DetailOrigin.STORY_CANDIDATE
            if story_provenance is not None
            else DetailOrigin.DESIGN_PROPOSAL
        ),
        evidence=reason,
        rationale=(
            f"Operator accepted approved-Story candidate for former {original.decision.value} field"
            if story_provenance is not None
            else f"Operator revision of former {original.decision.value} field"
        ),
        source_record_id=story_provenance.source_record_id if story_provenance else "",
        source_field=story_provenance.source_field if story_provenance else "",
        source_fingerprint=story_provenance.source_fingerprint if story_provenance else "",
        source_excerpt=story_provenance.excerpt if story_provenance else "",
        shot_authority=story_provenance.shot_authority if story_provenance else "",
        shot_source_record_id=story_provenance.shot_record_id if story_provenance else "",
        shot_source_fingerprint=(story_provenance.shot_fingerprint if story_provenance else ""),
        shot_excerpt=story_provenance.shot_excerpt if story_provenance else "",
    )
    fields = tuple(new_field if item.field == field else item for item in snapshot.review.fields)
    package = DesignReviewPackage(
        asset_id=snapshot.asset_id,
        base_fingerprint=snapshot.specification.fingerprint(),
        story_fingerprint=snapshot.story_fingerprint,
        context_fingerprint=snapshot.context_fingerprint,
        reviewer=name,
        fields=fields,
    )
    revised, audit = apply_review(snapshot.specification, package)
    revised = revised.model_copy(
        update={"master_prompt": build_reviewed_master_prompt(revised, package)}
    )
    service.validate_reviewed_dependencies(revised)
    metadata = dict(snapshot.expected_metadata)
    existing_history = metadata.get(REVISION_HISTORY_KEY)
    if existing_history is None:
        history: list[dict[str, str]] = []
    else:
        try:
            loaded = json.loads(existing_history)
            if not isinstance(loaded, list) or not all(isinstance(item, dict) for item in loaded):
                raise ValueError("Invalid CAP revision history")
            history = loaded
        except (ValueError, TypeError) as exc:
            raise DraftCAPRevisionError("Stored CAP revision history is invalid") from exc
    history.append(
        {
            "field": field,
            "reviewer": name,
            "rationale": reason,
            "prior_decision": original.decision.value,
            "prior_review_audit": snapshot.expected_metadata[DESIGN_REVIEW_KEY],
            "prior_specification_fingerprint": snapshot.specification.fingerprint(),
            "new_specification_fingerprint": revised.fingerprint(),
            "source_record_id": story_provenance.source_record_id if story_provenance else "",
            "source_fingerprint": story_provenance.source_fingerprint if story_provenance else "",
        }
    )
    metadata[SPECIFICATION_METADATA_KEY] = json.dumps(
        revised.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    )
    metadata[DESIGN_REVIEW_KEY] = audit
    metadata[REVISION_HISTORY_KEY] = json.dumps(history, sort_keys=True)
    caps = service.batch.generator.specifications.caps
    asset = caps.assets.get(snapshot.asset_id)
    if asset.category != revised.category:
        raise DraftCAPRevisionError("Asset category changed before Draft revision")
    caps.repository.compare_and_swap_draft_metadata(
        snapshot.asset_id,
        expected=snapshot.expected_metadata,
        replacement=metadata,
    )
    return revised
