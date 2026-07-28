"""Stable contracts for Production Readiness Evaluation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ProductionDecision(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    REGENERATE = "regenerate"


class CanonRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReadinessState(StrEnum):
    DEVELOPMENT = "development"
    CANDIDATE = "candidate"
    PRODUCTION_READY = "production_ready"
    CANON_LOCKED = "canon_locked"


class ProductionReadinessReport(BaseModel):
    """Combined technical and semantic production-readiness result."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_path: Path
    asset_id: str
    reference_id: int
    technical_score: int = Field(ge=0, le=100)
    semantic_score: int = Field(ge=0, le=100)
    canon_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    decision: ProductionDecision
    canon_risk: CanonRisk
    readiness_state: ReadinessState
    blocking_reasons: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    technical_report_path: Path
    semantic_report_path: Path
    engine_version: str = "1.0"

    def as_dict(self) -> dict[str, object]:
        return {
            "engine": "Production Readiness Evaluation",
            "engine_version": self.engine_version,
            "image_path": str(self.image_path),
            "asset_id": self.asset_id,
            "reference_id": self.reference_id,
            "technical_score": self.technical_score,
            "semantic_score": self.semantic_score,
            "canon_score": self.canon_score,
            "overall_score": self.overall_score,
            "decision": self.decision.value,
            "canon_risk": self.canon_risk.value,
            "readiness_state": self.readiness_state.value,
            "blocking_reasons": list(self.blocking_reasons),
            "recommendations": list(self.recommendations),
            "technical_report_path": str(self.technical_report_path),
            "semantic_report_path": str(self.semantic_report_path),
        }
