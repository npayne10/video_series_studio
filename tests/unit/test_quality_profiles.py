"""Tests for Preview and Production rendering profiles."""

from vscs.application.rendering import (
    AudioMode,
    LipSyncIntent,
    QualityLevel,
    QualityProfileRegistry,
    default_quality_profiles,
)


def test_default_profiles_define_preview_and_production() -> None:
    registry = QualityProfileRegistry(default_quality_profiles())

    preview = registry.require(QualityLevel.PREVIEW)
    production = registry.require(QualityLevel.PRODUCTION)

    assert preview.render.width < production.render.width
    assert preview.render.sampling_effort < production.render.sampling_effort
    assert not preview.render.upscale
    assert production.render.upscale
    assert preview.audio_mode is AudioMode.DRAFT
    assert production.audio_mode is AudioMode.FINAL
    assert preview.lip_sync_intent is LipSyncIntent.DRAFT
    assert production.lip_sync_intent is LipSyncIntent.FINAL
    assert registry.all() == (preview, production)
