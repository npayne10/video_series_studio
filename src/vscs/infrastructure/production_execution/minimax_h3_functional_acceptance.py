"""MiniMax H3 functional acceptance for Phase 20.18.2.3.6.4e."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from vscs.application.production_execution.package_compilation import CompiledProductionPackage

from .minimax_h3_span_adapter import MiniMaxH3SpanAdapterCompiler, MiniMaxH3SpanAdapterError


class MiniMaxH3FunctionalAcceptanceError(RuntimeError):
    """Raised when H3 functional-acceptance evidence is missing or inconsistent."""


class MiniMaxH3FunctionalAcceptanceState(StrEnum):
    """Functional-acceptance state for a real governed H3 Shot."""

    PENDING_VISUAL_QC = "pending_visual_qc"
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MiniMaxH3VisualObservation:
    """Human observations for the exact SHT-002 acceptance criteria."""

    james_sandra_present_frames_0_95: bool
    ros_absent_frames_0_95: bool
    ros_first_visible_frame_96: bool
    ros_continues_frames_96_143: bool
    no_extra_people: bool
    james_sandra_continuity_maintained: bool
    central_chair_continuity_maintained: bool
    bridge_xorix_coherent: bool
    no_provider_guide_cut: bool
    approved_by: str
    notes: str = ""

    def __post_init__(self) -> None:
        reviewer = self.approved_by.strip()
        if not reviewer:
            raise MiniMaxH3FunctionalAcceptanceError(
                "H3 functional acceptance requires approved_by"
            )
        object.__setattr__(self, "approved_by", reviewer)
        object.__setattr__(self, "notes", self.notes.strip())

    @property
    def passed(self) -> bool:
        return all(
            (
                self.james_sandra_present_frames_0_95,
                self.ros_absent_frames_0_95,
                self.ros_first_visible_frame_96,
                self.ros_continues_frames_96_143,
                self.no_extra_people,
                self.james_sandra_continuity_maintained,
                self.central_chair_continuity_maintained,
                self.bridge_xorix_coherent,
                self.no_provider_guide_cut,
            )
        )

    @property
    def failed_criteria(self) -> tuple[str, ...]:
        mapping = (
            ("James/Sandra present through frames 0-95", self.james_sandra_present_frames_0_95),
            ("Ros absent through frames 0-95", self.ros_absent_frames_0_95),
            ("Ros first visible at frame 96", self.ros_first_visible_frame_96),
            ("Ros may continue entering through frames 96-143", self.ros_continues_frames_96_143),
            ("No extra people", self.no_extra_people),
            ("James/Sandra continuity maintained", self.james_sandra_continuity_maintained),
            ("Central chair continuity maintained", self.central_chair_continuity_maintained),
            ("Bridge/Xorix coherent", self.bridge_xorix_coherent),
            ("No provider-guide cut", self.no_provider_guide_cut),
        )
        return tuple(label for label, passed in mapping if not passed)


@dataclass(frozen=True, slots=True)
class MiniMaxH3MediaObservation:
    """Technical facts observed from one video output."""

    frame_count: int
    frames_per_second: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if min(self.frame_count, self.frames_per_second, self.width, self.height) <= 0:
            raise MiniMaxH3FunctionalAcceptanceError(
                "H3 media observation values must all be positive"
            )


class MiniMaxH3MediaProbe(Protocol):
    def observe(self, path: Path) -> MiniMaxH3MediaObservation: ...


class FFprobeMiniMaxH3MediaProbe:
    """Read exact media facts required by functional acceptance."""

    def __init__(self, *, ffprobe: str = "ffprobe") -> None:
        self.ffprobe = ffprobe

    def observe(self, path: Path) -> MiniMaxH3MediaObservation:
        candidate = Path(path).expanduser().resolve(strict=False)
        if not candidate.is_file():
            raise MiniMaxH3FunctionalAcceptanceError(
                f"H3 acceptance media does not exist: {candidate}"
            )
        command = (
            self.ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames,width,height,r_frame_rate",
            "-of",
            "json",
            str(candidate),
        )
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            streams = payload.get("streams")
            if not isinstance(streams, list) or not streams:
                raise ValueError("no video stream")
            stream = streams[0]
            numerator, denominator = str(stream["r_frame_rate"]).split("/", maxsplit=1)
            fps = round(int(numerator) / int(denominator))
            return MiniMaxH3MediaObservation(
                frame_count=int(stream["nb_read_frames"]),
                frames_per_second=fps,
                width=int(stream["width"]),
                height=int(stream["height"]),
            )
        except (
            OSError,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            ZeroDivisionError,
        ) as exc:
            raise MiniMaxH3FunctionalAcceptanceError(
                f"Unable to inspect H3 acceptance media: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True)
class MiniMaxH3FunctionalAcceptanceReport:
    """Combined machine and human acceptance result for the governed Shot."""

    shot_id: str
    task_id: str
    state: MiniMaxH3FunctionalAcceptanceState
    technical_passed: bool
    visual_observation_present: bool
    visual_passed: bool | None
    final_path: str
    final_frame_count: int
    frames_per_second: int
    technical_failures: tuple[str, ...] = ()
    visual_failures: tuple[str, ...] = ()
    approved_by: str | None = None
    notes: str = ""

    @property
    def passed(self) -> bool:
        return self.state is MiniMaxH3FunctionalAcceptanceState.PASSED

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["technical_failures"] = list(self.technical_failures)
        payload["visual_failures"] = list(self.visual_failures)
        payload["passed"] = self.passed
        return payload


class MiniMaxH3FunctionalAcceptanceService:
    """Evaluate the real H3 orchestration result against Phase 6.4e gates."""

    def __init__(
        self,
        project_directory: Path,
        *,
        media_probe: MiniMaxH3MediaProbe | None = None,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.media_probe = media_probe or FFprobeMiniMaxH3MediaProbe()
        self.adapter = MiniMaxH3SpanAdapterCompiler(self.project_directory)

    def evaluate(
        self,
        compiled: CompiledProductionPackage,
        *,
        visual_observation: MiniMaxH3VisualObservation | None = None,
    ) -> MiniMaxH3FunctionalAcceptanceReport:
        try:
            plan = self.adapter.compile(compiled)
        except MiniMaxH3SpanAdapterError as exc:
            raise MiniMaxH3FunctionalAcceptanceError(
                f"H3 functional acceptance authority is invalid: {exc}"
            ) from exc

        manifest_path = (
            self.project_directory
            / ".vscs"
            / "h3_span_orchestration"
            / compiled.task_id
            / plan.plan_id
            / "orchestration.json"
        )
        manifest = self._read_manifest(manifest_path)
        technical_failures: list[str] = []
        self._check_manifest(compiled, plan.to_dict(), manifest, technical_failures)

        final_path = self._project_path(str(manifest.get("final_path") or ""))
        final_observation = self._observe_or_failure(
            final_path,
            "final assembled Shot",
            technical_failures,
        )
        if final_observation is not None:
            if final_observation.frame_count != compiled.frame_count:
                technical_failures.append(
                    f"Final Shot has {final_observation.frame_count} frames; "
                    f"expected {compiled.frame_count}."
                )
            if final_observation.frames_per_second != compiled.frames_per_second:
                technical_failures.append(
                    f"Final Shot is {final_observation.frames_per_second} fps; "
                    f"expected {compiled.frames_per_second}."
                )

        manifest_spans = manifest.get("spans")
        if isinstance(manifest_spans, list):
            for execution, raw in zip(plan.spans, manifest_spans, strict=False):
                if not isinstance(raw, dict):
                    technical_failures.append(
                        f"Span {execution.sequence_number} manifest row is invalid."
                    )
                    continue
                normalized = self._project_path(str(raw.get("normalized_output_path") or ""))
                observation = self._observe_or_failure(
                    normalized,
                    f"normalized span {execution.sequence_number}",
                    technical_failures,
                )
                if observation is None:
                    continue
                if observation.frame_count != execution.governed_frame_count:
                    technical_failures.append(
                        f"Normalized span {execution.sequence_number} has "
                        f"{observation.frame_count} frames; expected "
                        f"{execution.governed_frame_count}."
                    )
                if observation.frames_per_second != compiled.frames_per_second:
                    technical_failures.append(
                        f"Normalized span {execution.sequence_number} has "
                        f"{observation.frames_per_second} fps; expected "
                        f"{compiled.frames_per_second}."
                    )

        technical_passed = not technical_failures
        if not technical_passed:
            state = MiniMaxH3FunctionalAcceptanceState.FAILED
            visual_passed: bool | None = (
                None if visual_observation is None else visual_observation.passed
            )
        elif visual_observation is None:
            state = MiniMaxH3FunctionalAcceptanceState.PENDING_VISUAL_QC
            visual_passed = None
        elif visual_observation.passed:
            state = MiniMaxH3FunctionalAcceptanceState.PASSED
            visual_passed = True
        else:
            state = MiniMaxH3FunctionalAcceptanceState.FAILED
            visual_passed = False

        report = MiniMaxH3FunctionalAcceptanceReport(
            shot_id=compiled.shot_id,
            task_id=compiled.task_id,
            state=state,
            technical_passed=technical_passed,
            visual_observation_present=visual_observation is not None,
            visual_passed=visual_passed,
            final_path=str(final_path),
            final_frame_count=(0 if final_observation is None else final_observation.frame_count),
            frames_per_second=(
                0 if final_observation is None else final_observation.frames_per_second
            ),
            technical_failures=tuple(technical_failures),
            visual_failures=(
                () if visual_observation is None else visual_observation.failed_criteria
            ),
            approved_by=(None if visual_observation is None else visual_observation.approved_by),
            notes="" if visual_observation is None else visual_observation.notes,
        )
        self._persist_report(manifest_path.parent, report, visual_observation)
        return report

    def _check_manifest(
        self,
        compiled: CompiledProductionPackage,
        plan: dict[str, object],
        manifest: dict[str, object],
        failures: list[str],
    ) -> None:
        expected_scalars = {
            "provider": plan["provider_id"],
            "mode": plan["mode"],
            "shot_id": compiled.shot_id,
            "task_id": compiled.task_id,
            "source_package_fingerprint": compiled.package_fingerprint,
            "plan_id": plan["plan_id"],
            "plan_fingerprint": plan["fingerprint"],
            "assembly_policy": "concatenate_normalized_span_outputs_in_sequence",
            "final_frame_count": compiled.frame_count,
            "frames_per_second": compiled.frames_per_second,
        }
        for key, expected in expected_scalars.items():
            if manifest.get(key) != expected:
                failures.append(f"Orchestration manifest {key} does not match governed authority.")

        expected_spans = plan["spans"]
        actual_spans = manifest.get("spans")
        if not isinstance(expected_spans, list) or not isinstance(actual_spans, list):
            failures.append("Orchestration manifest has invalid span evidence.")
            return
        if len(actual_spans) != len(expected_spans):
            failures.append("Orchestration manifest span count does not match H3 plan.")
            return

        governed_keys = (
            "span_id",
            "sequence_number",
            "global_start_frame",
            "global_through_frame",
            "governed_frame_count",
            "provider_frame_count",
            "reference_slots",
            "positive_prompt",
            "negative_prompt",
            "motion_prompt",
            "guide_source_kind",
            "guide_image_path",
            "guide_image_sha256",
            "guide_frame_idx",
            "source_span_input_id",
            "source_span_input_plan_fingerprint",
            "normalization_policy",
            "reference_image_size",
            "reference_slot_fingerprint",
            "prompt_fingerprint",
            "guide_semantics",
            "temporal_asset_gate",
        )
        for index, (expected, actual) in enumerate(
            zip(expected_spans, actual_spans, strict=True),
            start=1,
        ):
            if not isinstance(expected, dict) or not isinstance(actual, dict):
                failures.append(f"Span {index} manifest evidence is invalid.")
                continue
            for key in governed_keys:
                if actual.get(key) != expected.get(key):
                    failures.append(
                        f"Span {index} manifest {key} differs from governed H3 authority."
                    )

    def _read_manifest(self, path: Path) -> dict[str, object]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MiniMaxH3FunctionalAcceptanceError(
                f"Cannot read H3 orchestration manifest: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise MiniMaxH3FunctionalAcceptanceError(
                "H3 orchestration manifest root must be an object"
            )
        return raw

    def _project_path(self, value: str) -> Path:
        if not value.strip():
            return self.project_directory / "__missing__"
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_directory / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_relative_to(self.project_directory):
            raise MiniMaxH3FunctionalAcceptanceError(
                f"H3 acceptance evidence escaped the VSCS project: {candidate}"
            )
        return candidate

    def _observe_or_failure(
        self,
        path: Path,
        label: str,
        failures: list[str],
    ) -> MiniMaxH3MediaObservation | None:
        try:
            return self.media_probe.observe(path)
        except MiniMaxH3FunctionalAcceptanceError as exc:
            failures.append(f"{label}: {exc}")
            return None

    @staticmethod
    def _persist_report(
        root: Path,
        report: MiniMaxH3FunctionalAcceptanceReport,
        observation: MiniMaxH3VisualObservation | None,
    ) -> None:
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "report": report.to_dict(),
        }
        if observation is not None:
            payload["visual_observation"] = asdict(observation)
        destination = root / "functional_acceptance.json"
        destination.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
