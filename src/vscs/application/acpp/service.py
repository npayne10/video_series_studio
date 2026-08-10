"""Project-backed creation, versioning and persistence for editable ACPP records."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.shots import ProductionShot
from vscs.application.story import StoryService

from .identifiers import build_clip_id
from .models import (
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderQualityMode,
    RenderSpecification,
    SeedPolicy,
)
from .serialization import ACPPSerializationError, ACPPSerializer
from .validator import ACPPValidationResult, ACPPValidator


class ACPPEditorError(RuntimeError):
    """Raised when an editable ACPP cannot be loaded or persisted."""


class ACPPEditorService:
    """Create, save and version one ACPP per persistent production shot."""

    DIRECTORY_NAME = "acpp"

    def __init__(
        self,
        projects: ProjectService,
        stories: StoryService,
        serializer: ACPPSerializer | None = None,
        validator: ACPPValidator | None = None,
    ) -> None:
        self.projects = projects
        self.stories = stories
        self.serializer = serializer or ACPPSerializer()
        self.validator = validator or ACPPValidator()

    @property
    def package_directory(self) -> Path:
        """Return the active project's editable ACPP directory."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.DIRECTORY_NAME

    def package_path(self, clip_id: str) -> Path:
        """Return the canonical path for one current package."""
        safe = clip_id.replace("/", "-").replace("\\", "-")
        return self.package_directory / f"{safe}.json"

    def history_directory(self, clip_id: str) -> Path:
        """Return the immutable version-history directory for one package."""
        safe = clip_id.replace("/", "-").replace("\\", "-")
        return self.package_directory / "history" / safe

    def list_packages(self) -> tuple[ClipProductionPackage, ...]:
        """Load all current packages in stable clip order."""
        directory = self.package_directory
        if not directory.is_dir():
            return ()
        packages = [self._read(path) for path in sorted(directory.glob("*.json"))]
        return tuple(sorted(packages, key=lambda item: item.identity.clip_id))

    def package(self, clip_id: str) -> ClipProductionPackage | None:
        """Load one current package by clip identity."""
        path = self.package_path(clip_id)
        return self._read(path) if path.is_file() else None

    def package_for_shot(self, shot_id: str) -> ClipProductionPackage | None:
        """Return the current package associated with one shot."""
        return next(
            (package for package in self.list_packages() if package.identity.shot_id == shot_id),
            None,
        )

    def create_from_shot(self, shot: ProductionShot) -> ClipProductionPackage:
        """Create a practical editable package prefilled from a production shot."""
        scene = self.stories.scene(shot.scene_id)
        if scene is None:
            raise ACPPEditorError(f"Scene not found for shot: {shot.scene_id}")
        production_id = scene.episode_id
        clip_id = build_clip_id(
            production_id,
            scene.sequence_number,
            shot.sequence_number,
        )
        frame_count = max(1, round(shot.estimated_duration_seconds * 24))
        bindings = [
            AssetBinding(
                asset_id=scene.location_asset_id,
                role=AssetBindingRole.LOCATION,
            )
        ]
        bindings.extend(
            AssetBinding(asset_id=asset_id, role=AssetBindingRole.SUBJECT)
            for asset_id in shot.subject_asset_ids or scene.participant_asset_ids
        )
        bindings.extend(
            AssetBinding(asset_id=asset_id, role=AssetBindingRole.PROP)
            for asset_id in shot.required_asset_ids or scene.required_asset_ids
        )
        camera = " ".join(
            (
                shot.shot_size.value.replace("_", " "),
                shot.camera_movement.value.replace("_", " "),
                shot.lens_family.value.replace("_", " "),
            )
        )
        continuity = "\n".join(
            value for value in (shot.continuity_notes, shot.blocking_notes) if value
        )
        return ClipProductionPackage(
            identity=ClipIdentity(
                clip_id=clip_id,
                production_id=production_id,
                episode_id=scene.episode_id,
                scene_id=scene.scene_id,
                shot_id=shot.shot_id,
            ),
            render=RenderSpecification(
                width=1920,
                height=800,
                frames_per_second=24,
                frame_count=frame_count,
                quality_mode=RenderQualityMode.PRODUCTION,
                seed_policy=SeedPolicy.DERIVED,
            ),
            assets=tuple(dict.fromkeys(bindings)),
            prompt=PromptSpecification(
                positive_visual_intent=shot.description,
                camera_language=camera,
                lighting_intent=shot.lighting_mood.value.replace("_", " "),
                behaviour_intent=shot.blocking_notes,
                environment_intent=scene.summary,
                continuity_intent=continuity,
            ),
            continuity=ContinuityBinding(
                requirements=tuple(
                    value for value in (shot.continuity_notes, shot.blocking_notes) if value
                )
            ),
            audio=AudioSpecification(dialogue_lines=shot.dialogue_lines),
            output=OutputSpecification(
                relative_directory=f"renders/{scene.episode_id}/{scene.scene_id}",
                filename_stem=clip_id,
            ),
            metadata={
                "editor_status": "draft",
                "editor_version": "1",
                "source_shot_title": shot.title,
            },
        )

    def save(self, package: ClipProductionPackage) -> ClipProductionPackage:
        """Persist a package and archive the previous current version."""
        path = self.package_path(package.identity.clip_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = self.package(package.identity.clip_id)
        version = 1
        if previous is not None:
            version = int(previous.metadata.get("editor_version", "1")) + 1
            history = self.history_directory(package.identity.clip_id)
            history.mkdir(parents=True, exist_ok=True)
            previous_version = int(previous.metadata.get("editor_version", "1"))
            self._write(history / f"v{previous_version:04d}.json", previous)
        metadata = dict(package.metadata)
        metadata["editor_version"] = str(version)
        stored = replace(package, metadata=metadata)
        self._write(path, stored)
        return stored

    def delete(self, clip_id: str) -> bool:
        """Delete the current editable package while retaining history."""
        path = self.package_path(clip_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def validate(self, package: ClipProductionPackage) -> ACPPValidationResult:
        """Validate a package using the established ACPP validator."""
        return self.validator.validate(package)

    def versions(self, clip_id: str) -> tuple[ClipProductionPackage, ...]:
        """Return archived versions followed by the current package."""
        history = self.history_directory(clip_id)
        versions = [self._read(path) for path in sorted(history.glob("*.json"))]
        current = self.package(clip_id)
        if current is not None:
            versions.append(current)
        return tuple(versions)

    def _read(self, path: Path) -> ClipProductionPackage:
        try:
            return self.serializer.loads(path.read_text(encoding="utf-8"))
        except (OSError, ACPPSerializationError) as exc:
            raise ACPPEditorError(f"Unable to load ACPP {path.name}: {exc}") from exc

    def _write(self, path: Path, package: ClipProductionPackage) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(self.serializer.dumps(package), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise ACPPEditorError(f"Unable to save ACPP {path.name}: {exc}") from exc
