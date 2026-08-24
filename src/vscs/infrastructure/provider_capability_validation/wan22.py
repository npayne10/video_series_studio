"""Wan 2.2 capability-validation pack at the provider edge."""

from vscs.domain.provider_capability_validation import ProviderCapabilityValidationPack

from .video_validation import standard_video_validation_scenarios


def wan22_video_validation_pack() -> ProviderCapabilityValidationPack:
    """Return the governed Wan 2.2 video-generation validation definition."""

    return ProviderCapabilityValidationPack(
        pack_id="wan-2.2-video-v1",
        provider_family="wan",
        capability_id="video-generation.wan-2.2",
        version="1.0",
        scenarios=standard_video_validation_scenarios(),
    )
