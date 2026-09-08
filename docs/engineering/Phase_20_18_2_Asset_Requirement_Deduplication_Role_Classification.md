# Phase 20.18.2 — Asset Requirement Deduplication & Role Classification

## Decision

Automated Shot asset inference must produce the smallest useful governed requirement set,
not a flat list of every Story, Scene and canonical entity whose wording happens to overlap.

The post-inference flow is now:

Ready governed Shot / Ready Scene
→ deterministic extraction
→ canonical XPD/CAP matching
→ optional AI gap inference
→ role normalization
→ exact proposal deduplication
→ story-placeholder suppression
→ location/environment/planet overlap reduction
→ human review
→ Draft ShotAssetBindings.

No stage creates canon or marks a binding Ready.

## 1. Minimal environment/location production set

Location, environment and planet concepts are treated as related production context but
retain distinct responsibilities:

- **Location** identifies the physical production space, such as a bridge or chamber.
- **Environment Context** identifies the surrounding environmental state, such as orbit.
- **Visible Planet** identifies a planet explicitly required in the Shot.
- **Planetary Context** identifies a planet inherited only from Scene context.

Within each category, semantically overlapping candidates are ranked by canonical
readiness, canonical-match authority, confidence and placeholder status. The stronger
candidate survives. Distinct categories are preserved when they perform distinct
production jobs; for example Bridge + Xorix Orbit + visible Xorix can all remain valid.

## 2. Story-placeholder suppression

Story-derived IDs such as `STORY-*`, `AUTO-*`, `TEMP-*` and `TMP-*` are proposal
identities, not preferred production authority.

When such a placeholder semantically overlaps a stronger resolved canonical XPD/CAP
match, the placeholder is suppressed from the human review set. The original Story
authority is not deleted or rewritten; only the redundant Shot requirement proposal is
removed.

If no stronger canonical match exists, the placeholder remains visible so the human can
see that canonical production authority is still incomplete.

## 3. Production-role classification

All deterministic and AI-derived proposals are normalized to governed production roles:

- **Dialogue Speaker**
- **Supporting Character**
- **Location**
- **Environment Context**
- **Visible Planet**
- **Planetary Context**
- **Vehicle/Ship**
- **Prop/Technology**
- **Wardrobe/Uniform**
- **Effect**
- **Audio**
- **Other Production Asset**

For Character assets, VSCS uses governed dialogue plus the Shot Required Action to
distinguish the speaking character from supporting characters. Speaker detection is
conservative and based on explicit character aliases near supported speech/report/order
verbs. Characters that are present but not established as the speaker remain Supporting
Character.

For Planet assets, explicit occurrence in Shot authority produces Visible Planet;
Scene-only inheritance produces Planetary Context.

## Governance

Inference remains proposal-first. The Asset Resolver still requires explicit human
confirmation before materializing suggestions. Accepted suggestions become Draft
ShotAssetBindings only and must pass normal Asset/CAP/reference readiness checks before
being marked Ready.

This refinement does not alter Camera, Lighting or Reference ownership.

## Acceptance

Acceptance requires:

- resolved canonical assets outrank semantically overlapping Story placeholders;
- placeholder suppression never deletes Story or XPD history;
- distinct Location, Environment Context and Visible Planet requirements can coexist;
- redundant same-category environment/location concepts are collapsed;
- dialogue speaker and supporting character roles are distinguishable;
- Ship/Vehicle, Prop/Technology and other category roles are explicit;
- AI suggestions pass through the same role normalization and deduplication path;
- all materialized bindings remain Draft until human approval.

Phase 20.18.2 remains open until automated validation, UI acceptance, downstream planning,
live provider execution, GeneratedMedia provenance and explicit owner acceptance pass.
