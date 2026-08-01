"""Canonical Asset Profile domain exports."""

from vscs.domain.caps.asset_generation import (
    CanonicalAssetGenerationRequest,
    GeneratedCanonicalAsset,
)
from vscs.domain.caps.generation import (
    CanonicalFactExtraction,
    CAPCanonAnalysis,
    CAPGenerationRequest,
    CAPSectionConfidence,
    ExtractedCanonicalFact,
    GeneratedCAPDraft,
)
from vscs.domain.caps.models import CanonicalAssetProfile, CAPCreate, CAPStatus, CAPUpdate
from vscs.domain.caps.references import (
    CanonicalReference,
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceUpdate,
)

__all__ = (
    "CAPCanonAnalysis",
    "CAPCreate",
    "CAPGenerationRequest",
    "CAPSectionConfidence",
    "CAPStatus",
    "CAPUpdate",
    "CanonicalAssetGenerationRequest",
    "CanonicalAssetProfile",
    "CanonicalFactExtraction",
    "CanonicalReference",
    "CanonicalReferenceCreate",
    "CanonicalReferenceRole",
    "CanonicalReferenceStatus",
    "CanonicalReferenceType",
    "CanonicalReferenceUpdate",
    "ExtractedCanonicalFact",
    "GeneratedCAPDraft",
    "GeneratedCanonicalAsset",
)
