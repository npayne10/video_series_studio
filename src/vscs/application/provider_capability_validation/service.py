"""Application contracts and orchestration for provider capability validation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol

from vscs.application.generated_media import GeneratedMediaRepository
from vscs.domain.provider_capability_validation import (
    CapabilityRecommendation,
    CapabilityValidationSession,
    CriterionResult,
    HumanDecision,
    ProviderCapabilityValidationPack,
    ScenarioResult,
    ValidationOutcome,
)


class CapabilityValidationRepositoryError(RuntimeError):
    """Raised when capability-validation persistence cannot complete safely."""


class CapabilityValidationRepository(Protocol):
    """Persistence boundary for provider capability-validation sessions."""

    def get(self, session_id: str) -> CapabilityValidationSession | None: ...

    def save(self, session: CapabilityValidationSession) -> CapabilityValidationSession: ...

    def list_all(self) -> tuple[CapabilityValidationSession, ...]: ...

    def list_for_provider(self, provider_id: str) -> tuple[CapabilityValidationSession, ...]: ...


class ProviderCapabilityValidationService:
    """Govern capability evidence without granting provider outputs authority."""

    def __init__(
        self,
        repository: CapabilityValidationRepository,
        media_repository: GeneratedMediaRepository,
        packs: tuple[ProviderCapabilityValidationPack, ...],
    ) -> None:
        self._repository = repository
        self._media_repository = media_repository
        self._packs = {pack.pack_id: pack for pack in packs}
        if not self._packs:
            raise ValueError("at least one capability-validation pack is required")

    @property
    def media_repository(self) -> GeneratedMediaRepository:
        return self._media_repository

    def available_packs(self) -> tuple[ProviderCapabilityValidationPack, ...]:
        return tuple(sorted(self._packs.values(), key=lambda item: item.pack_id))

    def start_session(
        self,
        *,
        session_id: str,
        provider_id: str,
        pack_id: str,
    ) -> CapabilityValidationSession:
        if self._repository.get(session_id) is not None:
            raise ValueError(f"capability-validation session already exists: {session_id}")
        pack = self._require_pack(pack_id)
        session = CapabilityValidationSession(
            session_id=session_id,
            provider_id=provider_id,
            pack_id=pack.pack_id,
            capability_id=pack.capability_id,
            scenario_results=tuple(
                ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    outcome=ValidationOutcome.NOT_RUN,
                    criterion_results=tuple(
                        CriterionResult(
                            criterion_id=criterion.criterion_id,
                            outcome=ValidationOutcome.NOT_RUN,
                        )
                        for criterion in scenario.criteria
                    ),
                )
                for scenario in pack.scenarios
            ),
        )
        return self._repository.save(session)

    def record_scenario(
        self,
        *,
        session_id: str,
        scenario_id: str,
        criterion_results: tuple[CriterionResult, ...],
        evidence_media_ids: tuple[str, ...],
        actor: str,
        notes: str | None = None,
    ) -> CapabilityValidationSession:
        session = self._require_session(session_id)
        pack = self._require_pack(session.pack_id)
        scenario = next(
            (item for item in pack.scenarios if item.scenario_id == scenario_id),
            None,
        )
        if scenario is None:
            raise ValueError(f"scenario is not part of pack {pack.pack_id}: {scenario_id}")
        expected = {criterion.criterion_id for criterion in scenario.criteria}
        actual = {result.criterion_id for result in criterion_results}
        if actual != expected:
            raise ValueError("criterion results must exactly match the validation scenario")
        self._validate_evidence(session.provider_id, evidence_media_ids)
        outcome = self._scenario_outcome(criterion_results)
        now = datetime.now(UTC)
        result = ScenarioResult(
            scenario_id=scenario_id,
            outcome=outcome,
            criterion_results=criterion_results,
            evidence_media_ids=evidence_media_ids,
            notes=notes,
            recorded_by=actor.strip(),
            recorded_at=now,
        )
        provisional = session.with_result(result, session.recommendation)
        recommendation = self._recommend(pack, provisional.scenario_results)
        updated = replace(provisional, recommendation=recommendation, updated_at=now)
        return self._repository.save(updated)

    def decide(
        self,
        *,
        session_id: str,
        decision: HumanDecision,
        actor: str,
        reason: str,
    ) -> CapabilityValidationSession:
        session = self._require_session(session_id)
        if session.recommendation is CapabilityRecommendation.INSUFFICIENT_EVIDENCE:
            raise ValueError("human decision requires complete validation evidence")
        return self._repository.save(session.with_decision(decision, actor, reason))

    def get(self, session_id: str) -> CapabilityValidationSession | None:
        return self._repository.get(session_id)

    def list_all(self) -> tuple[CapabilityValidationSession, ...]:
        return self._repository.list_all()

    def _validate_evidence(self, provider_id: str, media_ids: tuple[str, ...]) -> None:
        if not media_ids:
            raise ValueError("completed validation scenario requires Generated Media evidence")
        for media_id in media_ids:
            media = self._media_repository.get(media_id)
            if media is None:
                raise ValueError(f"Generated Media evidence does not exist: {media_id}")
            if media.provenance.provider_id != provider_id:
                raise ValueError(
                    f"Generated Media evidence {media_id} was produced by "
                    f"{media.provenance.provider_id}, not {provider_id}"
                )

    def _require_session(self, session_id: str) -> CapabilityValidationSession:
        session = self._repository.get(session_id)
        if session is None:
            raise ValueError(f"unknown capability-validation session: {session_id}")
        return session

    def _require_pack(self, pack_id: str) -> ProviderCapabilityValidationPack:
        try:
            return self._packs[pack_id]
        except KeyError as exc:
            raise ValueError(f"unknown capability-validation pack: {pack_id}") from exc

    @staticmethod
    def _scenario_outcome(
        criterion_results: tuple[CriterionResult, ...],
    ) -> ValidationOutcome:
        outcomes = {result.outcome for result in criterion_results}
        if ValidationOutcome.BLOCKED in outcomes or ValidationOutcome.NOT_RUN in outcomes:
            return ValidationOutcome.BLOCKED
        if ValidationOutcome.FAIL in outcomes:
            return ValidationOutcome.FAIL
        if ValidationOutcome.PARTIAL in outcomes:
            return ValidationOutcome.PARTIAL
        return ValidationOutcome.PASS

    @staticmethod
    def _recommend(
        pack: ProviderCapabilityValidationPack,
        results: tuple[ScenarioResult, ...],
    ) -> CapabilityRecommendation:
        by_id = {result.scenario_id: result for result in results}
        required = tuple(scenario for scenario in pack.scenarios if scenario.required)
        if any(
            by_id[scenario.scenario_id].outcome
            in (ValidationOutcome.NOT_RUN, ValidationOutcome.BLOCKED)
            for scenario in required
        ):
            return CapabilityRecommendation.INSUFFICIENT_EVIDENCE
        if any(
            by_id[scenario.scenario_id].outcome is ValidationOutcome.FAIL
            for scenario in required
        ):
            return CapabilityRecommendation.NOT_RECOMMENDED
        if any(
            by_id[scenario.scenario_id].outcome is ValidationOutcome.PARTIAL
            for scenario in required
        ):
            return CapabilityRecommendation.CONDITIONAL
        optional_non_pass = any(
            not scenario.required
            and by_id[scenario.scenario_id].outcome
            in (ValidationOutcome.PARTIAL, ValidationOutcome.FAIL)
            for scenario in pack.scenarios
        )
        if optional_non_pass:
            return CapabilityRecommendation.CONDITIONAL
        return CapabilityRecommendation.RECOMMENDED
