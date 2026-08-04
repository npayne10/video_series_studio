"""Prompt preview models and deterministic human-readable formatting."""

from __future__ import annotations

from dataclasses import dataclass

from .compiler import PromptSectionKind
from .renderer_profiles import ProfiledPromptPackage


@dataclass(frozen=True, slots=True)
class PromptPreviewSection:
    """One structured section exposed to a future prompt-preview UI."""

    kind: PromptSectionKind
    title: str
    text: str
    fragment_count: int
    canonical_asset_ids: tuple[str, ...] = ()
    reference_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptPreview:
    """Read-only renderer-profile preview of one prompt package."""

    package_id: str
    profile_id: str
    profile_name: str
    positive_prompt: str
    negative_prompt: str
    sections: tuple[PromptPreviewSection, ...]
    positive_character_count: int
    negative_character_count: int
    canonical_asset_count: int
    reference_count: int
    warnings: tuple[str, ...] = ()

    def section(self, kind: PromptSectionKind) -> PromptPreviewSection | None:
        return next((section for section in self.sections if section.kind is kind), None)


class PromptPreviewService:
    """Create deterministic prompt previews without renderer execution."""

    def create(self, package: ProfiledPromptPackage) -> PromptPreview:
        sections = tuple(
            PromptPreviewSection(
                kind=section.kind,
                title=section.kind.value.replace("_", " ").title(),
                text=section.text,
                fragment_count=len(section.fragments),
                canonical_asset_ids=tuple(
                    sorted(
                        {
                            fragment.canonical_asset_id
                            for fragment in section.fragments
                            if fragment.canonical_asset_id
                        }
                    )
                ),
                reference_ids=tuple(
                    sorted(
                        {
                            reference_id
                            for fragment in section.fragments
                            for reference_id in fragment.reference_ids
                        }
                    )
                ),
            )
            for section in package.source.sections
        )
        warnings: list[str] = []
        if package.positive_truncated:
            warnings.append("Positive prompt exceeds the renderer profile limit.")
        if package.negative_truncated:
            warnings.append("Negative prompt exceeds the renderer profile limit.")
        if not package.negative_prompt.strip():
            warnings.append("No negative prompt constraints are present.")
        if not package.source.reference_ids:
            warnings.append("No approved canonical references are attached.")
        return PromptPreview(
            package_id=package.source.package_id,
            profile_id=package.profile.profile_id,
            profile_name=package.profile.display_name,
            positive_prompt=package.positive_prompt,
            negative_prompt=package.negative_prompt,
            sections=sections,
            positive_character_count=len(package.positive_prompt),
            negative_character_count=len(package.negative_prompt),
            canonical_asset_count=len(package.source.canonical_asset_ids),
            reference_count=len(package.source.reference_ids),
            warnings=tuple(warnings),
        )

    @staticmethod
    def format(preview: PromptPreview) -> str:
        """Return a stable plain-text representation for logs and early UI use."""
        lines = [
            f"Prompt preview: {preview.package_id}",
            f"Profile: {preview.profile_name} ({preview.profile_id})",
            "",
            "POSITIVE PROMPT",
            preview.positive_prompt or "<empty>",
            "",
            "NEGATIVE PROMPT",
            preview.negative_prompt or "<empty>",
            "",
            "SECTIONS",
        ]
        for section in preview.sections:
            lines.extend((f"[{section.title}]", section.text or "<empty>"))
        lines.extend(
            (
                "",
                "SUMMARY",
                f"Positive characters: {preview.positive_character_count}",
                f"Negative characters: {preview.negative_character_count}",
                f"Canonical assets: {preview.canonical_asset_count}",
                f"Approved references: {preview.reference_count}",
            )
        )
        if preview.warnings:
            lines.extend(("", "WARNINGS", *preview.warnings))
        return "\n".join(lines)
