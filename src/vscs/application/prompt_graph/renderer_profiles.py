"""Renderer and quality specific prompt presentation profiles."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.rendering import QualityLevel, RendererKind

from .compiler import PromptPackage, PromptSectionKind


@dataclass(frozen=True, slots=True)
class RendererPromptProfile:
    """Approved formatting policy for one renderer and quality level."""

    profile_id: str
    display_name: str
    renderer: RendererKind
    quality_level: QualityLevel
    section_order: tuple[PromptSectionKind, ...]
    positive_separator: str = "; "
    negative_separator: str = "; "
    positive_prefix: str = ""
    positive_suffix: str = ""
    negative_prefix: str = ""
    negative_suffix: str = ""
    maximum_positive_characters: int | None = None
    maximum_negative_characters: int | None = None
    include_section_labels: bool = False

    def __post_init__(self) -> None:
        if not self.profile_id.strip() or not self.display_name.strip():
            raise ValueError("profile_id and display_name are required")
        if len(set(self.section_order)) != len(self.section_order):
            raise ValueError("section_order cannot contain duplicates")
        for name, value in (
            ("maximum_positive_characters", self.maximum_positive_characters),
            ("maximum_negative_characters", self.maximum_negative_characters),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be greater than zero")


class RendererPromptProfileRegistry:
    """Store approved prompt profiles by stable identity and target."""

    def __init__(self, profiles: tuple[RendererPromptProfile, ...] = ()) -> None:
        self._profiles: dict[str, RendererPromptProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: RendererPromptProfile) -> RendererPromptProfile:
        self._profiles[profile.profile_id] = profile
        return profile

    def get(self, profile_id: str) -> RendererPromptProfile | None:
        return self._profiles.get(profile_id)

    def require(self, profile_id: str) -> RendererPromptProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"Renderer prompt profile not registered: {profile_id}") from exc

    def resolve(
        self,
        renderer: RendererKind,
        quality_level: QualityLevel,
    ) -> RendererPromptProfile:
        matches = tuple(
            profile
            for profile in self._profiles.values()
            if profile.renderer is renderer and profile.quality_level is quality_level
        )
        if not matches:
            raise KeyError(
                f"Renderer prompt profile not registered for {renderer.value}/{quality_level.value}"
            )
        return sorted(matches, key=lambda item: item.profile_id)[0]

    def all(self) -> tuple[RendererPromptProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))


@dataclass(frozen=True, slots=True)
class ProfiledPromptPackage:
    """Renderer-formatted view of a renderer-neutral prompt package."""

    source: PromptPackage
    profile: RendererPromptProfile
    positive_prompt: str
    negative_prompt: str
    positive_truncated: bool = False
    negative_truncated: bool = False


class RendererPromptCompiler:
    """Apply a renderer profile without changing source production knowledge."""

    _NEGATIVE_SECTIONS = frozenset({PromptSectionKind.RESTRICTIONS, PromptSectionKind.NEGATIVE})

    def compile(
        self,
        package: PromptPackage,
        profile: RendererPromptProfile,
    ) -> ProfiledPromptPackage:
        by_kind = {section.kind: section for section in package.sections}
        positive_parts: list[str] = []
        negative_parts: list[str] = []
        for kind in profile.section_order:
            section = by_kind.get(kind)
            if section is None or not section.text.strip():
                continue
            text = section.text.strip()
            if profile.include_section_labels:
                text = f"{kind.value.replace('_', ' ').title()}: {text}"
            target = negative_parts if kind in self._NEGATIVE_SECTIONS else positive_parts
            target.append(text)

        positive = self._decorate(
            profile.positive_prefix,
            profile.positive_separator.join(positive_parts),
            profile.positive_suffix,
        )
        negative = self._decorate(
            profile.negative_prefix,
            profile.negative_separator.join(negative_parts),
            profile.negative_suffix,
        )
        positive, positive_truncated = self._limit(
            positive,
            profile.maximum_positive_characters,
        )
        negative, negative_truncated = self._limit(
            negative,
            profile.maximum_negative_characters,
        )
        return ProfiledPromptPackage(
            source=package,
            profile=profile,
            positive_prompt=positive,
            negative_prompt=negative,
            positive_truncated=positive_truncated,
            negative_truncated=negative_truncated,
        )

    @staticmethod
    def _decorate(prefix: str, value: str, suffix: str) -> str:
        return " ".join(part.strip() for part in (prefix, value, suffix) if part.strip())

    @staticmethod
    def _limit(value: str, maximum: int | None) -> tuple[str, bool]:
        if maximum is None or len(value) <= maximum:
            return value, False
        if maximum <= 1:
            return value[:maximum], True
        return f"{value[: maximum - 1].rstrip()}…", True


def default_renderer_prompt_profiles() -> tuple[RendererPromptProfile, ...]:
    """Return the approved initial ComfyUI Preview and Production profiles."""
    common = (
        PromptSectionKind.VISUAL_INTENT,
        PromptSectionKind.SCENE,
        PromptSectionKind.CHARACTERS,
        PromptSectionKind.ENVIRONMENT,
        PromptSectionKind.CAMERA,
        PromptSectionKind.LIGHTING,
        PromptSectionKind.MOVEMENT,
        PromptSectionKind.CONTINUITY,
        PromptSectionKind.EFFECTS,
        PromptSectionKind.DIALOGUE,
        PromptSectionKind.AUDIO,
        PromptSectionKind.STYLE,
        PromptSectionKind.QUALITY,
        PromptSectionKind.RESTRICTIONS,
        PromptSectionKind.NEGATIVE,
        PromptSectionKind.RENDERER,
        PromptSectionKind.OTHER,
    )
    return (
        RendererPromptProfile(
            profile_id="comfyui_preview_v1",
            display_name="ComfyUI Preview",
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PREVIEW,
            section_order=common,
            positive_separator=", ",
            negative_separator=", ",
            maximum_positive_characters=4000,
            maximum_negative_characters=2000,
        ),
        RendererPromptProfile(
            profile_id="comfyui_production_v1",
            display_name="ComfyUI Production",
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PRODUCTION,
            section_order=common,
            positive_separator="; ",
            negative_separator="; ",
            include_section_labels=True,
        ),
    )
