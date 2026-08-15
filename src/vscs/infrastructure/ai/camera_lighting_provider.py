"""Structured OpenAI Camera & Lighting proposals for Phase 19.5.8."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.automation.camera_lighting import (
    CameraLightingProposalDraft,
    CameraProposalDraft,
    LightingProposalDraft,
)
from vscs.application.story import (
    CameraAngle,
    CameraMovement,
    ExposureIntent,
    KeyDirection,
    LensFamily,
    LightingIntent,
    LightQuality,
    ScreenDirection,
    ShotSize,
)
from vscs.infrastructure.ai.provider import AIProviderError


class _CameraResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shot_size: Literal[
        "extreme_wide", "wide", "medium", "medium_close", "close_up", "extreme_close_up", "insert"
    ]
    angle: Literal["eye_level", "high", "low", "over_shoulder", "top_down"]
    movement: Literal["static", "pan", "tilt", "track", "push_in", "pull_back", "crane", "orbit"]
    lens_family: Literal["ultra_wide", "wide", "normal", "portrait", "telephoto", "macro"]
    focal_length_mm: int = Field(ge=8, le=1200)
    camera_height_m: float = Field(ge=0.0, le=100.0)
    screen_direction: Literal["preserve_previous", "left_to_right", "right_to_left", "neutral"]
    composition: str = Field(min_length=1)
    focus_strategy: str = Field(min_length=1)
    movement_notes: str
    continuity_notes: str
    camera_constraints: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class _LightingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lighting_intent: Literal[
        "naturalistic", "practical_motivated", "low_key", "high_key", "silhouette"
    ]
    key_direction: Literal["motivated", "front_side", "side", "back", "top"]
    key_quality: Literal["soft", "medium", "hard"]
    color_temperature_k: int = Field(ge=1000, le=20000)
    fill_level_percent: int = Field(ge=0, le=100)
    exposure_intent: Literal[
        "balanced", "protect_highlights", "preserve_shadow_detail", "silhouette_biased"
    ]
    source_strategy: str = Field(min_length=1)
    shadow_strategy: str = Field(min_length=1)
    subject_readability: str = Field(min_length=1)
    separation_strategy: str
    continuity_notes: str
    lighting_constraints: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class _CameraLightingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera: _CameraResponse
    lighting: _LightingResponse


class OpenAICameraLightingProposalProvider:
    """Generate renderer-neutral camera/lighting intent without production authority."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("An OpenAI API key is required")
        if not model.strip():
            raise ValueError("An OpenAI model is required")
        try:
            module = import_module("openai")
            client_type = module.OpenAI
        except (ImportError, AttributeError) as exc:
            raise AIProviderError(
                'Install the VSCS AI dependency with: python -m pip install "openai>=1.68"'
            ) from exc
        self._client: Any = client_type(api_key=api_key)
        self.model_name = model

    def propose_camera_lighting(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
        performance_payload: dict[str, object],
        environment_payload: dict[str, object],
    ) -> CameraLightingProposalDraft:
        instructions = (
            "You are the VSCS Camera & Lighting production proposal layer. Propose exactly one "
            "renderer-neutral Camera contract and one renderer-neutral Lighting contract for the "
            "supplied Shot. Preserve Story facts, Shot intent, performance continuity and physical "
            "Environment. Fields constrained by the response schema are governed enum identifiers: "
            "return only one of the exact schema values for those fields. Put descriptive cinematic "
            "phrasing in composition, focus_strategy, movement_notes, continuity_notes and the "
            "lighting strategy fields, never in an enum field. Camera may decide framing, angle, "
            "physically plausible movement, lens family, focal length, camera height, screen "
            "direction, composition and focus. Lighting may decide motivated lighting intent, key "
            "direction/quality, color temperature, fill, exposure priority, and source/shadow/"
            "readability/separation strategies. Do not invent plot facts, canonical asset identities, "
            "environmental physics or unsupported continuity. Do not select camera_profile_asset_id "
            "or lighting_profile_asset_id; canonical profile resolution belongs elsewhere. Do not "
            "emit renderer prompts, provider settings, Ready state or approval. Lighting must respect "
            "the physical Environment and proposed Camera."
        )
        input_text = (
            f"Story ID: {story_id}\n\nShot proposal:\n{shot_payload}\n\n"
            f"Action/Performance proposal:\n{performance_payload}\n\n"
            f"Environment proposal:\n{environment_payload}\n\nStory source:\n{source_text}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=input_text,
                text_format=_CameraLightingResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(
                f"OpenAI Camera/Lighting proposal generation failed: {exc}"
            ) from exc
        if parsed is None:
            raise AIProviderError("OpenAI Camera/Lighting proposal generation returned no result")
        if not isinstance(parsed, _CameraLightingResponse):
            parsed = _CameraLightingResponse.model_validate(parsed)
        try:
            camera = CameraProposalDraft(
                shot_size=ShotSize(parsed.camera.shot_size),
                angle=CameraAngle(parsed.camera.angle),
                movement=CameraMovement(parsed.camera.movement),
                lens_family=LensFamily(parsed.camera.lens_family),
                focal_length_mm=parsed.camera.focal_length_mm,
                camera_height_m=parsed.camera.camera_height_m,
                screen_direction=ScreenDirection(parsed.camera.screen_direction),
                composition=parsed.camera.composition,
                focus_strategy=parsed.camera.focus_strategy,
                movement_notes=parsed.camera.movement_notes,
                continuity_notes=parsed.camera.continuity_notes,
                camera_constraints=tuple(parsed.camera.camera_constraints),
                confidence=parsed.camera.confidence,
            )
            lighting = LightingProposalDraft(
                lighting_intent=LightingIntent(parsed.lighting.lighting_intent),
                key_direction=KeyDirection(parsed.lighting.key_direction),
                key_quality=LightQuality(parsed.lighting.key_quality),
                color_temperature_k=parsed.lighting.color_temperature_k,
                fill_level_percent=parsed.lighting.fill_level_percent,
                exposure_intent=ExposureIntent(parsed.lighting.exposure_intent),
                source_strategy=parsed.lighting.source_strategy,
                shadow_strategy=parsed.lighting.shadow_strategy,
                subject_readability=parsed.lighting.subject_readability,
                separation_strategy=parsed.lighting.separation_strategy,
                continuity_notes=parsed.lighting.continuity_notes,
                lighting_constraints=tuple(parsed.lighting.lighting_constraints),
                confidence=parsed.lighting.confidence,
            )
        except ValueError as exc:
            raise AIProviderError(
                f"OpenAI Camera/Lighting proposal used an invalid governed enum: {exc}"
            ) from exc
        return CameraLightingProposalDraft(camera=camera, lighting=lighting)
