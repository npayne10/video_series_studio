# Phase 20.18.2 — Shot-Local Character Authority Precedence

## Decision

Character asset inference is now governed by the individual Shot before broader Scene
context. A character appearing somewhere in a Scene must not automatically become a
required asset for every Shot in that Scene.

The precedence order is:

1. Shot title
2. Shot narrative purpose
3. Shot production objective
4. Shot required action
5. Shot dialogue requirement
6. Shot continuity in/out
7. Shot constraints
8. explicit Scene persistence constraints only

General Scene story scope, setting, required events and other Scene text may still inform
non-character production assets such as Location, Environment Context, Planet, Ship,
Prop and Technology. They no longer authorize character presence by themselves.

## Character inference rule

For `AssetCategory.CHARACTER`, deterministic inference accepts a character only when:

- the character is explicitly supported by Shot-local authority; or
- the Scene contains an explicit persistence constraint requiring that character in
  every Shot.

Supported persistence constraint forms are:

- `persistent character: <name>`
- `persistent asset: <name-or-asset-id>`
- `always present character: <name>`
- `always present asset: <name-or-asset-id>`

A general statement in Scene story scope that a character exists somewhere in the Scene
is not a persistence declaration.

## AI boundary

Optional semantic AI receives the same governance instruction: it must not promote a
Scene-only character into a Shot requirement.

AI proposals also pass through a deterministic post-inference authority gate. A matched
Character proposal is retained only if its canonical name is present in Shot-local
authority or explicitly required by a Scene persistence constraint. This prevents a
provider error from bypassing the governance rule.

Unresolved AI Character proposals are retained only when their proposal evidence
meaningfully overlaps Shot-local authority; otherwise they are discarded.

## Speaker classification

After the Shot-local gate, existing role classification remains in force:

- an explicitly supported speaking/reporting/ordering character can become
  **Dialogue Speaker**;
- another explicitly present character becomes **Supporting Character**.

This prevents Scene-level characters from displacing the actual Shot-local speaker.

## Xorix test oracle

For the opening **The Silent Relay** dialogue Shot:

- Sandra Crawford is required by Shot-local action and dialogue authority;
- Commander James Spence is required by Shot-local action/continuity;
- Captain Cheryl Draker appears later in the Scene and must not be inferred into this
  Shot unless a separate explicit Scene persistence constraint requires her.

## Governance

No Story, Scene, Shot, XPD or CAP history is deleted. This change affects only which
reviewable Shot asset requirement proposals are eligible to reach the Asset Resolver.

All materialized bindings remain Draft until explicit human approval.

Phase 20.18.2 remains open pending local automated validation, UI re-test, downstream
planning, live provider execution, GeneratedMedia provenance and explicit owner
acceptance.
