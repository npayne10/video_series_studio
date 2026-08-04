"""Deterministic, production-safe prompt optimisation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import StrEnum

from .compiler import PromptFragment, PromptPackage, PromptSection, PromptSectionKind
from .renderer_profiles import (
    ProfiledPromptPackage,
    RendererPromptCompiler,
    RendererPromptProfile,
)


class PromptOptimizationSeverity(StrEnum):
    """Severity assigned to one optimisation diagnostic."""

    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class PromptOptimizationDiagnostic:
    """One traceable optimisation decision or compatibility warning."""

    code: str
    severity: PromptOptimizationSeverity
    message: str
    subject: str = ""


@dataclass(frozen=True, slots=True)
class PromptOptimizationPolicy:
    """Rules controlling safe prompt compaction."""

    remove_exact_duplicates: bool = True
    normalize_whitespace: bool = True
    omit_optional_fragments_for_limits: bool = True
    protected_section_kinds: frozenset[PromptSectionKind] = frozenset(
        {
            PromptSectionKind.VISUAL_INTENT,
            PromptSectionKind.CHARACTERS,
            PromptSectionKind.CAMERA,
            PromptSectionKind.LIGHTING,
            PromptSectionKind.CONTINUITY,
            PromptSectionKind.DIALOGUE,
            PromptSectionKind.RESTRICTIONS,
            PromptSectionKind.NEGATIVE,
        }
    )


@dataclass(frozen=True, slots=True)
class PromptOptimizationReport:
    """Before-and-after metrics and decisions for one optimisation pass."""

    original_positive_characters: int
    optimized_positive_characters: int
    original_negative_characters: int
    optimized_negative_characters: int
    duplicate_fragments_removed: int
    optional_fragments_omitted: int
    protected_fragments_preserved: int
    within_profile_limits: bool
    diagnostics: tuple[PromptOptimizationDiagnostic, ...] = ()

    @property
    def characters_saved(self) -> int:
        original = self.original_positive_characters + self.original_negative_characters
        optimized = self.optimized_positive_characters + self.optimized_negative_characters
        return original - optimized


@dataclass(frozen=True, slots=True)
class OptimizedPromptPackage:
    """Optimised renderer package with complete source provenance."""

    source: PromptPackage
    profiled: ProfiledPromptPackage
    report: PromptOptimizationReport


@dataclass(slots=True)
class PromptOptimizationService:
    """Optimise prompts without weakening authoritative production knowledge."""

    renderer_compiler: RendererPromptCompiler
    policy: PromptOptimizationPolicy = field(default_factory=PromptOptimizationPolicy)

    def optimize(
        self,
        package: PromptPackage,
        profile: RendererPromptProfile,
    ) -> OptimizedPromptPackage:
        original = self.renderer_compiler.compile(package, profile)
        sections, duplicates, diagnostics = self._compact(package.sections)
        optimized_package = replace(package, sections=sections)
        profiled = self.renderer_compiler.compile(optimized_package, profile)
        omitted = 0

        if self.policy.omit_optional_fragments_for_limits:
            optimized_package, profiled, omitted, limit_diagnostics = self._fit_limits(
                optimized_package,
                profile,
            )
            diagnostics.extend(limit_diagnostics)

        within_limits = self._within_limits(profiled, profile)
        protected = sum(
            1
            for section in optimized_package.sections
            for fragment in section.fragments
            if self._protected(section.kind, fragment)
        )
        report = PromptOptimizationReport(
            original_positive_characters=len(original.positive_prompt),
            optimized_positive_characters=len(profiled.positive_prompt),
            original_negative_characters=len(original.negative_prompt),
            optimized_negative_characters=len(profiled.negative_prompt),
            duplicate_fragments_removed=duplicates,
            optional_fragments_omitted=omitted,
            protected_fragments_preserved=protected,
            within_profile_limits=within_limits,
            diagnostics=tuple(diagnostics),
        )
        return OptimizedPromptPackage(package, profiled, report)

    def _compact(
        self,
        sections: tuple[PromptSection, ...],
    ) -> tuple[
        tuple[PromptSection, ...],
        int,
        list[PromptOptimizationDiagnostic],
    ]:
        seen: set[tuple[bool, str]] = set()
        compacted: list[PromptSection] = []
        duplicates = 0
        diagnostics: list[PromptOptimizationDiagnostic] = []
        negative_kinds = {
            PromptSectionKind.RESTRICTIONS,
            PromptSectionKind.NEGATIVE,
        }
        for section in sections:
            fragments: list[PromptFragment] = []
            for fragment in section.fragments:
                text = self._normalize(fragment.text)
                key = (section.kind in negative_kinds, text.casefold())
                if self.policy.remove_exact_duplicates and key in seen:
                    duplicates += 1
                    diagnostics.append(
                        PromptOptimizationDiagnostic(
                            "optimization.duplicate_removed",
                            PromptOptimizationSeverity.INFO,
                            "Exact duplicate prompt fragment removed.",
                            fragment.node_id,
                        )
                    )
                    continue
                seen.add(key)
                fragments.append(replace(fragment, text=text))
            if fragments:
                compacted.append(PromptSection(section.kind, tuple(fragments)))
        return tuple(compacted), duplicates, diagnostics

    def _fit_limits(
        self,
        package: PromptPackage,
        profile: RendererPromptProfile,
    ) -> tuple[
        PromptPackage,
        ProfiledPromptPackage,
        int,
        list[PromptOptimizationDiagnostic],
    ]:
        current = package
        profiled = self.renderer_compiler.compile(current, profile)
        omitted = 0
        diagnostics: list[PromptOptimizationDiagnostic] = []
        while profiled.positive_truncated or profiled.negative_truncated:
            candidate = self._last_optional_fragment(current)
            if candidate is None:
                unlimited = replace(
                    profile,
                    maximum_positive_characters=None,
                    maximum_negative_characters=None,
                )
                preserved = self.renderer_compiler.compile(current, unlimited)
                profiled = replace(preserved, profile=profile)
                diagnostics.append(
                    PromptOptimizationDiagnostic(
                        "optimization.protected_content_exceeds_limit",
                        PromptOptimizationSeverity.WARNING,
                        "Protected production content exceeds the renderer profile limit; "
                        "full content was preserved.",
                        profile.profile_id,
                    )
                )
                break
            section_kind, node_id = candidate
            current = self._remove_fragment(current, section_kind, node_id)
            omitted += 1
            diagnostics.append(
                PromptOptimizationDiagnostic(
                    "optimization.optional_fragment_omitted",
                    PromptOptimizationSeverity.INFO,
                    "Optional fragment omitted to satisfy renderer limits.",
                    node_id,
                )
            )
            profiled = self.renderer_compiler.compile(current, profile)
        return current, profiled, omitted, diagnostics

    def _last_optional_fragment(
        self,
        package: PromptPackage,
    ) -> tuple[PromptSectionKind, str] | None:
        for section in reversed(package.sections):
            for fragment in reversed(section.fragments):
                if not self._protected(section.kind, fragment):
                    return section.kind, fragment.node_id
        return None

    @staticmethod
    def _remove_fragment(
        package: PromptPackage,
        kind: PromptSectionKind,
        node_id: str,
    ) -> PromptPackage:
        sections: list[PromptSection] = []
        for section in package.sections:
            fragments = tuple(
                fragment
                for fragment in section.fragments
                if not (section.kind is kind and fragment.node_id == node_id)
            )
            if fragments:
                sections.append(PromptSection(section.kind, fragments))
        return replace(package, sections=tuple(sections))

    def _protected(self, kind: PromptSectionKind, fragment: PromptFragment) -> bool:
        return fragment.mandatory or kind in self.policy.protected_section_kinds

    def _normalize(self, value: str) -> str:
        if not self.policy.normalize_whitespace:
            return value.strip()
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _within_limits(
        package: ProfiledPromptPackage,
        profile: RendererPromptProfile,
    ) -> bool:
        positive_ok = (
            profile.maximum_positive_characters is None
            or len(package.positive_prompt) <= profile.maximum_positive_characters
        )
        negative_ok = (
            profile.maximum_negative_characters is None
            or len(package.negative_prompt) <= profile.maximum_negative_characters
        )
        return positive_ok and negative_ok
