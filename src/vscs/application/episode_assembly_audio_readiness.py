"""Read-only technical audio inventory for a verified assembly preview."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vscs.application.episode_assembly_playback import validated_source_path
from vscs.application.episode_assembly_preview import AssemblyPreviewPlan


@dataclass(frozen=True, slots=True)
class ShotAudioInspection:
    shot_id: str
    media_id: str
    stream_count: int
    codec: str | None
    channels: int | None
    sample_rate: int | None
    technical_findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssemblyAudioReport:
    revision_fingerprint: str
    shots: tuple[ShotAudioInspection, ...]
    continuity_findings: tuple[str, ...]

    @property
    def silent_shots(self) -> int:
        return sum(shot.stream_count == 0 for shot in self.shots)


def inspect_assembly_audio(
    plan: AssemblyPreviewPlan,
    project_directory: Path,
    *,
    probe_command: str = "ffprobe",
) -> AssemblyAudioReport:
    """Inventory approved sources; silence is information, not an approval failure.

    All file identity/integrity checks are prerequisites through the verified
    preview plan. This function performs no writes and grants no approvals.
    """
    if not plan.ready:
        raise ValueError("Audio inspection requires a fully verified assembly preview")
    shots: list[ShotAudioInspection] = []
    for segment in plan.segments:
        path = validated_source_path(project_directory, segment)
        try:
            process = subprocess.run(
                [
                    probe_command, "-v", "error", "-select_streams", "a",
                    "-show_entries", "stream=codec_name,channels,sample_rate",
                    "-of", "json", str(path),
                ],
                capture_output=True,
                check=True,
                text=True,
                timeout=60,
            )
            streams = json.loads(process.stdout)["streams"]
            if not isinstance(streams, list):
                raise ValueError("Invalid audio stream inventory")
            if len(streams) > 1:
                raise ValueError("Multiple audio streams require explicit routing review")
            codec = channels = rate = None
            findings: list[str] = []
            if not streams:
                findings.append("NO EMBEDDED AUDIO — editorial intent unverified")
            else:
                stream = streams[0]
                codec = str(stream["codec_name"])
                channels = int(stream["channels"])
                rate = int(stream["sample_rate"])
                if not codec or codec == "None" or channels <= 0 or rate <= 0:
                    raise ValueError("Invalid embedded audio stream metadata")
            shots.append(
                ShotAudioInspection(
                    segment.shot_id,
                    segment.media_id,
                    len(streams),
                    codec,
                    channels,
                    rate,
                    tuple(findings),
                )
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
                KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{segment.shot_id}: Audio probe unavailable or invalid") from exc
    continuity: list[str] = []
    for previous, current in zip(shots, shots[1:], strict=False):
        if previous.stream_count != current.stream_count:
            continuity.append(
                f"{previous.shot_id} → {current.shot_id}: embedded audio presence changes"
            )
        elif previous.stream_count and (
            previous.codec, previous.channels, previous.sample_rate
        ) != (current.codec, current.channels, current.sample_rate):
            continuity.append(
                f"{previous.shot_id} → {current.shot_id}: audio stream formats differ"
            )
    return AssemblyAudioReport(plan.revision_fingerprint, tuple(shots), tuple(continuity))
