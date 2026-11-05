"""B.5.26 local image candidates from governed reviewed CAP design.

A candidate PNG is *not* a reference-library MASTER and is never approved here.
The existing XCIC/ComfyUI provider performs actual rendering only after a user action.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.reference_templates import CategoryReferenceTemplateService
from vscs.application.caps.visual_identity_preparation import (
    VisualIdentityPreparation,
    prepare_visual_identity,
)
from vscs.domain.caps import (
    CanonicalAssetGenerationRequest,
    CanonicalReferenceCreate,
    GeneratedCanonicalAsset,
    CanonicalReferenceRole,
    CanonicalReferenceType,
)
from vscs.infrastructure.ai.image_provider import CanonicalImageGenerationProvider
from vscs.infrastructure.xcic import XCICImageProvider

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class VisualCandidateGenerationError(RuntimeError):
    """A non-authoritative visual candidate could not safely be generated."""


class VisualCandidateGenerationService:
    """Generate one local candidate from a validated, unchanged reviewed CAP snapshot."""

    def __init__(
        self,
        references: CanonicalReferenceService,
        provider_factory: Callable[[Path], CanonicalImageGenerationProvider] = XCICImageProvider,
    ) -> None:
        self.references = references
        self.provider_factory = provider_factory
        self.library = ReferenceLibraryService(references)
        self.templates = CategoryReferenceTemplateService(references, self.library)

    def prepare(self, asset_id: str) -> VisualIdentityPreparation:
        cap = self.references.caps.get(asset_id)
        asset = self.references.caps.assets.get(asset_id)
        coverage = self.templates.coverage(asset_id)
        preparation = prepare_visual_identity(
            cap, coverage.template.required_views, coverage.present_views
        )
        if preparation.specification_fingerprint and preparation.category != asset.category:
            raise VisualCandidateGenerationError(
                "Reviewed CAP category does not match registered asset"
            )
        return preparation

    def generate(
        self, asset_id: str, *, seed: int = 0, width: int = 1280, height: int = 720
    ) -> int:
        """Synchronous orchestration for CLI/batch callers."""
        preparation = self.prepare(asset_id)
        project, request = self.prepare_request(
            preparation, seed=seed, width=width, height=height
        )
        rendered = self.render(preparation, project, request)
        return self.persist_candidate(preparation, project, request, rendered)

    def prepare_request(
        self,
        preparation: VisualIdentityPreparation,
        *,
        seed: int = 0,
        width: int = 1280,
        height: int = 720,
    ) -> tuple[Path, CanonicalAssetGenerationRequest]:
        if not preparation.ready_for_master_candidate:
            raise VisualCandidateGenerationError(
                "Visual candidate generation blocked: " + "; ".join(preparation.blockers)
            )
        project = self.references.caps.assets.projects.project_directory
        if project is None:
            raise VisualCandidateGenerationError("Open a VSCS project before image generation")
        project = project.resolve(strict=False)
        request = CanonicalAssetGenerationRequest(
            prompt=preparation.master_candidate_prompt,
            negative_prompt=preparation.negative_prompt,
            model="XCIC / local ComfyUI Qwen text-to-image",
            width=width,
            height=height,
            seed=seed,
            variations=1,
        )
        return project, request

    def render(
        self,
        preparation: VisualIdentityPreparation,
        project: Path,
        request: CanonicalAssetGenerationRequest,
    ) -> GeneratedCanonicalAsset:
        """Worker-safe local provider invocation: no CAP or reference writes."""
        outputs = self.provider_factory(project).generate_images(
            preparation.asset_id, preparation.title, request
        )
        if len(outputs) != 1:
            raise VisualCandidateGenerationError(
                "Local provider must return exactly one reviewable image candidate"
            )
        result = outputs[0]
        if result.media_type != "image/png" or not result.content.startswith(_PNG_SIGNATURE):
            raise VisualCandidateGenerationError(
                "Candidate provider must return a nonempty PNG image"
            )
        return result

    def persist_candidate(
        self,
        preparation: VisualIdentityPreparation,
        project: Path,
        request: CanonicalAssetGenerationRequest,
        generated: GeneratedCanonicalAsset,
    ) -> int:
        """GUI-thread phase: recheck current authority before writing Candidate only."""
        asset_id = preparation.asset_id
        if not preparation.ready_for_master_candidate:
            raise VisualCandidateGenerationError("Unreviewed CAP cannot publish a visual candidate")
        if self.prepare(asset_id) != preparation:
            raise VisualCandidateGenerationError(
                "CAP design or reference state changed during image generation; "
                "discarding stale output"
            )
        cap = self.references.caps.get(asset_id)
        root = project / "Canonical Assets" / cap.asset_id / "Images" / "Visual Candidates"
        manifest_root = project / "Canonical Assets" / cap.asset_id / ".metadata" / "visual"
        root.mkdir(parents=True, exist_ok=True)
        manifest_root.mkdir(parents=True, exist_ok=True)
        filename = f"{cap.asset_id}_visual_{uuid4().hex}.png"
        destination = root / filename
        manifest = manifest_root / f"{destination.stem}.json"
        provenance = {
            "asset_id": cap.asset_id,
            "specification_fingerprint": preparation.specification_fingerprint,
            "review_fingerprint": preparation.review_fingerprint,
            "provider": "VSCS XCIC / local ComfyUI",
            "model": generated.model,
            "seed": generated.seed,
            "width": generated.width,
            "height": generated.height,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "image_sha256": hashlib.sha256(generated.content).hexdigest(),
            "governance": "non-authoritative_candidate_not_MASTER",
        }
        reference_id: int | None = None
        try:
            destination.write_bytes(generated.content)
            manifest.write_text(
                json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8"
            )
            reference = self.references.create(
                cap.asset_id,
                CanonicalReferenceCreate(
                    cap_id=cap.id,
                    reference_type=CanonicalReferenceType.IMAGE,
                    role=CanonicalReferenceRole.SUPPLEMENTARY,
                    title=f"{cap.title} — local visual candidate",
                    file_path=destination.relative_to(project),
                    description=request.prompt,
                    notes=(
                        "B.5.26 non-authoritative local visual proposal. "
                        "NOT a ChatGPT MASTER and not approved or locked. "
                        f"Provenance: {manifest.relative_to(project)}"
                    ),
                    version=cap.version,
                ),
            )
            reference_id = reference.id
            self.references.mark_candidate(reference_id)
        except Exception:
            if reference_id is not None:
                self.references.delete(reference_id)
            destination.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
            raise
        return reference_id
