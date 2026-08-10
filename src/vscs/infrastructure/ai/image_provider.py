"""Provider-neutral canonical image generation contracts and local preview provider."""

from __future__ import annotations

from html import escape
from typing import Protocol

from vscs.domain.caps import CanonicalAssetGenerationRequest, GeneratedCanonicalAsset


class CanonicalImageGenerationProvider(Protocol):
    """Generate canonical image candidates from a validated request."""

    def generate_images(
        self, asset_id: str, title: str, request: CanonicalAssetGenerationRequest
    ) -> tuple[GeneratedCanonicalAsset, ...]:
        """Return generated image payloads with complete provenance."""


class LocalPreviewImageProvider:
    """Deterministic offline provider that creates reviewable SVG preview cards.

    The provider keeps Phase 11.5.4 fully usable without a remote image service while
    preserving the provider contract needed by ComfyUI, OpenAI, or other generators.
    """

    def generate_images(
        self, asset_id: str, title: str, request: CanonicalAssetGenerationRequest
    ) -> tuple[GeneratedCanonicalAsset, ...]:
        values: list[GeneratedCanonicalAsset] = []
        for index in range(request.variations):
            seed = request.seed + index
            filename = f"{asset_id}_generated_{seed:010d}.svg"
            prompt = escape(request.prompt[:1200])
            negative = escape(request.negative_prompt[:600])
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{request.width}" height="{request.height}" viewBox="0 0 {request.width} {request.height}">
<rect width="100%" height="100%" fill="#171b22"/>
<rect x="32" y="32" width="{request.width - 64}" height="{request.height - 64}" rx="18" fill="#232a35" stroke="#66758a" stroke-width="2"/>
<text x="64" y="92" fill="#ffffff" font-family="sans-serif" font-size="34" font-weight="700">{escape(title)}</text>
<text x="64" y="132" fill="#a9b7c9" font-family="sans-serif" font-size="20">{escape(asset_id)} · Canonical Generation Candidate</text>
<foreignObject x="64" y="170" width="{request.width - 128}" height="{request.height - 290}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:sans-serif;color:#e7edf5;font-size:20px;line-height:1.45;white-space:pre-wrap;overflow:hidden">{prompt}</div>
</foreignObject>
<text x="64" y="{request.height - 90}" fill="#a9b7c9" font-family="sans-serif" font-size="17">Model: {escape(request.model)} · Seed: {seed} · {request.width}x{request.height}</text>
<text x="64" y="{request.height - 58}" fill="#8391a3" font-family="sans-serif" font-size="14">Negative prompt: {negative or "None"}</text>
</svg>'''
            values.append(
                GeneratedCanonicalAsset(
                    filename=filename,
                    content=svg.encode("utf-8"),
                    prompt=request.prompt,
                    negative_prompt=request.negative_prompt,
                    model=request.model,
                    seed=seed,
                    width=request.width,
                    height=request.height,
                )
            )
        return tuple(values)
