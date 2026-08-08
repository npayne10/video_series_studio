"""Create Assets and govern their MASTER canonical references."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from vscs.application.assets.service import AssetError, AssetService
from vscs.application.caps.reference_library import ReferenceLibraryError, ReferenceLibraryService
from vscs.application.caps.reference_service import (
    CanonicalReferenceError,
    CanonicalReferenceService,
)
from vscs.application.caps.service import CAPError, CAPNotFoundError, CAPService
from vscs.domain.assets import Asset, AssetCreate, AssetUpdate
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CAPCreate,
    CAPStatus,
)


class CanonicalAssetCreationError(RuntimeError):
    """Raised when the coordinated Asset/CAP/MASTER workflow fails."""


@dataclass(frozen=True, slots=True)
class CanonicalAssetCreationResult:
    """Result of successfully creating or revising a canonical MASTER."""

    asset: Asset
    cap_asset_id: str
    reference_record_id: int
    production_reference_id: str
    lifecycle: CanonicalReferenceLifecycle


class CanonicalAssetCreationService:
    """Coordinate Asset, CAP, structured reference, and MASTER governance."""

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
        """Create a new asset and seed its authoritative MASTER."""
        self._require_confirmation(confirmed_chatgpt_master)
        master_reference = self._validate_master(master_reference)
        created_asset: Asset | None = None
        cap_created = False
        reference_record_id: int | None = None
        try:
            asset_input = asset.model_copy(update={"file_path": master_reference})
            created_asset = self.assets.create(asset_input)
            self._create_cap(created_asset)
            cap_created = True
            result = self._register_locked_master(
                created_asset,
                master_reference,
                actor=actor,
                version="1.0",
                note="Registered automatically during Asset Creation.",
            )
            reference_record_id = result.reference_record_id
            return result
        except (
            AssetError,
            CAPError,
            CanonicalReferenceError,
            ReferenceLibraryError,
            ValueError,
        ) as exc:
            self._rollback(created_asset, cap_created, reference_record_id)
            raise CanonicalAssetCreationError(str(exc)) from exc

    def set_or_revise_master(
        self,
        asset_id: str,
        master_reference: Path,
        *,
        confirmed_chatgpt_master: bool,
        actor: str = "Asset Edit",
    ) -> CanonicalAssetCreationResult:
        """Attach a missing MASTER or create a governed replacement revision."""
        self._require_confirmation(confirmed_chatgpt_master)
        master_reference = self._validate_master(master_reference)
        try:
            asset = self.assets.get(asset_id)
            self._ensure_cap(asset)
            active_entries = self.library.list_for_cap(asset.asset_id)
            master = next(
                (
                    entry
                    for entry in active_entries
                    if entry.family is CanonicalReferenceFamily.MASTER
                    and entry.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED
                ),
                None,
            )
            if master is not None:
                current = self.references.get(master.reference_record_id)
                if current.file_path == master_reference:
                    return CanonicalAssetCreationResult(
                        asset=asset,
                        cap_asset_id=asset.asset_id,
                        reference_record_id=current.id,
                        production_reference_id=master.reference_id,
                        lifecycle=master.lifecycle,
                    )
                dependants = tuple(
                    entry
                    for entry in active_entries
                    if entry.parent_reference_id == master.reference_id
                    and entry.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED
                )
                if dependants:
                    raise CanonicalAssetCreationError(
                        "The current MASTER has active derived references. Archive or migrate "
                        "those derived references before revising the MASTER."
                    )
                next_version = self._next_version(current.version)
                self.library.archive(
                    master.reference_record_id,
                    actor=actor,
                    note=f"Superseded by MASTER {next_version}",
                )
            else:
                next_version = "1.0"

            result = self._register_locked_master(
                asset,
                master_reference,
                actor=actor,
                version=next_version,
                note="Registered from Edit Asset MASTER selection.",
            )
            updated_asset = self.assets.update(
                asset.asset_id,
                AssetUpdate(file_path=master_reference),
            )
            return CanonicalAssetCreationResult(
                asset=updated_asset,
                cap_asset_id=result.cap_asset_id,
                reference_record_id=result.reference_record_id,
                production_reference_id=result.production_reference_id,
                lifecycle=result.lifecycle,
            )
        except CanonicalAssetCreationError:
            raise
        except (
            AssetError,
            CAPError,
            CanonicalReferenceError,
            ReferenceLibraryError,
            ValueError,
        ) as exc:
            raise CanonicalAssetCreationError(str(exc)) from exc

    def _register_locked_master(
        self,
        asset: Asset,
        master_reference: Path,
        *,
        actor: str,
        version: str,
        note: str,
    ) -> CanonicalAssetCreationResult:
        cap = self.caps.get(asset.asset_id)
        reference = self.references.create(
            asset.asset_id,
            CanonicalReferenceCreate(
                cap_id=cap.id,
                reference_type=CanonicalReferenceType.IMAGE,
                role=CanonicalReferenceRole.PRIMARY,
                title=f"{asset.name} — MASTER",
                file_path=master_reference,
                description="Approved ChatGPT master canonical reference",
                notes=note,
                version=version,
            ),
        )
        self.library.register_master(
            asset.asset_id,
            reference.id,
            actor=actor,
            note=f"MASTER {version} registered",
        )
        self.library.approve(
            reference.id,
            actor,
            note="Confirmed as approved ChatGPT MASTER",
        )
        entry = self.library.lock(
            reference.id,
            actor=actor,
            note=f"MASTER {version} locked",
        )
        return CanonicalAssetCreationResult(
            asset=asset,
            cap_asset_id=asset.asset_id,
            reference_record_id=reference.id,
            production_reference_id=entry.reference_id,
            lifecycle=entry.lifecycle,
        )

    def _create_cap(self, asset: Asset) -> None:
        description = asset.description.strip() or asset.name
        self.caps.create(
            CAPCreate(
                asset_id=asset.asset_id,
                title=asset.name,
                status=CAPStatus.DRAFT,
                canonical_description=description,
            )
        )

    def _ensure_cap(self, asset: Asset) -> None:
        try:
            self.caps.get(asset.asset_id)
        except CAPNotFoundError:
            self._create_cap(asset)

    @staticmethod
    def _require_confirmation(confirmed: bool) -> None:
        if not confirmed:
            raise CanonicalAssetCreationError(
                "Confirm that the selected file is the approved ChatGPT master reference"
            )

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

    @staticmethod
    def _next_version(version: str) -> str:
        try:
            major, minor = version.split(".", maxsplit=1)
            return f"{int(major)}.{int(minor) + 1}"
        except ValueError:
            return f"{version}.1"

    def _rollback(
        self,
        asset: Asset | None,
        cap_created: bool,
        reference_record_id: int | None,
    ) -> None:
        if reference_record_id is not None:
            with suppress(CanonicalReferenceError):
                self.references.unlock(reference_record_id)
            with suppress(CanonicalReferenceError):
                self.references.delete(reference_record_id)
        if cap_created and asset is not None:
            with suppress(CAPError):
                self.caps.delete(asset.asset_id)
        if asset is not None:
            with suppress(AssetError):
                self.assets.delete(asset.asset_id)
