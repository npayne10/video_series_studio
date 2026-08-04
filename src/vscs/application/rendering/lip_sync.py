"""Renderer-neutral lip-sync contracts and validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .voice import DialogueCue


class LipSyncMode(StrEnum):
    """Supported visible-dialogue production modes."""

    NONE = "none"
    OFF_SCREEN = "off_screen"
    SINGLE_SPEAKER = "single_speaker"
    ALTERNATING_SPEAKERS = "alternating_speakers"
    MULTIPLE_SPEAKERS = "multiple_speakers"
    PRECISION_CLOSE_UP = "precision_close_up"


@dataclass(frozen=True, slots=True)
class LipSyncTarget:
    """One visible target mapped to its speaking character."""

    target_id: str
    character_asset_id: str
    face_reference_ids: tuple[str, ...] = ()
    track_id: str | None = None

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("target_id is required")
        if not self.character_asset_id.strip():
            raise ValueError("character_asset_id is required")


@dataclass(frozen=True, slots=True)
class LipSyncRequest:
    """Post-generation request for applying dialogue to visible targets."""

    request_id: str
    production_id: str
    scene_id: str
    shot_id: str
    clip_id: str
    mode: LipSyncMode
    source_video_path: str
    output_directory: str
    dialogue_cues: tuple[DialogueCue, ...] = ()
    targets: tuple[LipSyncTarget, ...] = ()
    audio_reference_ids: tuple[str, ...] = ()
    precision_required: bool = False
    version: str = "1.0"

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("production_id", self.production_id),
            ("scene_id", self.scene_id),
            ("shot_id", self.shot_id),
            ("clip_id", self.clip_id),
            ("source_video_path", self.source_video_path),
            ("output_directory", self.output_directory),
            ("version", self.version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        self._validate_path("source_video_path", self.source_video_path)
        self._validate_path("output_directory", self.output_directory)
        target_ids = [target.target_id for target in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("lip-sync target IDs must be unique")
        self._validate_mode()
        self._validate_cue_targets()

    @staticmethod
    def _validate_path(name: str, value: str) -> None:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError(f"{name} must remain project-relative")

    def _validate_mode(self) -> None:
        visible_cues = tuple(
            cue for cue in self.dialogue_cues if not cue.off_screen
        )
        if self.mode is LipSyncMode.NONE:
            if self.dialogue_cues or self.targets or self.audio_reference_ids:
                raise ValueError(
                    "none lip-sync mode may not declare dialogue inputs"
                )
            return
        if self.mode is LipSyncMode.OFF_SCREEN:
            if any(not cue.off_screen for cue in self.dialogue_cues):
                raise ValueError(
                    "off-screen mode requires every cue to be off-screen"
                )
            if self.targets:
                raise ValueError(
                    "off-screen mode may not declare visible targets"
                )
            return
        if not visible_cues:
            raise ValueError(
                "visible lip-sync modes require at least one visible cue"
            )
        if not self.targets:
            raise ValueError(
                "visible lip-sync modes require at least one target"
            )
        speaker_ids = {cue.character_asset_id for cue in visible_cues}
        single_modes = {
            LipSyncMode.SINGLE_SPEAKER,
            LipSyncMode.PRECISION_CLOSE_UP,
        }
        if (
            self.mode in single_modes
            and (len(speaker_ids) != 1 or len(self.targets) != 1)
        ):
            raise ValueError(
                "single-speaker modes require one speaker and one target"
        )        
        if (
            self.mode is LipSyncMode.ALTERNATING_SPEAKERS
            and len(speaker_ids) < 2
        ):
            raise ValueError(
                "alternating-speaker mode requires at least two speakers"
            )
        if (
            self.mode is LipSyncMode.MULTIPLE_SPEAKERS
            and len(speaker_ids) < 2
        ):
            raise ValueError(
                "multiple-speaker mode requires at least two speakers"
            )
        if (
            self.mode is LipSyncMode.PRECISION_CLOSE_UP
            and not self.precision_required
        ):
            raise ValueError(
                "precision close-up mode requires precision_required"
            )

    def _validate_cue_targets(self) -> None:
        targets_by_character = {
            target.character_asset_id: target.target_id
            for target in self.targets
        }
        for cue in self.dialogue_cues:
            if cue.off_screen:
                continue
            expected = targets_by_character.get(cue.character_asset_id)
            if expected is None:
                raise ValueError(
                    f"no lip-sync target exists for {cue.character_asset_id}"
                )
            if cue.face_target_id is not None and cue.face_target_id != expected:
                raise ValueError(
                    f"dialogue cue {cue.cue_id} uses the wrong target"
                )

    @property
    def requires_lip_sync(self) -> bool:
        """Return whether this request needs a visible lip-sync pass."""
        return self.mode not in {
            LipSyncMode.NONE,
            LipSyncMode.OFF_SCREEN,
        }


@dataclass(frozen=True, slots=True)
class LipSyncValidation:
    """Machine-readable compatibility result for one request."""

    passed: bool
    issues: tuple[str, ...] = ()


class LipSyncContractValidator:
    """Validate workflow support against a lip-sync request."""

    def validate_capabilities(
        self,
        request: LipSyncRequest,
        *,
        supports_lip_sync: bool,
        supports_multiple_speakers: bool,
        supports_precision_close_up: bool,
    ) -> LipSyncValidation:
        """Return capability findings without invoking a renderer."""
        issues: list[str] = []
        if request.requires_lip_sync and not supports_lip_sync:
            issues.append("workflow does not support lip-sync")
        multi_modes = {
            LipSyncMode.ALTERNATING_SPEAKERS,
            LipSyncMode.MULTIPLE_SPEAKERS,
        }
        if request.mode in multi_modes and not supports_multiple_speakers:
            issues.append("workflow does not support multiple speakers")
        if (
            request.mode is LipSyncMode.PRECISION_CLOSE_UP
            and not supports_precision_close_up
        ):
            issues.append(
                "workflow does not support precision close-up lip-sync"
            )
        return LipSyncValidation(
            passed=not issues,
            issues=tuple(issues),
        )
