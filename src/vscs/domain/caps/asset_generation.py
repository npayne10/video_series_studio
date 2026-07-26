"""Domain models for canonical reference image generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CanonicalAssetGenerationRequest(BaseModel):
    """Validated request for one or more canonical image candidates."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    model: str = Field(default="VSCS Local Preview", min_length=1, max_length=200)
    seed: int = Field(default=0, ge=0)
    width: int = Field(default=1280, ge=256, le=8192)
    height: int = Field(default=720, ge=256, le=8192)
    variations: int = Field(default=1, ge=1, le=12)


class GeneratedCanonicalAsset(BaseModel):
    """Provider-neutral generated image payload and provenance."""

    filename: str
    media_type: str = "image/svg+xml"
    content: bytes
    prompt: str
    negative_prompt: str = ""
    model: str
    seed: int
    width: int
    height: int
