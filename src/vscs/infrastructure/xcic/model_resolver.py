"""Resolve portable XCIC model names against the active ComfyUI installation."""

from __future__ import annotations

from pathlib import PurePath
from typing import Any


class XCICModelResolutionError(RuntimeError):
    """Raised when a workflow model cannot be matched safely to ComfyUI."""


class XCICModelResolver:
    """Replace portable model basenames with exact ComfyUI combo values.

    ComfyUI validates loader inputs against the values returned by ``/object_info``.
    Profiles may intentionally store only portable basenames, while ComfyUI may expose
    values such as ``qwen\\qwen_image_vae.safetensors``. Resolution is conservative:
    exact matches win, then slash-normalised matches, then unique basename matches.
    Ambiguous or missing model references fail before the workflow is submitted.
    """

    def resolve(
        self,
        workflow: dict[str, Any],
        object_info: dict[str, Any],
    ) -> dict[str, Any]:
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(class_type, str) or not isinstance(inputs, dict):
                continue
            node_info = object_info.get(class_type)
            if not isinstance(node_info, dict):
                continue
            choices = self._input_choices(node_info)
            for input_name, available in choices.items():
                current = inputs.get(input_name)
                if not isinstance(current, str) or not current.strip():
                    continue
                inputs[input_name] = self._resolve_value(
                    current,
                    available,
                    node_id=str(node_id),
                    class_type=class_type,
                    input_name=input_name,
                )
        return workflow

    @staticmethod
    def _input_choices(node_info: dict[str, Any]) -> dict[str, tuple[str, ...]]:
        result: dict[str, tuple[str, ...]] = {}
        input_section = node_info.get("input")
        if not isinstance(input_section, dict):
            return result
        for group_name in ("required", "optional"):
            group = input_section.get(group_name)
            if not isinstance(group, dict):
                continue
            for input_name, spec in group.items():
                if not isinstance(spec, (list, tuple)) or not spec:
                    continue
                candidates = spec[0]
                if isinstance(candidates, (list, tuple)) and all(
                    isinstance(item, str) for item in candidates
                ):
                    result[str(input_name)] = tuple(candidates)
        return result

    def _resolve_value(
        self,
        requested: str,
        available: tuple[str, ...],
        *,
        node_id: str,
        class_type: str,
        input_name: str,
    ) -> str:
        if requested in available:
            return requested

        requested_normalised = self._normalise(requested)
        normalised = [item for item in available if self._normalise(item) == requested_normalised]
        if len(normalised) == 1:
            return normalised[0]

        requested_name = self._basename(requested)
        basename_matches = [
            item
            for item in available
            if self._basename(item).casefold() == requested_name.casefold()
        ]
        if len(basename_matches) == 1:
            return basename_matches[0]
        if len(basename_matches) > 1:
            matches = ", ".join(basename_matches)
            raise XCICModelResolutionError(
                f"Ambiguous ComfyUI model for node {node_id} ({class_type}.{input_name}): "
                f"'{requested}' matches multiple installed values: {matches}"
            )

        # Do not reject ordinary free-text combo values. Model/file selectors are the
        # inputs whose names conventionally end in _name or contain model/checkpoint.
        if not self._looks_like_model_input(input_name):
            return requested

        sample = ", ".join(available[:12])
        raise XCICModelResolutionError(
            f"Unable to resolve ComfyUI model for node {node_id} ({class_type}.{input_name}): "
            f"'{requested}' is not installed. Available values include: {sample}"
        )

    @staticmethod
    def _normalise(value: str) -> str:
        return value.strip().replace("\\", "/").casefold()

    @staticmethod
    def _basename(value: str) -> str:
        return PurePath(value.replace("\\", "/")).name

    @staticmethod
    def _looks_like_model_input(input_name: str) -> bool:
        name = input_name.casefold()
        return name.endswith("_name") or any(
            token in name for token in ("model", "checkpoint", "unet", "clip", "vae", "lora")
        )
