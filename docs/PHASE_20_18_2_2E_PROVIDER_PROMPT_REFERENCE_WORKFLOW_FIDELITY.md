# Phase 20.18.2.2e — Provider Prompt, Reference & Workflow Fidelity

## Status

Implementation committed for local automated and functional acceptance. The phase remains open until the owner completes the VSCS Standard Development Prompt validation and explicitly accepts it.

## Failure evidence

The first live SHT-001 production attempt was technically valid (1280×720, 24 fps, 144 frames / 6 seconds) but failed semantic production intent. Investigation established four execution-boundary defects:

1. Generic canonical location name matching allowed the generic name Bridge to resolve the Mauritania command deck while the governed Shot required the Iron Horizon bridge.
2. The complete Universal Production Description JSON text was being sent directly to the creative LTX text encoder.
3. Three static Ingredients IC-LoRA references were injected at generated frame zero instead of attention-only reference positions.
4. Provider capacity could defer a visually required asset such as Xorix without proving equivalent visual coverage in the selected direct references.

The provider submission payload also lacked a durable exact pre-submit audit artifact.

## Architecture

The approved authority hierarchy is unchanged:

Governed Shot / reviewed production authority
→ Universal Production Description (complete audit authority)
→ deterministic structured provider-prompt compiler
→ governed ReferencePlan
→ provider visual-fidelity guard
→ LTX provider contract
→ ComfyUI API workflow
→ exact pre-submit payload audit
→ live provider execution
→ GeneratedMedia

The UPD remains provider-neutral and complete. Provider prompt compilation is derived only from approved structured authority and does not become a second authority system.

## Provider prompt contract

ProductionProviderPromptCompiler translates only provider-relevant approved fields:

- production objective and required action;
- visual Action & Performance narrative;
- opening/closing continuity state;
- Shot constraints;
- camera language;
- lighting language;
- environment language;
- declared style/tone.

Hashes, file paths, persistence metadata, raw JSON, reference checksums, binding IDs and other governance implementation details are not sent to the creative text encoder.

Negative instructions are separated from positive cinematic intent. The compiler never silently truncates authority: over-limit prompts fail compilation and require refinement.

## Canonical location disambiguation

Generic location names such as Bridge, Engineering, Hangar, Quarters, and similar facility names no longer qualify solely because the generic word appears in governed Shot text.

A generic location must also match contextual scope from canonical subcategory/description metadata. This prevents Bridge on the Iron Horizon from silently selecting a Mauritania bridge asset.

Ambiguous generic locations fail to auto-resolve instead of inventing or substituting canon.

## LTX reference semantics

Static governed IC-LoRA reference guides use frame_idx = -1.

This keeps identity/environment images outside the generated temporal frame range while retaining attention conditioning.

The previous-approved-final-frame continuity path remains separate through the governed temporal continuity node. Static references must not masquerade as generated frame-zero continuity anchors.

Deployment assurance rejects any governed static guide that is not configured for attention-only frame_idx = -1.

## Provider visual-fidelity guard

Characters and primary location/set assets remain shot-critical. Semantic roles containing visible, required, critical, hero, foreground, interaction/usage markers, or dialogue-speaker authority are also shot-critical.

Before an LTX package can execute, selected direct references plus explicit contains_subjects, contains_props, and contains_environments coverage must cover every shot-critical visual asset.

If capacity would drop a shot-critical visual authority, compilation fails with PROVIDER_VISUAL_AUTHORITY_DROPPED.

The correct repair is a governed provider-ready reference/composite coverage decision or corrected Shot authority. Demoting a visibly required asset merely to fit provider capacity is prohibited.

The three-reference LTX capacity is intentionally unchanged because a higher limit has not yet been live-validated.

## Exact payload audit

Every production-package ComfyUI compilation on the LTX v7.2.1 execution path persists an exact pre-submit audit under:

.vscs/provider_executions/payload_audit/

The audit records:

- exact ComfyUI API payload;
- API payload SHA-256;
- workflow SHA-256;
- production package path/fingerprint/authority fingerprint;
- final provider positive and negative prompts;
- direct provider reference contract;
- IC-LoRA guide node IDs, bindings and frame indices;
- render geometry, frames, FPS and seed.

Audit persistence is fail-closed: a configured production execution cannot proceed if the payload audit cannot be written.

## SHT-001 consequence

The existing SHT-001 compiled package predates the structured provider-prompt contract and must be recompiled before execution.

Current governed planning must also be refreshed so CAP-LOC-008 (Mauritania command deck) is not retained as the Iron Horizon bridge.

Because SHT-001 explicitly requires Xorix to be visible, Xorix is required visual authority. If James + Sandra + correct Iron Horizon bridge consume all three LTX direct slots, compilation must remain blocked until one governed provider-ready reference proves combined visual coverage (for example the correct Iron Horizon bridge composition including Xorix in the forward display) or provider capacity is separately live-validated and deliberately increased.

## Acceptance

Automated:
- Ruff check/fix and format clean.
- MyPy clean.
- focused Phase 20.18.2.2e tests pass.
- related Phase 20.18.2 provider/reference tests pass.
- full pytest regression passes at >=70% coverage.

Functional/UI:
1. Refresh SHT-001 Asset authority from the current governed Shot.
2. Confirm Mauritania CAP-LOC-008 is no longer silently selected for the Iron Horizon bridge.
3. Apply/review current reference-priority suggestions; Visible Planet must be REQUIRED.
4. Rebuild downstream stale Production Planning stages and READY UPD.
5. Recompile/reschedule the ProductionTask as required by current authority.
6. Compile the Production Package.
7. Inspect the package: provider prompt is concise cinematic prose, not Universal Description JSON.
8. Confirm static direct references declare attention-only frame_idx = -1.
9. Confirm Xorix is either covered by selected provider reference coverage or compilation is explicitly blocked; silent dropping is a FAIL.
10. Do not start a live production attempt yet.
11. When live execution is later explicitly authorized, verify the pre-submit payload audit exists before accepting the run.

Phase closure still requires explicit owner acceptance.
