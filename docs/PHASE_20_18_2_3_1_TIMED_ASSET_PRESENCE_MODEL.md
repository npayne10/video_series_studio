# Phase 20.18.2.3.1 — Timed Asset Presence Model

## Purpose

Phase 20.18.2.3.1 introduces provider-neutral, frame-exact authority describing which
canonical production assets are visible or active during specific intervals of one
editorial Shot.

The model is generic. It applies to characters, ships, vehicles, locations,
environments, props, effects, technology, and future asset categories.

This phase defines and carries authority only. It does not yet split a Shot into
internal render spans or activate provider references dynamically. Those responsibilities
belong to Phase 20.18.2.3.2 and later phases.

## Core principle

An editorial Shot remains one Shot even when its visible asset composition changes.

Provider execution must never infer timing from prompt prose. Asset presence authority is
expressed in exact governed frame indices.

At 24 fps, an event beginning at exactly 4.000 seconds begins at frame 96.

## Model

A `TimedAssetPresencePlan` contains:

- Shot identity;
- authoritative frame rate;
- authoritative frame count;
- zero or more `TimedAssetPresence` intervals;
- deterministic plan identity and SHA-256 fingerprint;
- deterministic composition-change frame indices;
- provider-neutral status.

Each presence interval contains:

- governed asset identity;
- generic asset kind;
- inclusive `from_frame`;
- inclusive `through_frame`;
- introduction event;
- removal event;
- zero or more canonical-reference identities;
- required/optional status;
- production notes;
- deterministic presence identity.

### Asset kinds

- `character`
- `ship`
- `vehicle`
- `location`
- `environment`
- `prop`
- `effect`
- `technology`
- `other`

### Introduction events

- `present` — already present at the interval opening;
- `enter` — physically enters the visible composition;
- `reveal` — becomes visible because framing/occlusion changes;
- `appear` — becomes visible/active without physical entry.

An interval beginning after frame 0 may not use `present`; it must declare how the asset
is introduced.

### Removal events

- `through_shot` — remains present through the final governed frame;
- `exit` — physically leaves the composition;
- `hide` — ceases to be visible because framing/occlusion changes;
- `disappear` — ceases to be visible/active without physical exit.

An interval ending before the Shot's final governed frame may not use
`through_shot`; it must declare how the asset leaves visibility/authority.

## Ros acceptance example

For a six-second, 24 fps SHT-002 with 144 governed frames:

```text
frames 0-95   James + Sandra + Iron Horizon bridge
frame 96      Ros introduction boundary (4.000 seconds)
frames 96-143 James + Sandra + Iron Horizon bridge + Ros
```

Representative authority:

```json
{
  "schema_version": "1.0",
  "provider_neutral": true,
  "shot_id": "EP-001-SCN-001-SHT-002",
  "timing_basis": {
    "frames_per_second": 24,
    "frame_count": 144
  },
  "presences": [
    {
      "asset_id": "CAP-CHR-001",
      "asset_kind": "character",
      "from_frame": 0,
      "through_frame": 143,
      "introduction": "present",
      "removal": "through_shot"
    },
    {
      "asset_id": "CAP-CHR-003",
      "asset_kind": "character",
      "from_frame": 0,
      "through_frame": 143,
      "introduction": "present",
      "removal": "through_shot"
    },
    {
      "asset_id": "CAP-LOC-021",
      "asset_kind": "location",
      "from_frame": 0,
      "through_frame": 143,
      "introduction": "present",
      "removal": "through_shot"
    },
    {
      "asset_id": "CAP-CHR-004",
      "asset_kind": "character",
      "from_frame": 96,
      "through_frame": 143,
      "introduction": "enter",
      "removal": "through_shot",
      "canonical_reference_ids": ["REF-ROS-PRIMARY"]
    }
  ],
  "change_frames": [96]
}
```

Ros is therefore not active authority at frame 95 and is active authority at frame 96.

## Validation

The model fails closed when:

- Shot identity is blank or mismatched;
- frame rate or frame count is non-positive;
- an interval has negative frames;
- `through_frame` precedes `from_frame`;
- an interval exceeds the Shot's final frame;
- a late-starting interval has no explicit introduction event;
- an early-ending interval has no explicit removal event;
- intervals for the same asset overlap;
- canonical-reference identities are blank or duplicated;
- a presence references an asset absent from governed Asset authority;
- persisted presence or plan identity does not match its content;
- persisted plan fingerprint does not match its content;
- persisted `change_frames` do not match the intervals;
- executable render frame rate/count differ from the reviewed timing basis.

## Production authority integration

`ProductionPackageService.derive_timed_asset_presence()` appends a deterministic
Production Package revision and marks:

`timed_asset_presence_complete = true`

The authority is propagated through:

1. canonical Production Package;
2. Universal Production Description;
3. UPD dependency fingerprint;
4. UPD universal text;
5. provider-neutral compiled Production Package;
6. composition plan;
7. executable package fingerprint.

Changing a reviewed presence plan therefore changes downstream authority and requires
normal recompilation/review behavior.

## Current provider-execution boundary

Phase 20.18.2.3.1 deliberately does not implement internal render spans.

A static presence plan with no composition-change frames can be carried through the
existing provider package without changing provider behavior.

A dynamic plan with one or more `change_frames` fails closed during current ComfyUI
package compilation with an explicit message that internal governed render spans are
required.

This prevents a provider from receiving Ros's reference for an entire Shot and silently
allowing identity leakage before frame 96.

## Deferred to later Phase 20.18.2.3 work

Not implemented in 20.18.2.3.1:

- automatic internal render-span creation;
- governed internal span-boundary keyframes;
- timed provider reference activation/deactivation;
- governed Introduction Keyframes;
- reference-conditioning strategy for LTX-2.5;
- Shot Asset Timeline editing UI;
- vision QC for early/late/missing asset appearance;
- final span assembly into one authoritative Generated Media Shot.

These are intentionally downstream of the authority model.
