"""Deterministic cinematic provider prompts derived from approved production authority."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ProductionProviderPromptError(ValueError):
    """Raised when approved production authority cannot become a safe provider prompt."""


@dataclass(frozen=True, slots=True)
class ProductionProviderPrompt:
    """Provider-facing scene and motion prompts while the full UPD remains audit authority."""

    positive_prompt: str
    negative_prompt: str
    motion_prompt: str
    omitted_optional_sections: tuple[str, ...] = ()
    compiler: str = "cinematic-action-v2"

    @property
    def positive_word_count(self) -> int:
        return len(self.positive_prompt.split())

    @property
    def motion_word_count(self) -> int:
        return len(self.motion_prompt.split())


class ProductionProviderPromptCompiler:
    """Translate governed authority into literal, chronological cinematic prose."""

    COMPILER_ID = "cinematic-action-v2"
    MAX_POSITIVE_WORDS = 150
    MAX_MOTION_WORDS = 90
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
        style = self._mapping(production.get("style"))

        action_sentences, action_negatives = self._action_sentences(shot, action)
        participant_positive, participant_negative = self._participant_safeguards(
            production,
            shot,
            action,
            environment,
        )

        essential_positive: list[str] = []
        objective = self._text(shot.get("production_objective"))
        if objective:
            self._partition_text(objective, essential_positive, [])
        essential_positive.extend(participant_positive)
        essential_positive.extend(action_sentences)

        optional_positive = (
            ("camera", self._camera_text(camera)),
            ("lighting", self._lighting_text(lighting)),
            ("environment", self._environment_text(environment)),
            ("style", self._style_text(style)),
        )

        negative: list[str] = list(self._BASE_NEGATIVES)
        negative.extend(action_negatives)
        for value in self._string_list(shot.get("shot_constraints")):
            self._partition_text(value, [], negative)
        for value in self._string_list(camera.get("camera_constraints")):
            self._partition_text(value, [], negative)
        for value in self._string_list(lighting.get("lighting_constraints")):
            self._partition_text(value, [], negative)
        for value in self._string_list(environment.get("environment_constraints")):
            self._partition_text(value, [], negative)
        for key in ("negative_constraints", "avoid", "forbidden", "negative_prompt"):
            for value in self._negative_values(
                style.get(key),
                split_delimited=key == "negative_prompt",
            ):
                self._partition_text(value, [], negative, force_negative=True)
        negative.extend(participant_negative)

        essential_positive = self._deduplicate(essential_positive)
        negative = self._deduplicate(negative)
        motion = self._motion_prompt(
            action_sentences,
            participant_positive,
            camera,
            environment,
        )
        if not essential_positive:
            raise ProductionProviderPromptError(
                "approved production authority contains no provider-facing visual/action content"
            )

        positive_prompt, omitted_optional_sections = self._bounded_scene_prompt(
            essential_positive,
            optional_positive,
        )
        negative_prompt = "; ".join(negative)
        if self._word_count(motion) > self.MAX_MOTION_WORDS:
            raise ProductionProviderPromptError(
                "motion-only provider prompt exceeds "
                f"{self.MAX_MOTION_WORDS} words; simplify the governed Shot action"
            )
        if len(negative_prompt) > self.MAX_NEGATIVE_CHARS:
            raise ProductionProviderPromptError(
                "provider-facing negative prompt exceeds "
                f"{self.MAX_NEGATIVE_CHARS} characters; refine governed production authority "
                "instead of silently truncating it"
            )
        return ProductionProviderPrompt(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            motion_prompt=motion,
            omitted_optional_sections=omitted_optional_sections,
        )

    def _action_sentences(
        self,
        shot: dict[str, Any],
        action: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        temporal_positive: list[str] = []
        temporal_negative: list[str] = []
        required_positive: list[str] = []
        required_negative: list[str] = []
        performance_positive: list[str] = []
        performance_negative: list[str] = []

        self._partition_text(
            action.get("temporal_narrative"),
            temporal_positive,
            temporal_negative,
        )
        self._partition_text(
            shot.get("required_action"),
            required_positive,
            required_negative,
        )
        self._partition_text(
            action.get("performance_direction"),
            performance_positive,
            performance_negative,
        )

        positive = list(temporal_positive or required_positive)
        if temporal_positive:
            for sentence in required_positive:
                lowered = sentence.casefold()
                if lowered.startswith(("end ", "begin ", "keep ", "hold ", "remain ")):
                    positive.append(sentence)
        positive.extend(performance_positive)
        negative = temporal_negative + required_negative + performance_negative
        return self._deduplicate(positive), self._deduplicate(negative)

    def _motion_prompt(
        self,
        action_sentences: list[str],
        participant_positive: tuple[str, ...],
        camera: dict[str, Any],
        environment: dict[str, Any],
    ) -> str:
        motion: list[str] = []
        if participant_positive:
            motion.append(participant_positive[0])
        motion.extend(action_sentences)

        movement = self._text(camera.get("movement")).casefold()
        if movement == "static":
            motion.append("The camera remains locked in place throughout the shot.")

        environmental_motion = self._text(environment.get("environmental_motion"))
        if environmental_motion and environmental_motion.casefold().startswith("no "):
            motion.append("The environment remains visually stable throughout the shot.")

        cleaned = self._deduplicate(motion)
        return " ".join(self._ensure_terminal(value) for value in cleaned)

    def _bounded_scene_prompt(
        self,
        essential: list[str],
        optional: tuple[tuple[str, str], ...],
    ) -> tuple[str, tuple[str, ...]]:
        selected = list(essential)
        essential_prompt = " ".join(self._ensure_terminal(value) for value in selected)
        if self._word_count(essential_prompt) > self.MAX_POSITIVE_WORDS:
            raise ProductionProviderPromptError(
                "essential cinematic scene/action content exceeds "
                f"{self.MAX_POSITIVE_WORDS} words; simplify the governed Shot action before "
                "provider execution"
            )

        omitted: list[str] = []
        for label, value in optional:
            if not value:
                continue
            candidate = " ".join(
                self._ensure_terminal(item)
                for item in self._deduplicate([*selected, value])
            )
            if self._word_count(candidate) <= self.MAX_POSITIVE_WORDS:
                selected.append(value)
            else:
                omitted.append(label)
        prompt = " ".join(
            self._ensure_terminal(value)
            for value in self._deduplicate(selected)
        )
        return prompt, tuple(omitted)

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
            part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()
        )

    @classmethod
    def _camera_text(cls, camera: dict[str, Any]) -> str:
        parts: list[str] = []
        shot_size = cls._humanize(cls._text(camera.get("shot_size")))
        angle = cls._humanize(cls._text(camera.get("angle")))
        focal = camera.get("focal_length_mm")
        movement = cls._humanize(cls._text(camera.get("movement")))
        if shot_size:
            parts.append(shot_size)
        if angle:
            parts.append(angle)
        if isinstance(focal, int | float) and not isinstance(focal, bool) and focal > 0:
            parts.append(f"{focal:g} mm")
        if not parts and not movement:
            return ""

        description = "Use a " + " ".join(parts)
        if parts:
            description += " shot"
        if movement:
            description += f" with a {movement} camera"
        composition = cls._text(camera.get("composition"))
        if composition:
            description += f", {composition}"
        return description + "."

    @classmethod
    def _lighting_text(cls, lighting: dict[str, Any]) -> str:
        intent = cls._humanize(cls._text(lighting.get("lighting_intent")))
        temperature = lighting.get("color_temperature_k")
        quality = cls._humanize(cls._text(lighting.get("key_quality")))
        direction = cls._humanize(cls._text(lighting.get("key_direction")))
        fill = lighting.get("fill_level_percent")

        parts: list[str] = []
        if intent:
            parts.append(intent)
        if isinstance(temperature, int | float) and not isinstance(temperature, bool):
            parts.append(f"{temperature:g} K")
        if quality or direction:
            parts.append(" ".join(value for value in (quality, direction, "key") if value))
        if isinstance(fill, int | float) and not isinstance(fill, bool):
            parts.append(f"restrained {fill:g}% fill")
        return "Use " + ", ".join(parts) + " lighting." if parts else ""

    @classmethod
    def _environment_text(cls, environment: dict[str, Any]) -> str:
        values = [
            cls._humanize(cls._text(environment.get(key)))
            for key in (
                "environment_context",
                "atmosphere_state",
                "surface_state",
                "environmental_motion",
            )
        ]
        parts = [value for value in values if value]
        return "The environment remains " + ", ".join(parts) + "." if parts else ""

    @classmethod
    def _style_text(cls, style: dict[str, Any]) -> str:
        values = [
            cls._humanize(cls._text(style.get("declared_style"))),
            cls._humanize(cls._text(style.get("declared_tone"))),
        ]
        cleaned = [value for value in values if value]
        return (
            "Use a " + ", ".join(cls._deduplicate(cleaned)) + " visual treatment."
            if cleaned
            else ""
        )

    @classmethod
    def _participant_safeguards(
        cls,
        production: dict[str, Any],
        shot: dict[str, Any],
        action: dict[str, Any],
        environment: dict[str, Any],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Translate an existing two-person restriction into positive visual staging."""
        assets = production.get("assets")
        if not isinstance(assets, list | tuple):
            return (), ()
        character_ids = {
            cls._text(asset.get("asset_id")).upper()
            for asset in assets
            if isinstance(asset, dict)
            and cls._text(asset.get("category")).casefold() == "character"
            and cls._text(asset.get("asset_id"))
        }
        if len(character_ids) != 2:
            return (), ()

        governed_text = " ".join(
            (
                cls._text(shot.get("production_objective")),
                cls._text(shot.get("required_action")),
                cls._text(action.get("temporal_narrative")),
                cls._text(action.get("performance_direction")),
                cls._text(environment.get("continuity_notes")),
                *cls._string_list(shot.get("shot_constraints")),
            )
        ).casefold()
        if "additional named bridge officers" not in governed_text:
            return (), ()

        positive = ["Exactly two people are visible throughout the shot."]
        if "bridge" in governed_text:
            positive.append("All other bridge stations remain empty.")
        negative = (
            "extra people",
            "background people",
            "additional bridge crew",
            "additional officers",
            "third person",
        )
        return tuple(positive), negative

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

    @classmethod
    def _negative_values(
        cls,
        value: object,
        *,
        split_delimited: bool,
    ) -> tuple[str, ...]:
        values = cls._string_list(value)
        if not split_delimited:
            return values
        return tuple(
            fragment
            for raw in values
            for fragment in (part.strip() for part in re.split(r"[;,]\s*", raw))
            if fragment
        )

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    @staticmethod
    def _humanize(value: str) -> str:
        return " ".join(value.replace("_", " ").split())

    @staticmethod
    def _ensure_terminal(value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        return cleaned if cleaned.endswith((".", "!", "?")) else cleaned + "."

    @staticmethod
    def _word_count(value: str) -> int:
        return len(value.split())

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
