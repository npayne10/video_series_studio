"""Canonical Asset Intelligence Engine v1.0."""

from __future__ import annotations

import re

from vscs.application.caie.models import CanonicalPromptContext, CanonicalPromptPackage
from vscs.application.caie.rules import CATEGORY_RULES, DEFAULT_RULE, GLOBAL_NEGATIVE_TERMS, STYLE_PROFILES


class CAIEError(RuntimeError):
    """Raised when a canonical prompt cannot be compiled safely."""


class CanonicalAssetIntelligenceEngine:
    """Compile CAP facts into category-aware, model-ready image prompts."""

    VERSION = "1.0"
    _metadata_line = re.compile(
        r"^\s*(asset\s*id|cap[-_ ]?[a-z]+[-_ ]?\d+|category|status|version|story\s*role|canonical\s*description|visual\s*identity|production\s*notes)\s*[:\-]",
        re.IGNORECASE,
    )

    def compile(self, context: CanonicalPromptContext) -> CanonicalPromptPackage:
        rule = CATEGORY_RULES.get(context.category, DEFAULT_RULE)
        style = STYLE_PROFILES.get(context.style_profile, STYLE_PROFILES["grounded_cinematic"])
        description = self._clean_source(context.profile.canonical_description)
        identity = self._clean_source(context.profile.visual_identity)
        notes = self._clean_source(context.profile.production_notes)

        sections = [
            "Ultra-photorealistic premium production reference image.",
            f"Subject: {context.profile.title}. This is {rule.classification}.",
            rule.functional_language,
        ]
        if description:
            sections.append(f"Canonical design: {description}")
        if identity:
            sections.append(f"Visual identity: {identity}")
        if notes:
            sections.append(f"Production constraints: {notes}")
        sections.extend(
            (
                rule.environment_language,
                style,
                "Create one coherent image of the asset only. Do not render CAP metadata, labels, captions, title cards, interface panels or readable writing anywhere in the image.",
            )
        )
        positive = self._normalise("\n\n".join(sections))
        negative = ", ".join(dict.fromkeys((*rule.negative_terms, *GLOBAL_NEGATIVE_TERMS)))
        warnings = self._validate(positive, context, rule.required_anchors)
        return CanonicalPromptPackage(
            positive_prompt=positive,
            negative_prompt=negative,
            category=context.category,
            style_profile=context.style_profile,
            target_model=context.target_model,
            warnings=warnings,
            engine_version=self.VERSION,
        )

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

    def _validate(self, prompt: str, context: CanonicalPromptContext, anchors: tuple[str, ...]) -> tuple[str, ...]:
        lower = prompt.casefold()
        warnings: list[str] = []
        missing = [anchor for anchor in anchors if anchor.casefold() not in lower]
        if missing:
            raise CAIEError(
                f"CAIE could not establish required {context.category.value} prompt anchors: {', '.join(missing)}"
            )
        if context.profile.asset_id.casefold() in lower:
            warnings.append("Asset identifier was removed from visible prompt output where possible.")
        if len(prompt) > 6000:
            warnings.append("Compiled prompt exceeds 6,000 characters and may be shortened by some providers.")
        return tuple(warnings)
