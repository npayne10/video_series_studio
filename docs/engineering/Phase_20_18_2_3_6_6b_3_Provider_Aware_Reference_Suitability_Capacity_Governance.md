# Phase 20.18.2.3.6.6b.3 — Provider-Aware Reference Suitability & Capacity Governance

## Objective

Remove legacy LTX-specific assumptions from Reference Suitability and make governed visual
reference review consistent with the installed provider-policy registry.

This phase is required before the first real SHT-003 provider-selectable run because the
current Shot contains six governed visual assets while MiniMax H3 exposes five direct
reference-image slots.

## Failure evidence

Live SHT-003 acceptance exposed three structural defects:

1. Reference Suitability defaulted to `ltx23-local` and hard-coded the legacy
   three-reference LTX capacity.
2. Both supporting characters were initially suggested as `secondary_identity`, while
   the approval service deterministically treated the first governed character as the
   primary identity when no stronger semantic marker existed.
3. Timed Asset Presence allowed editing and Save until the persistence layer rejected the
   operation because no passing governed ReferencePlan existed.

These are upstream workflow defects. SHT-003 must not be repaired through one-off manual
JSON changes or by silently unchecking governed assets.

## Provider-aware policy source

Reference Suitability now receives the installed
`ProviderPolicyProfileRegistry`.

Current installed policies include:

- MiniMax H3 / `minimax-h3-ref2va-v1`
  - provider `minimax-h3-ref2va`
  - direct span-scoped canonical-reference projection
  - maximum five direct reference images.
- LTX-2.5 Candidate C / `ltx-2.5-candidate-c-v1`
  - provider `ltx-2.5`
  - governed references projected indirectly into the governed keyframe
  - zero direct picture slots at this review boundary.

The Target Provider control is a governed selector populated from enabled installed
profiles. Existing legacy provider IDs can still be displayed when loading old reviews,
but they are marked as legacy/unavailable and cannot silently inherit a new capacity
policy.

## Deterministic capacity projection

The complete governed ReferencePlan remains authoritative. Capacity projection does not
delete or demote governed references.

For providers using direct span-scoped canonical references:

1. required direct references are selected first in governed review order;
2. required references are never silently dropped;
3. if required count exceeds provider capacity, approval is blocked;
4. remaining slots are filled by provider-ready preferred references in governed review
   order;
5. optional references do not consume scarce direct slots merely to fill capacity;
6. provider-ready preferred references beyond capacity are explicitly recorded as
   deferred.

For an SHT-003 review with:

- Sandra — required;
- James — required;
- Iron Horizon bridge — required;
- Xorix — required;
- Xorix Orbit — preferred;
- Iron Horizon exterior — preferred;

MiniMax H3 projects five direct references:

1. Sandra;
2. James;
3. Iron Horizon bridge;
4. Xorix;
5. Xorix Orbit;

and explicitly defers the Iron Horizon exterior reference from direct provider slots.
The full six-reference governance remains preserved.

For non-direct provider projection modes, no fake direct-slot limit is imposed. The UI
reports the installed indirect projection policy instead.

## Character identity-role alignment

Character suggestion and approval now share the same deterministic primary-character
rule.

The primary character is:

1. the first governed character whose semantic role contains a primary marker such as
   dialogue speaker, primary, lead or principal; otherwise
2. the first governed character in Production Package order.

All other directly reviewed governed characters use `secondary_identity`, unless a
reviewed group identity is explicitly used.

For current SHT-003 authority this yields:

- CAP-CHR-003 Sandra Crawford — `primary_identity`;
- CAP-CHR-001 James Spence — `secondary_identity`.

## Persisted projection audit

The explicit suitability review stores a `provider_capacity_projection` object
containing:

- provider and policy-profile identity;
- policy-profile fingerprint;
- provider model family;
- projection mode;
- direct capacity;
- required reference IDs;
- provider-ready preferred reference IDs;
- projected direct reference IDs;
- deferred preferred reference IDs;
- pass/block state and reason.

When suitability resolves successfully, that projection is also carried into the
persisted governed ReferencePlan. This preserves the operator-reviewed provider-capacity
decision without weakening the complete ReferencePlan.

## MiniMax H3 execution integration

The H3 span adapter now derives direct picture slots through the same capacity policy.

For ordinary span-scoped references without a required scene-composition anchor,
the new policy-driven projection is activated only when the governed ReferencePlan carries
a passing, current MiniMax H3 `provider_capacity_projection`. The adapter verifies the
provider ID, policy-profile ID, policy fingerprint, projection mode and capacity before
using it. With that reviewed authority:

- required references are projected first;
- provider-ready preferred references fill remaining slots;
- deferred preferred reference IDs are recorded in the H3 span execution authority and
  provider evidence;
- provider prompt picture declarations are rebuilt to match the projected slot set.

Pre-6.6b.3 no-anchor H3 authority without a capacity projection retains the legacy
behavior when it already fits the installed H3 slot limit, and still fails closed when it
does not. This prevents the new policy from silently changing accepted production merely
because the application was upgraded.

Existing governed scene-composition-anchor projection remains supported and now obtains
its slot count from the installed H3 policy profile rather than a hard-coded literal.
That accepted legacy anchor path deliberately does not add empty/deferred fields to its
fingerprinted span serialization, so this hardening does not silently rewrite accepted
SHT-001/SHT-002 H3 execution authority merely because the new audit concept exists.

This means a six-reference SHT-003 ReferencePlan no longer fails later merely because all
six governed references became active; the fifth-slot decision is deterministic,
reviewable and auditable.

## Timed Asset Presence prerequisite UX

Timed Asset Presence now exposes the ReferencePlan dependency before Save.

Live preservation validation also exposed a cross-Shot UI-state hazard: the authority review
note editor retained the previous Shot's text when selecting a different Shot that had no
persisted Timed Asset Presence authority. The note was editor state only and had not altered
the protected Shot, but saving from that state could have copied the wrong human review note
into another Shot. The workspace now clears the note for non-persisted/error/no-selection
contexts and reloads the Shot-specific persisted review note from Production Package validation
when Timed Asset Presence authority exists.

When no passing governed ReferencePlan exists:

- full-shot governed-asset defaults remain visible for review;
- `Save Timed Presence Authority` is disabled;
- the status explains that Reference Suitability must be approved first;
- `Review Reference Suitability…` provides a direct workflow shortcut when the
  Production Planning workspace exposes that action.

No persistence-layer exception is required merely to discover the missing prerequisite.

## Governance boundaries

This phase does **not**:

- invent provider-readiness facts;
- mark canonical references provider-ready automatically;
- drop required references to satisfy provider limits;
- delete governed assets;
- alter accepted SHT-001 or SHT-002 production authority;
- execute a provider;
- bypass Timed Asset Presence, UPD, Production Review, ProductionTask or provider
  validation.

Reference provider-readiness, framing and coverage remain explicit human decisions.

## Automated regression coverage

Regression coverage includes:

- H3 four-required + two-preferred projection into five slots;
- explicit preferred-reference deferral;
- blocking when required direct references exceed H3 capacity;
- LTX-2.5 indirect projection with no fake direct-slot capacity;
- deterministic Sandra-primary / James-secondary role suggestion for SHT-003-shaped
  supporting-character authority;
- persisted provider-capacity projection in both explicit suitability and governed
  ReferencePlan authority;
- installed provider selector choices;
- H3 span-level direct-slot projection and deferred-reference evidence;
- Timed Asset Presence Save disabled until a passing ReferencePlan exists.

## Live SHT-003 acceptance

After automated validation passes:

1. open `D:\VSCS TSR2`;
2. select SHT-003 → Universal Description → Reference Suitability;
3. confirm Target Provider defaults to MiniMax H3 / `minimax-h3-ref2va`;
4. include all six governed references;
5. apply suggested priorities;
6. confirm Sandra is primary identity and James secondary identity;
7. explicitly review each reference for provider readiness, framing, coverage and
   completeness;
8. confirm the capacity preview shows four required references, two provider-ready
   preferred references, five projected direct slots, and one explicitly deferred
   preferred reference;
9. approve suitability and persist the passing ReferencePlan;
10. return to Timed Asset Presence;
11. confirm Save is enabled and the persisted ReferencePlan IDs are available;
12. save the reviewed static 0–239 SHT-003 presence authority;
13. verify SHT-001 and SHT-002 remain unchanged.

## Acceptance evidence

Post-repair local validation:

- Ruff check: PASS.
- Ruff format check: PASS — 1316 files already formatted.
- mypy: PASS — 595 source files.
- focused regression: PASS — 25 tests in 2.40 s.
- full regression: PASS — 1898 tests in 25.41 s.

Live SHT-003 acceptance:

- MiniMax H3 selected from installed provider policy.
- six governed references reviewed explicitly.
- Sandra resolved as `primary_identity`; James as `secondary_identity`.
- four references required and two preferred.
- direct H3 projection passed at 5/5.
- `LIVE-BACKGROUND_IDENTITY-CAP-SHP-002` was explicitly deferred.
- governed ReferencePlan persisted with status `passed`.
- Timed Asset Presence prerequisite unlocked only after that passing plan existed.
- six static presence intervals persisted for frames 0–239 at 24 fps with no change frames.
- SHT-003 authority review note reloads only for SHT-003.

Protected-work preservation:

- SHT-001 remains on its existing 144-frame accepted context; no Timed Asset Presence authority
  was created and its review-note editor is blank.
- SHT-002 remains persisted and current with seven presence intervals at 24 fps / 144 frames.
- SHT-002 retains the governed frame-96 change boundary.
- CAP-CHR-005 (Major Ros Rohsgard) remains absent through frame 95 and enters at frame 96,
  continuing through frame 143.
- SHT-002 retains its own persisted review note:
  `Phase 20.18.2.3.5 SHT-002 functional acceptance. Major Ros Rohsgard is absent through frame 95 and enters at global frame 96.`
- No stale/rebuild/migration warning or provider execution was triggered during read-only
  preservation checks.

## Phase state

**CLOSED — IMPLEMENTATION, STATIC VALIDATION, FOCUSED REGRESSION, FULL REGRESSION,
LIVE SHT-003 FUNCTIONAL ACCEPTANCE, CROSS-SHOT REVIEW-NOTE ISOLATION, AND SHT-001/SHT-002
PROTECTED-AUTHORITY PRESERVATION ALL PASSED.**
