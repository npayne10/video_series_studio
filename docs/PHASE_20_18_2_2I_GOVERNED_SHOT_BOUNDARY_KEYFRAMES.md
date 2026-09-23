# Phase 20.18.2.2i — Governed Shot Boundary Keyframes

## Purpose

Phase 20.18.2.2i establishes explicit VSCS authority for the visual boundary between
shots. It publishes the exact final governed frame of an accepted shot and allows a
later shot to inherit that frame only when its approved continuity authority explicitly
requires inheritance.

Provider output never becomes continuity authority automatically.

## Acceptance authority

VSCS currently represents human acceptance of Generated Media with
`GeneratedMediaState.APPROVED`. A closing Shot Boundary Keyframe may therefore be
published only from an APPROVED Generated Media video. GENERATED, UNDER_REVIEW,
REJECTED, INVALID and SUPERSEDED media are not eligible.

Publication is an explicit human action in Production Execution.

## Exact governed closing frame

The source is the VSCS-managed Generated Media file, not the raw provider tail.

The runtime uses FFprobe to resolve the governed video frame count, dimensions and
frame rate. The closing boundary is extracted from exact zero-based frame index:

`frame_count - 1`

For the accepted SHT-001 Candidate C result, 144 governed frames means frame index
143 is the closing continuity frame.

The published boundary records:

- stable boundary identity;
- source shot, Generated Media, execution and media revision;
- source project-relative media path and SHA-256;
- exact frame index and frame count;
- width, height and frame rate;
- extracted PNG path and SHA-256;
- publishing human identity and timestamp.

Both the extracted boundary image and its source Generated Media remain checksum
validated. A changed or missing source fails closed.

## Opening continuity modes

The approved shot continuity authority may declare one of:

- `CONTINUOUS`
- `NEW_COMPOSITION`
- `SCENE_ENTRY`
- `DISCONTINUITY`
- `MATCH_CUT`
- `SPECIAL`

`CONTINUOUS`, `MATCH_CUT` and `SPECIAL` inherit a prior closing boundary and
must explicitly name `source_shot_id`. VSCS does not infer previous-shot sequence.

`NEW_COMPOSITION`, `SCENE_ENTRY` and `DISCONTINUITY` do not inherit a prior
closing frame and continue to require the shot's independently human-approved Shot
Composition Keyframe for Candidate C.

When no boundary mode is supplied, the fail-safe default is `NEW_COMPOSITION`.

## Candidate C compilation

Candidate C compilation writes `shot_boundary_continuity` into the executable
Production Package.

For inherited continuity, the published closing PNG becomes the governed opening
keyframe and the package records the source boundary identity and checksums.

For independent continuity, the existing human-approved governed Shot Composition
Keyframe remains the opening source.

The shot-boundary payload participates in the executable package fingerprint.

## Staleness

Every Candidate C package validation re-resolves the current opening boundary
authority. If the source boundary identity, image checksum, source media identity or
source media checksum differs from the compiled authority, the downstream Production
Package is STALE and must be recompiled before execution.

If the source Generated Media bytes change after publication, boundary validation
fails closed.

## Operator UI

Production Execution displays:

- Opening Boundary mode and state;
- inherited source shot and boundary identity when applicable;
- Closing Boundary publication state;
- published boundary identity and exact frame index/count.

`Publish Closing Boundary` requires a human identity and exactly one APPROVED video
for the selected execution profile. Ambiguous multiple approved videos fail closed.

## Safety constraints

Phase 20.18.2.2i does not:

- reset retry authority;
- edit execution history;
- infer acceptance from provider completion;
- infer previous-shot sequence;
- publish from unapproved Generated Media;
- alter the accepted source video;
- require a new LTX render merely to publish an already accepted shot boundary.
