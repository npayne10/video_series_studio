"""Durable JSON persistence for provider capability-validation sessions."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from vscs.application.provider_capability_validation import (
    CapabilityValidationRepositoryError,
)
from vscs.domain.provider_capability_validation import (
    CapabilityRecommendation,
    CapabilityValidationSession,
    CriterionResult,
    HumanDecision,
    ScenarioResult,
    ValidationOutcome,
)


class JsonCapabilityValidationRepository:
    """Persist one provider capability-validation session per JSON document."""

    SCHEMA_VERSION = "1.0"
    _SAFE_ID_CHARACTERS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, session_id: str) -> CapabilityValidationSession | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        return self._read(path)

    def save(self, session: CapabilityValidationSession) -> CapabilityValidationSession:
        path = self._path(session.session_id)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "session": self._to_payload(session),
        }
        self._write_atomic(path, payload)
        return session

    def list_all(self) -> tuple[CapabilityValidationSession, ...]:
        if not self.root.exists():
            return ()
        sessions = tuple(self._read(path) for path in sorted(self.root.glob("*.json")))
        return tuple(sorted(sessions, key=lambda item: item.session_id))

    def list_for_provider(self, provider_id: str) -> tuple[CapabilityValidationSession, ...]:
        normalized = provider_id.strip()
        if not normalized:
            raise CapabilityValidationRepositoryError("provider_id cannot be blank")
        return tuple(session for session in self.list_all() if session.provider_id == normalized)

    def _path(self, session_id: str) -> Path:
        normalized = session_id.strip()
        if not normalized or any(
            character not in self._SAFE_ID_CHARACTERS for character in normalized
        ):
            raise CapabilityValidationRepositoryError(
                f"Capability validation identity is not filesystem-safe: {session_id!r}"
            )
        return self.root / f"{normalized}.json"

    def _read(self, path: Path) -> CapabilityValidationSession:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("repository payload must be an object")
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError(
                    "Unsupported capability validation repository schema: "
                    f"{payload.get('schema_version')!r}"
                )
            raw = _mapping(payload["session"], "session")
            return self._from_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise CapabilityValidationRepositoryError(
                f"Unable to read capability validation document {path}: {exc}"
            ) from exc

    def _write_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise CapabilityValidationRepositoryError(
                f"Unable to persist capability validation data {path}: {exc}"
            ) from exc

    @staticmethod
    def _to_payload(session: CapabilityValidationSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "provider_id": session.provider_id,
            "pack_id": session.pack_id,
            "capability_id": session.capability_id,
            "recommendation": session.recommendation.value,
            "human_decision": session.human_decision.value,
            "decision_actor": session.decision_actor,
            "decision_reason": session.decision_reason,
            "decided_at": _datetime_value(session.decided_at),
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "scenario_results": [
                {
                    "scenario_id": result.scenario_id,
                    "outcome": result.outcome.value,
                    "evidence_media_ids": list(result.evidence_media_ids),
                    "notes": result.notes,
                    "recorded_by": result.recorded_by,
                    "recorded_at": _datetime_value(result.recorded_at),
                    "criterion_results": [
                        {
                            "criterion_id": criterion.criterion_id,
                            "outcome": criterion.outcome.value,
                            "notes": criterion.notes,
                        }
                        for criterion in result.criterion_results
                    ],
                }
                for result in session.scenario_results
            ],
        }

    @staticmethod
    def _from_payload(raw: dict[str, Any]) -> CapabilityValidationSession:
        results_raw = raw.get("scenario_results", [])
        if not isinstance(results_raw, list):
            raise TypeError("scenario_results must be an array")
        scenario_results: list[ScenarioResult] = []
        for item in results_raw:
            result_raw = _mapping(item, "scenario result")
            criteria_raw = result_raw.get("criterion_results", [])
            if not isinstance(criteria_raw, list):
                raise TypeError("criterion_results must be an array")
            scenario_results.append(
                ScenarioResult(
                    scenario_id=str(result_raw["scenario_id"]),
                    outcome=ValidationOutcome(str(result_raw["outcome"])),
                    criterion_results=tuple(
                        CriterionResult(
                            criterion_id=str(_mapping(entry, "criterion result")["criterion_id"]),
                            outcome=ValidationOutcome(
                                str(_mapping(entry, "criterion result")["outcome"])
                            ),
                            notes=_optional_string(
                                _mapping(entry, "criterion result").get("notes")
                            ),
                        )
                        for entry in criteria_raw
                    ),
                    evidence_media_ids=tuple(
                        str(value) for value in result_raw.get("evidence_media_ids", [])
                    ),
                    notes=_optional_string(result_raw.get("notes")),
                    recorded_by=_optional_string(result_raw.get("recorded_by")),
                    recorded_at=_optional_datetime(result_raw.get("recorded_at")),
                )
            )
        return CapabilityValidationSession(
            session_id=str(raw["session_id"]),
            provider_id=str(raw["provider_id"]),
            pack_id=str(raw["pack_id"]),
            capability_id=str(raw["capability_id"]),
            scenario_results=tuple(scenario_results),
            recommendation=CapabilityRecommendation(str(raw["recommendation"])),
            human_decision=HumanDecision(str(raw["human_decision"])),
            decision_actor=_optional_string(raw.get("decision_actor")),
            decision_reason=_optional_string(raw.get("decision_reason")),
            decided_at=_optional_datetime(raw.get("decided_at")),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
            updated_at=datetime.fromisoformat(str(raw["updated_at"])),
        )


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be an object")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _datetime_value(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
