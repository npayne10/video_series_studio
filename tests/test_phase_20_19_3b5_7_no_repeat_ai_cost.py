"""Cost guard: Story fingerprint checks do not require CAP provider calls."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.story_batch import StoryBatchError, StoryCAPBatchService
from vscs.application.story.lifecycle import StoryStatus


def test_story_authority_fingerprint_requires_no_ai_provider():
    stories = Mock()
    stories.story.return_value = SimpleNamespace(
        story_id="STORY-001",
        title="The Quiet Console",
        description="Control room with a diagnostic console.",
        status=StoryStatus.APPROVED,
    )
    generator = Mock()
    batch = StoryCAPBatchService(stories, generator)
    first = batch.current_story_fingerprint("STORY-001")
    assert len(first) == 64
    assert first == batch.current_story_fingerprint("STORY-001")
    generator.propose.assert_not_called()


def test_story_status_change_rejected_without_provider():
    stories = Mock()
    stories.story.return_value = SimpleNamespace(
        story_id="STORY-001", title="Title", description="Context", status=StoryStatus.DRAFT
    )
    generator = Mock()
    with pytest.raises(StoryBatchError, match="Approved or Locked"):
        StoryCAPBatchService(stories, generator).current_story_fingerprint("STORY-001")
    generator.propose.assert_not_called()


def test_title_or_description_change_invalidates_fingerprint():
    story = SimpleNamespace(
        story_id="STORY-001", title="Original", description="Context", status=StoryStatus.APPROVED
    )
    stories = Mock()
    stories.story.return_value = story
    batch = StoryCAPBatchService(stories, Mock())
    original = batch.current_story_fingerprint("STORY-001")
    story.description = "Changed context"
    assert original != batch.current_story_fingerprint("STORY-001")
