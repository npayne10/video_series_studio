import pytest

from vscs.application.generated_media import GeneratedMediaReviewActor, ReviewAuthorityType


@pytest.mark.parametrize(
    "authority_type",
    (
        ReviewAuthorityType.SYSTEM,
        ReviewAuthorityType.AUTOMATION,
        ReviewAuthorityType.PROVIDER,
    ),
)
def test_non_human_generated_media_review_authority_is_rejected(
    authority_type: ReviewAuthorityType,
) -> None:
    with pytest.raises(ValueError, match="must be human"):
        GeneratedMediaReviewActor(
            actor_id="NON-HUMAN-01",
            display_name="Non Human Actor",
            authority_type=authority_type,
        )
