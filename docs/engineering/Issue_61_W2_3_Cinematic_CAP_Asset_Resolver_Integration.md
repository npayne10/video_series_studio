# Issue #61 W2.3 — Cinematic CAP Readiness and Episode Planner Integration

## Decision and scope

On 2026-11-27 the operator confirmed cinematic-use acceptance of Rear, Left and Right for CAP-PRP-002. The cinematic readiness dialog showed **75% overall / 80% reference readiness**, and only **CAP approval** and **generation readiness** remained blocked. Viewpoint refinement is closed for cinematic use; this is **not** canonical geometry approval.

W2.3 exposes the already implemented separate cinematic CAP projection to the Episode Planner **Asset Resolver**, by explicit choice on an individual Shot asset binding. Existing bindings and every new binding default to **canonical (strict)** reference authority. Neither mode changes the authoritative CAP/Asset lifecycle, automatically marks a Shot binding Ready, or starts a GPU job.

## Operator sequence

1. In **Canonical Profiles**, finish human CAP review and explicitly approve the relevant CAP; in **Assets**, approve the matching Asset. These approvals are separate from cinematic QC. Complete the required structured knowledge and readiness gates; never approve a CAP solely to bypass a video-generation warning.
2. Open **Episode Planner → Asset Resolver**, select a visible physical asset binding and **Edit** it while Draft.
3. Where the intended production use is cinematic, check **Use human-accepted cinematic views for video (not canonical approval)**. The **Current resolution** line immediately evaluates cinematic CAP/reference readiness. Leave unchecked for strict canonical consumers.
4. **Save** the binding. The mode is recorded in `planning/asset_resolutions.json`, defaults to `false` for old files, and contributes to the binding's dependency fingerprint. It is not approval.
5. Once the Asset, CAP, and all *required* cinematic views are current and production-ready, select **Mark Ready**. If images, MASTER/Front authority, CAP/Asset state or binding mode change, the fingerprint/currentness gate fails closed; use **Return to Draft** before reviewing and reapproving.
6. Complete all other physical requirements, retaining reviewed nonvisual scopes; proceed **Camera Planner → Lighting/Environment → Planning Review → Production Packages**. Separately authorize any eventual GPU generation.

## Engineering boundaries

- `AssetResolutionRequest.cinematic_references` is opt-in. The resolver uses `project_cinematic()` and requires cinematic reference **and** CAP production readiness, including freshness, when cinematic mode is chosen. Strict callers retain their existing behavior.
- Each `ShotAssetBinding.cinematic_references` flag persists with the Shot binding and is used in resolution, fingerprinting, readiness and downstream `production_projection`. It does not imply canonical reference approval or exempt CAP/Asset approval.
- The Gallery's **Cinematic Readiness…** is an informational CAP assessment; its 80% reference score reflects unapproved *recommended* views, not an outstanding required viewpoint. Only an assessment state of Ready passes the requirement gate.
- Changing the source comparison images invalidates cinematic acceptance. The operator must re-review cross-view suitability; the Asset Resolver must not silently treat the stale record as approved.
- W2.3 does **not** automatically enable cinematic mode in all other canonical consumers or authorize video execution. Downstream packaging and video paths still require separately tested, explicit propagation of this authority before the first GPU trial.

## Windows acceptance

With CAP-PRP-002 still Draft, check cinematic mode in the Asset Binding editor: it must show CAP approval as a blocker, and **Mark Ready** must remain unavailable. After genuine CAP and Asset approvals and current cinematic readiness, save/mark a binding Ready, restart VSCS, verify the mode and persisted Ready state, then change a relevant reference image or authority *only in a disposable test project* and confirm the binding becomes stale. Verify an unchecked binding remains strict and no GPU job is submitted.
