"""Deterministic prompt distillation for Phase 20.15.1b.

Structured production authority remains the source of truth. This module converts
that authority into concise model-facing language without serialising raw JSON into
the text-conditioning path. Encoder-facing text is deliberately bounded so provider
text encoders do not receive unbounded authority prose.
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
    positive_character_budget: int
    positive_character_count: int
    positive_compacted: bool
    negative_character_budget: int
    negative_character_count: int
    negative_compacted: bool


class ProductionPromptDistillationService:
    """Compile governed structured production intent into clean cinematic prose."""

    # LTX/Gemma text encoding is a provider resource boundary. The structured package
    # remains complete, but encoder-facing prose must stay deterministic and bounded.
    MAX_POSITIVE_PROMPT_CHARACTERS = 2000
    MAX_NEGATIVE_PROMPT_CHARACTERS = 800

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
        timing_text = f"Target runtime {duration_seconds:g} seconds at {fps} fps."

        # Priority order is intentional. If the encoder budget is reached, lower-priority
        # descriptive prose is omitted while governed identity, shot intent, action,
        # environment, camera, constraints and timing remain represented first.
        required_sections = (
            "Create one continuous uninterrupted cinematic shot.",
            shot_summary,
            identity_text,
            action_text,
            environment_text,
            camera_text,
            constraints,
            timing_text,
        )
        optional_sections = (
            dialogue_text,
            lighting_text,
            continuity_text,
            style_text,
        )
        positive, positive_compacted = self._bounded_sections(
            required_sections,
            optional_sections,
            self.MAX_POSITIVE_PROMPT_CHARACTERS,
        )
        negative_raw = self._negative_prompt(style, shot, environment)
        negative, negative_compacted = self._bounded_text(
            negative_raw,
            self.MAX_NEGATIVE_PROMPT_CHARACTERS,
        )

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
            positive_character_budget=self.MAX_POSITIVE_PROMPT_CHARACTERS,
            positive_character_count=len(positive),
            positive_compacted=positive_compacted,
            negative_character_budget=self.MAX_NEGATIVE_PROMPT_CHARACTERS,
            negative_character_count=len(negative),
            negative_compacted=negative_compacted,
        )

    @classmethod
    def _bounded_sections(
        cls,
        required: tuple[str, ...],
        optional: tuple[str, ...],
        budget: int,
    ) -> tuple[str, bool]:
        required_clean = [cls._encoder_safe_text(value) for value in required if value.strip()]
        optional_clean = [cls._encoder_safe_text(value) for value in optional if value.strip()]
        full = " ".join(required_clean + optional_clean)
        full = " ".join(full.split())
        if len(full) <= budget:
            return full, False

        selected: list[str] = []
        # Required sections may be compacted but are never silently displaced by optional prose.
        remaining_required = len(required_clean)
        for section in required_clean:
            remaining_required -= 1
            reserved = remaining_required * 80
            available = budget - len(" ".join(selected)) - reserved
            if selected:
                available -= 1
            if available <= 0:
                break
            selected.append(cls._truncate_at_boundary(section, available))

        for section in optional_clean:
            current = " ".join(selected)
            available = budget - len(current) - (1 if current else 0)
            if available < 80:
                break
            if len(section) <= available:
                selected.append(section)

        bounded = " ".join(selected)
        bounded = " ".join(bounded.split())
        if len(bounded) > budget:
            bounded = cls._truncate_at_boundary(bounded, budget)
        return bounded, True

    @classmethod
    def _bounded_text(cls, value: str, budget: int) -> tuple[str, bool]:
        safe = cls._encoder_safe_text(value)
        if len(safe) <= budget:
            return safe, False
        return cls._truncate_at_boundary(safe, budget), True

    @staticmethod
    def _truncate_at_boundary(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        if limit <= 3:
            return value[:limit]
        candidate = value[: limit - 3].rstrip()
        boundary = max(
            candidate.rfind(". "),
            candidate.rfind("; "),
            candidate.rfind(", "),
            candidate.rfind(" "),
        )
        if boundary >= max(40, len(candidate) // 2):
            candidate = candidate[:boundary].rstrip(" .;,")
        return candidate + "..."

    @staticmethod
    def _encoder_safe_text(value: str) -> str:
        replacements = str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2013": "-",
                "\u2014": "-",
                "\u2026": "...",
                "\u00a0": " ",
            }
        )
        return " ".join(value.translate(replacements).split())

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
            "Use supplied canonical visual references as authoritative identity definitions. "
            "Preserve exact canonical identity, geometry, scale, materials, markings and wardrobe. "
            "Do not redesign, merge or substitute canonical assets."
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
            parts.append(f"Begin with {opening.rstrip('. ')}")
        if closing:
            parts.append(f"End with {closing.rstrip('. ')}")
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
