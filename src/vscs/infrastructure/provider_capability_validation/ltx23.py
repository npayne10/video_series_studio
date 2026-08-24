"""LTX 2.3 capability-validation pack at the provider edge."""

from vscs.domain.provider_capability_validation import ProviderCapabilityValidationPack

from .video_validation import standard_video_validation_scenarios


def ltx23_video_validation_pack() -> ProviderCapabilityValidationPack:
    """Return the governed LTX 2.3 video-generation validation definition."""

    return ProviderCapabilityValidationPack(
        pack_id="ltx-2.3-video-v1",
        provider_family="ltx",
        capability_id="video-generation.ltx-2.3",
        version="1.0",
        scenarios=standard_video_validation_scenarios(),
    )
