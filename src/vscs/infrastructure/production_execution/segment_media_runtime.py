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
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class SegmentVideoInfo:
    frame_count: int
    frames_per_second: float
    width: int
    height: int


class SegmentMediaRuntime:
    """Use FFmpeg/FFprobe for continuity capture and normalized governed assembly."""

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
        overlap_trim_frames: int = 0,
        tail_trim_frames: int = 0,
        expected_width: int | None = None,
        expected_height: int | None = None,
    ) -> SegmentAssemblyResult:
        if len(segment_paths) < 2:
            raise SegmentMediaRuntimeError(
                "Segmented assembly requires at least two provider segment videos"
            )
        if expected_frame_count <= 0 or expected_frames_per_second <= 0:
            raise SegmentMediaRuntimeError("Governed assembly frame count and FPS must be positive")
        if overlap_trim_frames < 0 or tail_trim_frames < 0:
            raise SegmentMediaRuntimeError("Assembly trim values cannot be negative")

        resolved = tuple(Path(path).expanduser().resolve(strict=False) for path in segment_paths)
        missing = tuple(str(path) for path in resolved if not path.is_file())
        if missing:
            raise SegmentMediaRuntimeError(
                "Cannot assemble missing provider segment video(s): " + ", ".join(missing)
            )

        infos = tuple(self.inspect_video_info(path) for path in resolved)
        for index, info in enumerate(infos, start=1):
            if abs(info.frames_per_second - expected_frames_per_second) > 0.01:
                raise SegmentMediaRuntimeError(
                    f"Provider SEG-{index:03d} FPS does not match governed FPS: "
                    f"expected {expected_frames_per_second}, observed "
                    f"{info.frames_per_second:.6f}"
                )
        effective_total = sum(info.frame_count for info in infos) - overlap_trim_frames
        if effective_total < expected_frame_count:
            raise SegmentMediaRuntimeError(
                "Provider segment media is too short after continuity-overlap removal: "
                f"needs {expected_frame_count} frames, has {effective_total}"
            )
        if effective_total - tail_trim_frames < expected_frame_count:
            raise SegmentMediaRuntimeError(
                "Configured provider tail trim would remove governed frame authority"
            )

        target = Path(destination).expanduser().resolve(strict=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        width = expected_width or infos[0].width
        height = expected_height or infos[0].height
        if width <= 0 or height <= 0:
            raise SegmentMediaRuntimeError("Governed output width and height must be positive")

        args: list[str] = [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
        ]
        for path in resolved:
            args.extend(("-i", str(path)))

        filters: list[str] = []
        labels: list[str] = []
        for index, info in enumerate(infos):
            start = 0 if index == 0 else 1
            if start >= info.frame_count:
                raise SegmentMediaRuntimeError(
                    f"Provider SEG-{index + 1:03d} has no frame after continuity trim"
                )
            label = f"v{index}"
            filters.append(
                f"[{index}:v]trim=start_frame={start},setpts=PTS-STARTPTS[{label}]"
            )
            labels.append(f"[{label}]")
        filters.append(
            "".join(labels)
            + f"concat=n={len(labels)}:v=1:a=0,"
            + f"trim=end_frame={expected_frame_count},setpts=PTS-STARTPTS,"
            + f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            + f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black[vout]"
        )
        args.extend(
            (
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[vout]",
                "-r",
                str(expected_frames_per_second),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(target),
            )
        )
        self._run(*args)

        if not target.is_file() or target.stat().st_size <= 0:
            raise SegmentMediaRuntimeError(f"FFmpeg did not create assembled media: {target}")
        info = self.inspect_video_info(target)
        if info.frame_count != expected_frame_count:
            raise SegmentMediaRuntimeError(
                "Assembled provider media does not preserve governed frame count: "
                f"expected {expected_frame_count}, observed {info.frame_count}"
            )
        if abs(info.frames_per_second - expected_frames_per_second) > 0.01:
            raise SegmentMediaRuntimeError(
                "Assembled provider media does not preserve governed FPS: "
                f"expected {expected_frames_per_second}, observed "
                f"{info.frames_per_second:.6f}"
            )
        if info.width != width or info.height != height:
            raise SegmentMediaRuntimeError(
                "Assembled provider media does not restore governed geometry: "
                f"expected {width}x{height}, observed {info.width}x{info.height}"
            )
        return SegmentAssemblyResult(
            target,
            info.frame_count,
            info.frames_per_second,
            info.width,
            info.height,
        )

    def inspect_video(self, path: Path) -> tuple[int, float]:
        info = self.inspect_video_info(path)
        return info.frame_count, info.frames_per_second

    def inspect_video_info(self, path: Path) -> SegmentVideoInfo:
        source = Path(path).expanduser().resolve(strict=False)
        completed = self._run(
            self.ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames,avg_frame_rate,width,height",
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
            width = int(stream["width"])
            height = int(stream["height"])
        except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise SegmentMediaRuntimeError(
                f"FFprobe did not return usable frame/FPS/geometry metadata for {source}"
            ) from exc
        return SegmentVideoInfo(frame_count, fps, width, height)

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
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            command = " ".join(args[:2])
            raise SegmentMediaRuntimeError(
                f"Segment media command failed ({command}): {exc}"
            ) from exc
