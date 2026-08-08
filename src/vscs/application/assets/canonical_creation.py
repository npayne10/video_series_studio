"""Create an Asset together with its seeded CAP and MASTER canonical reference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vscs.application.assets.service import AssetError, AssetService
from vscs.application.caps import (
    CanonicalReferenceError,
    CanonicalReferenceService,
    CAPError,
    CAPService,
    ReferenceLibraryError,
    ReferenceLibraryService,
)
from vscs.domain.assets import Asset, AssetCreate
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceLifecycle,
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CAPCreate,
    CAPStatus,
)


class CanonicalAssetCreationError(RuntimeError):
    """Raised when the coordinated Asset/CAP/MASTER creation workflow fails."""


@dataclass(frozen=True, slots=True)
class CanonicalAssetCreationResult:
    """Result of successfully creating a canonically seeded asset."""

    asset: Asset
    cap_asset_id: str
    reference_record_id: int
    production_reference_id: str
    lifecycle: CanonicalReferenceLifecycle


class CanonicalAssetCreationService:
    """Coordinate Asset, CAP, structured reference, and reference-library creation."""

    def __init__(
        self,
        assets: AssetService,
        caps: CAPService,
        references: CanonicalReferenceService,
        library: ReferenceLibraryService,
    ) -> None:
        self.assets = assets
        self.caps = caps
        self.references = references
        self.library = library

    def create(
        self,
        asset: AssetCreate,
        master_reference: Path,
        *,
        confirmed_chatgpt_master: bool,
        actor: str = "Asset Creation",
    ) -> CanonicalAssetCreationResult:
        """Create a new asset and seed its canonical MASTER atomically as far as practical."""
        if not confirmed_chatgpt_master:
            raise CanonicalAssetCreationError(
                "Confirm that the selected file is the approved ChatGPT master reference"
            )
        master_reference = self._validate_master(master_reference)
        created_asset: Asset | None = None
        cap_created = False
        reference_record_id: int | None = None
        try:
            asset_input = asset.model_copy(update={"file_path": master_reference})
            created_asset = self.assets.create(asset_input)
            description = created_asset.description.strip() or created_asset.name
            self.caps.create(
                CAPCreate(
                    asset_id=created_asset.asset_id,
                    title=created_asset.name,
                    status=CAPStatus.DRAFT,
                    canonical_description=description,
                )
            )
            cap_created = True
            cap = self.caps.get(created_asset.asset_id)
            reference = self.references.create(
                created_asset.asset_id,
                CanonicalReferenceCreate(
                    cap_id=cap.id,
                    reference_type=CanonicalReferenceType.IMAGE,
                    role=CanonicalReferenceRole.PRIMARY,
                    title=f"{created_asset.name} — MASTER",
                    file_path=master_reference,
                    description="Approved ChatGPT master canonical reference",
                    notes="Registered automatically during asset creation.",
                    version="1.0",
                ),
            )
            reference_record_id = reference.id
            self.library.register_master(
                created_asset.asset_id,
                reference.id,
                actor=actor,
                note="MASTER registered from Asset Creation",
            )
            self.library.approve(
                reference.id,
                actor,
                note="Confirmed during Asset Creation",
            )
            entry = self.library.lock(
                reference.id,
                actor=actor,
                note="MASTER locked at creation",
            )
            return CanonicalAssetCreationResult(
                asset=created_asset,
                cap_asset_id=created_asset.asset_id,
                reference_record_id=reference.id,
                production_reference_id=entry.reference_id,
                lifecycle=entry.lifecycle,
            )
        except (
            AssetError,
            CAPError,
            CanonicalReferenceError,
            ReferenceLibraryError,
            ValueError,
        ) as exc:
            self._rollback(created_asset, cap_created, reference_record_id)
            raise CanonicalAssetCreationError(str(exc)) from exc

    def _validate_master(self, path: Path) -> Path:
        if not str(path).strip():
            raise CanonicalAssetCreationError("Master Canonical Reference is required")
        project = self.assets.projects.project_directory
        if project is None:
            raise CanonicalAssetCreationError("Open a project before creating an asset")
        resolved = path if path.is_absolute() else project / path
        resolved = resolved.resolve(strict=False)
        if not resolved.exists() or not resolved.is_file():
            raise CanonicalAssetCreationError(
                f"Master Canonical Reference does not exist: {resolved}"
            )
        if resolved.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise CanonicalAssetCreationError(
                "Master Canonical Reference must be a PNG, JPG, JPEG, or WebP image"
            )
        try:
            return resolved.relative_to(project.resolve(strict=False))
        except ValueError as exc:
            raise CanonicalAssetCreationError(
                "Master Canonical Reference must be inside the active project"
            ) from exc

    def _rollback(
        self,
        asset: Asset | None,
        cap_created: bool,
        reference_record_id: int | None,
    ) -> None:
        if reference_record_id is not None:
            try:
                self.references.unlock(reference_record_id)
            except CanonicalReferenceError:
                pass
            try:
                self.references.delete(reference_record_id)
            except CanonicalReferenceError:
                pass
        if cap_created and asset is not None:
            try:
                self.caps.delete(asset.asset_id)
            except CAPError:
                pass
        if asset is not None:
            try:
                self.assets.delete(asset.asset_id)
            except AssetError:
                pass
