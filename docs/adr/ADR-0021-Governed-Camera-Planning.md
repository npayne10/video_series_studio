# ADR-0021 — Governed Camera Planning

**Status:** Accepted for Phase 19.3.5 implementation  
**Date:** 2026-08-11

## Context

Phase 19.3 establishes one authoritative production-planning chain. By Phase 19.3.4 VSCS has governed Story → Episode → Scene → Shot planning and governed Shot asset resolution. Camera decisions were still represented only in legacy SSIE/Shot structures where camera, lighting, environment and asset concerns were mixed together.

The Phase 19.3 planning principles require every stored value to contribute directly to producing the series, support automation and continuity, remain easy to use, and stay physically grounded unless story canon explicitly requires otherwise.

## Decision

VSCS will own exactly one authoritative, renderer-neutral `CameraPlan` per governed Shot. Camera Planning is a specialist layer beneath a current Ready Shot and its governed asset context.

The Camera Plan owns only camera-specific production decisions:

- shot size / framing;
- camera angle;
- camera movement;
- lens family and full-frame-equivalent focal length;
- physical camera height;
- screen direction;
- composition intent;
- focus strategy;
- movement/physical notes;
- camera continuity notes;
- camera-specific constraints;
- optional binding to an existing governed Camera Profile asset.

Camera Planning does **not** own lighting, environment configuration, general asset authoring, prompt text, renderer settings or render execution.

Draft Camera Plans may be created once the governed Shot is current and Ready so creative iteration can continue. A Camera Plan may become Ready only when:

1. the parent Shot remains current and production-ready;
2. all declared Shot asset requirements are current and Ready;
3. the Camera Plan still matches the Shot contract fingerprint;
4. the Camera Plan still matches the governed asset-context fingerprint; and
5. any selected Camera Profile remains an approved Camera asset with an approved CAP.

Canonical image references are not required for Camera Profile assets because camera profiles are production-control knowledge rather than visual identity assets.

## Automation

The service provides deterministic suggested Drafts derived from governed Shot intent. Suggestions use conservative rules for establishing, dialogue, reaction and moving-action Shots. Suggestions are editable and never bypass governance.

## Continuity and physical grounding

Screen direction is structured rather than embedded only in prose. Focal length is stored as a full-frame-equivalent physical value, camera height is stored in metres, and movement guidance explicitly avoids impossible acceleration or unmotivated camera motion.

Shot and asset-context fingerprints make downstream camera authority stale when upstream production truth changes.

## Persistence

Camera Plans are persisted atomically in:

`planning/camera_plans.json`

Schema version `1.0` is independent from legacy SSIE camera data. Legacy camera information is preserved but is not authoritative for Phase 19.3 planning.

## Consequences

- Phase 19.3.6 Lighting Planner can consume a stable Ready Camera Plan without inheriting camera ownership.
- Phase 19.3.7 Environment Planner remains responsible for environmental implementation.
- Production Review can detect stale camera decisions deterministically.
- Existing reusable XPD Camera Profiles can be used without duplicating them into Camera Plans.
- Camera planning remains renderer-neutral and suitable for later automated prompt compilation.
