# Phase 20.18.2.3.3 — Timed Canonical Reference Activation

## Purpose

Phase 20.18.2.3.3 converts accepted Timed Asset Presence and Governed Internal Render
Span authority into exact per-span canonical-reference activation authority.

The objective is to ensure that a canonical reference can condition only the temporal
region in which its governed asset is active.

For the SHT-002 acceptance case, Ros's canonical reference must be absent from frames
0-95 and become active only for the span beginning at frame 96.

This phase remains provider-neutral. It does not yet execute multiple LTX-2.5 provider
jobs or publish actual internal-boundary images.

## Authority chain

The activation plan is derived from three accepted sources:

1. `TimedAssetPresencePlan` — which asset is active and when;
2. `GovernedInternalRenderSpanPlan` — exact render-span topology;
3. compiled governed `ReferencePlan` — provider-ready reference identities and asset
   ownership.

The resulting authority is checksum-linked to all three.

## Ros acceptance case

For SHT-002 at 24 fps and 144 governed frames:

```text
SPAN-001
global frames 0-95

active references:
  REF-JAMES-PRIMARY
  REF-SANDRA-PRIMARY
  REF-IRON-HORIZON-BRIDGE

REF-ROS-PRIMARY is NOT active
```

At the exact governed change frame:

```text
frame 96
Ros ENTER
REF-ROS-PRIMARY becomes active
```

Then:

```text
SPAN-002
global frames 96-143

active references:
  REF-JAMES-PRIMARY
  REF-SANDRA-PRIMARY
  REF-IRON-HORIZON-BRIDGE
  REF-ROS-PRIMARY

introduced references:
  REF-ROS-PRIMARY
```

This makes early Ros conditioning structurally invalid rather than relying on prompt
wording such as "Ros enters later."

## Span activation record

Each `SpanCanonicalReferenceActivation` contains:

- deterministic activation ID;
- source internal span ID;
- sequence number;
- exact global start and through frames;
- active asset IDs;
- active canonical-reference IDs;
- reference IDs introduced at the span opening;
- reference IDs removed at the span opening.

Introduced references must be active in the target span.

Removed references may not remain active in the target span.

## Activation plan

`TimedCanonicalReferenceActivationPlan` contains:

- Shot identity;
- source Timed Asset Presence plan ID and fingerprint;
- source Internal Render Span plan ID and fingerprint;
- compiled governed ReferencePlan fingerprint;
- frame-state reference IDs;
- ordered per-span activation records;
- deterministic plan ID and SHA-256 fingerprint;
- provider-neutral status.

Any change to the timed presence, render topology, reference ownership, reference file
facts, or compiled ReferencePlan changes downstream activation authority.

## Canonical-reference ownership validation

Every canonical reference explicitly named by a Timed Asset Presence interval must:

1. exist in the compiled governed ReferencePlan;
2. have a governed `asset_id`;
3. belong to the same asset as the Timed Asset Presence interval;
4. not be a frame-state reference.

For example:

```text
Timed presence asset:
  CAP-CHR-004

Reference:
  REF-ROS-PRIMARY

ReferencePlan asset_id:
  CAP-CHR-004
```

is valid.

If `REF-ROS-PRIMARY` is accidentally bound to `CAP-CHR-001`, compilation fails
closed.

## Frame-state references are deliberately separate

The following roles define or preserve frame state and are not treated as timed canonical
asset references:

- `scene_composition_anchor`
- `continuity_anchor`
- `start_frame_reference`
- `end_frame_reference`

They are recorded under `frame_state_reference_ids` for audit, but they are excluded
from per-span canonical-reference activation sets.

This prevents a start/composition image from being confused with an identity reference.

Their actual use at internal boundaries belongs to later governed keyframe/runtime work.

## Unscoped supporting references

For a dynamic multi-span Shot, any governed supporting reference that is neither:

- explicitly attached to a Timed Asset Presence interval, nor
- a frame-state reference

is rejected.

VSCS does not infer that such a reference is safe for every span.

This is especially important for character/group/style references that could contain or
imply an asset before its governed introduction.

For a one-span Shot, legacy unscoped supporting references may remain active for the
whole Shot because there is no temporal activation boundary to violate.

## Production Package integration

When Timed Asset Presence and Internal Render Span authority are present,
`ProductionPackageCompilerService` now derives Timed Canonical Reference Activation
after the governed ReferencePlan has been compiled and validated.

The activation plan is included in:

- `CompiledProductionPackage.timed_reference_activation`;
- `CompiledProductionPackage.to_dict()`;
- `composition_plan.timed_reference_activation`;
- the executable Production Package fingerprint.

This ensures that reference activation is production authority rather than provider-side
advice.

## Provider boundary

The existing provider path remains deliberately fail-closed for multi-span Shots.

The new sequence is:

```text
Timed Asset Presence                  VALID
Governed Internal Render Spans        VALID
Timed Canonical Reference Activation  VALID
Provider multi-span execution         NOT YET IMPLEMENTED
```

A dynamic package with valid 3.3 authority reaches the provider boundary and is rejected
with an explicit message that current provider execution remains monolithic.

The full, shot-wide ReferencePlan must not be passed directly into future individual span
renders. Future provider orchestration must consume each span's
`active_reference_ids`.

## Deliberate exclusions

Phase 20.18.2.3.3 does not implement:

- separate LTX-2.5 provider jobs for each internal span;
- provider-specific reference-input mapping per span;
- actual extraction/publication of internal boundary images;
- governed Introduction Keyframes;
- frame-95 to frame-96 runtime conditioning;
- span retry/recovery authority;
- final span assembly;
- automated visual QC for early/late asset appearance;
- Timed Asset Timeline UI.

Those are downstream capabilities built on this activation authority.
