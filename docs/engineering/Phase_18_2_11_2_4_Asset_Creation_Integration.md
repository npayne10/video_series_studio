# Phase 18.2.11.2.4 — Asset Creation Integration

## Purpose

Integrate interactive Asset creation with the Canonical Production Contract so a newly authored production asset begins with one authoritative ChatGPT MASTER reference rather than a generic project-relative attachment.

## Governing workflow

```text
New Asset
    ↓
Asset identity + category + metadata
    ↓
Select approved ChatGPT Master Canonical Reference
    ↓
Explicit MASTER confirmation
    ↓
Create Asset
    ↓
Create Draft CAP
    ↓
Create structured Primary image reference
    ↓
Register MASTER / CHATGPT_MASTER
    ↓
Approve and Lock MASTER
```

The user does not manually recreate the same MASTER inside Canonical Profiles after creating the asset.

## UI contract

The former **Project-relative file** field in the New Asset dialog is presented as **Master Canonical Reference**. The file picker accepts PNG, JPG/JPEG and WebP images inside the active project. The user must explicitly confirm that the selected file is the approved ChatGPT Master Canonical Reference.

The Asset list's file column is relabelled `MASTER` for newly created canonical assets.

## Seeded CAP

Interactive creation automatically creates a Draft CAP using:

- Asset ID as the CAP linkage.
- Asset name as CAP title.
- Asset description as initial canonical description.
- Asset name as a safe initial description when the description is blank.
- CAP version `1.0`.

Later CAP phases refine canonical facts, functional identity, constraints and production guidance.

## MASTER registration

The selected image is registered in the existing structured CanonicalReference repository as:

- Type: Image
- Legacy role: Primary (migration compatibility)
- Production family: MASTER
- Production view: MASTER
- Origin: CHATGPT_MASTER
- Parent: none
- Production lifecycle: Candidate → Approved → Locked

The production reference metadata is persisted through the Phase 18.2.11.2.3 Reference Library.

## Compatibility boundary

`AssetService.create()` remains a low-level registry operation. XPD import/synchronization and migrations may continue registering assets that do not yet have MASTER references. Interactive `Assets → Add Asset` uses `CanonicalAssetCreationService` and therefore enforces the new canonical workflow.

This distinction prevents Phase 18.2.11.2.4 from breaking existing XPD imports before a dedicated legacy migration phase is implemented.

## Failure behavior

Canonical creation coordinates Asset, CAP, reference and production-library creation. If a downstream creation step fails, the service performs best-effort rollback of newly created records so the UI does not intentionally leave a half-created canonical asset.

## Explicitly deferred

This phase does not implement:

- category-specific required reference templates;
- Front/Rear/Port/Starboard/Top/etc. generation;
- generator plugin selection;
- derived-reference generation;
- readiness calculation;
- CAP editor/reference-gallery redesign;
- migration of existing XPD/legacy assets that lack registered MASTER metadata.

Those remain assigned to later Phase 18.2.11.2 work packages.

## Acceptance criteria

1. New Asset UI calls the selected file `Master Canonical Reference`.
2. Only supported image formats inside the project may be used as a new MASTER.
3. Explicit confirmation of ChatGPT MASTER authority is required.
4. One successful UI creation creates the Asset, Draft CAP, structured reference and production-library MASTER.
5. The MASTER is approved and locked automatically after explicit user confirmation.
6. MASTER origin is recorded as `CHATGPT_MASTER`; it has no parent.
7. The Asset stores the project-relative MASTER path for migration compatibility.
8. Existing low-level Asset/XPD creation remains compatible.
9. Failure does not intentionally leave a partially created canonical asset.
10. No derived references are generated in this phase.
