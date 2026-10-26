"""Project Story authority and batch CAP proposal protection."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.story_batch import StoryBatchError, StoryCAPBatchService
from vscs.application.story.lifecycle import StoryStatus


def _story(status=StoryStatus.APPROVED, description="A control room and vessel"):
    return SimpleNamespace(
        story_id="STORY-001",
        title="The Quiet Console",
        status=status,
        description=description,
    )


def test_batch_refuses_unapproved_or_missing_stories():
    stories = Mock()
    generator = Mock()
    service = StoryCAPBatchService(stories, generator)
    for story in (None, _story(StoryStatus.DRAFT)):
        stories.story.return_value = story
        with pytest.raises(StoryBatchError, match="Approved or Locked"):
            service.preview("STORY-001", ("CAP-LOC-001",))
    generator.propose.assert_not_called()


def test_batch_deduplicates_and_skips_existing_specifications():
    stories = Mock()
    stories.story.return_value = _story()
    generator = Mock()
    generator.specifications.get.side_effect = lambda asset_id: (
        object() if asset_id == "CAP-LOC-001" else None
    )
    generator.propose.return_value = Mock()
    batch = StoryCAPBatchService(stories, generator).preview(
        "STORY-001", ("CAP-LOC-001", "cap-prp-001", "CAP-PRP-001")
    )
    assert len(batch.candidates) == 1
    assert batch.candidates[0].asset_id == "CAP-PRP-001"
    assert len(batch.candidates[0].story_fingerprint) == 64
    assert len(batch.skipped) == 1
    generator.propose.assert_called_once_with("CAP-PRP-001", "A control room and vessel")
    generator.specifications.save_draft.assert_not_called()


def test_empty_approved_story_description_fails_closed():
    stories = Mock()
    stories.story.return_value = _story(description="")
    generator = Mock()
    with pytest.raises(StoryBatchError, match="description is empty"):
        StoryCAPBatchService(stories, generator).preview("STORY-001", ("CAP-LOC-001",))
    generator.propose.assert_not_called()


def test_locked_story_may_be_previewed_without_writes():
    stories = Mock()
    stories.story.return_value = _story(status=StoryStatus.LOCKED)
    generator = Mock()
    generator.specifications.get.return_value = None
    generator.propose.return_value = Mock()
    result = StoryCAPBatchService(stories, generator).preview("STORY-001", ("CAP-LOC-001",))
    assert len(result.candidates) == 1
    generator.specifications.save_draft.assert_not_called()
