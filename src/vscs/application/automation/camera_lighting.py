"""Camera & Lighting production proposal automation for Phase 19.5.8."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from vscs.application.story import (
    CameraAngle,
    CameraMovement,
    ExposureIntent,
    KeyDirection,
    LensFamily,
    LightQuality,
    LightingIntent,
    ScreenDirection,
    ShotSize,
)

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class CameraProposalDraft:
    shot_size: ShotSize
    angle: CameraAngle
    movement: CameraMovement
    lens_family: LensFamily
    focal_length_mm: int
    camera_height_m: float
    screen_direction: ScreenDirection
    composition: str
    focus_strategy: str
    movement_notes: str = ""
    continuity_notes: str = ""
    camera_constraints: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class LightingProposalDraft:
    lighting_intent: LightingIntent
    key_direction: KeyDirection
    key_quality: LightQuality
    color_temperature_k: int
    fill_level_percent: int
    exposure_intent: ExposureIntent
    source_strategy: str
    shadow_strategy: str
    subject_readability: str
    separation_strategy: str = ""
    continuity_notes: str = ""
    lighting_constraints: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class CameraLightingProposalDraft:
    camera: CameraProposalDraft
    lighting: LightingProposalDraft


class CameraLightingProposalProvider(Protocol):
    provider_name: str
    model_name: str

    def propose_camera_lighting(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
        performance_payload: dict[str, object],
        environment_payload: dict[str, object],
    ) -> CameraLightingProposalDraft: ...


class TemplateCameraLightingProposalProvider:
    """Deterministic restrained defaults that do not select canonical profiles."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose_camera_lighting(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
        performance_payload: dict[str, object],
        environment_payload: dict[str, object],
    ) -> CameraLightingProposalDraft:
        del story_id, source_text, performance_payload
        dialogue = str(shot_payload.get("dialogue_requirement", "")).strip()
        action = str(shot_payload.get("required_action", "")).lower()
        context = str(environment_payload.get("environment_context", ""))
        shot_size = ShotSize.MEDIUM_CLOSE if dialogue else ShotSize.MEDIUM
        movement = CameraMovement.STATIC
        lens = LensFamily.NORMAL
        focal = 50
        if any(term in action for term in ("walk", "run", "move", "approach", "cross", "fly")):
            shot_size = ShotSize.WIDE
            movement = CameraMovement.TRACK
            lens = LensFamily.WIDE
            focal = 35
        if context in {"orbital_space", "deep_space", "exterior_surface", "atmospheric"}:
            shot_size = ShotSize.WIDE
            lens = LensFamily.WIDE
            focal = 28
        camera = CameraProposalDraft(
            shot_size=shot_size,
            angle=CameraAngle.EYE_LEVEL,
            movement=movement,
            lens_family=lens,
            focal_length_mm=focal,
            camera_height_m=1.6,
            screen_direction=ScreenDirection.PRESERVE_PREVIOUS,
            composition="Prioritise the primary narrative action with stable, readable composition.",
            focus_strategy="Hold focus on the primary narrative subject with plausible depth of field.",
            movement_notes="Keep movement restrained, motivated and mechanically plausible.",
            continuity_notes=str(shot_payload.get("continuity_in", "")).strip(),
            camera_constraints=("Do not introduce camera behaviour unsupported by the Shot intent.",),
            confidence=0.6,
        )
        exterior = context in {"orbital_space", "deep_space", "exterior_surface", "atmospheric"}
        lighting = LightingProposalDraft(
            lighting_intent=(LightingIntent.NATURALISTIC if exterior else LightingIntent.PRACTICAL_MOTIVATED),
            key_direction=KeyDirection.MOTIVATED,
            key_quality=LightQuality.MEDIUM if exterior else LightQuality.SOFT,
            color_temperature_k=5600 if exterior else 4300,
            fill_level_percent=20 if exterior else 45,
            exposure_intent=ExposureIntent.PROTECT_HIGHLIGHTS if exterior else ExposureIntent.BALANCED,
            source_strategy="Use physically motivated sources justified by the proposed environment; avoid decorative glow.",
            shadow_strategy="Preserve credible modelling while retaining story-critical detail.",
            subject_readability="Keep the primary narrative subject readable without flattening the environment.",
            separation_strategy="Use restrained tonal separation only where needed for readability.",
            continuity_notes=str(environment_payload.get("continuity_notes", "")).strip(),
            lighting_constraints=("Do not contradict the physical Environment proposal.",),
            confidence=0.6,
        )
        return CameraLightingProposalDraft(camera=camera, lighting=lighting)


class CameraLightingProposalAutomationService:
    """Generate Camera and Lighting proposals without mutating governed planning authority."""

    def __init__(self, provider: CameraLightingProposalProvider, proposals: AutomationProposalService) -> None:
        self._provider = provider
        self._proposals = proposals

    def generate(self, *, story_id: str, source_text: str, source_revision: str) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision or not source_text.strip():
            raise ValueError("Story ID, source revision and source text are required")
        current = tuple(
            item for item in self._proposals.list_proposals()
            if item.provenance.source_story_id == normalized_story
            and item.provenance.source_revision == revision
        )
        shots = tuple(item for item in current if item.proposal_type is AutomationProposalType.SHOT)
        performances = {item.target_id: item for item in current if item.proposal_type is AutomationProposalType.ACTION_PERFORMANCE}
        environments = {item.target_id: item for item in current if item.proposal_type is AutomationProposalType.ENVIRONMENT}
        if not shots:
            raise ValueError("Generate current Shot proposals before Camera & Lighting proposals")
        missing_performance = tuple(shot.target_id for shot in shots if shot.target_id not in performances)
        missing_environment = tuple(shot.target_id for shot in shots if shot.target_id not in environments)
        if missing_performance:
            raise ValueError(
                "Generate current Action/Performance proposals before Camera & Lighting proposals; "
                f"missing {len(missing_performance)} Shot(s)"
            )
        if missing_environment:
            raise ValueError(
                "Generate current Environment proposals before Camera & Lighting proposals; "
                f"missing {len(missing_environment)} Shot(s)"
            )

        generated: list[AutomationProposal] = []
        for shot in sorted(shots, key=lambda item: item.target_id):
            performance = performances[shot.target_id]
            environment = environments[shot.target_id]
            draft = self._provider.propose_camera_lighting(
                story_id=normalized_story,
                source_text=source_text,
                shot_payload=shot.payload,
                performance_payload=performance.payload,
                environment_payload=environment.payload,
            )
            self._validate_camera(draft.camera, shot.target_id)
            self._validate_lighting(draft.lighting, shot.target_id)
            camera = self._proposals.save(
                self._camera_proposal(normalized_story, revision, source_text, shot, performance, environment, draft.camera)
            )
            generated.append(camera)
            generated.append(
                self._proposals.save(
                    self._lighting_proposal(
                        normalized_story, revision, source_text, shot, performance, environment, camera, draft.lighting
                    )
                )
            )
        return tuple(generated)

    @staticmethod
    def _validate_camera(draft: CameraProposalDraft, shot_id: str) -> None:
        if not 8 <= draft.focal_length_mm <= 1200:
            raise ValueError(f"Camera proposal for {shot_id} has invalid focal length")
        if not 0.0 <= draft.camera_height_m <= 100.0:
            raise ValueError(f"Camera proposal for {shot_id} has invalid camera height")
        if not draft.composition.strip() or not draft.focus_strategy.strip():
            raise ValueError(f"Camera proposal for {shot_id} requires composition and focus strategy")

    @staticmethod
    def _validate_lighting(draft: LightingProposalDraft, shot_id: str) -> None:
        if not 1000 <= draft.color_temperature_k <= 20000:
            raise ValueError(f"Lighting proposal for {shot_id} has invalid color temperature")
        if not 0 <= draft.fill_level_percent <= 100:
            raise ValueError(f"Lighting proposal for {shot_id} has invalid fill level")
        if not draft.source_strategy.strip() or not draft.shadow_strategy.strip() or not draft.subject_readability.strip():
            raise ValueError(f"Lighting proposal for {shot_id} requires source, shadow and readability strategy")

    def _source_kind(self) -> AutomationSourceKind:
        return (
            AutomationSourceKind.AI_INFERENCE
            if self._provider.provider_name != "vscs-template"
            else AutomationSourceKind.DETERMINISTIC_RESOLUTION
        )

    def _camera_proposal(
        self,
        story_id: str,
        revision: str,
        source_text: str,
        shot: AutomationProposal,
        performance: AutomationProposal,
        environment: AutomationProposal,
        draft: CameraProposalDraft,
    ) -> AutomationProposal:
        digest = sha256(
            f"{story_id}|{revision}|camera|{shot.proposal_id}|{performance.proposal_id}|{environment.proposal_id}".encode()
        ).hexdigest()
        return AutomationProposal(
            proposal_id=f"AUT-CAMERA-{digest[:12].upper()}",
            proposal_type=AutomationProposalType.CAMERA,
            target_id=shot.target_id,
            payload={
                "shot_id": shot.target_id,
                "shot_size": draft.shot_size.value,
                "angle": draft.angle.value,
                "movement": draft.movement.value,
                "lens_family": draft.lens_family.value,
                "focal_length_mm": draft.focal_length_mm,
                "camera_height_m": draft.camera_height_m,
                "screen_direction": draft.screen_direction.value,
                "composition": draft.composition,
                "focus_strategy": draft.focus_strategy,
                "movement_notes": draft.movement_notes,
                "continuity_notes": draft.continuity_notes,
                "camera_constraints": list(draft.camera_constraints),
                "camera_profile_asset_id": "",
            },
            provenance=AutomationProvenance(
                source_kind=self._source_kind(),
                source_story_id=story_id,
                source_revision=revision,
                source_scope="current Shot, Action/Performance and Environment proposals plus Story source",
                provider=self._provider.provider_name,
                model=self._provider.model_name,
                confidence=max(0.0, min(1.0, draft.confidence)),
                inference_note="Camera intent is proposed for human review only; no governed Camera Plan or profile selection is created.",
                resolution_method="provider-neutral camera production interpretation",
            ),
            metadata={
                "phase": "19.5.8",
                "parent_shot_proposal_id": shot.proposal_id,
                "parent_action_performance_proposal_id": performance.proposal_id,
                "parent_environment_proposal_id": environment.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )

    def _lighting_proposal(
        self,
        story_id: str,
        revision: str,
        source_text: str,
        shot: AutomationProposal,
        performance: AutomationProposal,
        environment: AutomationProposal,
        camera: AutomationProposal,
        draft: LightingProposalDraft,
    ) -> AutomationProposal:
        digest = sha256(
            f"{story_id}|{revision}|lighting|{shot.proposal_id}|{environment.proposal_id}|{camera.proposal_id}".encode()
        ).hexdigest()
        return AutomationProposal(
            proposal_id=f"AUT-LIGHTING-{digest[:12].upper()}",
            proposal_type=AutomationProposalType.LIGHTING,
            target_id=shot.target_id,
            payload={
                "shot_id": shot.target_id,
                "lighting_intent": draft.lighting_intent.value,
                "key_direction": draft.key_direction.value,
                "key_quality": draft.key_quality.value,
                "color_temperature_k": draft.color_temperature_k,
                "fill_level_percent": draft.fill_level_percent,
                "exposure_intent": draft.exposure_intent.value,
                "source_strategy": draft.source_strategy,
                "shadow_strategy": draft.shadow_strategy,
                "subject_readability": draft.subject_readability,
                "separation_strategy": draft.separation_strategy,
                "continuity_notes": draft.continuity_notes,
                "lighting_constraints": list(draft.lighting_constraints),
                "lighting_profile_asset_id": "",
            },
            provenance=AutomationProvenance(
                source_kind=self._source_kind(),
                source_story_id=story_id,
                source_revision=revision,
                source_scope="current Shot, Action/Performance, Environment and Camera proposals plus Story source",
                provider=self._provider.provider_name,
                model=self._provider.model_name,
                confidence=max(0.0, min(1.0, draft.confidence)),
                inference_note="Lighting intent is proposed for human review only; no governed Lighting Plan or profile selection is created.",
                resolution_method="provider-neutral lighting production interpretation",
            ),
            metadata={
                "phase": "19.5.8",
                "parent_shot_proposal_id": shot.proposal_id,
                "parent_action_performance_proposal_id": performance.proposal_id,
                "parent_environment_proposal_id": environment.proposal_id,
                "parent_camera_proposal_id": camera.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )
