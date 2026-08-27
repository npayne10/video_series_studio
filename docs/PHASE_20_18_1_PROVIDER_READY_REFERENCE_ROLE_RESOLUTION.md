# Phase 20.18.1 — Provider-Ready Reference Role Resolution & Multi-Reference Binding

## Status

Implementation phase. This document defines the governed reference-role model that VSCS must apply to provider-bound visual references going forward.

## 1. Purpose

VSCS must treat visual references as governed production inputs, not loose images. A reference may define canonical identity, frame-zero composition, subject continuity, environment continuity, prop continuity, start/end state, or provider-specific conditioning support.

The model therefore separates:

1. what a reference is;
2. what production role it fulfils;
3. whether it is provider-ready for the requested output profile;
4. how it is mapped into a provider workflow.

## 2. Core Rules

### 2.1 Canonical authority is not provider readiness

A canonical master may define production truth while still being unsuitable for direct generation. Provider-ready suitability must be resolved independently.

### 2.2 Reference completeness rule

If a provider is expected to preserve or reproduce a visual feature, the feature must be visible in at least one required governed reference. VSCS must not rely on provider extrapolation for unseen identity-critical or design-critical anatomy, wardrobe, vehicle geometry, prop geometry, room layout, furniture, or other canonical content.

### 2.3 Target framing rule

Provider-ready references should closely match the target output aspect ratio and, where practical, target pixel dimensions. For a 1280 × 720 production profile, a provider-ready derivative should normally be prepared as 1280 × 720 or an equivalent 16:9 composition unless the provider profile explicitly requires another form.

### 2.4 Multi-subject rule

For a complex shot, the preferred governed plan is:

- one `scene_composition_anchor` showing the intended frame-zero shot;
- one `primary_identity` reference for the principal subject;
- one `secondary_identity` reference for each additional important subject;
- one `environment_reference` for the governed set/location;
- optional `prop_reference` or `furniture_reference` records for design-critical set elements;
- optional continuity/start/end/motion references as required by the shot or provider.

### 2.5 Provider mapping remains provider-edge logic

VSCS core governs roles and suitability. Provider-specific limits and workflow input bindings remain at the provider/infrastructure edge. If a provider cannot consume all governed references directly, VSCS must apply a declared fallback rather than silently discarding required reference authority.

## 3. Reference Hierarchy

### Canonical Master Reference

Highest-authority representation of an asset. It defines identity/design truth and is preserved unchanged.

### Provider-Ready Reference Derivative

A governed derivative prepared for a production use, such as:

- video 16:9 identity reference;
- close identity reference;
- upper-body dialogue reference;
- full-body action reference;
- ship exterior full-asset reference;
- environment establishing reference;
- provider-specific conditioning derivative.

Every derivative must retain traceable provenance to its canonical master.

### Shot-Resolved Reference Binding

A production-time binding that declares what a specific reference is doing in the current shot.

## 4. Formal Roles

### Composition and continuity

- `scene_composition_anchor`
- `continuity_anchor`
- `start_frame_reference`
- `end_frame_reference`
- `motion_reference`

### Identity

- `primary_identity`
- `secondary_identity`
- `group_identity`

### Environment

- `environment_reference`
- `background_identity`

### Objects and set dressing

- `prop_reference`
- `furniture_reference`

### Styling

- `style_reference`

A style reference is always subordinate to identity and canonical design authority.

## 5. Reference Classes

- `canonical_master`
- `provider_ready_derivative`
- `shot_composite`
- `continuity_capture`
- `provider_specific_helper`

## 6. Priority

- `required` — missing/unsuitable reference blocks execution;
- `preferred` — execution may continue but VSCS emits a quality/continuity warning;
- `optional` — useful when supported but does not block execution.

## 7. Suitability Metadata

Provider-ready or shot-resolved references should carry at least:

- reference ID;
- asset ID where applicable;
- role;
- reference class;
- priority;
- subject type;
- source path;
- canonical source ID;
- width/height/aspect ratio;
- framing type;
- coverage type;
- whether identity-critical detail is visible;
- whether all required features are visible;
- whether the full required asset is visible;
- provider-ready approval state;
- approved provider profiles;
- reference fingerprint;
- physical file checksum.

## 8. Required Validation

Before provider submission, VSCS must validate:

### Structural

- every resolved reference has a governed role;
- every required requested role resolves;
- required files/references exist through the supplying catalog or package;
- integrity/provenance metadata is available where required.

### Suitability

- aspect ratio is compatible with the target;
- dimensions are known and usable;
- required features are visible;
- identity detail is visible for identity roles;
- full required asset coverage is present where the shot may reveal that asset;
- the reference is approved for the target profile when profile restrictions exist;
- destructive extrapolation risk is not accepted for required content.

### Provider binding

- mapped roles are supported by the selected provider/workflow profile;
- provider reference-count limits are respected;
- if direct mapping is impossible, an explicit governed fallback exists;
- required references must never be silently dropped.

## 9. Provider Fallback Policy

The preferred order is:

1. direct multi-reference binding;
2. governed scene-composition anchor fallback;
3. provider-specific helper/composite generated from canonical authority;
4. block execution if required authority cannot be represented safely.

## 10. Production Package Shape

A production package may carry a reference plan conceptually as:

```json
{
  "reference_plan": {
    "schema_version": "1.0",
    "target": {
      "width": 1280,
      "height": 720,
      "profile_id": "production-video-16x9",
      "provider_id": "ltx23-local"
    },
    "references": [
      {
        "reference_id": "REF-SHOT-001",
        "asset_id": "CAP-CHR-001",
        "role": "primary_identity",
        "reference_class": "provider_ready_derivative",
        "priority": "required",
        "subject_type": "character",
        "source_path": "assets/characters/CAP-CHR-001-Video16x9-FullBody-V1.png",
        "canonical_source_id": "CAP-CHR-001-Master-V1",
        "width": 1280,
        "height": 720,
        "provider_ready": true,
        "provider_profiles": ["production-video-16x9"],
        "coverage": {
          "framing_type": "full_body",
          "coverage": "full_body",
          "identity_visible": true,
          "required_features_visible": true,
          "full_required_asset_visible": true
        }
      }
    ]
  }
}
```

## 11. Example: James, Cheryl and Ros in a Room

A governed complex-dialogue shot should normally resolve at least:

1. `scene_composition_anchor` — 1280 × 720 frame-zero composition containing James, Cheryl, Ros, the room and relevant furniture;
2. `primary_identity` — provider-ready James reference;
3. `secondary_identity` — provider-ready Cheryl reference;
4. `secondary_identity` — provider-ready Ros reference;
5. `environment_reference` — governed room/set reference;
6. `furniture_reference` — when furniture is continuity/design critical.

This model intentionally allows more references than a provider may support directly. VSCS owns the complete governed plan; the provider adapter owns how that plan is safely bound to provider inputs.

## 12. Architectural Principle

> Canonical references define what an asset is. Provider-ready references define how that canonical asset is safely presented to a generation provider. A provider must never be asked to invent unseen canonical content that the production expects it to preserve.

This complements the existing project principle:

> PROVIDERS PRODUCE OUTPUTS. VSCS OWNS GENERATED MEDIA.

VSCS also owns governance of the inputs supplied to providers.

## 13. Phase 20.18.1 Implementation Boundary

This phase introduces provider-neutral domain/application structures for:

- governed reference roles/classes/priorities;
- provider-ready reference suitability validation;
- role-request resolution;
- multi-reference shot plans;
- provider capability declarations;
- provider mapping and explicit fallback diagnostics;
- serialization-ready structures suitable for production package integration.

It must not hard-code LTX, Wan, ComfyUI, WANGP, or any other provider into the VSCS core model.

## 14. Acceptance Intent

The implementation is acceptable when focused automated tests demonstrate that:

- exact-profile provider-ready references resolve successfully;
- required aspect mismatch blocks resolution;
- missing full-asset coverage produces extrapolation-risk failure;
- multiple required identity/environment roles can coexist in one plan;
- supported provider roles bind directly;
- unsupported required roles use an explicit composition fallback where available;
- unsupported required roles without a governed fallback block execution;
- provider reference-count limits are enforced;
- existing ACPP behavior remains backward compatible.
