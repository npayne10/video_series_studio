"""Governed, provider-generated one-field proposals for existing Draft CAP reviews.

The provider is invoked only after operator consent in the UI. All results
are unapproved advice and cached outside CAP metadata; only a separately
reviewed confirmation may call the existing Draft compare-and-swap path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from vscs.application.caps.design_quality import assess_design_grounding
from vscs.application.caps.draft_cap_revision import DraftCAPRevisionSnapshot
from vscs.application.caps.provider_design_expansion import (
    CAPSingleFieldRegenerationProvider,
    validate_design_expansion,
)
from vscs.application.caps.proposal_cache import cache_fingerprint, provider_cache_fingerprint
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService

CONTRACT_VERSION = "draft-cap-field-regeneration-v1"


class DraftCAPFieldGenerationError(RuntimeError):
    """Generation, provenance or expected Draft review state is unsafe."""


class CachedDraftCAPFieldProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    contract: str
    story_id: str
    asset_id: str
    field: str
    story_fingerprint: str
    context_fingerprint: str
    specification_fingerprint: str
    provider_fingerprint: str
    proposed_value: str
    rationale: str
    source_type: str
    generation_number: int
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class DraftCAPFieldRequest:
    snapshot: DraftCAPRevisionSnapshot
    field: str
    story_context: str
    provider_fingerprint: str
    request_fingerprint: str
    generation_number: int


class DraftCAPFieldProposalCache:
    """Non-authoritative project-local cache with immutable sequential versions."""

    def __init__(self, project_root: Path) -> None:
        self.directory = project_root / "production" / "caps" / "draft_field_proposals"

    def _path(self, request: DraftCAPFieldRequest) -> Path:
        digest = cache_fingerprint(request.snapshot.story_id, request.snapshot.asset_id, request.field)
        return self.directory / digest / f"{request.generation_number:04d}.json"

    def next_number(self, request: DraftCAPFieldRequest) -> int:
        folder = self._path(request).parent
        if not folder.exists():
            return 1
        indices = []
        for path in folder.iterdir():
            if not path.is_file() or path.suffix not in {".json", ".pending"}:
                raise DraftCAPFieldGenerationError("Unexpected proposal cache entry")
            try:
                indices.append(int(path.stem))
            except ValueError as exc:
                raise DraftCAPFieldGenerationError("Invalid cached proposal filename") from exc
        return max(indices, default=0) + 1

    def latest_completed_number(self, request: DraftCAPFieldRequest) -> int | None:
        """Find the latest complete, reviewable proposal without any provider call."""
        folder = self._path(request).parent
        if not folder.is_dir():
            return None
        numbers = []
        for path in folder.glob("*.json"):
            try:
                numbers.append(int(path.stem))
            except ValueError as exc:
                raise DraftCAPFieldGenerationError("Invalid cached proposal filename") from exc
        return max(numbers, default=None)

    def reserve(self, request: DraftCAPFieldRequest) -> None:
        """Reserve once before any provider call; ambiguous outcomes remain recorded."""
        path = self._path(request).with_suffix(".pending")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(request.request_fingerprint)
        except FileExistsError as exc:
            raise DraftCAPFieldGenerationError("This provider request was already reserved") from exc

    def save(self, request: DraftCAPFieldRequest, proposal: CachedDraftCAPFieldProposal) -> None:
        path = self._path(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: failed or uncertain requests must not overwrite evidence.
        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(proposal.model_dump_json())
        except FileExistsError as exc:
            raise DraftCAPFieldGenerationError("Proposal generation number already used") from exc
        reservation = path.with_suffix(".pending")
        if reservation.read_text(encoding="utf-8") != request.request_fingerprint:
            raise DraftCAPFieldGenerationError("Provider reservation identity changed")
        reservation.unlink()

    def load(self, request: DraftCAPFieldRequest) -> CachedDraftCAPFieldProposal:
        try:
            raw = self._path(request).read_text(encoding="utf-8")
            proposal = CachedDraftCAPFieldProposal.model_validate_json(raw)
        except (OSError, ValueError) as exc:
            raise DraftCAPFieldGenerationError("Cached field proposal unavailable or invalid") from exc
        if (
            proposal.contract != CONTRACT_VERSION
            or proposal.story_id != request.snapshot.story_id
            or proposal.asset_id != request.snapshot.asset_id
            or proposal.field != request.field
            or proposal.story_fingerprint != request.snapshot.story_fingerprint
            or proposal.context_fingerprint != request.snapshot.context_fingerprint
            or proposal.specification_fingerprint != request.snapshot.specification.fingerprint()
            or proposal.provider_fingerprint != request.provider_fingerprint
            or proposal.request_fingerprint != request.request_fingerprint
            or proposal.generation_number != request.generation_number
        ):
            raise DraftCAPFieldGenerationError("Cached field proposal is stale or mismatched")
        return proposal


def prepare_field_request(
    service: StoryCAPBatchReviewService,
    snapshot: DraftCAPRevisionSnapshot,
    *,
    field: str,
    provider: object,
    generation_number: int,
) -> DraftCAPFieldRequest:
    """Attest Story/context and missing-field boundary without provider calls."""
    original = next((item for item in snapshot.review.fields if item.field == field), None)
    if original is None or original.decision.value not in {"defer", "reject"}:
        raise DraftCAPFieldGenerationError("Only deferred/rejected fields may be generated")
    if field in snapshot.specification.canonical_attributes:
        raise DraftCAPFieldGenerationError("Target field already has an accepted value")
    if service.batch.current_story_fingerprint(snapshot.story_id) != snapshot.story_fingerprint:
        raise DraftCAPFieldGenerationError("Story changed since review was loaded")
    context = service.prepare_context(snapshot.story_id, snapshot.asset_id)
    if context.fingerprint != snapshot.context_fingerprint:
        raise DraftCAPFieldGenerationError("Governed context changed since review was loaded")
    trusted = tuple(
        item.excerpt
        for item in context.sources
        if item.authority in {"approved_story_context", "verified_ready_shot"}
    )
    if not trusted:
        raise DraftCAPFieldGenerationError("No approved Story or verified Shot context available")
    if generation_number < 1:
        raise DraftCAPFieldGenerationError("Invalid proposal sequence")
    story_context = "\n".join(trusted)
    identity = provider_cache_fingerprint(provider)
    digest = cache_fingerprint(
        CONTRACT_VERSION,
        snapshot.story_id,
        snapshot.asset_id,
        snapshot.specification.fingerprint(),
        snapshot.story_fingerprint,
        snapshot.context_fingerprint,
        field,
        story_context,
        identity,
        str(generation_number),
    )
    return DraftCAPFieldRequest(
        snapshot=snapshot,
        field=field,
        story_context=story_context,
        provider_fingerprint=identity,
        request_fingerprint=digest,
        generation_number=generation_number,
    )


def generate_field_proposal(
    request: DraftCAPFieldRequest,
    provider: CAPSingleFieldRegenerationProvider,
) -> CachedDraftCAPFieldProposal:
    """Pure provider-bound call; no Qt/project DB access from the worker thread."""
    if not isinstance(provider, CAPSingleFieldRegenerationProvider):
        raise DraftCAPFieldGenerationError(
            "Selected CAP provider does not support scoped Draft field regeneration"
        )
    original = next(
        item for item in request.snapshot.review.fields if item.field == request.field
    )
    response = provider.regenerate_draft_cap_field(
        request.snapshot.specification,
        request.field,
        request.story_context,
        original.proposed_value,
    )
    proposals = validate_design_expansion(request.snapshot.specification, response)
    if set(proposals) != {request.field}:
        raise DraftCAPFieldGenerationError(
            "Provider must return exactly one scoped field proposal"
        )
    selected = proposals[request.field]
    issues = [issue for issue in assess_design_grounding(request.story_context, (selected,))]
    if issues:
        raise DraftCAPFieldGenerationError("Generated field failed source-grounding validation")
    return CachedDraftCAPFieldProposal(
        contract=CONTRACT_VERSION,
        story_id=request.snapshot.story_id,
        asset_id=request.snapshot.asset_id,
        field=request.field,
        story_fingerprint=request.snapshot.story_fingerprint,
        context_fingerprint=request.snapshot.context_fingerprint,
        specification_fingerprint=request.snapshot.specification.fingerprint(),
        provider_fingerprint=request.provider_fingerprint,
        proposed_value=selected.proposed_value.strip(),
        rationale=selected.rationale.strip(),
        source_type="AI-proposed design; not established Story canon",
        generation_number=request.generation_number,
        request_fingerprint=request.request_fingerprint,
    )


def verify_proposal_for_review(
    service: StoryCAPBatchReviewService,
    request: DraftCAPFieldRequest,
    proposal: CachedDraftCAPFieldProposal,
) -> None:
    """Check current Draft authority again before permitting operator approval."""
    from vscs.application.caps.draft_cap_revision import prepare_draft_cap_revision

    current = prepare_draft_cap_revision(
        service, request.snapshot.story_id, request.snapshot.asset_id
    )
    if current.expected_metadata != request.snapshot.expected_metadata:
        raise DraftCAPFieldGenerationError("Draft changed after automatic field proposal")
    if (
        current.story_fingerprint != proposal.story_fingerprint
        or current.context_fingerprint != proposal.context_fingerprint
        or request.request_fingerprint != proposal.request_fingerprint
    ):
        raise DraftCAPFieldGenerationError("Generated proposal provenance is stale")
