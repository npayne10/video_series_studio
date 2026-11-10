"""Automated existing Draft CAP field generation: consent boundary and provenance."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.automated_draft_field import (
    CachedDraftCAPFieldProposal,
    DraftCAPFieldGenerationError,
    DraftCAPFieldProposalCache,
    generate_field_proposal,
    prepare_field_request,
)
from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
)
from vscs.application.caps.draft_cap_revision import DraftCAPRevisionSnapshot
from vscs.application.caps.provider_design_expansion import (
    DesignExpansionResponse,
    ProposedDesignField,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


class _Provider:
    _model = "test-structured"

    def __init__(self, fields=None):
        self.calls = []
        self.fields = fields

    def expand_cap_design(self, spec, story_context):
        self.calls.append((spec, story_context))
        fields = self.fields
        if fields is None:
            fields = (
                ProposedDesignField(
                    field="geometry",
                    proposed_value="Proposed rectangular console housing with its blue display",
                    rationale="New Draft design choice constrained by accepted components",
                ),
            )
        return DesignExpansionResponse(fields=fields)


def _context():
    return SimpleNamespace(
        fingerprint="ctx-1",
        sources=(
            SimpleNamespace(
                authority="approved_story_context",
                excerpt="The diagnostic console has a blue display beside a workstation.",
            ),
            SimpleNamespace(authority="unverified_shot", excerpt="UNVERIFIED: an extra door."),
        ),
    )


def _review_fixture():
    spec = CAPStructuredSpecification(
        asset_id="STORY-PRO-TEST",
        category=AssetCategory.PROP,
        design_intent="Diagnostic console",
        canonical_attributes={
            "materials": "Graphite",
            "components": "Blue display",
            "scale": "1.1 metres high",
        },
        master_prompt="Draft identity",
    )
    review = DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        reviewer="Operator",
        story_fingerprint="story-1",
        context_fingerprint="ctx-1",
        fields=(
            DesignFieldReview(
                field="geometry",
                decision=DetailDecision.DEFER,
                origin=DetailOrigin.UNRESOLVED,
            ),
        ),
    )
    snap = DraftCAPRevisionSnapshot(
        story_id="STORY-001",
        asset_id=spec.asset_id,
        story_fingerprint="story-1",
        context_fingerprint="ctx-1",
        expected_metadata={"audit": "unchanged"},
        specification=spec,
        review=review,
    )
    service = SimpleNamespace(
        batch=SimpleNamespace(current_story_fingerprint=Mock(return_value="story-1")),
        prepare_context=Mock(return_value=_context()),
    )
    return service, snap


def _request(number=1, provider=None):
    service, snapshot = _review_fixture()
    provider = provider or _Provider()
    request = prepare_field_request(
        service, snapshot, field="geometry", provider=provider, generation_number=number
    )
    return request, provider, service


def test_scoped_provider_receives_only_accepted_attributes_and_authoritative_story():
    request, provider, _service = _request()
    proposal = generate_field_proposal(request, provider)
    assert proposal.field == "geometry"
    assert proposal.source_type.startswith("AI-proposed design")
    assert len(provider.calls) == 1
    spec, source = provider.calls[0]
    assert spec.canonical_attributes["components"] == "Blue display"
    assert "diagnostic console" in source.lower()
    assert "UNVERIFIED" not in source


def test_refuses_provider_unrelated_field():
    provider = _Provider(
        fields=(
            ProposedDesignField(
                field="materials", proposed_value="Silver", rationale="Unapproved change"
            ),
        )
    )
    request, provider, _service = _request(provider=provider)
    with pytest.raises(ValueError, match="already-defined"):
        generate_field_proposal(request, provider)


def test_refuses_empty_generation():
    request, _provider, _service = _request()
    with pytest.raises(DraftCAPFieldGenerationError, match="exactly one"):
        generate_field_proposal(request, _Provider(fields=()))


def test_rejects_stale_context_before_provider_call():
    service, snap = _review_fixture()
    service.prepare_context.return_value.fingerprint = "changed"
    with pytest.raises(DraftCAPFieldGenerationError, match="context changed"):
        prepare_field_request(service, snap, field="geometry", provider=_Provider(), generation_number=1)


def test_cache_reservation_and_reopen_are_non_authoritative(tmp_path):
    request, provider, _service = _request()
    cache = DraftCAPFieldProposalCache(tmp_path)
    assert cache.next_number(request) == 1
    cache.reserve(request)
    assert cache.next_number(request) == 2
    with pytest.raises(DraftCAPFieldGenerationError, match="already reserved"):
        cache.reserve(request)
    proposal = generate_field_proposal(request, provider)
    cache.save(request, proposal)
    assert cache.load(request) == proposal
    assert cache.next_number(request) == 2
    assert not cache._path(request).with_suffix(".pending").exists()


def test_tampered_cache_cannot_be_reused(tmp_path):
    request, provider, _service = _request()
    cache = DraftCAPFieldProposalCache(tmp_path)
    cache.reserve(request)
    cache.save(request, generate_field_proposal(request, provider))
    path = cache._path(request)
    bad = CachedDraftCAPFieldProposal.model_validate_json(path.read_text())
    bad = bad.model_copy(update={"story_fingerprint": "forged"})
    path.write_text(bad.model_dump_json(), encoding="utf-8")
    with pytest.raises(DraftCAPFieldGenerationError, match="stale"):
        cache.load(request)


def test_approved_field_cannot_be_generated():
    service, snap = _review_fixture()
    with pytest.raises(DraftCAPFieldGenerationError, match="deferred/rejected"):
        prepare_field_request(service, snap, field="materials", provider=_Provider(), generation_number=1)
