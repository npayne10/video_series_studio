"""Deterministic lighting planning for SSIE shots."""

from __future__ import annotations

from .models import LightingMood, LightingPlan, Scene, ShotPlan, ShotPurpose


class RuleBasedLightingPlanner:
    """Derive consistent narrative lighting intent from scene and shot context."""

    def plan_lighting(
        self,
        scene: Scene,
        shot: ShotPlan,
        emotional_intent: str,
    ) -> LightingPlan:
        mood = self._mood(scene, shot, emotional_intent)
        return LightingPlan(
            mood=mood,
            key_direction=self._key_direction(shot),
            contrast=self._contrast(mood),
            practical_sources=self._practical_sources(scene),
            continuity_key=self._continuity_key(scene, mood),
            profile_requirements=(
                f"support {mood.value} narrative lighting",
                "preserve physically plausible source direction",
            ),
        )

    @staticmethod
    def _mood(
        scene: Scene,
        shot: ShotPlan,
        emotional_intent: str,
    ) -> LightingMood:
        text = f"{scene.summary} {emotional_intent}".casefold()
        if any(term in text for term in ("tension", "alarm", "attack", "danger")):
            return LightingMood.TENSE
        if any(term in text for term in ("wonder", "discover", "reveal", "awe")):
            return LightingMood.AWE
        if any(term in text for term in ("grief", "loss", "sombre", "sad")):
            return LightingMood.SOMBRE
        if any(term in text for term in ("hope", "optimism", "relief")):
            return LightingMood.HOPEFUL
        if shot.purpose is ShotPurpose.TRANSITION:
            return LightingMood.TRANSITIONAL
        return LightingMood.NATURALISTIC

    @staticmethod
    def _key_direction(shot: ShotPlan) -> str:
        if shot.purpose in {ShotPurpose.COVERAGE, ShotPurpose.REACTION}:
            return "retain the established scene key across the subject eye-line"
        if shot.purpose is ShotPurpose.INSERT:
            return "shape the featured detail from the established practical source"
        return "motivate the key from the dominant environmental source"

    @staticmethod
    def _contrast(mood: LightingMood) -> str:
        if mood in {LightingMood.TENSE, LightingMood.SOMBRE}:
            return "controlled low-key contrast with retained shadow detail"
        if mood in {LightingMood.AWE, LightingMood.HOPEFUL}:
            return "open contrast with restrained highlights and readable faces"
        return "balanced naturalistic contrast"

    @staticmethod
    def _practical_sources(scene: Scene) -> tuple[str, ...]:
        sources = ["approved location practical lighting"]
        if scene.time_of_day:
            sources.append(f"{scene.time_of_day.strip()} environmental light")
        return tuple(sources)

    @staticmethod
    def _continuity_key(scene: Scene, mood: LightingMood) -> str:
        time = scene.time_of_day.strip() if scene.time_of_day else "unspecified time"
        return f"{scene.location_asset_id}:{time}:{mood.value}"
