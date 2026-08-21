"""Deterministic prompt distillation for Phase 20.15.1b.

Structured production authority remains the source of truth. This module converts
that authority into concise model-facing language without serialising raw JSON into
the text-conditioning path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DistilledPromptSet:
    """Provider-facing prompt language derived from governed production authority."""

    positive: str
    negative: str
    identity: str
    environment: str
    camera: str
    lighting: str
    action: str
    continuity: str
    dialogue: str
    shot_summary: str


class ProductionPromptDistillationService:
    """Compile governed structured production intent into clean cinematic prose."""

    DEFAULT_NEGATIVE_CONSTRAINTS = (
        "wrong canonical asset identity",
        "redesigned canonical asset",
        "altered canonical geometry",
        "incorrect canonical scale",
        "duplicate subjects",
        "unrequested people or objects",
        "identity drift",
        "morphing",
        "flicker",
        "unstable lighting",
        "erratic camera movement",
        "unrequested jump cut",
        "cartoon or anime styling",
        "painterly styling",
        "low detail",
        "AI artifacts",
    )

    def distill(
        self,
        production: dict[str, Any],
        *,
        universal_text: str,
        fps: int,
        duration_seconds: float,
    ) -> DistilledPromptSet:
        shot = self._mapping(production.get("shot"))
        assets = self._list_of_mappings(production.get("assets"))
        camera = self._mapping(production.get("camera"))
        lighting = self._mapping(production.get("lighting"))
        environment = self._mapping(production.get("environment"))
        action = self._mapping(production.get("action_performance"))
        continuity = self._mapping(production.get("continuity"))
        style = self._mapping(production.get("style"))
        dialogue = self._list_of_mappings(production.get("dialogue"))

        shot_summary = self._first_text(
            shot,
            ("production_objective", "narrative_purpose", "required_action", "title"),
        ) or self._clean_universal_text(universal_text)
        identity_text = self._identity_prompt(assets)
        environment_text = self._environment_prompt(environment)
        camera_text = self._camera_prompt(camera)
        lighting_text = self._lighting_prompt(lighting)
        action_text = self._action_prompt(shot, action)
        continuity_text = self._continuity_prompt(shot, continuity)
        dialogue_text = self._dialogue_prompt(shot, action, dialogue)
        constraints = self._constraints(shot, environment, camera, lighting)
        style_text = self._style_prompt(style)

        sections = [
            "Create one continuous uninterrupted cinematic shot.",
            shot_summary,
            identity_text,
            action_text,
            environment_text,
            camera_text,
            lighting_text,
            continuity_text,
            dialogue_text,
            constraints,
            style_text,
            f"Target runtime {duration_seconds:g} seconds at {fps} fps.",
        ]
        positive = " ".join(section.strip() for section in sections if section.strip())
        positive = " ".join(positive.split())
        negative = self._negative_prompt(style, shot, environment)
        return DistilledPromptSet(
            positive=positive,
            negative=negative,
            identity=identity_text,
            environment=environment_text,
            camera=camera_text,
            lighting=lighting_text,
            action=action_text,
            continuity=continuity_text,
            dialogue=dialogue_text,
            shot_summary=shot_summary,
        )

    @staticmethod
    def _clean_universal_text(value: str) -> str:
        """Use universal text only when it is prose rather than structured dump text."""
        markers = (
            "SHOT:",
            "ACTION & PERFORMANCE:",
            "ASSETS:",
            "CAMERA:",
            "LIGHTING:",
            "ENVIRONMENT:",
            "CONTINUITY:",
            "STYLE:",
            "CANONICAL REFERENCES:",
        )
        if any(marker in value for marker in markers):
            return ""
        return " ".join(value.split())

    @classmethod
    def _identity_prompt(cls, assets: list[dict[str, Any]]) -> str:
        if not assets:
            return ""
        labels: list[str] = []
        for asset in assets:
            role = cls._text(asset.get("role"))
            requirement = cls._text(asset.get("requirement"))
            asset_id = cls._text(asset.get("asset_id"))
            label = role or requirement or asset_id
            if label:
                labels.append(label.rstrip("."))
        names = ", ".join(dict.fromkeys(labels))
        base = (
            "Use all supplied canonical visual references as authoritative identity definitions. "
            "Preserve exact canonical identity, geometry, scale, materials, markings, wardrobe and "
            "other declared visual characteristics. Do not redesign, merge or substitute canonical assets."
        )
        return f"{base} Required canonical subjects: {names}." if names else base

    @classmethod
    def _environment_prompt(cls, environment: dict[str, Any]) -> str:
        context = cls._humanize(environment.get("environment_context"))
        atmosphere = cls._humanize(environment.get("atmosphere_state"))
        motion = cls._text(environment.get("environmental_motion"))
        surface = cls._text(environment.get("surface_state"))
        parts = [part for part in (context, atmosphere, motion, surface) if part]
        if not parts:
            return ""
        return "Environment: " + "; ".join(dict.fromkeys(parts)) + "."

    @classmethod
    def _camera_prompt(cls, camera: dict[str, Any]) -> str:
        if not camera:
            return ""
        pieces: list[str] = []
        shot_size = cls._humanize(camera.get("shot_size"))
        angle = cls._humanize(camera.get("angle"))
        movement = cls._humanize(camera.get("movement"))
        focal = camera.get("focal_length_mm")
        lens = cls._humanize(camera.get("lens_family"))
        composition = cls._text(camera.get("composition"))
        focus = cls._text(camera.get("focus_strategy"))
        if shot_size:
            pieces.append(shot_size)
        if angle:
            pieces.append(f"{angle} angle")
        if isinstance(focal, int | float) and not isinstance(focal, bool):
            pieces.append(f"{focal:g} mm {lens} lens" if lens else f"{focal:g} mm lens")
        if movement:
            pieces.append(f"{movement} camera")
        if composition:
            pieces.append(composition)
        if focus:
            pieces.append(focus)
        return "Camera: " + "; ".join(pieces) + "." if pieces else ""

    @classmethod
    def _lighting_prompt(cls, lighting: dict[str, Any]) -> str:
        if not lighting:
            return ""
        pieces: list[str] = []
        intent = cls._humanize(lighting.get("lighting_intent"))
        direction = cls._humanize(lighting.get("key_direction"))
        quality = cls._humanize(lighting.get("key_quality"))
        temperature = lighting.get("color_temperature_k")
        source = cls._text(lighting.get("source_strategy"))
        readability = cls._text(lighting.get("subject_readability"))
        if intent:
            pieces.append(intent)
        if direction:
            pieces.append(f"{direction} key")
        if quality:
            pieces.append(f"{quality} key quality")
        if isinstance(temperature, int | float) and not isinstance(temperature, bool):
            pieces.append(f"approximately {temperature:g} K")
        if source:
            pieces.append(source)
        if readability:
            pieces.append(readability)
        return "Lighting: " + "; ".join(pieces) + "." if pieces else ""

    @classmethod
    def _action_prompt(cls, shot: dict[str, Any], action: dict[str, Any]) -> str:
        value = cls._first_text(
            action,
            ("temporal_narrative", "performance_direction", "opening_state", "closing_state"),
        ) or cls._first_text(shot, ("required_action",))
        return f"Action and performance: {value}" if value else ""

    @classmethod
    def _continuity_prompt(cls, shot: dict[str, Any], continuity: dict[str, Any]) -> str:
        opening = cls._first_text(continuity, ("opening_state",)) or cls._first_text(
            shot, ("continuity_in",)
        )
        closing = cls._first_text(continuity, ("closing_state",)) or cls._first_text(
            shot, ("continuity_out",)
        )
        parts: list[str] = []
        if opening:
            parts.append(f"Begin with {opening}")
        if closing:
            parts.append(f"End with {closing}")
        return "Continuity: " + "; ".join(parts) + "." if parts else ""

    @classmethod
    def _dialogue_prompt(
        cls,
        shot: dict[str, Any],
        action: dict[str, Any],
        dialogue: list[dict[str, Any]],
    ) -> str:
        spoken = cls._first_text(action, ("spoken_content",)) or cls._first_text(
            shot, ("dialogue_requirement",)
        )
        if not spoken and dialogue:
            lines: list[str] = []
            for item in dialogue:
                text = cls._first_text(item, ("text", "line", "dialogue", "spoken_content"))
                if text:
                    lines.append(text)
            spoken = " ".join(lines)
        return f"Required spoken content: {spoken}" if spoken else ""

    @classmethod
    def _constraints(
        cls,
        shot: dict[str, Any],
        environment: dict[str, Any],
        camera: dict[str, Any],
        lighting: dict[str, Any],
    ) -> str:
        values: list[str] = []
        for mapping, key in (
            (shot, "shot_constraints"),
            (environment, "environment_constraints"),
            (camera, "camera_constraints"),
            (lighting, "lighting_constraints"),
        ):
            raw = mapping.get(key)
            if isinstance(raw, list):
                values.extend(cls._text(item) for item in raw if cls._text(item))
        return "Constraints: " + " ".join(dict.fromkeys(values)) if values else ""

    @classmethod
    def _style_prompt(cls, style: dict[str, Any]) -> str:
        declared = cls._first_text(style, ("declared_style", "declared_tone"))
        if declared:
            return f"Visual style: {declared}."
        return (
            "Grounded photorealistic cinematic realism, physically plausible materials and lighting, "
            "premium streaming television quality, restrained visual effects and natural motion."
        )

    @classmethod
    def _negative_prompt(
        cls,
        style: dict[str, Any],
        shot: dict[str, Any],
        environment: dict[str, Any],
    ) -> str:
        values = list(cls.DEFAULT_NEGATIVE_CONSTRAINTS)
        for mapping, keys in (
            (style, ("negative_constraints", "avoid", "forbidden", "negative_prompt")),
            (shot, ("negative_constraints", "avoid", "forbidden")),
            (environment, ("negative_constraints", "avoid", "forbidden")),
        ):
            for key in keys:
                raw = mapping.get(key)
                if isinstance(raw, str) and raw.strip():
                    values.append(raw.strip())
                elif isinstance(raw, list):
                    values.extend(cls._text(item) for item in raw if cls._text(item))
        return "; ".join(dict.fromkeys(values))

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _list_of_mappings(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, dict)]

    @classmethod
    def _first_text(cls, value: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            text = cls._text(value.get(key))
            if text:
                return text
        return ""

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if isinstance(value, str) and value.strip() else ""

    @classmethod
    def _humanize(cls, value: object) -> str:
        text = cls._text(value)
        return text.replace("_", " ") if text else ""
