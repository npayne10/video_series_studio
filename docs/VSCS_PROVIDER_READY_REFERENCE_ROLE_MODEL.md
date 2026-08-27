# VSCS Provider-Ready Reference Role Model

**Status:** Governing project standard  
**Introduced:** Phase 20.18.1 — Provider-Ready Reference Role Resolution & Multi-Reference Binding  
**Applies to:** All provider-bound visual generation workflows

## 1. Purpose

VSCS treats visual references as governed production inputs. References are not loose images and canonical approval alone does not make an image safe for provider execution.

This model defines:

1. what a visual reference is;
2. what production role it fulfils;
3. whether it is suitable for the requested output profile;
4. how several references coexist in one shot plan;
5. how provider adapters map governed references into provider-specific workflow inputs.

The model is provider-neutral in VSCS core. LTX, Wan, ComfyUI, WANGP, and future provider constraints remain at the provider/infrastructure edge.

## 2. Governing Principles

### 2.1 Canonical authority and provider readiness are separate

A canonical master reference defines production truth. It may still be unsuitable for direct video generation because of framing, aspect ratio, dimensions, missing visible asset features, or provider-specific conditioning requirements.

VSCS must therefore distinguish:

- **Canonical Master Reference** — highest-authority identity/design source;
- **Provider-Ready Reference Derivative** — governed derivative prepared for a specific generation use;
- **Shot-Resolved Reference Binding** — production-time assignment of a reference to a governed role.

### 2.2 Reference completeness rule

If the requested shot may reveal a canonical feature, that feature must be visible in at least one required governed reference.

VSCS must not silently rely on a provider to invent unseen:

- facial or body identity features;
- hair, wardrobe, insignia, footwear, or accessories;
- spacecraft hull sections, engines, markings, or geometry;
- prop or furniture geometry;
- room/set layout;
- other design-critical canonical content.

If a full asset may become visible during the shot, the provider-ready reference must show the full required asset.

### 2.3 Frame-anchor exact-size rule

Frame-state references define the visual canvas of the requested shot and must match the target video dimensions exactly.

This applies to:

- `scene_composition_anchor`;
- `start_frame_reference`;
- `end_frame_reference`;
- `continuity_anchor` when used as a frame-state input.

For a **1280 × 720** production profile, those references must therefore be **1280 × 720** unless a future explicit provider profile changes the governed rule before resolution.

Supporting identity/environment references may use another provider-approved resolution when they retain compatible aspect ratio, complete required content, and profile approval.

### 2.4 Multi-reference rule

A complex shot should normally carry several independent sources of visual authority rather than forcing one image to define every production concern.

For a scene containing James, Cheryl and Ros in a governed room, the reference plan should normally include at least:

1. one `scene_composition_anchor` showing the intended frame-zero composition;
2. one `primary_identity` reference for the principal character;
3. one `secondary_identity` reference for each additional important character;
4. one `environment_reference` for the room/set;
5. `prop_reference` and/or `furniture_reference` records when those elements are design-critical;
6. continuity/start/end/motion references when required by the shot.

The complete governed plan may contain more references than a selected provider can consume directly. VSCS owns the full authority plan; the provider adapter owns safe binding and declared fallback behavior.

## 3. Formal Reference Roles

### Composition and continuity

- `scene_composition_anchor`
- `continuity_anchor`
- `start_frame_reference`
- `end_frame_reference`
- `motion_reference`

### Subject identity

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

A `style_reference` is always subordinate to canonical identity and design authority.

## 4. Reference Classes

Every shot reference declares its governed origin:

- `canonical_master`
- `provider_ready_derivative`
- `shot_composite`
- `continuity_capture`
- `provider_specific_helper`

Provider-ready derivatives remain traceable to canonical masters and never replace canonical authority.

## 5. Priority

Each role request has one execution priority:

- `required` — missing or unsuitable reference blocks safe execution;
- `preferred` — execution may continue with a continuity/quality warning;
- `optional` — useful when supported but non-blocking.

The **shot-level role request priority is authoritative**. Catalog defaults must not weaken an explicitly required production role.

## 6. Required Suitability Metadata

Provider-ready and shot-resolved references should carry:

- `reference_id`
- `asset_id` where applicable
- `role`
- `reference_class`
- `priority`
- `subject_type`
- `source_path`
- `canonical_source_id`
- `width`
- `height`
- aspect ratio derived from dimensions
- `framing_type`
- `coverage`
- `required_features_visible`
- `identity_visible`
- `full_required_asset_visible`
- `provider_ready`
- approved `provider_profiles`
- `reference_fingerprint`
- physical `file_checksum`
- contained subjects/props/environments when useful

## 7. Provider-Ready Validation Rules

Before provider submission VSCS must validate at least:

### Structural

- every requested reference role resolves;
- every explicitly preferred reference actually fulfils the requested role;
- required references are present;
- integrity/provenance data is available where required.

### Framing and dimensions

- aspect ratio is compatible with the target profile;
- frame anchors match target pixel dimensions exactly;
- dimensions are known and usable;
- framing exposes the content the shot may require.

### Completeness

- required features are visible;
- identity-critical detail is visible for identity roles;
- full required asset coverage is visible when the shot may reveal the full asset;
- no required authority depends on uncontrolled provider extrapolation.

### Profile governance

- provider-ready approval is present;
- profile restrictions are satisfied;
- supporting references use provider-approved dimensions/aspect ratios.

## 8. Provider Binding Model

VSCS core resolves a complete `ReferencePlan`. Provider adapters declare capabilities such as:

- supported reference roles;
- workflow profile;
- maximum reference count.

The preferred binding order is:

1. direct multi-reference binding;
2. governed `scene_composition_anchor` fallback;
3. provider-specific helper/composite generated from canonical authority;
4. block execution when required authority cannot be represented safely.

Required references must never be silently dropped.

## 9. Production Package Concept

A production package may include:

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

## 10. Multi-Character Dialogue Example

For James, Cheryl and Ros talking in a governed room with continuity-critical furniture:

- `scene_composition_anchor` — exact target-size frame-zero composition containing all required in-frame elements;
- `primary_identity` — James;
- `secondary_identity` — Cheryl;
- `secondary_identity` — Ros;
- `environment_reference` — room/set;
- `furniture_reference` — furniture when its design/location matters;
- optional `continuity_anchor`, start/end frame, prop and motion references.

The composition anchor answers **where everything is**. Supporting references answer **what each governed asset must remain**.

## 11. Naming Guidance

Examples:

### Characters

- `CAP-CHR-001-Master-V1.png`
- `CAP-CHR-001-Video16x9-FullBody-V1.png`
- `CAP-CHR-001-Video16x9-Medium-V1.png`
- `CAP-CHR-001-CloseIdentity-V1.png`

### Ships

- `CAP-SHP-002-Master-V1.png`
- `CAP-SHP-002-Video16x9-ExteriorWide-V1.png`

### Locations

- `CAP-LOC-014-Master-V1.png`
- `CAP-LOC-014-Video16x9-Establishing-V1.png`

## 12. Architectural Rule

> **Canonical references define what an asset is. Provider-ready references define how that canonical asset is safely presented to a generation provider. A provider must never be asked to invent unseen canonical content that the production expects it to preserve.**

This complements the project principle:

> **PROVIDERS PRODUCE OUTPUTS. VSCS OWNS GENERATED MEDIA.**

VSCS also owns governance of the inputs supplied to providers.

## 13. Implementation Ownership

The provider-neutral reference-role model belongs in the VSCS application/domain production-package boundary.

Provider-specific handling belongs at the infrastructure/provider edge, including:

- accepted reference slots;
- reference-count limits;
- start/end-frame implementation;
- identity/reference adapters;
- provider-specific composites/helpers;
- provider workflow field mapping.

No LTX-, Wan-, ComfyUI-, WANGP-, or future-provider-specific fields should be embedded into the core reference plan.

## 14. Required Future Behavior

All future VSCS production execution should resolve and validate a governed reference plan before provider submission. A provider-bound package must not be considered ready merely because canonical references exist.

Execution readiness requires that the references are **role-correct, profile-suitable, dimension-safe, complete for required visible content, and representable by the selected provider workflow**.
