# Phase 20.18.2.3.2 — Governed Internal Render Spans

## Purpose

Phase 20.18.2.3.2 converts accepted Timed Asset Presence authority into deterministic,
provider-neutral internal render spans without changing the editorial Shot identity.

An editorial Shot remains one Shot. Internal spans exist only to make frame-exact
composition changes executable in later provider phases.

This phase establishes span topology and governed internal-boundary requirements. It
does not yet activate/deactivate canonical references at the provider or orchestrate
multiple provider renders. Those remain downstream work.

## Source authority

The sole temporal source is the accepted Phase 20.18.2.3.1
`TimedAssetPresencePlan`.

Internal spans are derived from:

- frame 0;
- every governed `change_frames` entry;
- the Shot's exclusive final frame boundary (`frame_count`).

No provider or prompt text may invent additional span boundaries.

## Ros example

For SHT-002:

```text
Shot duration: 6.000 s
Frame rate:    24 fps
Frame count:   144
Change frame:  96
```

The resulting topology is:

```text
SHT-002 (one editorial Shot)
│
├─ IRS span 001
│  global frames 0-95
│  local frames  0-95
│  active: James, Sandra, Iron Horizon bridge
│
├─ governed internal boundary requirement
│  source global frame: 95
│  target global frame: 96
│  source local frame:  95
│  target local frame:   0
│
└─ IRS span 002
   global frames 96-143
   local frames  0-47
   active: James, Sandra, Iron Horizon bridge, Ros
   introduced at span opening: Ros
```

The first span therefore ends on the exact governed visual state immediately before
Ros enters. The second span starts at the exact asset-change frame.

## Internal render span authority

Each `GovernedInternalRenderSpan` records:

- deterministic `span_id`;
- original Shot identity;
- sequence number;
- inclusive global `start_frame`;
- inclusive global `through_frame`;
- derived frame count;
- frame rate and duration;
- source Timed Asset Presence fingerprint;
- active presence identities;
- active asset identities;
- presence/asset identities introduced at the span opening;
- presence/asset identities removed at the span opening;
- optional governed internal opening-boundary requirement;
- optional governed internal closing-boundary requirement.

The span ID is derived from immutable span content plus the source Timed Asset Presence
fingerprint. Internal-boundary linkage does not redefine span identity.

## Governed internal boundary requirement

A `GovernedInternalSpanBoundary` is an authority requirement, not a claim that an
image has already been rendered or accepted.

It records:

- deterministic `boundary_id`;
- source span identity;
- target span identity;
- exact source global frame;
- exact target global frame;
- exact source local final frame;
- target local frame 0;
- source Timed Asset Presence fingerprint;
- status `required`.

For adjacent spans, the required relation is always:

```text
target_global_frame = source_global_frame + 1
target_local_frame  = 0
source_local_frame  = source_span.frame_count - 1
```

A later runtime phase may satisfy this requirement by extracting and approving the
actual final frame produced by the source span.

## Span plan

`GovernedInternalRenderSpanPlan` records:

- original Shot identity;
- authoritative frame rate and frame count;
- source Timed Asset Presence plan ID and SHA-256 fingerprint;
- governed change frames;
- ordered spans;
- ordered boundary requirements;
- deterministic plan ID and SHA-256 fingerprint;
- provider-neutral status.

The plan must cover every governed Shot frame exactly once.

No gaps or overlaps are allowed.

For N spans, exactly N-1 internal boundary requirements must exist.

## Asset transition semantics

The span compiler does not duplicate Phase 20.18.2.3.1 event semantics.

Instead it records which presence and asset identities are:

- active in the span;
- introduced at that span opening;
- removed at that span opening.

The authoritative ENTER / REVEAL / APPEAR / EXIT / HIDE / DISAPPEAR semantics remain in
the source Timed Asset Presence plan and are checksum-linked by its fingerprint.

Timed canonical-reference activation is deliberately deferred to Phase 20.18.2.3.3.

## Determinism and tamper detection

The following are deterministic and content-derived:

- span IDs;
- internal boundary IDs;
- span-plan ID;
- span-plan SHA-256 fingerprint.

Deserialization fails closed when persisted derived fields or topology do not agree with
their authoritative inputs, including:

- frame counts;
- durations;
- span IDs;
- boundary IDs;
- plan ID;
- plan fingerprint;
- span ordering;
- frame coverage;
- change-frame boundaries;
- source/target span linkage;
- local/global frame mapping;
- source Timed Asset Presence identity/fingerprint.

## Production Package integration

When a compiled Production Package contains Timed Asset Presence authority,
`ProductionPackageCompilerService` now automatically derives the corresponding governed
internal render-span plan.

The plan is included in:

- the provider-neutral `CompiledProductionPackage`;
- `composition_plan.internal_render_spans`;
- the executable authority fingerprint;
- `CompiledProductionPackage.to_dict()`.

Changing the source Timed Asset Presence authority therefore changes both span topology
and downstream package authority.

## Provider execution boundary

Phase 20.18.2.3.2 does not pretend that the current monolithic LTX-2.5 Candidate C
workflow can execute multiple spans.

Behavior is fail-closed:

1. Dynamic Timed Asset Presence without a compiled span plan is rejected.
2. A compiled multi-span plan is validated successfully.
3. Provider package compilation then stops with an explicit message that current
   provider execution is still monolithic and that timed canonical-reference activation
   plus governed multi-span orchestration are required.
4. A single-span plan remains compatible with the current monolithic provider path.

This is intentional. It proves that VSCS understands the required render topology while
preventing premature execution that could leak Ros or another newly introduced asset into
the wrong temporal region.

## Deliberate exclusions

Phase 20.18.2.3.2 does not implement:

- per-span canonical-reference filtering/activation;
- provider-specific per-span prompts;
- rendering Span A and Span B as separate jobs;
- extraction/publication of actual internal span boundary images;
- governed Introduction Keyframes;
- multi-span retry authority;
- final span concatenation/assembly;
- automated temporal vision QC;
- Timed Asset Timeline editing UI.

These capabilities remain downstream of the accepted provider-neutral span model.
