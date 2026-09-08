# Phase 20.18.2 — Automated Shot Asset Requirement Inference

## Decision

The governed Asset Resolver must not require the human reviewer to invent the complete
asset list for a Shot. VSCS now derives reviewable Shot asset requirement proposals
before governed bindings are created.

The authority flow is:

Ready governed Shot / Ready Scene
→ deterministic requirement extraction
→ current XPD/CAP canonical matching
→ optional AI semantic inference for remaining coverage gaps
→ human review
→ Draft ShotAssetBindings
→ explicit Ready approval per binding.

Inference never creates canonical assets and never marks a binding Ready.

## Layer 1 — deterministic extraction

VSCS builds evidence from the governed Shot and Scene contracts, including:

- Shot title;
- narrative purpose;
- production objective;
- required action;
- governed dialogue;
- continuity;
- cinematic coverage role constraints;
- Scene title, story scope, setting requirement, required events and constraints.

The analyzer compares this authority against current project asset names, IDs and tags.
Explicit canonical asset-name occurrences receive the strongest deterministic
confidence. Category-specific downstream ownership remains intact: Camera, Lighting and
Reference categories are excluded from this phase.

## Layer 2 — canonical matching

Every deterministic asset mention is resolved against current authoritative XPD/CAP and
approved canonical-reference state.

A proposal records:

- expected category;
- matched asset ID and name;
- confidence;
- inference source;
- rationale;
- canonical resolution status.

An existing asset can therefore be proposed even when its CAP/reference chain is not
yet production-ready. Such a binding remains Draft and cannot be approved until normal
governed Asset Resolution succeeds.

## Layer 3 — optional AI semantic inference

The service exposes a provider-neutral `ShotAssetSemanticInferenceProvider` boundary.
AI inference is invoked only when deterministic coverage is insufficient, including:

- no deterministic requirement was found;
- a Dialogue Delivery Shot has no detected Character requirement;
- a Detail Insert Shot has no detected Prop or Technology requirement.

AI output remains proposal-only. Unmatched AI requirements remain explicitly
unresolved. AI proposals are rematched deterministically against current XPD before
human review; ambiguous matches stay unresolved rather than creating or guessing canon.

No AI provider is required for deterministic operation. When VSCS Settings selects
OpenAI and a valid OpenAI API key is available from secure credential storage, the
composition root registers `OpenAIShotAssetRequirementProvider` automatically using the
configured OpenAI model. Test mode and non-OpenAI configurations remain deterministic.
The UI reports whether semantic AI inference is configured.

## Human governance

The Asset Resolver now exposes **Analyze Requirements**.

On opening a Ready Shot, it reports:

- number of inferred requirements;
- canonical matches;
- unresolved proposals;
- whether AI semantic inference is configured.

Analyze Requirements shows the inferred role, category, canonical match or UNRESOLVED
state, inference source, confidence and canonical readiness. The user must explicitly
approve materialization.

Approved suggestions become Draft `ShotAssetBinding` records only. They remain editable
and must individually pass existing Asset/CAP/reference validation before being marked
Ready.

## Acceptance

Phase 20.18.2 acceptance for this capability requires:

- deterministic extraction from governed Shot/Scene authority;
- correct XPD/CAP matching without invented canon;
- unresolved requirements remain visible and Draft;
- optional AI is called only for deterministic coverage gaps;
- human confirmation is required before proposal materialization;
- inferred bindings are never automatically marked Ready;
- Camera/Lighting/Reference ownership remains downstream;
- UI clearly explains suggested and unresolved asset requirements.

Phase 20.18.2 remains open until local automated validation, UI acceptance, downstream
planning, live provider execution, GeneratedMedia provenance and explicit owner
acceptance pass.
