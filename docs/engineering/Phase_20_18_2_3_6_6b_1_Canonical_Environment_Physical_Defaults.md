# Phase 20.18.2.3.6.6b.1 — Canonical Environment Physical Defaults

## Objective

Allow the governed Environment Planner to inherit known physical environment values
from approved Canonical Asset Profile (CAP) production authority instead of forcing
operators to re-enter the same values for every Shot.

This phase preserves the Phase 19.3.7 rule that unknown fictional physics must
remain unknown. A generic interior is **not** assumed to be Earth-normal.

## Authority model

The Environment Planner consumes physical defaults only from current,
production-ready Shot asset bindings whose CAP authority is published through the
stable Production Projection API.

Supported source categories are:

1. **Location** — highest-priority local physical authority.
2. **Environment** — wider physical authority, consumed only when it explicitly
   declares the same environment context as the governed Shot.

A Location CAP may omit the context key because its bound Shot-local identity
already establishes locality. If a Location CAP explicitly declares a context
that conflicts with the governed Shot, planning fails closed.

A wider Environment CAP must explicitly declare a matching context. This prevents
an orbital Environment such as Xorix Orbit from leaking vacuum values into a
spacecraft bridge interior.

## Canonical keys

Physical defaults are represented through existing structured CAP production
knowledge; no persistence schema migration is required.

The Environment Planner recognises these canonical keys:

- `environment.context`
- `environment.gravity_m_s2`
- `environment.pressure_kpa`
- `environment.temperature_c`
- `environment.visibility_m`

Values may be supplied as approved/canonical structured CAP facts or through CAP
`production_metadata`. When both are present for the same key, the structured
fact wins.

Valid `environment.context` values are the existing governed Environment
Planner values:

- `interior`
- `exterior_surface`
- `atmospheric`
- `orbital_space`
- `deep_space`
- `subterranean`
- `underwater`

## Example — controlled human spacecraft bridge

For a canonical bridge Location such as `CAP-LOC-021`:

| Key | Value |
| --- | --- |
| `environment.context` | `interior` |
| `environment.gravity_m_s2` | `9.81` |
| `environment.pressure_kpa` | `101.3` |
| `environment.temperature_c` | `21` |
| `environment.visibility_m` | `30` |

These values are examples of explicitly approved canonical authority. They are not
global defaults and are never inferred merely because a Shot is indoors.

## Merge policy

For each physical field:

1. current Location CAP authority wins;
2. matching Environment CAP authority fills only values not supplied by Location;
3. multiple equal-priority sources that disagree fail closed;
4. malformed or out-of-range canonical numeric values fail closed;
5. no canonical value means the existing Environment Planner inference remains in
   force, including `Unknown` where canon is silent.

Canonical values override heuristic values such as the existing explicit-Earth
special case because canonical asset authority is more specific.

## Invalidation

Environment Plans already fingerprint the current Shot asset context. Asset
dependency fingerprints include the CAP checksum. Therefore changing canonical
physical environment metadata makes the relevant Asset binding stale and prevents
downstream Environment authority from silently remaining current.

## Acceptance criteria

Implementation is accepted when:

- current Ready asset bindings can expose their structured CAP Production
  Projection;
- a Location CAP can populate gravity, pressure, temperature and visibility;
- approved structured facts override duplicate production metadata;
- a wider Environment CAP with a mismatched context cannot leak values into a
  Shot-local interior;
- malformed canonical physical values fail closed;
- unspecified fictional environments remain unknown;
- canonical source asset IDs are recorded in Environment constraints for audit;
- existing Phase 19.3.7 environment behavior remains backward compatible when no
  canonical physical metadata exists;
- Ruff, format, mypy, focused tests and full repository regression pass.

## Phase state

Implementation does not by itself promote existing Shot-level values into CAP
authority. Existing projects must explicitly add the desired canonical facts or
production metadata to the governing Location/Environment CAP once; future
Suggested Environment Drafts then inherit them automatically.

Because CAP checksums participate in current Asset dependency fingerprints,
retrofitting physical metadata onto a CAP already used by accepted production is
an intentional canonical change and can make existing planning dependencies
stale. Do not retrofit such a live CAP merely to demonstrate this phase. Validate
the inheritance path in a scratch/test project or on new, not-yet-produced
authority unless an explicit production-supersession review has been approved.

## Acceptance evidence

Validation completed successfully on 2026-10-11:

- Ruff lint passed.
- Ruff formatting check passed across 1312 files.
- mypy passed across 594 source files.
- Focused Environment/CAP validation passed: 46 tests.
- Full repository regression passed: 1883 tests in 26.50 seconds.
- `git diff --check` and `git status --short` were clean.
- A disposable clone of the Xorix project was used for live acceptance so accepted
  production authority in the real project was not disturbed.
- After adding the controlled-interior physical metadata to `CAP-LOC-021` in the
  clone, `Create Suggested Draft` populated:
  - gravity `9.81 m/s²`;
  - pressure `101.3 kPa`;
  - temperature `21 °C`;
  - visibility `30 m`.
- The generated Environment Plan remained current against Shot, Asset, Camera and
  Lighting authority and transitioned successfully from Draft to Ready with the
  inherited physical values unchanged.

## Phase state

Implementation does not by itself promote existing Shot-level values into CAP
authority. Existing projects must explicitly add the desired canonical facts or
production metadata to the governing Location/Environment CAP once; future
Suggested Environment Drafts then inherit them automatically.

Because CAP checksums participate in current Asset dependency fingerprints,
retrofitting physical metadata onto a CAP already used by accepted production is
an intentional canonical change and can make existing planning dependencies
stale. Do not retrofit such a live CAP merely to demonstrate this phase. Validate
the inheritance path in a scratch/test project or on new, not-yet-produced
authority unless an explicit production-supersession review has been approved.

**Phase 20.18.2.3.6.6b.1 — COMPLETE / ACCEPTED.**
