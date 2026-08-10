"""Canonical JSON serialization for Advanced Clip Production Packages."""

from __future__ import annotations

import hashlib
import json
from typing import Any

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


class ACPPSerializationError(ValueError):
    """Raised when an ACPP payload cannot be serialized or restored."""


class ACPPSerializer:
    """Serialize packages using stable, provider-neutral JSON."""

    def dumps(self, package: ClipProductionPackage) -> str:
        """Serialize one package to canonical indented JSON."""
        return (
            json.dumps(
                self.to_dict(package),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        )

    def loads(self, payload: str) -> ClipProductionPackage:
        """Restore one package from JSON text."""
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ACPPSerializationError(f"Invalid ACPP JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ACPPSerializationError("ACPP JSON root must be an object")
        try:
            return self.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise ACPPSerializationError(f"Invalid ACPP payload: {exc}") from exc

    def checksum(self, package: ClipProductionPackage) -> str:
        """Return a stable SHA-256 checksum for package content."""
        payload = json.dumps(
            self.to_dict(package),
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def to_dict(package: ClipProductionPackage) -> dict[str, Any]:
        """Convert a package to JSON-compatible primitives."""
        return {
            "schema_version": package.schema_version,
            "identity": {
                "clip_id": package.identity.clip_id,
                "production_id": package.identity.production_id,
                "episode_id": package.identity.episode_id,
                "scene_id": package.identity.scene_id,
                "shot_id": package.identity.shot_id,
                "clip_sequence_number": package.identity.clip_sequence_number,
            },
            "render": {
                "width": package.render.width,
                "height": package.render.height,
                "frames_per_second": package.render.frames_per_second,
                "frame_count": package.render.frame_count,
                "quality_mode": package.render.quality_mode.value,
                "seed_policy": package.render.seed_policy.value,
                "fixed_seed": package.render.fixed_seed,
            },
            "assets": [
                {
                    "asset_id": binding.asset_id,
                    "role": binding.role.value,
                    "required": binding.required,
                    "canonical_reference_ids": list(binding.canonical_reference_ids),
                    "behaviour_package_ids": list(binding.behaviour_package_ids),
                }
                for binding in package.assets
            ],
            "prompt": {
                "positive_visual_intent": package.prompt.positive_visual_intent,
                "negative_constraints": list(package.prompt.negative_constraints),
                "camera_language": package.prompt.camera_language,
                "lighting_intent": package.prompt.lighting_intent,
                "behaviour_intent": package.prompt.behaviour_intent,
                "environment_intent": package.prompt.environment_intent,
                "continuity_intent": package.prompt.continuity_intent,
            },
            "continuity": {
                "incoming_clip_id": package.continuity.incoming_clip_id,
                "start_reference_id": package.continuity.start_reference_id,
                "end_reference_id": package.continuity.end_reference_id,
                "requirements": list(package.continuity.requirements),
                "outgoing_state": list(package.continuity.outgoing_state),
            },
            "audio": {
                "dialogue_lines": list(package.audio.dialogue_lines),
                "voice_profile_ids": list(package.audio.voice_profile_ids),
                "ambience_profile_id": package.audio.ambience_profile_id,
                "music_cue_id": package.audio.music_cue_id,
                "sound_effect_ids": list(package.audio.sound_effect_ids),
            },
            "output": {
                "relative_directory": package.output.relative_directory,
                "filename_stem": package.output.filename_stem,
                "container": package.output.container,
            },
            "dependencies": list(package.dependencies),
            "metadata": dict(package.metadata),
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> ClipProductionPackage:
        """Restore a package from JSON-compatible primitives."""
        identity = raw["identity"]
        render = raw["render"]
        prompt = raw["prompt"]
        continuity = raw["continuity"]
        audio = raw["audio"]
        output = raw["output"]
        assets = raw.get("assets", [])
        return ClipProductionPackage(
            identity=ClipIdentity(
                clip_id=str(identity["clip_id"]),
                production_id=str(identity["production_id"]),
                episode_id=str(identity["episode_id"]),
                scene_id=str(identity["scene_id"]),
                shot_id=str(identity["shot_id"]),
                clip_sequence_number=int(identity.get("clip_sequence_number", 1)),
            ),
            render=RenderSpecification(
                width=int(render["width"]),
                height=int(render["height"]),
                frames_per_second=int(render["frames_per_second"]),
                frame_count=int(render["frame_count"]),
                quality_mode=RenderQualityMode(str(render["quality_mode"])),
                seed_policy=SeedPolicy(str(render["seed_policy"])),
                fixed_seed=(
                    None if render.get("fixed_seed") is None else int(render["fixed_seed"])
                ),
            ),
            assets=tuple(
                AssetBinding(
                    asset_id=str(binding["asset_id"]),
                    role=AssetBindingRole(str(binding["role"])),
                    required=bool(binding.get("required", True)),
                    canonical_reference_ids=tuple(
                        str(value) for value in binding.get("canonical_reference_ids", [])
                    ),
                    behaviour_package_ids=tuple(
                        str(value) for value in binding.get("behaviour_package_ids", [])
                    ),
                )
                for binding in assets
            ),
            prompt=PromptSpecification(
                positive_visual_intent=str(prompt["positive_visual_intent"]),
                negative_constraints=tuple(
                    str(value) for value in prompt.get("negative_constraints", [])
                ),
                camera_language=str(prompt.get("camera_language", "")),
                lighting_intent=str(prompt.get("lighting_intent", "")),
                behaviour_intent=str(prompt.get("behaviour_intent", "")),
                environment_intent=str(prompt.get("environment_intent", "")),
                continuity_intent=str(prompt.get("continuity_intent", "")),
            ),
            continuity=ContinuityBinding(
                incoming_clip_id=_optional_text(continuity.get("incoming_clip_id")),
                start_reference_id=_optional_text(continuity.get("start_reference_id")),
                end_reference_id=_optional_text(continuity.get("end_reference_id")),
                requirements=tuple(str(value) for value in continuity.get("requirements", [])),
                outgoing_state=tuple(str(value) for value in continuity.get("outgoing_state", [])),
            ),
            audio=AudioSpecification(
                dialogue_lines=tuple(str(value) for value in audio.get("dialogue_lines", [])),
                voice_profile_ids=tuple(str(value) for value in audio.get("voice_profile_ids", [])),
                ambience_profile_id=_optional_text(audio.get("ambience_profile_id")),
                music_cue_id=_optional_text(audio.get("music_cue_id")),
                sound_effect_ids=tuple(str(value) for value in audio.get("sound_effect_ids", [])),
            ),
            output=OutputSpecification(
                relative_directory=str(output["relative_directory"]),
                filename_stem=str(output["filename_stem"]),
                container=str(output.get("container", "mp4")),
            ),
            schema_version=str(raw.get("schema_version", "1.0")),
            dependencies=tuple(str(value) for value in raw.get("dependencies", [])),
            metadata={str(key): str(value) for key, value in raw.get("metadata", {}).items()},
        )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
