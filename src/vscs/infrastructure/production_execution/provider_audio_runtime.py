"""Provider-output audio governance before Generated Media ingestion."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from vscs.application.production_execution import ProviderAudioPolicy
from vscs.application.provider_execution import ProviderExecutionOutput


class ProviderAudioGovernanceRuntimeError(RuntimeError):
    """Raised when provider audio cannot be governed safely."""


@dataclass(frozen=True, slots=True)
class GovernedProviderOutputs:
    """Provider outputs prepared for authoritative Generated Media ingestion."""

    outputs: tuple[ProviderExecutionOutput, ...]
    source_root: Path
    note: str


class ProviderAudioGovernanceRuntime:
    """Strip or preserve provider audio according to explicit Shot authority."""

    _VIDEO_KINDS = frozenset({"production_video", "preview_video", "lip_sync_video", "video"})
    _AUDIO_KINDS = frozenset({"audio", "dialogue_audio", "music", "effects"})

    def __init__(
        self,
        *,
        ffmpeg_executable: str | None = None,
        ffprobe_executable: str | None = None,
    ) -> None:
        self.ffmpeg = self._resolve_executable(
            ffmpeg_executable or os.environ.get("VSCS_FFMPEG_EXE"),
            "ffmpeg",
        )
        self.ffprobe = self._resolve_executable(
            ffprobe_executable or os.environ.get("VSCS_FFPROBE_EXE"),
            "ffprobe",
        )

    def apply(
        self,
        policy: ProviderAudioPolicy,
        *,
        execution_id: str,
        outputs: tuple[ProviderExecutionOutput, ...],
        source_root: Path,
        staging_root: Path,
    ) -> GovernedProviderOutputs:
        if not execution_id.strip():
            raise ProviderAudioGovernanceRuntimeError("Provider execution identity is required")
        if not outputs:
            raise ProviderAudioGovernanceRuntimeError(
                "Provider audio governance requires at least one provider output"
            )
        source = Path(source_root).expanduser().resolve(strict=False)
        if not source.is_dir():
            raise ProviderAudioGovernanceRuntimeError(
                f"Provider output root does not exist: {source}"
            )

        if not policy.discard_provider_audio:
            governed = tuple(
                replace(output, metadata=self._metadata(output, policy, "preserved"))
                for output in outputs
            )
            return GovernedProviderOutputs(
                governed,
                source,
                (
                    f"Provider audio policy {policy.mode.value} preserved provider audio for VSCS "
                    f"execution {execution_id}."
                ),
            )

        staging = Path(staging_root).expanduser().resolve(strict=False)
        staging.mkdir(parents=True, exist_ok=True)
        retained: list[ProviderExecutionOutput] = []
        discarded_audio_outputs = 0
        stripped_videos = 0

        for output in outputs:
            kind = output.media_kind.strip().casefold()
            if kind in self._AUDIO_KINDS:
                discarded_audio_outputs += 1
                continue

            input_path = self._resolve_relative(source, output.relative_path)
            suffix = input_path.suffix.casefold()
            safe_id = self._safe_segment(output.output_id)

            if kind in self._VIDEO_KINDS:
                relative = PurePosixPath("video") / f"{safe_id}{suffix or '.mp4'}"
                destination = staging.joinpath(*relative.parts)
                self._strip_audio(input_path, destination)
                if self._audio_stream_count(destination) != 0:
                    raise ProviderAudioGovernanceRuntimeError(
                        f"Governed provider video still contains audio: {destination}"
                    )
                stripped_videos += 1
                retained.append(
                    replace(
                        output,
                        relative_path=relative.as_posix(),
                        metadata=self._metadata(
                            output,
                            policy,
                            "discarded",
                            original_path=output.relative_path,
                            video_stream_copy=True,
                        ),
                    )
                )
                continue

            relative = PurePosixPath("passthrough") / f"{safe_id}{suffix}"
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input_path, destination)
            retained.append(
                replace(
                    output,
                    relative_path=relative.as_posix(),
                    metadata=self._metadata(
                        output,
                        policy,
                        "not_applicable",
                        original_path=output.relative_path,
                    ),
                )
            )

        if not retained:
            raise ProviderAudioGovernanceRuntimeError(
                "Provider audio policy discarded every provider output; no visual output remains"
            )
        if stripped_videos == 0:
            raise ProviderAudioGovernanceRuntimeError(
                "Provider audio policy expected a video output but no video output was governed"
            )

        note = (
            f"Provider audio policy {policy.mode.value} removed audio from {stripped_videos} "
            f"video output(s)"
        )
        if discarded_audio_outputs:
            note += f" and discarded {discarded_audio_outputs} separate audio output(s)"
        note += f"; authoritative audio remains with VSCS for execution {execution_id}."
        return GovernedProviderOutputs(tuple(retained), staging, note)

    def _strip_audio(self, source: Path, destination: Path) -> None:
        if not source.is_file():
            raise ProviderAudioGovernanceRuntimeError(f"Provider output does not exist: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-map_metadata",
            "0",
            str(destination),
        )
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise ProviderAudioGovernanceRuntimeError(
                f"FFmpeg did not create governed video output: {destination}"
            )

    def _audio_stream_count(self, path: Path) -> int:
        completed = self._run(
            self.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(path),
            capture_output=True,
        )
        try:
            payload = json.loads(completed.stdout or "{}")
            streams = payload.get("streams", [])
            if not isinstance(streams, list):
                raise TypeError("streams must be an array")
            return len(streams)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ProviderAudioGovernanceRuntimeError(
                f"FFprobe did not return usable audio-stream metadata for {path}"
            ) from exc

    @staticmethod
    def _metadata(
        output: ProviderExecutionOutput,
        policy: ProviderAudioPolicy,
        action: str,
        *,
        original_path: str | None = None,
        video_stream_copy: bool = False,
    ) -> tuple[tuple[str, str], ...]:
        values = dict(output.metadata)
        values.update(
            {
                "provider_audio_policy": policy.mode.value,
                "provider_audio_action": action,
                "provider_audio_authority": policy.authoritative_audio_source,
            }
        )
        if original_path is not None:
            values["provider_audio_original_path"] = original_path
        if video_stream_copy:
            values["provider_video_stream_copy"] = "true"
        return tuple(sorted(values.items()))

    @staticmethod
    def _resolve_relative(root: Path, raw_path: str) -> Path:
        normalized = raw_path.strip().replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            not normalized
            or pure.is_absolute()
            or ".." in pure.parts
            or (pure.parts and ":" in pure.parts[0])
        ):
            raise ProviderAudioGovernanceRuntimeError(
                "Provider output path must remain relative to the configured output root"
            )
        candidate = root.joinpath(*pure.parts).resolve(strict=False)
        if not candidate.is_relative_to(root):
            raise ProviderAudioGovernanceRuntimeError(
                "Provider output path escapes the configured output root"
            )
        return candidate

    @staticmethod
    def _safe_segment(value: str) -> str:
        normalized = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in value.strip()
        )
        if not normalized:
            raise ProviderAudioGovernanceRuntimeError("Provider output identity is empty")
        return normalized

    @staticmethod
    def _resolve_executable(configured: str | None, default_name: str) -> str:
        if configured:
            candidate = Path(configured).expanduser().resolve(strict=False)
            if candidate.is_file():
                return str(candidate)
            resolved = shutil.which(configured)
            if resolved:
                return resolved
            raise ProviderAudioGovernanceRuntimeError(
                f"Configured {default_name} executable does not exist: {configured}"
            )
        resolved = shutil.which(default_name)
        if resolved:
            return resolved
        raise ProviderAudioGovernanceRuntimeError(
            f"{default_name} is required for governed provider audio. "
            f"Put it on PATH or configure VSCS_{default_name.upper()}_EXE."
        )

    @staticmethod
    def _run(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args,
                check=True,
                text=True,
                capture_output=capture_output,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            command = " ".join(args[:2])
            raise ProviderAudioGovernanceRuntimeError(
                f"Provider audio command failed ({command}): {exc}"
            ) from exc
