"""Deterministic provider-facing prompt compilation from approved production authority."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ProductionProviderPromptError(ValueError):
    """Raised when approved production authority cannot become a safe provider prompt."""


@dataclass(frozen=True, slots=True)
class ProductionProviderPrompt:
    """Concise provider-facing prompt while the full UPD remains audit authority."""

    positive_prompt: str
    negative_prompt: str
    compiler: str = "structured-authority-v1"


class ProductionProviderPromptCompiler:
    """Translate structured approved authority into cinematic provider prose."""

    MAX_POSITIVE_CHARS = 6000
    MAX_NEGATIVE_CHARS = 3000

    _NEGATIVE_PREFIXES = ("do not ", "don't ", "never ", "avoid ", "no ", "without ")
    _ADMINISTRATIVE_MARKERS = (
        "hardware-aware shot runtime",
        "preserve semantic source shot",
        "cinematic coverage role:",
        "provider-neutral",
    )
    _BASE_NEGATIVES = (
        "generated speech",
        "invented dialogue",
        "unscripted voice",
        "identity swap",
        "duplicated character",
        "merged identity",
        "contact sheet",
        "split screen",
        "tiled references",
    )

    def compile(self, production: dict[str, Any]) -> ProductionProviderPrompt:
        if not isinstance(production, dict):
            raise ProductionProviderPromptError("production authority must be an object")
        shot = self._mapping(production.get("shot"))
        action = self._mapping(production.get("action_performance"))
        camera = self._mapping(production.get("camera"))
        lighting = self._mapping(production.get("lighting"))
        environment = self._mapping(production.get("environment"))
        continuity = self._mapping(production.get("continuity"))
        style = self._mapping(production.get("style"))

        positive: list[str] = []
        negative: list[str] = list(self._BASE_NEGATIVES)
        for value in (
            shot.get("production_objective"),
            shot.get("required_action"),
            action.get("temporal_narrative"),
            action.get("performance_direction"),
            continuity.get("opening_state") or action.get("opening_state"),
            continuity.get("closing_state") or action.get("closing_state"),
        ):
            self._partition_text(value, positive, negative)
        for value in self._string_list(shot.get("shot_constraints")):
            self._partition_text(value, positive, negative)

        camera_text = self._camera_text(camera)
        if camera_text:
            positive.append(camera_text)
        for value in self._string_list(camera.get("camera_constraints")):
            self._partition_text(value, positive, negative)

        lighting_text = self._lighting_text(lighting)
        if lighting_text:
            positive.append(lighting_text)
        for value in self._string_list(lighting.get("lighting_constraints")):
            self._partition_text(value, positive, negative)

        environment_text = self._environment_text(environment)
        if environment_text:
            positive.append(environment_text)
        for value in self._string_list(environment.get("environment_constraints")):
            self._partition_text(value, positive, negative)

        style_text = self._style_text(style)
        if style_text:
            positive.append(style_text)
        for key in ("negative_constraints", "avoid", "forbidden", "negative_prompt"):
            raw = style.get(key)
            if isinstance(raw, str):
                self._partition_text(raw, [], negative, force_negative=True)
            else:
                for value in self._string_list(raw):
                    self._partition_text(value, [], negative, force_negative=True)

        positive = self._deduplicate(positive)
        negative = self._deduplicate(negative)
        if not positive:
            raise ProductionProviderPromptError(
                "approved production authority contains no provider-facing visual/action content"
            )
        positive_prompt = "\n".join(positive)
        negative_prompt = "; ".join(negative)
        if len(positive_prompt) > self.MAX_POSITIVE_CHARS:
            raise ProductionProviderPromptError(
                "provider-facing positive prompt exceeds "
                f"{self.MAX_POSITIVE_CHARS} characters; refine governed production authority "
                "instead of silently truncating it"
            )
        if len(negative_prompt) > self.MAX_NEGATIVE_CHARS:
            raise ProductionProviderPromptError(
                "provider-facing negative prompt exceeds "
                f"{self.MAX_NEGATIVE_CHARS} characters; refine governed production authority "
                "instead of silently truncating it"
            )
        return ProductionProviderPrompt(positive_prompt, negative_prompt)

    def _partition_text(
        self,
        value: object,
        positive: list[str],
        negative: list[str],
        *,
        force_negative: bool = False,
    ) -> None:
        text = str(value or "").strip()
        if not text:
            return
        for sentence in self._sentences(text):
            lowered = sentence.casefold()
            if any(marker in lowered for marker in self._ADMINISTRATIVE_MARKERS):
                continue
            if lowered.startswith(("continue directly into ep-", "continue into ep-")):
                continue
            if force_negative or lowered.startswith(self._NEGATIVE_PREFIXES):
                negative.append(sentence)
            else:
                positive.append(sentence)

    @staticmethod
    def _sentences(text: str) -> tuple[str, ...]:
        normalized = " ".join(text.split())
        if not normalized:
            return ()
        return tuple(
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", normalized)
            if part.strip()
        )

    @classmethod
    def _camera_text(cls, camera: dict[str, Any]) -> str:
        values: list[str] = []
        shot_size = cls._text(camera.get("shot_size"))
        angle = cls._text(camera.get("angle"))
        focal = camera.get("focal_length_mm")
        movement = cls._text(camera.get("movement"))
        if shot_size:
            values.append(f"{cls._humanize(shot_size)} shot")
        if angle:
            values.append(f"{cls._humanize(angle)} angle")
        if isinstance(focal, int | float) and not isinstance(focal, bool) and focal > 0:
            values.append(f"{focal:g} mm lens")
        if movement:
            values.append(f"{cls._humanize(movement)} camera movement")
        values.extend(
            value
            for value in (
                cls._text(camera.get("composition")),
                cls._text(camera.get("focus_strategy")),
                cls._text(camera.get("movement_notes")),
            )
            if value
        )
        return "Camera: " + "; ".join(cls._deduplicate(values)) if values else ""

    @classmethod
    def _lighting_text(cls, lighting: dict[str, Any]) -> str:
        values: list[str] = []
        intent = cls._text(lighting.get("lighting_intent"))
        temperature = lighting.get("color_temperature_k")
        quality = cls._text(lighting.get("key_quality"))
        direction = cls._text(lighting.get("key_direction"))
        fill = lighting.get("fill_level_percent")
        if intent:
            values.append(cls._humanize(intent))
        if isinstance(temperature, int | float) and not isinstance(temperature, bool):
            values.append(f"{temperature:g} K")
        if quality or direction:
            values.append(
                " ".join(
                    value
                    for value in (
                        cls._humanize(quality),
                        cls._humanize(direction),
                        "key",
                    )
                    if value
                )
            )
        if isinstance(fill, int | float) and not isinstance(fill, bool):
            values.append(f"{fill:g}% restrained fill")
        values.extend(
            value
            for value in (
                cls._text(lighting.get("source_strategy")),
                cls._text(lighting.get("shadow_strategy")),
                cls._text(lighting.get("subject_readability")),
            )
            if value
        )
        return "Lighting: " + "; ".join(cls._deduplicate(values)) if values else ""

    @classmethod
    def _environment_text(cls, environment: dict[str, Any]) -> str:
        values = [
            cls._humanize(value)
            for value in (
                cls._text(environment.get("environment_context")),
                cls._text(environment.get("atmosphere_state")),
                cls._text(environment.get("surface_state")),
                cls._text(environment.get("environmental_motion")),
            )
            if value
        ]
        return "Environment: " + "; ".join(cls._deduplicate(values)) if values else ""

    @classmethod
    def _style_text(cls, style: dict[str, Any]) -> str:
        values = [
            cls._text(style.get("declared_style")),
            cls._text(style.get("declared_tone")),
        ]
        cleaned = [cls._humanize(value) for value in values if value]
        return "Style: " + "; ".join(cls._deduplicate(cleaned)) if cleaned else ""

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _string_list(value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            return (value,) if value.strip() else ()
        if not isinstance(value, list | tuple):
            return ()
        return tuple(str(item).strip() for item in value if str(item).strip())

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    @staticmethod
    def _humanize(value: str) -> str:
        return " ".join(value.replace("_", " ").split())

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(str(raw).split()).strip(" ;")
            if not value:
                continue
            key = value.casefold().rstrip(".")
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result
