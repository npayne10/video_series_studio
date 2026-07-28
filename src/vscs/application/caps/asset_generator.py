"""Canonical image generation orchestration and provenance storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from vscs.application.caie import CAIEError, CanonicalAssetIntelligenceEngine, CanonicalPromptContext
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.domain.caps import (
    CanonicalAssetGenerationRequest,
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)
from vscs.infrastructure.ai.image_provider import (
    CanonicalImageGenerationProvider,
    LocalPreviewImageProvider,
)
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.xcic import XCICImageProvider
from vscs.infrastructure.xcic_core import XCICCoreRenderingError


class CanonicalAssetGenerationError(RuntimeError):
    """Raised when canonical image candidates cannot be generated or stored."""


class CanonicalAssetGeneratorService:
    """Compile intelligent prompts, generate candidates, and register CAP references."""

    def __init__(
        self,
        references: CanonicalReferenceService,
        provider: CanonicalImageGenerationProvider,
        intelligence: CanonicalAssetIntelligenceEngine | None = None,
    ) -> None:
        self.references = references
        self.provider = provider
        self.intelligence = intelligence or CanonicalAssetIntelligenceEngine()
        self._logger = LoggingService.get_logger("canonical_asset_generator")

    def generate(
        self,
        asset_id: str,
        request: CanonicalAssetGenerationRequest,
    ) -> tuple[int, ...]:
        cap = self.references.caps.get(asset_id)
        asset = self.references.caps.assets.get(asset_id)
        project_directory = self.references.caps.assets.projects.project_directory
        if project_directory is None:
            raise CanonicalAssetGenerationError("Open a VSCS project before generating assets")

        try:
            package = self.intelligence.compile(
                CanonicalPromptContext(
                    asset=asset,
                    profile=cap,
                    target_model=request.model,
                )
            )
        except CAIEError as exc:
            raise CanonicalAssetGenerationError(str(exc)) from exc

        compiled_request = request.model_copy(
            update={
                "prompt": package.positive_prompt,
                "negative_prompt": package.negative_prompt,
            }
        )

        provider = self.provider
        if isinstance(provider, LocalPreviewImageProvider):
            provider = XCICImageProvider(project_directory)
        try:
            generated = provider.generate_images(asset_id, cap.title, compiled_request)
        except (XCICCoreRenderingError, OSError, ValueError) as exc:
            raise CanonicalAssetGenerationError(str(exc)) from exc
        if not generated:
            raise CanonicalAssetGenerationError("The image provider returned no generated assets")

        image_root = project_directory / "Canonical Assets" / asset_id.upper() / "Images"
        metadata_root = project_directory / "Canonical Assets" / asset_id.upper() / ".metadata" / "generation"
        image_root.mkdir(parents=True, exist_ok=True)
        metadata_root.mkdir(parents=True, exist_ok=True)

        existing = self.references.list_for_cap(asset_id)
        next_version = len(existing) + 1
        created_ids: list[int] = []
        for offset, result in enumerate(generated):
            destination = self._next_available_path(image_root / result.filename)
            destination.write_bytes(result.content)
            relative_path = destination.relative_to(project_directory)
            version = f"1.{next_version + offset}"
            generated_at = datetime.now(UTC).isoformat()
            provenance = {
                "asset_id": asset_id,
                "asset_category": asset.category.value,
                "reference_file": str(relative_path),
                "provider": "XCIC Core Rendering Library v1.0 / ComfyUI",
                "prompt_engine": "Canonical Asset Intelligence Engine v1.0",
                "style_profile": package.style_profile,
                "target_model": package.target_model,
                "prompt_warnings": list(package.warnings),
                "prompt": result.prompt,
                "negative_prompt": result.negative_prompt,
                "model": result.model,
                "seed": result.seed,
                "width": result.width,
                "height": result.height,
                "media_type": result.media_type,
                "version": version,
                "generated_at": generated_at,
            }
            manifest = metadata_root / f"{destination.stem}.generation.json"
            manifest.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
            reference = self.references.create(
                asset_id,
                CanonicalReferenceCreate(
                    cap_id=cap.id,
                    reference_type=CanonicalReferenceType.IMAGE,
                    role=CanonicalReferenceRole.SUPPLEMENTARY,
                    title=f"{cap.title} Generation {next_version + offset}",
                    file_path=relative_path,
                    description=result.prompt,
                    notes=(
                        "Generated by VSCS XCIC Core Rendering Library v1.0\n"
                        "Prompt compiled by CAIE v1.0\n"
                        f"Category: {asset.category.value}\n"
                        f"Model: {result.model}\nSeed: {result.seed}\n"
                        f"Size: {result.width}x{result.height}\n"
                        f"Provenance: {manifest.relative_to(project_directory)}"
                    ),
                    version=version,
                    status=CanonicalReferenceStatus.CANDIDATE,
                ),
            )
            reference = self.references.mark_candidate(reference.id)
            created_ids.append(reference.id)

        self._logger.info(
            "Generated %s CAIE/XCIC Core candidates for %s (%s)",
            len(created_ids),
            asset_id,
            asset.category.value,
        )
        return tuple(created_ids)

    @staticmethod
    def _next_available_path(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1
