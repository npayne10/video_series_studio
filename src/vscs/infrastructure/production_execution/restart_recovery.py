"""ComfyUI provider reconciliation probe for Phase 20.16 restart recovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Protocol

from vscs.application.provider_execution import ProviderExecutionOutput
from vscs.infrastructure.rendering import ComfyUIClient, UrllibComfyUITransport


class ComfyUIRecoveryPresence(StrEnum):
    """Provider-observed presence of one durable ComfyUI prompt."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class ComfyUIRecoveryObservation:
    """One read-only reconciliation observation for a durable provider prompt."""

    presence: ComfyUIRecoveryPresence
    prompt_id: str
    message: str
    failure_reason: str | None = None


class ComfyUIRecoveryClient(Protocol):
    def queue(self) -> dict[str, object]: ...

    def history(self, prompt_id: str) -> dict[str, object] | None: ...


class ComfyUIRestartRecoveryProbe:
    """Establish whether ComfyUI still accounts for a durable execution identity."""

    def __init__(
        self,
        endpoint: str,
        *,
        client: ComfyUIRecoveryClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.endpoint = endpoint.strip().rstrip("/")
        self.client = client or ComfyUIClient(
            UrllibComfyUITransport(self.endpoint, timeout_seconds=timeout_seconds),
            self.endpoint,
        )

    def observe(self, prompt_id: str) -> ComfyUIRecoveryObservation:
        normalized = prompt_id.strip()
        if not normalized:
            raise ValueError("prompt_id cannot be blank")
        try:
            history = self.client.history(normalized)
            if history is not None:
                terminal = _history_terminal(history)
                if terminal is ComfyUIRecoveryPresence.COMPLETED:
                    return ComfyUIRecoveryObservation(
                        terminal,
                        normalized,
                        "ComfyUI history reports the durable prompt completed.",
                    )
                if terminal is ComfyUIRecoveryPresence.FAILED:
                    return ComfyUIRecoveryObservation(
                        terminal,
                        normalized,
                        "ComfyUI history reports the durable prompt failed.",
                        failure_reason=_history_failure_reason(history),
                    )
            queue = self.client.queue()
        except Exception as exc:
            return ComfyUIRecoveryObservation(
                ComfyUIRecoveryPresence.UNREACHABLE,
                normalized,
                f"Unable to reconcile durable prompt with ComfyUI: {exc}",
            )

        running = _prompt_ids(queue.get("queue_running", []))
        if normalized in running:
            return ComfyUIRecoveryObservation(
                ComfyUIRecoveryPresence.RUNNING,
                normalized,
                "ComfyUI reports the durable prompt is currently running.",
            )
        pending = _prompt_ids(queue.get("queue_pending", []))
        if normalized in pending:
            return ComfyUIRecoveryObservation(
                ComfyUIRecoveryPresence.PENDING,
                normalized,
                "ComfyUI reports the durable prompt is still queued.",
            )
        return ComfyUIRecoveryObservation(
            ComfyUIRecoveryPresence.NOT_FOUND,
            normalized,
            "ComfyUI history and queue no longer contain the durable prompt identity.",
        )

    def completed_outputs(self, prompt_id: str) -> tuple[ProviderExecutionOutput, ...]:
        normalized = prompt_id.strip()
        if not normalized:
            raise ValueError("prompt_id cannot be blank")
        history = self.client.history(normalized)
        if history is None or _history_terminal(history) is not ComfyUIRecoveryPresence.COMPLETED:
            return ()
        paths = _history_outputs(history)
        return tuple(
            ProviderExecutionOutput(
                output_id=f"PEO-RO-COMFY-{normalized}-{index:03d}",
                relative_path=path,
                media_kind=_media_kind(path),
                source_output_id=f"RO-COMFY-{normalized}-{index:03d}",
                metadata=(
                    ("renderer", "comfyui"),
                    ("recovered_after_restart", "true"),
                ),
            )
            for index, path in enumerate(paths, start=1)
        )


def _prompt_ids(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    values: list[str] = []
    for item in raw:
        if isinstance(item, list) and len(item) >= 2:
            prompt_id = str(item[1]).strip()
            if prompt_id:
                values.append(prompt_id)
    return tuple(values)


def _history_terminal(history: dict[str, object]) -> ComfyUIRecoveryPresence | None:
    raw_status = history.get("status")
    if not isinstance(raw_status, dict):
        return None
    completed = bool(raw_status.get("completed", False))
    status_str = str(raw_status.get("status_str", "")).casefold()
    if completed and status_str in {"success", "completed"}:
        return ComfyUIRecoveryPresence.COMPLETED
    if completed or status_str in {"error", "failed"}:
        return ComfyUIRecoveryPresence.FAILED
    return None


def _history_failure_reason(history: dict[str, object]) -> str:
    raw_status = history.get("status")
    if not isinstance(raw_status, dict):
        return "ComfyUI execution failed"
    messages = raw_status.get("messages", [])
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, list) and len(item) >= 2:
                return f"ComfyUI {item[0]}: {item[1]}"
    status_str = str(raw_status.get("status_str", "")).strip()
    return status_str or "ComfyUI execution failed"


def _history_outputs(history: dict[str, object]) -> tuple[str, ...]:
    raw_outputs = history.get("outputs", {})
    if not isinstance(raw_outputs, dict):
        return ()
    paths: set[str] = set()
    for node_output in raw_outputs.values():
        if not isinstance(node_output, dict):
            continue
        for collection in node_output.values():
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type", "output")).casefold() != "output":
                    continue
                filename = str(item.get("filename", "")).strip()
                if not filename:
                    continue
                subfolder = str(item.get("subfolder", "")).strip().replace("\\", "/")
                candidate = (
                    PurePosixPath(subfolder) / filename if subfolder else PurePosixPath(filename)
                )
                if candidate.is_absolute() or ".." in candidate.parts:
                    continue
                paths.add(str(candidate))
    return tuple(sorted(paths))


def _media_kind(path: str) -> str:
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix in {".mp4", ".webm", ".mov", ".mkv"}:
        return "production_video"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if suffix in {".wav", ".mp3", ".flac", ".ogg", ".m4a"}:
        return "audio"
    return "metadata"
