"""Stable contracts for the Canonical Asset Intelligence Engine."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.domain.assets import Asset, AssetCategory
from vscs.domain.caps import CanonicalAssetProfile


@dataclass(frozen=True, slots=True)
class CanonicalPromptContext:
    """Canonical asset facts supplied to CAIE."""

    asset: Asset
    profile: CanonicalAssetProfile
    target_model: str = "Qwen Image 2512"
    style_profile: str = "xorix_grounded_scifi"
    refinement_instructions: tuple[str, ...] = ()

    @property
    def category(self) -> AssetCategory:
        return self.asset.category


@dataclass(frozen=True, slots=True)
class CanonicalPromptPackage:
    """Validated positive and negative prompts produced by CAIE."""

    positive_prompt: str
    negative_prompt: str
    category: AssetCategory
    style_profile: str
    target_model: str
    knowledge_id: str = "generic_asset"
    warnings: tuple[str, ...] = ()
    engine_version: str = "2.0"
