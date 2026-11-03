"""B.5.21B offline cache-first queue and legacy-context safety tests."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.context_preparation import CAPContextManifest, CAPContextSource
from vscs.application.caps.preparation_queue import CAPPreparationQueueService
from vscs.application.caps.proposal_cache import (
    CAPProposalCache,
    provider_cache_fingerprint,
)
from vscs.application.caps.story_batch import StoryBatchProposal
from vscs.application.caps.story_batch_review import CAPAssetCandidate
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.dialogs.story_cap_batch_dialog import StoryCAPBatchDialog


STORY = "STORY-001"
ASSET = "CAP-LOC-001"


def _proposal():
    spec = CAPStructuredSpecification(
        asset_id=ASSET,
        category=AssetCategory.LOCATION,
        design_intent="A quiet room.",
        canonical_attributes={"architecture": "Room"},
        master_prompt="Draft design.",
        origin="story_intelligence_proposal",
    )
    return StoryBatchProposal(STORY, "story-hash", ASSET, StoryCAPProposal(spec, "architecture", ()))


def _manifest(asset_id=ASSET, fingerprint="context-hash"):
    return CAPContextManifest(
        STORY,
        asset_id,
        "story-hash",
        "asset-hash",
        (
            CAPContextSource(
                "approved_story",
                STORY,
                "description",
                "A quiet room.",
                "approved_story_context",
                "source-hash",
            ),
        ),
        (),
        fingerprint,
    )


def _review():
    candidates = (
        CAPAssetCandidate(ASSET, "Engineering control room", "location", False, False),
        CAPAssetCandidate("CAP-PRP-001", "Diagnostic console", "prop", False, False),
    )
    batch = SimpleNamespace(current_story_fingerprint=lambda story_id: "story-hash")
    return SimpleNamespace(
        batch=batch,
        discover=lambda story_id: candidates,
        prepare_context=lambda story_id, asset_id: _manifest(asset_id),
    )


def test_cache_recovers_legacy_without_promoting_context(tmp_path):
    cache = CAPProposalCache(tmp_path)
    provider = object()
    fingerprint = provider_cache_fingerprint(provider)
    cache.save(_proposal(), "asset-hash", fingerprint)
    inspection = cache.inspect(
        STORY, ASSET, "story-hash", "asset-hash", fingerprint, "context-hash"
    )
    assert inspection.status == "legacy_cached"
    assert inspection.proposal is not None
    assert inspection.proposal.proposal.specification.asset_id == ASSET


def test_v2_context_change_invalidates_cache_without_deleting(tmp_path):
    cache = CAPProposalCache(tmp_path)
    fingerprint = provider_cache_fingerprint(object())
    cache.save(_proposal(), "asset-hash", fingerprint, "context-hash")
    assert cache.inspect(
        STORY, ASSET, "story-hash", "asset-hash", fingerprint, "context-hash"
    ).status == "cached_current"
    assert cache.inspect(
        STORY, ASSET, "story-hash", "asset-hash", fingerprint, "new-context"
    ).status == "stale"
    assert cache.inspect(
        STORY, ASSET, "story-hash", "changed-asset", fingerprint, "context-hash"
    ).status == "stale"
    assert cache.inspect(
        STORY, ASSET, "changed-story", "asset-hash", fingerprint, "context-hash"
    ).status == "stale"
    assert cache.inspect(
        STORY, ASSET, "story-hash", "asset-hash", "different-provider", "context-hash"
    ).status == "stale"
    assert cache.load(
        STORY, ASSET, "story-hash", "asset-hash", fingerprint, "new-context"
    ) is None


def test_queue_is_read_only_and_cache_first(tmp_path):
    cache = CAPProposalCache(tmp_path)
    provider = object()
    fingerprint = provider_cache_fingerprint(provider)
    cache.save(_proposal(), "asset-hash", fingerprint, "context-hash")
    before = tuple(cache.directory.iterdir())
    plan = CAPPreparationQueueService(_review(), cache, provider).plan(STORY)
    assert [item.asset_id for item in plan.items] == [ASSET, "CAP-PRP-001"]
    assert [item.status for item in plan.items] == ["cached_current", "missing"]
    assert [item.context_authority for item in plan.items] == [
        "approved_story_context",
        "approved_story_context",
    ]
    assert tuple(cache.directory.iterdir()) == before


def test_already_specified_does_not_invoke_context_or_cache(tmp_path):
    review = _review()
    review.discover = lambda story_id: (
        CAPAssetCandidate(ASSET, "Room", "location", True, True),
    )
    review.prepare_context = Mock(side_effect=AssertionError("must not inspect"))
    cache = Mock()
    plan = CAPPreparationQueueService(review, cache, object()).plan(STORY)
    assert plan.items[0].status == "already_specified"
    review.prepare_context.assert_not_called()
    cache.inspect.assert_not_called()


def test_queue_ui_offline_and_story_switch_reset(tmp_path, monkeypatch, qtbot):
    from vscs.application.story.lifecycle import StoryRecord, StoryStatus
    from vscs.presentation.dialogs import story_cap_batch_dialog as ui

    approved = StoryRecord(
        story_id=STORY,
        title="Quiet Console",
        description="A quiet room.",
        status=StoryStatus.APPROVED,
    )
    monkeypatch.setattr(
        ui,
        "StoryLifecycleService",
        lambda _projects: SimpleNamespace(list_stories=lambda: (approved,)),
    )
    generator = SimpleNamespace(
        caps=SimpleNamespace(
            assets=SimpleNamespace(
                projects=SimpleNamespace(project_directory=tmp_path)
            )
        ),
        provider=object(),
    )
    dialog = StoryCAPBatchDialog(generator)
    qtbot.addWidget(dialog)
    dialog.review_service = _review()
    dialog.assets.addItem(ASSET, ASSET)
    dialog.queue_button.setEnabled(True)
    with patch.object(QMessageBox, "warning") as warning:
        dialog.queue_button.click()
    warning.assert_not_called()
    assert "cache-first CAP preparation (offline)" in dialog.summary.toPlainText()
    assert "missing" in dialog.summary.toPlainText()
    dialog.story.addItem("STORY-002", "STORY-002")
    dialog.story.setCurrentIndex(1)
    assert not dialog.queue_button.isEnabled()
