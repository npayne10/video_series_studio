# ADR-0032 — Camera & Lighting Production Automation

## Status
Accepted for Phase 19.5.8 implementation.

## Decision
Phase 19.5.8 generates reviewable Camera and Lighting proposals from current Shot, Action/Performance and Environment proposals. It reuses the governed Camera and Lighting enums and field semantics, but persists only `AutomationProposal` records.

Camera proposals may describe renderer-neutral framing, movement, lens family, focal length, composition and focus. Lighting proposals may describe motivated lighting intent, direction, quality, color temperature, fill, exposure, shadow/readability and separation. Lighting retains explicit lineage to the paired Camera proposal.

Automation may not select canonical Camera or Lighting profile asset IDs, create governed Camera or Lighting Plans, mark them Ready, approve them, or create renderer/provider settings. Human review remains mandatory through the shared Phase 19.5 Proposal Review surface.
