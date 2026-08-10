"""Validation rules for Advanced Clip Production Packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath

from .models import ClipProductionPackage, SeedPolicy


class ACPPValidationSeverity(StrEnum):
    """Severity assigned to one ACPP validation issue."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ACPPValidationIssue:
    """One machine-readable ACPP validation finding."""

    severity: ACPPValidationSeverity
    code: str
    message: str
    object_id: str | None = None


@dataclass(slots=True)
class ACPPValidationResult:
    """Complete validation result for one clip package."""

    issues: list[ACPPValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return whether no error-level issues were found."""
        return not any(issue.severity is ACPPValidationSeverity.ERROR for issue in self.issues)


class ACPPValidator:
    """Validate package integrity without compiling or rendering media."""

    def validate(self, package: ClipProductionPackage) -> ACPPValidationResult:
        """Validate one complete clip production package."""
        result = ACPPValidationResult()
        clip_id = package.identity.clip_id
        for field_name, value in (
            ("clip_id", clip_id),
            ("production_id", package.identity.production_id),
            ("episode_id", package.identity.episode_id),
            ("scene_id", package.identity.scene_id),
            ("shot_id", package.identity.shot_id),
            ("schema_version", package.schema_version),
        ):
            self._require_text(result, field_name, value, clip_id)

        if package.identity.clip_sequence_number < 1:
            self._error(
                result,
                "INVALID_CLIP_SEQUENCE",
                "Clip sequence number must be at least 1.",
                clip_id,
            )

        self._validate_render(package, result)
        self._validate_assets(package, result)
        self._validate_prompt(package, result)
        self._validate_audio(package, result)
        self._validate_output(package, result)
        self._validate_dependencies(package, result)
        return result

    @staticmethod
    def _validate_render(
        package: ClipProductionPackage,
        result: ACPPValidationResult,
    ) -> None:
        render = package.render
        clip_id = package.identity.clip_id
        for field_name, value in (
            ("width", render.width),
            ("height", render.height),
            ("frames_per_second", render.frames_per_second),
            ("frame_count", render.frame_count),
        ):
            if value <= 0:
                ACPPValidator._error(
                    result,
                    "INVALID_RENDER_VALUE",
                    f"Render field '{field_name}' must be greater than zero.",
                    clip_id,
                )
        if render.width % 2 or render.height % 2:
            ACPPValidator._error(
                result,
                "ODD_RENDER_DIMENSION",
                "Render width and height must be even numbers.",
                clip_id,
            )
        if render.seed_policy is SeedPolicy.FIXED and render.fixed_seed is None:
            ACPPValidator._error(
                result,
                "FIXED_SEED_MISSING",
                "A fixed seed policy requires fixed_seed.",
                clip_id,
            )
        if render.seed_policy is not SeedPolicy.FIXED and render.fixed_seed is not None:
            ACPPValidator._warning(
                result,
                "UNUSED_FIXED_SEED",
                "fixed_seed is ignored unless the seed policy is fixed.",
                clip_id,
            )

    @staticmethod
    def _validate_assets(
        package: ClipProductionPackage,
        result: ACPPValidationResult,
    ) -> None:
        seen: set[tuple[str, str]] = set()
        for binding in package.assets:
            if not binding.asset_id.strip():
                ACPPValidator._error(
                    result,
                    "EMPTY_ASSET_ID",
                    "Asset bindings must declare a non-empty asset ID.",
                    package.identity.clip_id,
                )
            key = (binding.asset_id, binding.role.value)
            if key in seen:
                ACPPValidator._error(
                    result,
                    "DUPLICATE_ASSET_BINDING",
                    f"Asset '{binding.asset_id}' is duplicated for role '{binding.role.value}'.",
                    package.identity.clip_id,
                )
            seen.add(key)

    @staticmethod
    def _validate_prompt(
        package: ClipProductionPackage,
        result: ACPPValidationResult,
    ) -> None:
        if not package.prompt.positive_visual_intent.strip():
            ACPPValidator._error(
                result,
                "EMPTY_VISUAL_INTENT",
                "Positive visual intent must not be empty.",
                package.identity.clip_id,
            )

    @staticmethod
    def _validate_audio(
        package: ClipProductionPackage,
        result: ACPPValidationResult,
    ) -> None:
        audio = package.audio
        if audio.voice_profile_ids and not audio.dialogue_lines:
            ACPPValidator._warning(
                result,
                "VOICE_WITHOUT_DIALOGUE",
                "Voice profiles are declared without dialogue lines.",
                package.identity.clip_id,
            )
        if len(audio.voice_profile_ids) > len(audio.dialogue_lines):
            ACPPValidator._warning(
                result,
                "EXCESS_VOICE_PROFILES",
                "More voice profiles than dialogue lines were declared.",
                package.identity.clip_id,
            )

    @staticmethod
    def _validate_output(
        package: ClipProductionPackage,
        result: ACPPValidationResult,
    ) -> None:
        output = package.output
        clip_id = package.identity.clip_id
        for field_name, value in (
            ("filename_stem", output.filename_stem),
            ("container", output.container),
        ):
            ACPPValidator._require_text(result, field_name, value, clip_id)
        path = PurePosixPath(output.relative_path.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            ACPPValidator._error(
                result,
                "UNSAFE_OUTPUT_PATH",
                "Output paths must remain relative and may not contain '..'.",
                clip_id,
            )

    @staticmethod
    def _validate_dependencies(
        package: ClipProductionPackage,
        result: ACPPValidationResult,
    ) -> None:
        clip_id = package.identity.clip_id
        if clip_id in package.dependencies:
            ACPPValidator._error(
                result,
                "SELF_DEPENDENCY",
                "A clip package may not depend on itself.",
                clip_id,
            )
        if len(set(package.dependencies)) != len(package.dependencies):
            ACPPValidator._error(
                result,
                "DUPLICATE_DEPENDENCY",
                "Clip dependencies must be unique.",
                clip_id,
            )

    @staticmethod
    def _require_text(
        result: ACPPValidationResult,
        field_name: str,
        value: str,
        object_id: str | None,
    ) -> None:
        if not value.strip():
            ACPPValidator._error(
                result,
                "REQUIRED_TEXT_MISSING",
                f"Required field '{field_name}' must not be empty.",
                object_id,
            )

    @staticmethod
    def _error(
        result: ACPPValidationResult,
        code: str,
        message: str,
        object_id: str | None,
    ) -> None:
        result.issues.append(
            ACPPValidationIssue(
                severity=ACPPValidationSeverity.ERROR,
                code=code,
                message=message,
                object_id=object_id,
            )
        )

    @staticmethod
    def _warning(
        result: ACPPValidationResult,
        code: str,
        message: str,
        object_id: str | None,
    ) -> None:
        result.issues.append(
            ACPPValidationIssue(
                severity=ACPPValidationSeverity.WARNING,
                code=code,
                message=message,
                object_id=object_id,
            )
        )
