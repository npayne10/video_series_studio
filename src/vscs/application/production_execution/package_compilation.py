"""Provider-neutral production execution package compilation for Phase 20.15.1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.governed_reference_plan_source import (
    GovernedReferencePlanSourceError,
    PersistedGovernedReferencePlanSource,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)

from .governed_reference_compilation import (
    GovernedReferenceCompilationError,
    GovernedReferenceCompiler,
)
from .introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeRequirementCompiler,
)
from .internal_render_spans import (
    GovernedInternalRenderSpanCompiler,
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from .provider_prompt import ProductionProviderPromptCompiler, ProductionProviderPromptError
from .timed_reference_activation import (
    TimedCanonicalReferenceActivationCompiler,
    TimedCanonicalReferenceActivationError,
)


class ProductionPackageCompilationError(RuntimeError):
    """Raised when approved production authority cannot be compiled safely."""


class _ReferencePlanProjectDirectory:
    """Minimal ProjectService-compatible view for persisted reference authority."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory


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
    cfg: float
    ic_lora_strength: float
    seed: int
    composition_plan: dict[str, Any]
    production_authority: dict[str, Any]
    package_fingerprint: str
    timed_asset_presence: dict[str, Any] | None = None
    internal_render_spans: dict[str, Any] | None = None
    timed_reference_activation: dict[str, Any] | None = None
    reference_plan: dict[str, Any] | None = None
    motion_prompt: str = ""
    omitted_provider_prompt_sections: tuple[str, ...] = ()
    introduction_keyframe_requirements: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible provider-neutral content."""
        payload = {
            "schema_version": "1.0",
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
                "motion_prompt": self.motion_prompt,
                "omitted_optional_sections": list(self.omitted_provider_prompt_sections),
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
                "cfg": self.cfg,
                "ic_lora_strength": self.ic_lora_strength,
                "seed": self.seed,
            },
            "composition_plan": self.composition_plan,
            "production_authority": self.production_authority,
            "package_fingerprint": self.package_fingerprint,
        }
        if self.timed_asset_presence is not None:
            payload["timed_asset_presence"] = self.timed_asset_presence
        if self.internal_render_spans is not None:
            payload["internal_render_spans"] = self.internal_render_spans
        if self.timed_reference_activation is not None:
            payload["timed_reference_activation"] = self.timed_reference_activation
        if self.reference_plan is not None:
            payload["reference_plan"] = self.reference_plan
        if self.introduction_keyframe_requirements is not None:
            payload["introduction_keyframe_requirements"] = (
                self.introduction_keyframe_requirements
            )
        return payload


class ProductionPackageCompilerService:
    """Compile one approved Phase 19 ProductionPackage for deterministic execution."""

    def __init__(self, *, reference_root: Path | None = None) -> None:
        self.reference_compiler = GovernedReferenceCompiler(reference_root)
        self.provider_prompt_compiler = ProductionProviderPromptCompiler()
        self.reference_plan_source = (
            PersistedGovernedReferencePlanSource(
                _ReferencePlanProjectDirectory(reference_root)  # type: ignore[arg-type]
            )
            if reference_root is not None
            else None
        )

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
        timed_asset_presence = self._timed_asset_presence(
            production,
            shot_id=source.shot_id,
            frames_per_second=render["frames_per_second"],
            frame_count=render["frame_count"],
        )
        internal_render_spans = self._internal_render_spans(timed_asset_presence)
        reference_plan_payload = self._reference_plan_payload(production, source.shot_id)
        try:
            governed_references = self.reference_compiler.compile(
                reference_plan_payload,
                width=render["width"],
                height=render["height"],
                profile=normalized_profile,
            )
        except GovernedReferenceCompilationError as exc:
            raise ProductionPackageCompilationError(
                f"Governed reference compilation failed: {exc}"
            ) from exc
        reference_plan = governed_references.to_dict() if governed_references is not None else None
        timed_reference_activation = self._timed_reference_activation(
            timed_asset_presence,
            internal_render_spans,
            reference_plan,
        )
        introduction_keyframe_requirements = self._introduction_keyframe_requirements(
            internal_render_spans,
            timed_reference_activation,
        )

        try:
            provider_prompt = self.provider_prompt_compiler.compile(production)
        except ProductionProviderPromptError as exc:
            raise ProductionPackageCompilationError(
                f"Provider prompt compilation failed: {exc}"
            ) from exc
        positive_prompt = provider_prompt.positive_prompt
        negative_prompt = provider_prompt.negative_prompt
        motion_prompt = provider_prompt.motion_prompt
        omitted_provider_prompt_sections = provider_prompt.omitted_optional_sections
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
        if timed_asset_presence is not None:
            composition_plan["timed_asset_presence"] = timed_asset_presence
        if internal_render_spans is not None:
            composition_plan["internal_render_spans"] = internal_render_spans
        if timed_reference_activation is not None:
            composition_plan["timed_reference_activation"] = timed_reference_activation
        if reference_plan is not None:
            composition_plan["reference_plan"] = reference_plan
        if introduction_keyframe_requirements is not None:
            composition_plan["introduction_keyframe_requirements"] = (
                introduction_keyframe_requirements
            )

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
            "motion_prompt": motion_prompt,
            "omitted_provider_prompt_sections": omitted_provider_prompt_sections,
            "previous_frame": previous_frame,
            "filename_prefix": filename_prefix,
            "render": render,
            "seed": seed,
            "composition_plan": composition_plan,
            "production_authority": production,
            "timed_asset_presence": timed_asset_presence,
            "internal_render_spans": internal_render_spans,
            "timed_reference_activation": timed_reference_activation,
            "reference_plan": reference_plan,
            "introduction_keyframe_requirements": introduction_keyframe_requirements,
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
            cfg=render["cfg"],
            ic_lora_strength=render["ic_lora_strength"],
            seed=seed,
            composition_plan=composition_plan,
            production_authority=production,
            package_fingerprint=package_fingerprint,
            timed_asset_presence=timed_asset_presence,
            internal_render_spans=internal_render_spans,
            timed_reference_activation=timed_reference_activation,
            reference_plan=reference_plan,
            motion_prompt=motion_prompt,
            omitted_provider_prompt_sections=omitted_provider_prompt_sections,
            introduction_keyframe_requirements=introduction_keyframe_requirements,
        )

    def _timed_asset_presence(
        self,
        production: dict[str, Any],
        *,
        shot_id: str,
        frames_per_second: int,
        frame_count: int,
    ) -> dict[str, Any] | None:
        raw = production.get("timed_asset_presence")
        if raw in (None, {}, []):
            return None
        if not isinstance(raw, dict):
            raise ProductionPackageCompilationError(
                "Timed Asset Presence authority must be a structured object"
            )
        try:
            plan = TimedAssetPresencePlan.from_dict(raw)
            plan.require_execution_timing(
                shot_id=shot_id,
                frames_per_second=frames_per_second,
                frame_count=frame_count,
            )
            plan.require_governed_assets(
                self._governed_asset_ids(self._list_of_mappings(production.get("assets")))
            )
        except TimedAssetPresenceError as exc:
            raise ProductionPackageCompilationError(
                f"Timed Asset Presence authority cannot compile: {exc}"
            ) from exc
        return plan.to_dict()

    @staticmethod
    def _internal_render_spans(
        timed_asset_presence: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if timed_asset_presence is None:
            return None
        try:
            source = TimedAssetPresencePlan.from_dict(timed_asset_presence)
            plan = GovernedInternalRenderSpanCompiler().compile(source)
            plan.require_source(source)
        except (TimedAssetPresenceError, GovernedInternalRenderSpanError) as exc:
            raise ProductionPackageCompilationError(
                f"Governed Internal Render Span authority cannot compile: {exc}"
            ) from exc
        return plan.to_dict()

    @staticmethod
    def _timed_reference_activation(
        timed_asset_presence: dict[str, Any] | None,
        internal_render_spans: dict[str, Any] | None,
        reference_plan: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if timed_asset_presence is None or internal_render_spans is None:
            return None
        try:
            timed = TimedAssetPresencePlan.from_dict(timed_asset_presence)
            spans = GovernedInternalRenderSpanPlan.from_dict(internal_render_spans)
            plan = TimedCanonicalReferenceActivationCompiler().compile(
                timed,
                spans,
                reference_plan,
            )
            plan.require_sources(timed, spans, reference_plan)
        except (
            TimedAssetPresenceError,
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
        ) as exc:
            raise ProductionPackageCompilationError(
                f"Timed Canonical Reference Activation authority cannot compile: {exc}"
            ) from exc
        return plan.to_dict()

    @staticmethod
    def _introduction_keyframe_requirements(
        internal_render_spans: dict[str, Any] | None,
        timed_reference_activation: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if internal_render_spans is None or timed_reference_activation is None:
            return None
        try:
            spans = GovernedInternalRenderSpanPlan.from_dict(internal_render_spans)
            activation = TimedCanonicalReferenceActivationPlan.from_dict(
                timed_reference_activation
            )
            plan = GovernedIntroductionKeyframeRequirementCompiler().compile(
                spans,
                activation,
            )
            plan.require_sources(spans, activation)
        except (
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
            GovernedIntroductionKeyframeError,
        ) as exc:
            raise ProductionPackageCompilationError(
                f"Governed Introduction Keyframe requirements cannot compile: {exc}"
            ) from exc
        return plan.to_dict()

    def _reference_plan_payload(
        self, production: dict[str, Any], shot_id: str
    ) -> dict[str, Any] | None:
        embedded = production.get("reference_plan")
        if isinstance(embedded, dict):
            return self._require_usable_reference_plan(embedded, shot_id)

        persisted = None
        if self.reference_plan_source is not None:
            try:
                persisted = self.reference_plan_source.reference_plan_for_shot(shot_id)
            except GovernedReferencePlanSourceError as exc:
                raise ProductionPackageCompilationError(
                    f"Governed reference authority cannot be resolved: {exc}"
                ) from exc
        if persisted is not None:
            return self._require_usable_reference_plan(persisted, shot_id)

        canonical_references = self._list_of_mappings(production.get("canonical_references"))
        if canonical_references:
            raise ProductionPackageCompilationError(
                f"Governed reference authority is required for {shot_id.strip().upper()} because "
                "approved canonical visual references are present, but no provider-ready governed "
                "ReferencePlan has been persisted. Resolve and persist governed provider-ready "
                "reference authority before Production Package compilation."
            )
        return None

    @staticmethod
    def _require_usable_reference_plan(
        reference_plan: dict[str, Any], shot_id: str
    ) -> dict[str, Any]:
        status = str(reference_plan.get("status") or "").strip().lower()
        if status and status != "passed":
            diagnostics_raw = reference_plan.get("diagnostics", [])
            diagnostics: list[str] = []
            if isinstance(diagnostics_raw, list):
                for item in diagnostics_raw:
                    if not isinstance(item, dict):
                        continue
                    code = str(item.get("code") or "").strip()
                    message = str(item.get("message") or "").strip()
                    detail = ": ".join(value for value in (code, message) if value)
                    if detail:
                        diagnostics.append(detail)
            suffix = f" Diagnostics: {'; '.join(diagnostics)}" if diagnostics else ""
            raise ProductionPackageCompilationError(
                f"Governed ReferencePlan for {shot_id.strip().upper()} has status '{status}' and "
                f"cannot be used for provider execution.{suffix}"
            )
        return reference_plan

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
        action_performance = cls._mapping(production.get("action_performance"))
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

        explicit_frames = cls._optional_positive_int(render, ("frame_count", "frames"))
        if explicit_frames is None:
            explicit_frames = cls._optional_positive_int(shot, ("frame_count", "frames"))
        if explicit_frames is not None:
            frames = explicit_frames
        else:
            runtime_seconds = cls._optional_positive_float(
                shot,
                ("target_runtime_seconds", "runtime_seconds", "duration_seconds"),
            )
            if runtime_seconds is None:
                runtime_seconds = cls._optional_positive_float(
                    action_performance,
                    ("target_runtime_seconds", "runtime_seconds", "duration_seconds"),
                )
            frames = (
                max(1, round(runtime_seconds * fps))
                if runtime_seconds is not None
                else default_frames
            )

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
            "cfg": cfg,
            "ic_lora_strength": strength,
        }

    @staticmethod
    def _negative_prompt(value: object) -> str:
        style = ProductionPackageCompilerService._mapping(value)
        collected: list[str] = []
        for key in ("negative_constraints", "avoid", "forbidden", "negative_prompt"):
            raw = style.get(key)
            if isinstance(raw, str) and raw.strip():
                collected.append(raw.strip())
            elif isinstance(raw, list):
                collected.extend(str(item).strip() for item in raw if str(item).strip())
        return "; ".join(dict.fromkeys(collected))

    @staticmethod
    def _governed_asset_ids(assets: list[dict[str, Any]]) -> set[str]:
        governed: set[str] = set()
        for item in assets:
            candidates: list[object] = [item.get("asset_id")]
            for section_name in ("production", "resolution", "binding", "governed"):
                section = item.get(section_name)
                if isinstance(section, dict):
                    candidates.append(section.get("asset_id"))
            for candidate in candidates:
                value = str(candidate or "").strip().upper()
                if value:
                    governed.add(value)
        return governed

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
    def _positive_int(value: dict[str, Any], keys: tuple[str, ...], default: int) -> int:
        resolved = ProductionPackageCompilerService._optional_positive_int(value, keys)
        return resolved if resolved is not None else default

    @staticmethod
    def _optional_positive_int(value: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
                return raw
        return None

    @staticmethod
    def _positive_float(value: dict[str, Any], keys: tuple[str, ...], default: float) -> float:
        resolved = ProductionPackageCompilerService._optional_positive_float(value, keys)
        return resolved if resolved is not None else default

    @staticmethod
    def _optional_positive_float(value: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, int | float) and not isinstance(raw, bool) and raw > 0:
                return float(raw)
        return None

    @classmethod
    def _derived_seed(cls, authority_fingerprint: str, profile: str) -> int:
        digest = hashlib.sha256(f"{authority_fingerprint}:{profile}".encode()).digest()
        return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)

    @staticmethod
    def _fingerprint(value: object) -> str:
        canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
