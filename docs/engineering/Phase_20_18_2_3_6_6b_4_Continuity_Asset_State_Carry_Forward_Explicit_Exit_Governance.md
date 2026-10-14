# Phase 20.18.2.3.6.6b.4 — Continuity Asset-State Carry-Forward & Explicit Exit Governance

## Objective

Prevent a continuous Shot boundary from silently dropping an asset that remains active at
the end of the previous Shot.

This hardening was triggered by live SHT-003 compilation. SHT-002 explicitly establishes
CAP-CHR-005 (Major Ros Rohsgard) as present on the Iron Horizon bridge through its final
governed frame. SHT-003 begins with a preserve/continue-directly boundary but its current
Asset and Timed Asset Presence authority omitted CAP-CHR-005. The legacy Continuity
Compiler displayed no conflict because it compared textual opening/closing state but did
not reconcile frame-exact asset state across the boundary.

## Governance rule

For a continuous boundary:

1. determine the assets active on the previous Shot's final governed frame;
2. determine any assets with an explicit previous-boundary removal event;
3. subtract explicitly removed assets from the carry-forward requirement;
4. determine assets active at frame 0 of the current Shot;
5. any remaining carried asset absent at current frame 0 is a blocking continuity
   conflict.

The compiler never invents an exit from prose and never silently drops a carried asset.

## Explicit exit authority

Timed Asset Presence is the structured authority for an explicit exit/removal event.

A previous-Shot asset is exempt from carry-forward only when its final interval reaches
the previous Shot's final governed frame and its removal is one of:

- `exit`
- `hide`
- `disappear`

`through_shot` is not an exit. An asset governed `through_shot` remains part of the
continuous-boundary carry-forward state.

This deliberately avoids NLP inference from phrases such as "walks away" or "is no longer
seen." If the production intends a boundary exit, it must be encoded as explicit governed
Timed Asset Presence authority.

## Structured Continuity evidence

The Continuity draft now records:

- `previous_final_active_asset_ids`
- `previous_boundary_exit_asset_ids`
- `current_opening_active_asset_ids`
- `carry_forward_required_asset_ids`
- `missing_carried_asset_ids`
- `blocking_continuity_conflicts`

The compiled provider-neutral Continuity production view carries the same asset-state
evidence.

## Blocking semantics

Textual inherited-state conflicts retain the historical reviewable behavior.

Asset-state carry-forward conflicts are stronger. They are blocking because allowing a
continuous boundary to compile while dropping unresolved carried state would create
contradictory production authority.

When `blocking_continuity_conflicts` is non-empty:

- `Mark Ready & Compile` is disabled in the Continuity UI;
- service-level validation also rejects Ready/Compile, so the UI cannot be bypassed;
- the operator is told to either:
  - restore the asset into current governed Asset + Timed Asset Presence authority; or
  - explicitly govern EXIT/HIDE/DISAPPEAR at the previous Shot boundary.

## Timed Asset Presence dependency

New Continuity drafts include current and previous Timed Asset Presence authority in the
dependency fingerprint. Changing either side makes the Draft stale and requires
`Refresh Inherited State`.

When no Timed Asset Presence authority exists, the compiler falls back conservatively to
the governed Asset IDs for that Shot.

## Accepted-production compatibility

Existing Ready Continuity drafts created before this phase are not invalidated merely
because the application gained the new dependency model.

A per-draft `asset_state_governance_version` distinguishes new authority from legacy
authority:

- new Drafts use the asset-state-aware dependency model;
- legacy Drafts are stale and must refresh before new approval;
- legacy Ready drafts continue to use the legacy dependency fingerprint while they remain
  Ready;
- once a legacy Ready draft is explicitly returned to Draft, it must refresh into the new
  asset-state model before it can be approved again.

This preserves accepted SHT-001/SHT-002 production while ensuring new or reopened work is
governed by the stronger rule.

## SHT-003 expected result

After this phase is installed, the existing pre-phase SHT-003 Continuity Draft must appear
stale and require `Refresh Inherited State`.

The refreshed draft is expected to resolve:

- previous final active assets: the seven SHT-002 governed presences;
- previous boundary exits: none;
- current opening active assets: the six current SHT-003 presences;
- missing carried asset: `CAP-CHR-005`;
- blocking conflict: one.

SHT-003 must not compile until Ros is either carried into current governed authority or an
explicit previous-boundary removal is governed.

## Automated regression coverage

Regression coverage includes:

- blocking a continuous boundary when a final-active asset disappears without exit;
- allowing an explicit previous-boundary EXIT;
- allowing a carried asset that is present at current frame 0;
- Timed Asset Presence changes invalidating new Continuity drafts;
- legacy Ready draft compatibility;
- UI disabling Ready and surfacing the missing carried asset.

## Acceptance evidence

Post-implementation local validation:

- working tree clean before validation;
- Ruff check: PASS;
- Ruff format check: PASS — 1318 files already formatted;
- mypy: PASS — 595 source files;
- focused regression: PASS — 41 tests in 6.16 s;
- full regression: PASS — 1907 tests in 26.61 s.

Live SHT-003 acceptance:

- existing pre-phase Continuity Draft became stale and was refreshed into the new
  asset-state-aware model;
- previous final active assets resolved to the seven SHT-002 governed presences;
- previous boundary exits resolved to none;
- current opening active assets resolved to the six current SHT-003 presences;
- carry-forward required assets contained all seven previous final-active assets;
- missing carried asset resolved to `CAP-CHR-005`;
- one blocking continuity conflict was surfaced;
- `Mark Ready & Compile` was disabled while the conflict remained unresolved.

Protected-work preservation:

- SHT-001 Continuity remained Ready / Compiled with no stale warning, no refresh request
  and no migration requirement;
- SHT-002 Continuity remained Ready / Compiled with no stale warning, no refresh request
  and no migration requirement;
- SHT-002 retained its accepted closing state establishing Ros present on the Iron Horizon
  bridge with the unusual signal unresolved;
- the legacy Ready compatibility boundary therefore protected accepted SHT-001/SHT-002
  authority while new SHT-003 work adopted the stronger asset-state model.

## Phase state

**CLOSED — IMPLEMENTATION, STATIC VALIDATION, FOCUSED REGRESSION, FULL REGRESSION,
LIVE SHT-003 BLOCKING DETECTION, AND SHT-001/SHT-002 PROTECTED-AUTHORITY PRESERVATION
ALL PASSED.**
