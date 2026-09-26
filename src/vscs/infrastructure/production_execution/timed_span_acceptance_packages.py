"""Build executable LTX-2.5 packages for governed internal-span acceptance runs."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirementPlan,
)
from vscs.application.production_execution.timed_reference_activation import (
    TimedCanonicalReferenceActivationError,
    TimedCanonicalReferenceActivationPlan,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)


class TimedSpanAcceptancePackageError(RuntimeError):
    """Raised when executable acceptance packages cannot be built safely."""


@dataclass(frozen=True, slots=True)
class TimedSpanAcceptancePackageSet:
    """Materialized provider packages for every governed internal render span."""

    shot_id: str
    source_package_path: Path
    source_package_fingerprint: str
    span_ids: tuple[str, ...]
    package_paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if not self.shot_id.strip():
            raise TimedSpanAcceptancePackageError("Span package set requires shot_id")
        if not self.source_package_fingerprint.strip():
            raise TimedSpanAcceptancePackageError(
                "Span package set requires source package fingerprint"
            )
        if not self.span_ids or len(self.span_ids) != len(self.package_paths):
            raise TimedSpanAcceptancePackageError(
                "Span package set requires one executable package per span"
            )


class LTX25TimedSpanAcceptancePackageBuilder:
    """Materialize isolated Candidate C packages without creating production executions."""

    SCHEMA_VERSION = "7.2.2-vscs-1"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)

    def build(self, source_package_path: Path) -> TimedSpanAcceptancePackageSet:
        """Build every governed span after all later-span keyframes are available."""
        return self._build(source_package_path, sequence_numbers=None)

    def build_span(
        self,
        source_package_path: Path,
        sequence_number: int,
    ) -> Path:
        """Build one governed span on demand for automated sequential orchestration."""
        if sequence_number <= 0:
            raise TimedSpanAcceptancePackageError("Span sequence number must be positive")
        package_set = self._build(source_package_path, sequence_numbers=(sequence_number,))
        return package_set.package_paths[0]

    def _build(
        self,
        source_package_path: Path,
        *,
        sequence_numbers: tuple[int, ...] | None,
    ) -> TimedSpanAcceptancePackageSet:
        source_path = Path(source_package_path).expanduser().resolve(strict=False)
        root = self._read(source_path)
        if root.get("schema_version") != self.SCHEMA_VERSION:
            raise TimedSpanAcceptancePackageError(
                "Timed-span acceptance requires a Candidate C LTX-2.5 Production Package"
            )
        manifest = root.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise TimedSpanAcceptancePackageError(
                "Candidate C Production Package has no compilation manifest"
            )
        source_fingerprint = str(manifest.get("package_fingerprint") or "").strip().lower()
        if not source_fingerprint:
            raise TimedSpanAcceptancePackageError(
                "Candidate C Production Package has no package fingerprint"
            )

        timed_raw = root.get("timed_asset_presence")
        spans_raw = root.get("internal_render_spans")
        activation_raw = root.get("timed_reference_activation")
        requirements_raw = root.get("introduction_keyframe_requirements")
        if not isinstance(timed_raw, dict):
            raise TimedSpanAcceptancePackageError(
                "Candidate C package has no Timed Asset Presence authority"
            )
        if not isinstance(spans_raw, dict):
            raise TimedSpanAcceptancePackageError(
                "Candidate C package has no governed internal render spans"
            )
        if not isinstance(activation_raw, dict):
            raise TimedSpanAcceptancePackageError(
                "Candidate C package has no timed canonical-reference activation"
            )
        if not isinstance(requirements_raw, dict):
            raise TimedSpanAcceptancePackageError(
                "Candidate C package has no Introduction Keyframe requirements"
            )
        try:
            timed = TimedAssetPresencePlan.from_dict(timed_raw)
            spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
            activation = TimedCanonicalReferenceActivationPlan.from_dict(activation_raw)
            requirements = IntroductionKeyframeRequirementPlan.from_dict(requirements_raw)
            spans.require_source(timed)
            self._require_activation_structural_sources(timed, spans, activation)
            requirements.require_sources(spans, activation)
        except (
            TimedAssetPresenceError,
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
            GovernedIntroductionKeyframeError,
            TimedSpanAcceptancePackageError,
        ) as exc:
            raise TimedSpanAcceptancePackageError(
                f"Candidate C timed-span authority is invalid: {exc}"
            ) from exc
        if spans.span_count <= 1:
            raise TimedSpanAcceptancePackageError(
                "Monolithic Shots do not require timed-span acceptance packages"
            )
        if len(activation.activations) != spans.span_count:
            raise TimedSpanAcceptancePackageError(
                "Timed reference activation does not cover every internal span"
            )
        if requirements.requirement_count != len(spans.boundaries):
            raise TimedSpanAcceptancePackageError(
                "Introduction Keyframe requirements do not cover every internal boundary"
            )

        opening_keyframe = root.get("governed_keyframe")
        if not isinstance(opening_keyframe, dict) or opening_keyframe.get("status") != "approved":
            raise TimedSpanAcceptancePackageError(
                "Candidate C package has no approved opening governed keyframe"
            )

        activation_by_span = {item.span_id: item for item in activation.activations}
        requirement_by_span = {item.target_span_id: item for item in requirements.requirements}

        task_id = str(manifest.get("task_id") or "TASK").strip()
        profile = str(root.get("profile") or "production").strip().lower()
        destination = (
            self.project_directory
            / ".vscs"
            / "timed_span_acceptance"
            / "packages"
            / task_id
            / profile
        )
        destination.mkdir(parents=True, exist_ok=True)

        selected = (
            spans.spans
            if sequence_numbers is None
            else tuple(span for span in spans.spans if span.sequence_number in sequence_numbers)
        )
        if not selected:
            raise TimedSpanAcceptancePackageError(
                "Requested governed internal span does not exist"
            )
        if sequence_numbers is not None and len(selected) != len(set(sequence_numbers)):
            raise TimedSpanAcceptancePackageError(
                "One or more requested governed internal spans do not exist"
            )

        package_paths: list[Path] = []
        for span in selected:
            active = activation_by_span.get(span.span_id)
            if active is None:
                raise TimedSpanAcceptancePackageError(
                    f"No timed reference activation exists for {span.span_id}"
                )
            if span.sequence_number == 1:
                keyframe = deepcopy(opening_keyframe)
                conditioning_source = "shot_opening_authority"
                preceding_boundary = None
            else:
                requirement = requirement_by_span.get(span.span_id)
                if requirement is None:
                    raise TimedSpanAcceptancePackageError(
                        f"No Introduction Keyframe requirement exists for {span.span_id}"
                    )
                try:
                    approved = self.keyframes.require_approved(requirement)
                except GovernedIntroductionKeyframeError as exc:
                    raise TimedSpanAcceptancePackageError(
                        f"Span {span.sequence_number} is blocked until its Introduction "
                        f"Keyframe is approved: {exc}"
                    ) from exc
                keyframe = {
                    **approved.to_dict(),
                    "image_path": str(self.keyframes.image_path(approved)),
                    "source_kind": "governed_introduction_keyframe",
                }
                conditioning_source = "governed_introduction_keyframe"
                preceding_boundary = span.start_frame - 1

            provider_frames = self._provider_frame_count(span.frame_count)
            payload = deepcopy(root)
            payload["status"] = "READY"
            payload["frame_count"] = span.frame_count
            payload["governed_keyframe"] = keyframe
            payload["motion_prompt"] = self._span_motion_prompt(span.sequence_number)
            payload["shot_prompt"] = payload["motion_prompt"]
            base_prefix = str(root.get("filename_prefix") or task_id).rstrip("/")
            payload["filename_prefix"] = f"{base_prefix}/SPAN-{span.sequence_number:03d}"
            payload["provider_execution_plan"] = {
                "provider": "ltx-2.5",
                "mode": "governed_internal_span_i2v",
                "governed_frame_count": span.frame_count,
                "provider_frame_count": provider_frames,
                "provider_trim_frames": provider_frames - span.frame_count,
                "governed_duration_seconds": span.frame_count / spans.frames_per_second,
                "hidden_segmentation": True,
                "keyframe_conditioning": "first_frame_i2v",
                "automatic_provider_submission": False,
                "monolithic_submission_permitted": False,
            }
            payload["timed_span_execution"] = {
                "schema_version": "1.0",
                "span_id": span.span_id,
                "sequence_number": span.sequence_number,
                "global_start_frame": span.start_frame,
                "global_through_frame": span.through_frame,
                "conditioning_source_kind": conditioning_source,
                "conditioning_frame_global_index": span.start_frame,
                "conditioning_frame_is_emitted": True,
                "preceding_boundary_global_frame_index": preceding_boundary,
                "preceding_boundary_frame_reemitted": False,
                "active_reference_ids": list(active.active_reference_ids),
                "introduced_reference_ids": list(active.introduced_reference_ids),
                "direct_provider_reference_ids": [],
                "reference_conditioning_mode": "baked_into_governed_keyframe",
                "combined_identity_video_reference": False,
            }
            payload.pop("reference_plan", None)

            span_manifest = payload.get("_vscs_manifest")
            if not isinstance(span_manifest, dict):
                raise TimedSpanAcceptancePackageError(
                    "Candidate C span package lost its compilation manifest"
                )
            span_manifest = dict(span_manifest)
            span_manifest["parent_package_fingerprint"] = source_fingerprint
            span_manifest["span_id"] = span.span_id
            span_manifest["span_sequence_number"] = span.sequence_number
            span_manifest["compiler"] = (
                "VSCS Phase 20.18.2.3.6 / LTX-2.5 automated timed-span orchestration"
            )
            payload["_vscs_manifest"] = span_manifest
            fingerprint_source = dict(payload)
            fingerprint_source.pop("_vscs_manifest", None)
            span_manifest["package_fingerprint"] = self._fingerprint(fingerprint_source)

            package_path = destination / f"span-{span.sequence_number:03d}.json"
            package_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            package_paths.append(package_path)

        return TimedSpanAcceptancePackageSet(
            shot_id=spans.shot_id,
            source_package_path=source_path,
            source_package_fingerprint=source_fingerprint,
            span_ids=tuple(span.span_id for span in selected),
            package_paths=tuple(package_paths),
        )

    @staticmethod
    def _require_activation_structural_sources(
        timed: TimedAssetPresencePlan,
        spans: GovernedInternalRenderSpanPlan,
        activation: TimedCanonicalReferenceActivationPlan,
    ) -> None:
        if activation.shot_id != timed.shot_id or activation.shot_id != spans.shot_id:
            raise TimedSpanAcceptancePackageError(
                "Timed reference activation Shot identity does not match source authority"
            )
        if activation.source_timed_asset_presence_plan_id != timed.plan_id:
            raise TimedSpanAcceptancePackageError(
                "Timed reference activation source presence identity changed"
            )
        if activation.source_timed_asset_presence_fingerprint != timed.fingerprint:
            raise TimedSpanAcceptancePackageError(
                "Timed reference activation source presence fingerprint changed"
            )
        if activation.source_internal_render_span_plan_id != spans.plan_id:
            raise TimedSpanAcceptancePackageError(
                "Timed reference activation source span identity changed"
            )
        if activation.source_internal_render_span_fingerprint != spans.fingerprint:
            raise TimedSpanAcceptancePackageError(
                "Timed reference activation source span fingerprint changed"
            )

    @staticmethod
    def _span_motion_prompt(sequence_number: int) -> str:
        if sequence_number == 1:
            return (
                "Continue this exact approved opening composition with the governed active "
                "subjects only. Preserve camera, identities, environment, positions, scale, "
                "lighting, and physical continuity. Do not introduce any new subject."
            )
        return (
            "Continue from this exact approved Introduction Keyframe. Preserve the visible "
            "governed identities, camera, environment, positions, scale, lighting, and physical "
            "continuity. Do not add any unapproved subject."
        )

    @staticmethod
    def _provider_frame_count(governed_frames: int) -> int:
        if governed_frames <= 0:
            raise TimedSpanAcceptancePackageError(
                "Governed internal span frame count must be positive"
            )
        candidate = governed_frames
        remainder = (candidate - 1) % 8
        if remainder:
            candidate += 8 - remainder
        return candidate

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise TimedSpanAcceptancePackageError(
                f"Candidate C Production Package does not exist: {path}"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TimedSpanAcceptancePackageError(
                f"Cannot read Candidate C Production Package: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise TimedSpanAcceptancePackageError(
                "Candidate C Production Package root must be an object"
            )
        return raw

    @staticmethod
    def _fingerprint(value: object) -> str:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()
