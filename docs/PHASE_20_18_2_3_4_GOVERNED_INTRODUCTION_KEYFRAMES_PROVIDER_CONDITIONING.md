# Phase 20.18.2.3.4 — Governed Introduction Keyframes and Provider Conditioning

## Purpose

Phase 20.18.2.3.4 turns accepted internal-span and timed-reference authority into
provider-safe image-to-video conditioning contracts without changing the editorial Shot
identity.

For a dynamic Shot, every non-initial internal render span now requires a human-approved
Governed Introduction Keyframe representing that span's exact first emitted frame.

The provider-conditioning layer then binds those approved keyframes into deterministic
LTX-2.5 per-span frame-count and continuity contracts.

## SHT-002 acceptance case

For SHT-002:

```text
24 fps
144 governed frames

SPAN-001
global frames 0-95
governed frames 96

internal boundary
source global frame 95
target global frame 96

SPAN-002
global frames 96-143
governed frames 48
Ros is introduced at frame 96
```

The key distinction is:

```text
frame 95 = source continuity evidence
frame 96 = Governed Introduction Keyframe
frame 96 = first emitted frame of SPAN-002
```

Frame 95 is not emitted again by SPAN-002.

This prevents a 145-frame final Shot caused by duplicating the internal boundary.

## Introduction-keyframe requirements

`GovernedIntroductionKeyframeRequirementCompiler` derives one
`IntroductionKeyframeRequirement` for each non-initial internal span.

Each requirement records:

- Shot identity;
- governed internal boundary ID;
- source and target span IDs;
- exact source global frame;
- exact target global frame;
- target span final frame;
- target active asset IDs;
- target active canonical-reference IDs;
- assets introduced at the target opening;
- references introduced at the target opening;
- source Internal Render Span fingerprint;
- source Timed Canonical Reference Activation fingerprint;
- explicit conditioning/emission semantics.

For the Ros example the requirement states:

```text
source_global_frame_index = 95
target_global_frame_index = 96
target_through_frame       = 143
target_frame_count         = 48

introduced_asset_ids:
  CAP-CHR-004

introduced_reference_ids:
  REF-ROS-PRIMARY
```

The conditioning contract is explicitly:

```text
conditioning_frame_global_index = 96
conditioning_frame_is_emitted = true
preceding_boundary_frame_global_index = 95
preceding_boundary_frame_reemitted_in_target_span = false
```

## Governed Introduction Keyframe

A `GovernedIntroductionKeyframe` is a human-approved image representing the exact first
emitted frame of one target span.

It is linked to:

- the current introduction-keyframe requirement;
- the governed internal boundary;
- the target span;
- the target global frame index;
- active reference IDs;
- newly introduced reference IDs;
- a checksum-pinned introduction image;
- checksum-pinned source boundary continuity evidence;
- approval actor and timestamp;
- required acceptance criteria.

The default acceptance criteria are:

- `source_boundary_continuity_preserved`
- `target_span_first_emitted_frame_correct`
- `introduced_assets_present`
- `active_identities_preserved`
- `no_unapproved_assets_introduced`
- `composition_physically_plausible`

The authority is human-approved and checksum-pinned. Changing either the introduction
image or its source boundary evidence invalidates the approved record.

## Why the introduction frame is separate from the source boundary frame

The source boundary frame proves the accepted visual state immediately before the timed
change.

The Introduction Keyframe represents the first visual state after that change.

For Ros:

```text
frame 95:
  James
  Sandra
  Iron Horizon bridge
  Ros absent

frame 96 Introduction Keyframe:
  James
  Sandra
  Iron Horizon bridge
  Ros present in the approved entry composition
```

This gives the provider a fully governed first frame for the changed composition rather
than asking the video model to infer when and how Ros should appear from prompt prose.

## Candidate C provider strategy

Phase 20.18.2.3.4 preserves the accepted Candidate C architecture.

Direct multi-reference video conditioning remains disabled.

For each span:

```text
direct_provider_reference_ids = []
combined_identity_video_reference = false
reference_conditioning_mode = baked_into_governed_keyframe
```

Canonical reference activation remains governance input for building and approving the
keyframe, but the LTX-2.5 video workflow consumes the approved keyframe itself.

This avoids repeating the earlier combined-reference failure mode that produced unwanted
additional people.

## LTX-2.5 provider frame counts

LTX-2.5 requires provider frame counts satisfying:

```text
(frames - 1) % 8 == 0
```

The provider-conditioning compiler therefore distinguishes governed frame counts from
provider frame counts.

For SHT-002:

```text
SPAN-001
governed frames = 96
provider frames = 97
trim after generation = 1

SPAN-002
governed frames = 48
provider frames = 49
trim after generation = 1
```

The eventual normalized outputs remain:

```text
96 + 48 = 144 governed frames
```

not 146 provider frames and not 145 frames caused by boundary duplication.

## LTX25SpanProviderConditioningPlan

`LTX25SpanProviderConditioningCompiler` builds a provider-specific conditioning plan
only after all required Introduction Keyframes are human-approved.

The first span uses:

```text
conditioning_source_kind = shot_opening_authority
```

This preserves the accepted Phase 20.18.2.2i Shot-opening behavior.

Each later span uses:

```text
conditioning_source_kind = governed_introduction_keyframe
```

with the approved Introduction Keyframe path and SHA-256 checksum.

Each span records:

- global start and through frames;
- governed frame count;
- padded LTX-2.5 provider frame count;
- provider trim count;
- conditioning source kind;
- conditioning frame global index;
- whether the conditioning frame is emitted;
- preceding boundary global frame;
- whether that preceding frame is re-emitted;
- active and introduced canonical-reference IDs;
- bound Introduction Keyframe identity/path/checksum when required.

The plan also records:

- Shot identity;
- source package fingerprint;
- source span-plan fingerprint;
- source activation-plan fingerprint;
- source Introduction Keyframe requirement-plan fingerprint;
- deterministic plan ID and fingerprint;
- final assembly policy:
  `concatenate_normalized_span_outputs_in_sequence`.

## Candidate C integration

`CurrentAuthorityLTX25GovernedKeyframeCompilationService` now exposes:

```text
compile_span_provider_conditioning(...)
```

This provides the governed per-span Candidate C conditioning contract after Introduction
Keyframes are approved.

It does not yet submit multiple provider jobs automatically.

## Fail-closed execution boundary

The ordinary monolithic provider path remains blocked for dynamic multi-span Shots.

The authority chain can now reach:

```text
Timed Asset Presence                       VALID
Governed Internal Render Spans             VALID
Timed Canonical Reference Activation       VALID
Introduction Keyframe Requirements         VALID
Human-approved Introduction Keyframes      VALID when present
LTX-2.5 Span Provider Conditioning         VALID when present
Automatic multi-span execution/assembly    NOT YET ENABLED
```

This prevents an existing monolithic workflow from silently ignoring span-level
conditioning authority.

## Deliberate exclusions

Phase 20.18.2.3.4 does not yet implement:

- automatic generation of Introduction Keyframes;
- UI for Introduction Keyframe approval;
- automatic extraction/publication of source internal boundary frames;
- automatic submission of separate LTX-2.5 jobs for each span;
- per-span retry/recovery UI;
- automatic normalized span concatenation;
- visual QC proving Ros is absent before frame 96 and present from frame 96;
- final end-to-end Production Execution acceptance.

Those belong to Phase 20.18.2.3.5 UI, QC, and Functional Acceptance.
