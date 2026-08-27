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
from .reference_roles import (
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlan,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
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
        payload: dict[str, Any] = {
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
        if package.reference_plan is not None:
            payload["reference_plan"] = _reference_plan_to_dict(package.reference_plan)
        return payload

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
        reference_plan_raw = raw.get("reference_plan")
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
            reference_plan=(
                None
                if reference_plan_raw is None
                else _reference_plan_from_dict(reference_plan_raw)
            ),
        )


def _reference_plan_to_dict(plan: ReferencePlan) -> dict[str, Any]:
    return {
        "schema_version": plan.schema_version,
        "target": {
            "width": plan.target.width,
            "height": plan.target.height,
            "profile_id": plan.target.profile_id,
            "provider_id": plan.target.provider_id,
            "aspect_tolerance": plan.target.aspect_tolerance,
        },
        "references": [
            {
                "reference_id": reference.reference_id,
                "asset_id": reference.asset_id,
                "role": reference.role.value,
                "reference_class": reference.reference_class.value,
                "priority": reference.priority.value,
                "subject_type": reference.subject_type.value,
                "source_path": reference.source_path,
                "canonical_source_id": reference.canonical_source_id,
                "label": reference.label,
                "width": reference.width,
                "height": reference.height,
                "provider_ready": reference.provider_ready,
                "provider_profiles": list(reference.provider_profiles),
                "coverage": {
                    "framing_type": reference.coverage.framing_type,
                    "coverage": reference.coverage.coverage,
                    "required_features_visible": reference.coverage.required_features_visible,
                    "identity_visible": reference.coverage.identity_visible,
                    "full_required_asset_visible": reference.coverage.full_required_asset_visible,
                },
                "reference_fingerprint": reference.reference_fingerprint,
                "file_checksum": reference.file_checksum,
                "contains_subjects": list(reference.contains_subjects),
                "contains_props": list(reference.contains_props),
                "contains_environments": list(reference.contains_environments),
            }
            for reference in plan.references
        ],
    }


def _reference_plan_from_dict(raw: Any) -> ReferencePlan:
    if not isinstance(raw, dict):
        raise TypeError("reference_plan must be an object")
    target = raw["target"]
    references = raw.get("references", [])
    return ReferencePlan(
        schema_version=str(raw.get("schema_version", "1.0")),
        target=ReferenceTarget(
            width=int(target["width"]),
            height=int(target["height"]),
            profile_id=str(target["profile_id"]),
            provider_id=_optional_text(target.get("provider_id")),
            aspect_tolerance=float(target.get("aspect_tolerance", 0.03)),
        ),
        references=tuple(_shot_reference_from_dict(reference) for reference in references),
    )


def _shot_reference_from_dict(raw: Any) -> ShotReference:
    if not isinstance(raw, dict):
        raise TypeError("reference entry must be an object")
    coverage = raw.get("coverage", {})
    return ShotReference(
        reference_id=str(raw["reference_id"]),
        asset_id=_optional_text(raw.get("asset_id")),
        role=ReferenceRole(str(raw["role"])),
        reference_class=ReferenceClass(str(raw["reference_class"])),
        priority=ReferencePriority(str(raw["priority"])),
        subject_type=ReferenceSubjectType(str(raw["subject_type"])),
        source_path=str(raw["source_path"]),
        canonical_source_id=_optional_text(raw.get("canonical_source_id")),
        label=str(raw.get("label", "")),
        width=int(raw.get("width", 0)),
        height=int(raw.get("height", 0)),
        provider_ready=bool(raw.get("provider_ready", False)),
        provider_profiles=tuple(str(value) for value in raw.get("provider_profiles", [])),
        coverage=ReferenceCoverage(
            framing_type=str(coverage.get("framing_type", "unknown")),
            coverage=str(coverage.get("coverage", "unknown")),
            required_features_visible=bool(coverage.get("required_features_visible", True)),
            identity_visible=bool(coverage.get("identity_visible", True)),
            full_required_asset_visible=bool(coverage.get("full_required_asset_visible", True)),
        ),
        reference_fingerprint=_optional_text(raw.get("reference_fingerprint")),
        file_checksum=_optional_text(raw.get("file_checksum")),
        contains_subjects=tuple(str(value) for value in raw.get("contains_subjects", [])),
        contains_props=tuple(str(value) for value in raw.get("contains_props", [])),
        contains_environments=tuple(str(value) for value in raw.get("contains_environments", [])),
    )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
