"""Built-in provider implementations for derived production references."""

from __future__ import annotations

from html import escape
from pathlib import Path

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceRequest,
    GeneratedDerivedReference,
)


class OfflineDerivedReferencePreviewProvider:
    """Deterministic, non-production provider used for workflow validation and tests.

    It reads the MASTER file as a mandatory input and emits an SVG review card. Production
    providers must implement the same contract and use the supplied MASTER image for image-
    conditioned generation.
    """

    @property
    def name(self) -> str:
        return "VSCS Offline Derived Preview"

    @property
    def production_capable(self) -> bool:
        return False

    def generate(self, request: DerivedReferenceRequest) -> GeneratedDerivedReference:
        master = Path(request.master_path)
        master_bytes = master.read_bytes()
        if not master_bytes:
            raise ValueError("MASTER reference is empty")
        view_label = request.view.value.replace("_", " ").title()
        prompt = escape(request.prompt[:1200])
        master_name = escape(master.name)
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{request.width}" height="{request.height}" viewBox="0 0 {request.width} {request.height}">
<rect width="100%" height="100%" fill="#171b22"/>
<rect x="32" y="32" width="{request.width - 64}" height="{request.height - 64}" rx="18" fill="#232a35" stroke="#66758a" stroke-width="2"/>
<text x="64" y="92" fill="#ffffff" font-family="sans-serif" font-size="32" font-weight="700">{escape(request.title)} — {escape(view_label)}</text>
<text x="64" y="132" fill="#a9b7c9" font-family="sans-serif" font-size="18">Derived Reference Preview · MASTER input: {master_name}</text>
<foreignObject x="64" y="170" width="{request.width - 128}" height="{request.height - 270}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:sans-serif;color:#e7edf5;font-size:18px;line-height:1.45;white-space:pre-wrap;overflow:hidden">{prompt}</div>
</foreignObject>
<text x="64" y="{request.height - 64}" fill="#8391a3" font-family="sans-serif" font-size="14">Non-production preview · seed {request.seed} · MASTER bytes {len(master_bytes)}</text>
</svg>'''
        return GeneratedDerivedReference(
            filename=f"{request.asset_id}_{request.view.value}_preview.svg",
            content=svg.encode("utf-8"),
            media_type="image/svg+xml",
            provider_name=self.name,
            model="offline-preview",
            seed=request.seed,
        )
