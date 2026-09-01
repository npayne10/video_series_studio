"""Provider-segment final-frame extraction and governed media assembly."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class SegmentMediaRuntimeError(RuntimeError):
    """Raised when provider segment media cannot be captured or assembled safely."""


@dataclass(frozen=True, slots=True)
class SegmentAssemblyResult:
    output_path: Path
    frame_count: int
    frames_per_second: float


class SegmentMediaRuntime:
    """Use FFmpeg/FFprobe for exact continuity-frame capture and lossless concatenation."""

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

    def capture_final_frame(
        self,
        video_path: Path,
        *,
        frame_count: int,
        destination: Path,
    ) -> Path:
        source = Path(video_path).expanduser().resolve(strict=False)
        if not source.is_file():
            raise SegmentMediaRuntimeError(f"Segment video does not exist: {source}")
        if frame_count <= 0:
            raise SegmentMediaRuntimeError("Segment frame_count must be positive")
        target = Path(destination).expanduser().resolve(strict=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        selector = f"select=eq(n\\,{frame_count - 1})"
        self._run(
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            selector,
            "-vsync",
            "0",
            "-frames:v",
            "1",
            str(target),
        )
        if not target.is_file() or target.stat().st_size <= 0:
            raise SegmentMediaRuntimeError(
                f"FFmpeg did not create the final continuity frame: {target}"
            )
        return target

    def assemble(
        self,
        segment_paths: tuple[Path, ...],
        *,
        destination: Path,
        expected_frame_count: int,
        expected_frames_per_second: int,
    ) -> SegmentAssemblyResult:
        if len(segment_paths) < 2:
            raise SegmentMediaRuntimeError(
                "Segmented assembly requires at least two provider segment videos"
            )
        if expected_frame_count <= 0 or expected_frames_per_second <= 0:
            raise SegmentMediaRuntimeError(
                "Governed assembly frame count and FPS must be positive"
            )
        resolved = tuple(Path(path).expanduser().resolve(strict=False) for path in segment_paths)
        missing = tuple(str(path) for path in resolved if not path.is_file())
        if missing:
            raise SegmentMediaRuntimeError(
                "Cannot assemble missing provider segment video(s): " + ", ".join(missing)
            )

        target = Path(destination).expanduser().resolve(strict=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        concat_file = target.with_suffix(".concat.txt")
        concat_file.write_text(
            "".join(f"file '{self._concat_escape(path)}'\n" for path in resolved),
            encoding="utf-8",
        )
        try:
            self._run(
                self.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(target),
            )
        finally:
            concat_file.unlink(missing_ok=True)

        if not target.is_file() or target.stat().st_size <= 0:
            raise SegmentMediaRuntimeError(f"FFmpeg did not create assembled media: {target}")
        frame_count, fps = self.inspect_video(target)
        if frame_count != expected_frame_count:
            raise SegmentMediaRuntimeError(
                "Assembled provider media does not preserve governed frame count: "
                f"expected {expected_frame_count}, observed {frame_count}"
            )
        if abs(fps - expected_frames_per_second) > 0.01:
            raise SegmentMediaRuntimeError(
                "Assembled provider media does not preserve governed FPS: "
                f"expected {expected_frames_per_second}, observed {fps:.6f}"
            )
        return SegmentAssemblyResult(target, frame_count, fps)

    def inspect_video(self, path: Path) -> tuple[int, float]:
        source = Path(path).expanduser().resolve(strict=False)
        completed = self._run(
            self.ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames,avg_frame_rate",
            "-of",
            "json",
            str(source),
            capture_output=True,
        )
        try:
            root = json.loads(completed.stdout or "{}")
            stream = root["streams"][0]
            frame_count = int(stream["nb_read_frames"])
            numerator, denominator = str(stream["avg_frame_rate"]).split("/", 1)
            fps = float(numerator) / float(denominator)
        except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise SegmentMediaRuntimeError(
                f"FFprobe did not return usable frame/FPS metadata for {source}"
            ) from exc
        return frame_count, fps

    @staticmethod
    def _concat_escape(path: Path) -> str:
        return str(path).replace("'", "'\\''")

    @staticmethod
    def _resolve_executable(configured: str | None, default_name: str) -> str:
        if configured:
            candidate = Path(configured).expanduser().resolve(strict=False)
            if candidate.is_file():
                return str(candidate)
            resolved = shutil.which(configured)
            if resolved:
                return resolved
            raise SegmentMediaRuntimeError(
                f"Configured {default_name} executable does not exist: {configured}"
            )
        resolved = shutil.which(default_name)
        if resolved:
            return resolved
        raise SegmentMediaRuntimeError(
            f"{default_name} is required for segmented production execution. "
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
                timeout=180,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            command = " ".join(args[:2])
            raise SegmentMediaRuntimeError(f"Segment media command failed ({command}): {exc}") from exc
