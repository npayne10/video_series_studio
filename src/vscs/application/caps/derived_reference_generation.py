"""MASTER-conditioned derived production-reference generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.reference_templates import CategoryReferenceTemplateService
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CanonicalReferenceView,
    ReferenceCoverage,
)


class DerivedReferenceGenerationError(RuntimeError):
    """Raised when a governed derived reference cannot be generated."""


@dataclass(frozen=True, slots=True)
class DerivedReferenceRequest:
    """One provider-neutral, MASTER-conditioned generation request."""

    asset_id: str
    title: str
    view: CanonicalReferenceView
    master_path: Path
    prompt: str
    negative_prompt: str
    width: int = 1280
    height: int = 720
    seed: int = 0
    project_directory: Path | None = None


@dataclass(frozen=True, slots=True)
class GeneratedDerivedReference:
    """One generated image payload returned by a provider plugin."""

    filename: str
    content: bytes
    media_type: str
    provider_name: str
    model: str = ""
    seed: int = 0


class DerivedReferenceGenerator(Protocol):
    """Provider contract; implementations must use request.master_path as visual authority."""

    @property
    def name(self) -> str:
        """Human-readable provider name."""

    @property
    def production_capable(self) -> bool:
        """Whether outputs may be considered production-generation candidates."""

    def generate(self, request: DerivedReferenceRequest) -> GeneratedDerivedReference:
        """Generate one requested view using the MASTER reference as input."""


class DerivedReferenceGeneratorRegistry:
    """Small plugin-style registry for replaceable image-generation providers."""

    def __init__(self) -> None:
        self._providers: dict[str, DerivedReferenceGenerator] = {}

    def register(self, provider: DerivedReferenceGenerator) -> None:
        name = provider.name.strip()
        if not name:
            raise ValueError("Derived reference provider name is required")
        self._providers[name] = provider

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def require(self, name: str) -> DerivedReferenceGenerator:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise DerivedReferenceGenerationError(
                f"Derived reference generator is not registered: {name}"
            ) from exc


class DerivedReferenceGenerationService:
    """Generate governed Candidate views that trace directly to the locked MASTER."""

    def __init__(
        self,
        references: CanonicalReferenceService,
        library: ReferenceLibraryService,
        providers: DerivedReferenceGeneratorRegistry,
        templates: CategoryReferenceTemplateService | None = None,
    ) -> None:
        self.references = references
        self.library = library
        self.providers = providers
        self.templates = templates or CategoryReferenceTemplateService(references, library)

    def coverage(self, asset_id: str) -> ReferenceCoverage:
        """Return category-template coverage for the active CAP reference set."""
        return self.templates.coverage(asset_id)

    def generate_missing_required(
        self,
        asset_id: str,
        *,
        provider_name: str,
        actor: str = "Derived Reference Generation",
        width: int = 1280,
        height: int = 720,
        seed: int = 0,
    ) -> tuple[int, ...]:
        """Generate every currently missing required derived view for the asset category."""
        coverage = self.coverage(asset_id)
        if CanonicalReferenceView.MASTER in coverage.missing_required:
            raise DerivedReferenceGenerationError(
                "The category template requires a MASTER reference. Attach and lock the approved "
                "ChatGPT MASTER before generating derived views."
            )
        views = self.templates.missing_required_views(asset_id)
        if not views:
            return ()
        return self.generate(
            asset_id,
            views,
            provider_name=provider_name,
            actor=actor,
            width=width,
            height=height,
            seed=seed,
        )

    def generate(
        self,
        asset_id: str,
        views: tuple[CanonicalReferenceView, ...],
        *,
        provider_name: str,
        actor: str = "Derived Reference Generation",
        width: int = 1280,
        height: int = 720,
        seed: int = 0,
    ) -> tuple[int, ...]:
        """Generate selected views and register every output as a derived Candidate."""
        normalized_views = tuple(dict.fromkeys(views))
        if not normalized_views:
            raise DerivedReferenceGenerationError("Select at least one production reference view")
        if CanonicalReferenceView.MASTER in normalized_views:
            raise DerivedReferenceGenerationError("MASTER cannot be generated as a derived view")

        provider = self.providers.require(provider_name)
        cap = self.references.caps.get(asset_id)
        project = self.references.caps.assets.projects.project_directory
        if project is None:
            raise DerivedReferenceGenerationError("Open a project before generating references")
        project = project.resolve(strict=False)

        entries = self.library.list_for_cap(asset_id)
        master = next(
            (
                entry
                for entry in entries
                if entry.family is CanonicalReferenceFamily.MASTER
                and entry.lifecycle is CanonicalReferenceLifecycle.LOCKED
            ),
            None,
        )
        if master is None:
            raise DerivedReferenceGenerationError(
                "A locked ChatGPT MASTER is required before derived references can be generated"
            )
        master_record = self.references.get(master.reference_record_id)
        master_path = (project / master_record.file_path).resolve(strict=False)
        if not master_path.exists():
            raise DerivedReferenceGenerationError(
                f"MASTER reference file does not exist: {master_record.file_path}"
            )

        existing_views = {
            entry.view
            for entry in entries
            if entry.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED
        }
        duplicates = tuple(view for view in normalized_views if view in existing_views)
        if duplicates:
            labels = ", ".join(view.value for view in duplicates)
            raise DerivedReferenceGenerationError(
                f"Active derived references already exist for: {labels}. Archive or reject them first."
            )

        image_root = project / "Canonical Assets" / asset_id.upper() / "Images" / "Derived"
        image_root.mkdir(parents=True, exist_ok=True)
        created_ids: list[int] = []
        for offset, view in enumerate(normalized_views):
            request = DerivedReferenceRequest(
                asset_id=asset_id.upper(),
                title=cap.title,
                view=view,
                master_path=master_path,
                prompt=self._prompt(cap.canonical_description, cap.visual_identity, view),
                negative_prompt=self._negative_prompt(),
                width=width,
                height=height,
                seed=seed + offset,
                project_directory=project,
            )
            generated = provider.generate(request)
            suffix = Path(generated.filename).suffix or ".png"
            destination = self._destination(image_root, view, suffix)
            destination.write_bytes(generated.content)
            relative_path = destination.relative_to(project)
            family = self._family(view)
            reference = self.references.create(
                asset_id,
                CanonicalReferenceCreate(
                    cap_id=cap.id,
                    reference_type=CanonicalReferenceType.IMAGE,
                    role=CanonicalReferenceRole.SUPPLEMENTARY,
                    title=f"{cap.title} — {self._label(view)}",
                    file_path=relative_path,
                    description=request.prompt,
                    notes=(
                        "VSCS derived production reference\n"
                        f"Provider: {generated.provider_name}\n"
                        f"Model: {generated.model or 'unspecified'}\n"
                        f"MASTER: {master.reference_id}\n"
                        f"View: {view.value}\n"
                        f"Production capable provider: {provider.production_capable}"
                    ),
                    version=master_record.version,
                ),
            )
            self.references.mark_candidate(reference.id)
            self.library.register_derived(
                asset_id,
                reference.id,
                family=family,
                view=view,
                generator=generated.provider_name,
                actor=actor,
                note=f"Generated {view.value} from locked MASTER {master.reference_id}",
            )
            created_ids.append(reference.id)
        return tuple(created_ids)

    @staticmethod
    def _prompt(description: str, visual_identity: str, view: CanonicalReferenceView) -> str:
        label = DerivedReferenceGenerationService._label(view)
        visual = (
            visual_identity.strip() or "Preserve every visible canonical feature from the MASTER."
        )
        return (
            f"Using the supplied MASTER image as the absolute visual identity authority, create a "
            f"canonical {label} production reference of the exact same asset. Do not redesign, "
            f"restyle, add, remove, or reinterpret canonical features. Preserve geometry, "
            f"proportions, materials, colours, markings and identity exactly. Asset canon: "
            f"{description.strip()} Visual identity: {visual} Requested viewpoint only: {label}. "
            f"Neutral production-reference presentation, no dramatic action or scene context."
        )

    @staticmethod
    def _negative_prompt() -> str:
        return (
            "redesign, alternate asset, changed proportions, changed colours, changed markings, "
            "extra components, missing components, text overlays, cinematic action, identity drift"
        )

    @staticmethod
    def _label(view: CanonicalReferenceView) -> str:
        return view.value.replace("_", " ").title()

    @staticmethod
    def _family(view: CanonicalReferenceView) -> CanonicalReferenceFamily:
        if view is CanonicalReferenceView.DETAIL:
            return CanonicalReferenceFamily.DETAIL
        if view is CanonicalReferenceView.INTERIOR:
            return CanonicalReferenceFamily.INTERIOR
        if view is CanonicalReferenceView.VARIANT:
            return CanonicalReferenceFamily.VARIANT
        return CanonicalReferenceFamily.PRODUCTION_VIEW

    @staticmethod
    def _destination(root: Path, view: CanonicalReferenceView, suffix: str) -> Path:
        base = root / f"{view.value}{suffix.lower()}"
        if not base.exists():
            return base
        counter = 2
        while True:
            candidate = root / f"{view.value}_{counter}{suffix.lower()}"
            if not candidate.exists():
                return candidate
            counter += 1
