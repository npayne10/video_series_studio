"""Compile resolved ACPP intent into provider-neutral production prompts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from .resolution import ACPPResolutionResult, ResolutionProvenance


class PromptCompilationError(ValueError):
    """Raised when a resolved ACPP cannot produce a valid prompt."""


@dataclass(frozen=True, slots=True)
class PromptContribution:
    """Structured contribution supplied by one resolved prompt package."""

    package_id: str
    version: str
    positive_fragments: tuple[str, ...] = ()
    negative_fragments: tuple[str, ...] = ()
    behaviour_fragments: tuple[str, ...] = ()
    source: str = "catalog"
    checksum: str | None = None


class PromptContributionCatalog(Protocol):
    """Resolve structured text contributed by one prompt package."""

    def resolve_prompt_package(self, package_id: str) -> PromptContribution | None:
        """Return one prompt-package contribution, if available."""
        ...


@dataclass(frozen=True, slots=True)
class PromptCompilerConfig:
    """Policy controlling deterministic prompt compilation."""

    schema_version: str = "1.0"
    section_separator: str = "\n\n"
    require_resolved_package: bool = True
    require_prompt_contributions: bool = True
    include_provenance: bool = True

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
        if not self.section_separator:
            raise ValueError("section_separator must not be empty")


@dataclass(frozen=True, slots=True)
class CompiledPromptSection:
    """One named section in a compiled provider-neutral prompt."""

    name: str
    content: str


@dataclass(frozen=True, slots=True)
class CompiledProductionPrompt:
    """Complete deterministic prompt artifact for one ACPP clip."""

    clip_id: str
    schema_version: str
    positive_prompt: str
    negative_prompt: str
    sections: tuple[CompiledPromptSection, ...]
    canonical_reference_ids: tuple[str, ...]
    prompt_package_ids: tuple[str, ...]
    start_reference_id: str | None
    end_reference_id: str | None
    provenance: tuple[ResolutionProvenance, ...]
    checksum: str


class ACPPPromptCompiler:
    """Compile resolved ACPP intent and prompt-package contributions."""

    def __init__(
        self,
        contribution_catalog: PromptContributionCatalog | None = None,
        config: PromptCompilerConfig | None = None,
    ) -> None:
        self.contribution_catalog = contribution_catalog
        self.config = config or PromptCompilerConfig()

    def compile(self, resolution: ACPPResolutionResult) -> CompiledProductionPrompt:
        """Compile one resolved package into a stable prompt artifact."""
        if self.config.require_resolved_package and not resolution.passed:
            raise PromptCompilationError("Cannot compile prompts from a failed resource resolution")

        package = resolution.package
        prompt_package_ids = tuple(
            item.resource_id
            for item in resolution.provenance
            if item.resource_type == "prompt_package"
        )
        contributions = self._resolve_contributions(prompt_package_ids)
        sections = self._sections(resolution, contributions)
        positive_prompt = self.config.section_separator.join(
            section.content
            for section in sections
            if section.name != "negative_constraints" and section.content
        )
        negative_values = [*package.prompt.negative_constraints]
        for contribution in contributions:
            negative_values.extend(contribution.negative_fragments)
        negative_prompt = "; ".join(
            dict.fromkeys(value.strip() for value in negative_values if value.strip())
        )
        reference_ids = tuple(
            dict.fromkeys(
                reference_id
                for binding in package.assets
                for reference_id in binding.canonical_reference_ids
            )
        )
        provenance = resolution.provenance if self.config.include_provenance else ()
        checksum = self._checksum(
            package.identity.clip_id,
            positive_prompt,
            negative_prompt,
            sections,
            reference_ids,
            prompt_package_ids,
            package.continuity.start_reference_id,
            package.continuity.end_reference_id,
            provenance,
        )
        return CompiledProductionPrompt(
            clip_id=package.identity.clip_id,
            schema_version=self.config.schema_version,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            sections=sections,
            canonical_reference_ids=reference_ids,
            prompt_package_ids=prompt_package_ids,
            start_reference_id=package.continuity.start_reference_id,
            end_reference_id=package.continuity.end_reference_id,
            provenance=provenance,
            checksum=checksum,
        )

    def _resolve_contributions(
        self,
        package_ids: tuple[str, ...],
    ) -> tuple[PromptContribution, ...]:
        if not package_ids:
            return ()
        if self.contribution_catalog is None:
            if self.config.require_prompt_contributions:
                raise PromptCompilationError(
                    "Prompt packages were resolved but no contribution catalog is configured"
                )
            return ()

        contributions: list[PromptContribution] = []
        for package_id in package_ids:
            contribution = self.contribution_catalog.resolve_prompt_package(package_id)
            if contribution is None:
                if self.config.require_prompt_contributions:
                    raise PromptCompilationError(
                        f"Prompt package contribution not found: {package_id}"
                    )
                continue
            contributions.append(contribution)
        return tuple(contributions)

    @staticmethod
    def _sections(
        resolution: ACPPResolutionResult,
        contributions: tuple[PromptContribution, ...],
    ) -> tuple[CompiledPromptSection, ...]:
        package = resolution.package
        prompt = package.prompt
        contribution_positive = " ".join(
            fragment
            for contribution in contributions
            for fragment in contribution.positive_fragments
            if fragment.strip()
        )
        contribution_behaviour = " ".join(
            fragment
            for contribution in contributions
            for fragment in contribution.behaviour_fragments
            if fragment.strip()
        )
        canonical_assets = "; ".join(
            f"{binding.role.value}: {binding.asset_id}" for binding in package.assets
        )
        reference_binding = "; ".join(
            f"{binding.asset_id} -> {', '.join(binding.canonical_reference_ids)}"
            for binding in package.assets
            if binding.canonical_reference_ids
        )
        start_requirement = (
            f"Use start reference {package.continuity.start_reference_id}."
            if package.continuity.start_reference_id
            else ""
        )
        end_requirement = (
            f"Produce end reference {package.continuity.end_reference_id}."
            if package.continuity.end_reference_id
            else ""
        )
        continuity = " ".join(
            value
            for value in (
                prompt.continuity_intent,
                *package.continuity.requirements,
                start_requirement,
                end_requirement,
            )
            if value.strip()
        )
        return tuple(
            section
            for section in (
                CompiledPromptSection(
                    "visual_intent",
                    prompt.positive_visual_intent.strip(),
                ),
                CompiledPromptSection("canonical_assets", canonical_assets),
                CompiledPromptSection(
                    "canonical_references",
                    reference_binding,
                ),
                CompiledPromptSection(
                    "environment",
                    prompt.environment_intent.strip(),
                ),
                CompiledPromptSection("camera", prompt.camera_language.strip()),
                CompiledPromptSection("lighting", prompt.lighting_intent.strip()),
                CompiledPromptSection(
                    "behaviour",
                    " ".join(
                        value
                        for value in (
                            prompt.behaviour_intent.strip(),
                            contribution_behaviour,
                        )
                        if value
                    ),
                ),
                CompiledPromptSection(
                    "prompt_packages",
                    contribution_positive,
                ),
                CompiledPromptSection("continuity", continuity),
                CompiledPromptSection(
                    "negative_constraints",
                    "; ".join(prompt.negative_constraints),
                ),
            )
            if section.content
        )

    def _checksum(
        self,
        clip_id: str,
        positive_prompt: str,
        negative_prompt: str,
        sections: tuple[CompiledPromptSection, ...],
        reference_ids: tuple[str, ...],
        prompt_package_ids: tuple[str, ...],
        start_reference_id: str | None,
        end_reference_id: str | None,
        provenance: tuple[ResolutionProvenance, ...],
    ) -> str:
        payload = {
            "clip_id": clip_id,
            "schema_version": self.config.schema_version,
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "sections": [
                {"name": section.name, "content": section.content} for section in sections
            ],
            "canonical_reference_ids": list(reference_ids),
            "prompt_package_ids": list(prompt_package_ids),
            "start_reference_id": start_reference_id,
            "end_reference_id": end_reference_id,
            "provenance": [
                {
                    "resource_id": item.resource_id,
                    "resource_type": item.resource_type,
                    "version": item.version,
                    "source": item.source,
                    "checksum": item.checksum,
                    "related_ids": list(item.related_ids),
                }
                for item in provenance
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
