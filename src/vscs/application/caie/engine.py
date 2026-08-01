"""Canonical Asset Intelligence Engine v2.0."""

from __future__ import annotations

import re

from vscs.application.caie.knowledge_base import (
    CAIEKnowledgeBase,
    CAIEKnowledgeError,
    DesignKnowledge,
)
from vscs.application.caie.models import CanonicalPromptContext, CanonicalPromptPackage
from vscs.application.caie.rules import GLOBAL_NEGATIVE_TERMS


class CAIEError(RuntimeError):
    """Raised when a canonical prompt cannot be compiled safely."""


class CanonicalAssetIntelligenceEngine:
    """Compile CAP facts with category, archetype, engineering and style intelligence."""

    VERSION = "2.0"
    _metadata_line = re.compile(
        r"^\s*(asset\s*id|cap[-_ ]?[a-z]+[-_ ]?\d+|category|status|version|story\s*role|canonical\s*description|visual\s*identity|production\s*notes)\s*[:\-]",
        re.IGNORECASE,
    )

    def __init__(self, knowledge_base: CAIEKnowledgeBase | None = None) -> None:
        self.knowledge_base = knowledge_base or CAIEKnowledgeBase()

    def compile(self, context: CanonicalPromptContext) -> CanonicalPromptPackage:
        description = self._clean_source(context.profile.canonical_description)
        identity = self._clean_source(context.profile.visual_identity)
        notes = self._clean_source(context.profile.production_notes)
        refinements = tuple(
            cleaned
            for value in context.refinement_instructions
            if (cleaned := self._clean_source(value))
        )
        try:
            knowledge = self.knowledge_base.resolve(
                category=context.category,
                title=context.profile.title,
                description=description,
                visual_identity=identity,
            )
            style = self.knowledge_base.load_style(context.style_profile)
        except CAIEKnowledgeError as exc:
            raise CAIEError(str(exc)) from exc

        sections = [
            "Ultra-photorealistic premium production reference image.",
            f"Subject: {context.profile.title}.",
            f"Unambiguous classification: This is {knowledge.classification}.",
            self._section("Canonical purpose", knowledge.purpose),
            self._section("Required design language", knowledge.required_features),
            self._section("Engineering logic", knowledge.engineering_principles),
            self._section("Preferred semantic anchors", knowledge.preferred_language),
            self._section("Required semantic anchors", knowledge.required_anchors),
        ]
        if description:
            sections.append(f"Approved canonical description: {description}")
        if identity:
            sections.append(f"Approved visual identity: {identity}")
        if notes:
            sections.append(f"Production constraints: {notes}")
        sections.extend(
            (
                f"Operating environment: {knowledge.environment_guidance}",
                f"Reference composition: {knowledge.composition_guidance}",
                self._section("Forbidden visible features", knowledge.forbidden_features),
                self._section("Forbidden archetypes and interpretations", knowledge.forbidden_archetypes),
            )
        )
        if refinements:
            sections.append(
                self._section("Evaluation-driven corrections for this new iteration", refinements)
                + " These corrections refine presentation only and must not introduce new canon."
            )
        sections.extend(
            (
                self._section("Production style", style.positive_language),
                "Create one coherent image of the asset only. Do not render CAP metadata, labels, captions, title cards, interface panels, logos, registration numbers, hull names or readable writing anywhere in the image.",
            )
        )

        positive = self._normalise("\n\n".join(value for value in sections if value))
        negative = ", ".join(
            dict.fromkeys(
                (
                    *knowledge.negative_terms,
                    *knowledge.forbidden_features,
                    *knowledge.forbidden_archetypes,
                    *style.negative_terms,
                    *GLOBAL_NEGATIVE_TERMS,
                )
            )
        )
        warnings = list(self._validate(positive, context, knowledge))
        if refinements:
            warnings.append(f"Applied {len(refinements)} evaluation-feedback refinement(s).")
        return CanonicalPromptPackage(
            positive_prompt=positive,
            negative_prompt=negative,
            category=context.category,
            style_profile=context.style_profile,
            target_model=context.target_model,
            knowledge_id=knowledge.knowledge_id,
            warnings=tuple(warnings),
            engine_version=self.VERSION,
        )

    @staticmethod
    def _section(title: str, values: tuple[str, ...]) -> str:
        if not values:
            return ""
        return f"{title}: " + "; ".join(values) + "."

    def _clean_source(self, value: str) -> str:
        cleaned: list[str] = []
        for raw_line in value.replace("\r", "\n").split("\n"):
            line = raw_line.strip().strip("#*` ")
            if not line or self._metadata_line.match(line):
                continue
            cleaned.append(line)
        return self._normalise(" ".join(cleaned))

    @staticmethod
    def _normalise(value: str) -> str:
        return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", value)).strip()

    def _validate(
        self,
        prompt: str,
        context: CanonicalPromptContext,
        knowledge: DesignKnowledge,
    ) -> tuple[str, ...]:
        lower = prompt.casefold()
        warnings: list[str] = []
        missing = [anchor for anchor in knowledge.required_anchors if anchor.casefold() not in lower]
        if missing:
            raise CAIEError(
                f"CAIE knowledge '{knowledge.knowledge_id}' did not establish required prompt anchors: "
                + ", ".join(missing)
            )
        if context.profile.asset_id.casefold() in lower:
            warnings.append("Asset identifier remains in source prose and may need CAP cleanup.")
        if len(prompt) > 8000:
            warnings.append("Compiled prompt exceeds 8,000 characters and may be shortened by some providers.")
        return tuple(warnings)
