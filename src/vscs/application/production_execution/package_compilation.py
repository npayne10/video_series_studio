"""Provider-neutral production execution package compilation for Phase 20.15.1b."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_execution.prompt_distillation import (
    ProductionPromptDistillationService,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskState,
    ProductionTaskType,
)


class ProductionPackageCompilationError(RuntimeError):
    """Raised when approved production authority cannot be compiled safely."""


class ProductionPackageCompilationState(StrEnum):
    """Operator-visible state of the executable production package."""

    NOT_COMPILED = "not_compiled"
    COMPILED = "compiled"
    STALE = "stale"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ProductionPackageStatus:
    """Current compilation state for one ProductionTask."""

    task_id: str
    state: ProductionPackageCompilationState
    profile: str = "production"
    path: Path | None = None
    authority_fingerprint: str | None = None
    package_fingerprint: str | None = None
    source_package_id: str | None = None
    message: str = ""

    @property
    def executable(self) -> bool:
        return self.state is ProductionPackageCompilationState.COMPILED and self.path is not None


@dataclass(frozen=True, slots=True)
class CompiledProductionPackage:
    """Provider-neutral executable package compiled from approved production authority."""

    task_id: str
    production_id: str
    episode_id: str
    scene_id: str | None
    shot_id: str
    profile: str
    authority_id: str
    authority_revision: int
    authority_fingerprint: str
    approved_by: str
    source_package_id: str
    source_package_fingerprint: str
    source_schema_version: str
    universal_text: str
    positive_prompt: str
    negative_prompt: str
    previous_approved_final_frame: str | None
    filename_prefix: str
    width: int
    height: int
    frame_count: int
    frames_per_second: int
    duration_seconds: float
    cfg: float
    ic_lora_strength: float
    seed: int
    composition_plan: dict[str, Any]
    production_authority: dict[str, Any]
    package_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.2",
            "task": {
                "task_id": self.task_id,
                "production_id": self.production_id,
                "episode_id": self.episode_id,
                "scene_id": self.scene_id,
                "shot_id": self.shot_id,
            },
            "profile": self.profile,
            "authority": {
                "authority_id": self.authority_id,
                "revision": self.authority_revision,
                "fingerprint": self.authority_fingerprint,
                "approved_by": self.approved_by,
                "source_package_id": self.source_package_id,
                "source_package_fingerprint": self.source_package_fingerprint,
                "source_schema_version": self.source_schema_version,
            },
            "prompt": {
                "universal_text": self.universal_text,
                "positive_prompt": self.positive_prompt,
                "negative_prompt": self.negative_prompt,
            },
            "continuity": {
                "previous_approved_final_frame": self.previous_approved_final_frame,
            },
            "render": {
                "filename_prefix": self.filename_prefix,
                "width": self.width,
                "height": self.height,
                "frame_count": self.frame_count,
                "frames_per_second": self.frames_per_second,
                "duration_seconds": self.duration_seconds,
                "cfg": self.cfg,
                "ic_lora_strength": self.ic_lora_strength,
                "seed": self.seed,
            },
            "composition_plan": self.composition_plan,
            "production_authority": self.production_authority,
            "package_fingerprint": self.package_fingerprint,
        }


class ProductionPackageCompilerService:
    """Compile one approved Phase 19 ProductionPackage for deterministic execution."""

    def __init__(self) -> None:
        self.prompt_distiller = ProductionPromptDistillationService()

    def compile(
        self,
        task: ProductionTask,
        source: ProductionPackage,
        *,
        profile: str = "production",
    ) -> CompiledProductionPackage:
        self._require_task(task, source)
        production = source.universal_description.get("production")
        if not isinstance(production, dict):
            raise ProductionPackageCompilationError(
                "Approved Production Package has no compiled Universal Production Description"
            )
        universal_text = str(production.get("universal_text", "")).strip()
        if not universal_text:
            raise ProductionPackageCompilationError(
                "Universal Production Description has no governed production text"
            )

        normalized_profile = profile.strip().lower() or "production"
        render = self._render_settings(production, normalized_profile)
        distilled = self.prompt_distiller.distill(
            production,
            universal_text=universal_text,
            fps=render["frames_per_second"],
            duration_seconds=render["duration_seconds"],
        )
        positive_prompt = distilled.positive
        negative_prompt = distilled.negative
        continuity = self._mapping(production.get("continuity"))
        previous_frame = self._first_text(
            continuity,
            (
                "previous_approved_final_frame",
                "previous_final_frame",
                "start_reference_path",
                "start_frame_path",
                "continuity_frame_path",
            ),
        )
        composition_plan = {
            "shot_id": source.shot_id,
            "story_context": self._mapping(production.get("story_context")),
            "shot": self._mapping(production.get("shot")),
            "assets": self._list_of_mappings(production.get("assets")),
            "canonical_references": self._list_of_mappings(production.get("canonical_references")),
            "camera": self._mapping(production.get("camera")),
            "lighting": self._mapping(production.get("lighting")),
            "environment": self._mapping(production.get("environment")),
            "action_performance": self._mapping(production.get("action_performance")),
            "continuity": continuity,
            "style": self._mapping(production.get("style")),
            "dialogue": self._list_of_mappings(production.get("dialogue")),
            "effects": self._list_of_mappings(production.get("effects")),
        }
        seed = self._derived_seed(task.authority.fingerprint, normalized_profile)
        filename_prefix = f"{task.production_id}/{task.episode_id}/{task.task_id}"
        base = {
            "task_id": task.task_id,
            "profile": normalized_profile,
            "authority_fingerprint": task.authority.fingerprint,
            "source_package_fingerprint": source.package_fingerprint,
            "universal_text": universal_text,
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "previous_frame": previous_frame,
            "filename_prefix": filename_prefix,
            "render": render,
            "seed": seed,
            "composition_plan": composition_plan,
            "production_authority": production,
        }
        package_fingerprint = self._fingerprint(base)
        return CompiledProductionPackage(
            task_id=task.task_id,
            production_id=task.production_id,
            episode_id=task.episode_id,
            scene_id=task.scene_id,
            shot_id=source.shot_id,
            profile=normalized_profile,
            authority_id=task.authority.authority_id,
            authority_revision=task.authority.revision,
            authority_fingerprint=task.authority.fingerprint,
            approved_by=task.authority.approved_by or "",
            source_package_id=source.package_id,
            source_package_fingerprint=source.package_fingerprint,
            source_schema_version=source.schema_version,
            universal_text=universal_text,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            previous_approved_final_frame=previous_frame,
            filename_prefix=filename_prefix,
            width=render["width"],
            height=render["height"],
            frame_count=render["frame_count"],
            frames_per_second=render["frames_per_second"],
            duration_seconds=render["duration_seconds"],
            cfg=render["cfg"],
            ic_lora_strength=render["ic_lora_strength"],
            seed=seed,
            composition_plan=composition_plan,
            production_authority=production,
            package_fingerprint=package_fingerprint,
        )

    @classmethod
    def authority_fingerprint(cls, source: ProductionPackage) -> str:
        return cls._fingerprint(source.universal_description)

    def _require_task(self, task: ProductionTask, source: ProductionPackage) -> None:
        if task.task_type is not ProductionTaskType.VIDEO_GENERATION:
            raise ProductionPackageCompilationError(
                "Production Package compilation currently supports VIDEO_GENERATION tasks"
            )
        if task.state is not ProductionTaskState.READY:
            raise ProductionPackageCompilationError(
                f"ProductionTask must be READY before package compilation: {task.task_id}"
            )
        if not task.authority.approved:
            raise ProductionPackageCompilationError(
                "Production Package compilation requires approved human-governed authority"
            )
        if task.shot_id is None or task.shot_id.strip().upper() != source.shot_id.strip().upper():
            raise ProductionPackageCompilationError(
                "ProductionTask Shot does not match Production Package authority"
            )
        if source.validation.get("universal_description_complete") is not True:
            raise ProductionPackageCompilationError(
                "Universal Production Description authority is not compiled"
            )
        if source.validation.get("cross_authority_consistent") is not True:
            raise ProductionPackageCompilationError(
                "Production Package has unresolved cross-authority inconsistencies"
            )
        fingerprint = self.authority_fingerprint(source)
        if fingerprint != task.authority.fingerprint:
            raise ProductionPackageCompilationError(
                "Production Package authority fingerprint does not match the scheduled ProductionTask"
            )

    @classmethod
    def _render_settings(cls, production: dict[str, Any], profile: str) -> dict[str, Any]:
        render = cls._mapping(production.get("render"))
        shot = cls._mapping(production.get("shot"))
        defaults = {
            "preview": (1280, 720, 24, 145, 1.0, 0.85),
            "production": (1280, 720, 24, 145, 1.0, 1.0),
            "master": (1280, 720, 24, 145, 1.0, 1.0),
        }
        if profile not in defaults:
            raise ProductionPackageCompilationError(
                f"Unsupported production execution profile: {profile}"
            )
        width, height, fps, default_frames, cfg, strength = defaults[profile]
        width = cls._positive_int(render, ("width",), width)
        height = cls._positive_int(render, ("height",), height)
        fps = cls._positive_int(
            render,
            ("frames_per_second", "fps"),
            cls._positive_int(shot, ("frames_per_second", "fps"), fps),
        )
        duration = cls._optional_positive_float(
            render,
            ("duration_seconds", "target_runtime_seconds", "runtime_seconds"),
        )
        if duration is None:
            duration = cls._optional_positive_float(
                shot,
                ("duration_seconds", "target_runtime_seconds", "runtime_seconds"),
            )
        explicit_frames = cls._optional_positive_int(render, ("frame_count", "frames"))
        if explicit_frames is None:
            explicit_frames = cls._optional_positive_int(shot, ("frame_count", "frames"))
        if duration is not None:
            frames = max(1, round(duration * fps))
            duration_seconds = duration
        elif explicit_frames is not None:
            frames = explicit_frames
            duration_seconds = frames / fps
        else:
            frames = default_frames
            duration_seconds = frames / fps
        cfg = cls._positive_float(render, ("cfg", "guidance_scale"), cfg)
        strength = cls._positive_float(
            render,
            ("ic_lora_strength", "reference_strength"),
            strength,
        )
        return {
            "width": width,
            "height": height,
            "frames_per_second": fps,
            "frame_count": frames,
            "duration_seconds": duration_seconds,
            "cfg": cfg,
            "ic_lora_strength": strength,
        }

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _list_of_mappings(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, dict)]

    @staticmethod
    def _first_text(value: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return None

    @staticmethod
    def _optional_positive_int(value: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
                return raw
        return None

    @classmethod
    def _positive_int(cls, value: dict[str, Any], keys: tuple[str, ...], default: int) -> int:
        return cls._optional_positive_int(value, keys) or default

    @staticmethod
    def _optional_positive_float(value: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, int | float) and not isinstance(raw, bool) and raw > 0:
                return float(raw)
        return None

    @classmethod
    def _positive_float(cls, value: dict[str, Any], keys: tuple[str, ...], default: float) -> float:
        return cls._optional_positive_float(value, keys) or default

    @classmethod
    def _derived_seed(cls, authority_fingerprint: str, profile: str) -> int:
        digest = hashlib.sha256(f"{authority_fingerprint}:{profile}".encode()).digest()
        return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)

    @staticmethod
    def _fingerprint(value: object) -> str:
        canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
