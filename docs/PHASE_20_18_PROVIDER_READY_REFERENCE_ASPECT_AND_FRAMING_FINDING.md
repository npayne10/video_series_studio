# Phase 20.18 Finding — Provider-Ready Reference Aspect Ratio and Framing

**Project:** Video Series Creation Studio (VSCS)  
**Phase:** 20.18 — LTX 2.3 Provider Capability Validation  
**Status:** Accepted validation finding and project rule  
**Date:** 2026-08-26

## 1. Finding

During LTX 2.3 image-to-video validation, repeated character-continuity failures were initially observed for Commander James Spence. The generated video exhibited significant identity drift, including changes to facial features, hair, wardrobe, and in some tests even apparent sex.

The ComfyUI installation was rebuilt in a clean parallel environment and the same behavior was reproduced, reducing the likelihood that the original ComfyUI installation was the primary cause.

The root cause was then identified in the canonical reference framing used for the video-generation task:

- target video generation size: **1280 × 720 (16:9 landscape)**
- canonical character reference used: **1024 × 1536 (2:3 portrait)**

The portrait reference required aggressive resizing/cropping/recomposition to fit the 16:9 video frame. The resulting conditioning did not present the character to the video model in a framing appropriate to the target shot. In practice, the model received a poorly aligned character reference and did not retain the intended identity reliably.

When a different reference image with framing more appropriate to the target 16:9 video composition was used, LTX 2.3 produced a substantially improved result with strong subject and scene continuity.

## 2. Conclusion

A canonical image may be correct as an asset identity reference while still being unsuitable as a direct video-generation conditioning image.

**Canonical authority and provider-ready generation suitability are separate concerns.**

The observed LTX 2.3 character-continuity failures must therefore not be interpreted solely as evidence that LTX 2.3 cannot preserve governed character identity. Reference aspect ratio, crop, framing, and composition materially affect provider behavior and must be validated before execution.

## 3. New VSCS Project Rule

### Provider-Ready Reference Rule

Before a visual reference is supplied to a video-generation provider, VSCS must verify that the selected reference is suitable for the requested generation profile.

A reference is not provider-ready merely because it is canonical or approved.

For each video-generation request, VSCS must validate or resolve an appropriate provider-ready derivative based on at least:

1. **Target aspect ratio**
2. **Target output dimensions**
3. **Subject framing**
4. **Required identity/detail visibility**
5. **Shot composition**
6. **Provider-specific conditioning requirements**

Where the canonical master does not satisfy those requirements, VSCS must use or create a provider-ready derivative rather than sending the master reference directly to the provider.

## 4. Character Reference Guidance

For identity-sensitive image-to-video generation, a provider-ready character reference should normally:

- closely match the target video aspect ratio;
- be framed for the intended shot rather than for general asset documentation;
- keep the face clearly visible at useful resolution;
- retain visible hair/head shape and other identity-critical features;
- retain enough wardrobe/upper-body detail for continuity when required;
- avoid destructive cropping when mapped to the target video frame;
- avoid excessive unused space that reduces effective identity resolution;
- preserve the composition needed by the requested shot.

For a standard **1280 × 720 (16:9)** production profile, the preferred reference derivative should also be prepared as a 16:9 landscape image or a closely compatible framing unless the provider explicitly supports another reference strategy.

## 5. Canonical Asset Model Implication

VSCS should distinguish between:

### Canonical Master Reference

The highest-authority representation of an asset. It defines identity, design, appearance, and production truth. Its dimensions and composition may be optimized for documentation or asset governance rather than a specific generation task.

### Provider-Ready Reference Derivative

A governed derivative of the canonical master prepared for a specific production use, such as:

- video 16:9 identity reference;
- close identity reference;
- upper-body dialogue reference;
- full-body action reference;
- environment establishing reference;
- provider-specific conditioning reference.

Provider-ready derivatives remain subordinate to the canonical master and must retain traceable provenance back to it.

## 6. Validation and Execution Requirement

Provider execution should eventually reject or flag a reference when its framing/aspect relationship to the requested generation profile is likely to cause destructive transformation.

At minimum, future VSCS implementation should be capable of detecting:

- significant aspect-ratio mismatch;
- severe expected crop loss;
- insufficient subject occupancy or identity detail;
- reference dimensions below provider/profile requirements;
- missing provider-ready derivative for an identity-sensitive shot.

The system should prefer an approved provider-ready derivative when available and should preserve the canonical master unchanged.

## 7. Architectural Principle

> **Canonical references define what an asset is. Provider-ready references define how that canonical asset is safely presented to a generation provider.**

This rule extends the existing VSCS principle:

> **PROVIDERS PRODUCE OUTPUTS. VSCS OWNS GENERATED MEDIA.**

VSCS must also own the governance of the inputs supplied to those providers.

## 8. Phase 20.18 Impact

This finding materially affects interpretation of the LTX 2.3 capability-validation evidence.

Earlier character-continuity failures performed with the mismatched portrait reference remain valid evidence of the behavior of that specific input configuration, but they should not be treated as definitive evidence that LTX 2.3 inherently fails character continuity.

Future LTX 2.3 and Wan 2.2 comparison tests involving canonical characters should use equivalent provider-ready references so that provider capability is assessed independently of avoidable reference-preparation defects.

## 9. Recommended Follow-Up

A future implementation increment should introduce **Provider-Ready Reference Framing and Aspect Validation** into the production-package/reference-resolution path. This should occur before provider submission and should remain provider-neutral in the VSCS core, with provider-specific constraints supplied at the provider/infrastructure edge.
