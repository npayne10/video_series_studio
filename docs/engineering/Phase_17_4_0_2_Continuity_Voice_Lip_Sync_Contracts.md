# Phase 17.4.0.2 — Continuity, Voice and Lip-sync Contracts

## Status

Build and integration implementation.

No media generation, speech synthesis, face tracking or lip-sync execution is included.

## Objective

Represent the production state required to keep characters, locations, ships,
vehicles, props, costumes, lighting, camera state and effects consistent across
shots, scenes and episodes. Define canonical voice identity, timed dialogue and
post-generation lip-sync requests independently from renderer workflows.

## Continuity hierarchy

Continuity is resolved from broadest to narrowest scope:

1. Series state
2. Episode or production-container state
3. Scene state
4. Shot state
5. Previous and next boundary-frame references

Narrower state replaces broader state for the same entity. This allows a
character's series-level canonical appearance to remain stable while a scene or
shot records a deliberate costume, position, injury or prop-state change.

### Entity continuity

Each entity state can declare:

- Canonical asset identity
- Named state values
- Mandatory visible traits
- Prohibited changes
- Approved canonical references

This supports requirements such as preserving Commander James Spence's face,
uniform and voice, or retaining the Iron Horizon's approved hull, four rear
engines and blue-white fusion exhaust.

### Boundary frames

Continuity frame references are project-relative and may identify an exact frame
number and checksum. Future workflow adapters can use the approved final frame
of one shot as the start reference for the next shot.

## Voice identity

A `VoiceProfile` provides one canonical reusable voice identity per character.
It records:

- Provider and provider voice ID
- Language and accent
- Speaking rate and pitch
- Default emotion
- Pronunciation overrides
- Optional processing profile
- Version

`VoiceProfileRegistry` is registered as an empty bootstrap service. Persistence
and user-facing management will be introduced in a later integration phase.

## Timed dialogue

Each `DialogueCue` binds exact text to:

- Character asset
- Voice profile
- Target time window
- Emotional performance intent
- Optional visible face target
- Off-screen state
- Pronunciation notes

A `VoiceGenerationRequest` groups uniquely identified cues for one shot and
declares a project-relative dialogue-output directory. Timing windows may
overlap deliberately for interruptions and multi-speaker performances.

## Lip-sync strategy

Lip-sync remains a separate post-generation operation. Supported modes are:

- None
- Off-screen dialogue
- Single visible speaker
- Alternating visible speakers
- Multiple visible speakers
- Precision close-up

A `LipSyncRequest` binds the generated video, dialogue cues, approved audio
references and visible face targets. It validates speaker-to-face mapping before
a workflow is selected.

`LipSyncContractValidator` evaluates whether a future workflow supports:

- Lip-sync at all
- Multiple speakers
- Precision close-up processing

## Render-request integration

`RenderRequest` remains backwards compatible and now accepts optional:

- `VoicePackageReference`
- `LipSyncPackageReference`

The actual detailed contracts remain separate objects. The universal render
request therefore records dependencies without embedding renderer-specific
speech or face-processing data.

## Dependency injection

Bootstrap registers:

- `ContinuityStateRegistry`
- `VoiceProfileRegistry`

Both registries start empty. No renderer, voice provider or lip-sync engine is
instantiated.

## Extension points

Later phases can add:

- Project-backed continuity persistence and state-ledger editing
- Canonical voice-profile management
- Voice-generation provider adapters
- ComfyUI lip-sync workflow manifests
- Face tracking and speaker allocation
- Dialogue-duration validation against shot timing
- Automated extraction and approval of continuity boundary frames

## Completion outcome

VSCS now has renderer-neutral contracts for continuity, canonical voice identity,
timed dialogue and post-generation lip-sync. These contracts are ready for use
by the workflow manifest, validation and ComfyUI adapter phases.
