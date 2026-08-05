# Phase 17.5.6 — Integration and Foundation Tests

## Objective

Certify Phase 17.5 as one coherent Asset Manager integration boundary rather than as isolated services.

The certified production flow is:

```text
Project
→ Asset Manager
→ CAP
→ Approved primary canonical reference
→ Resolution-aware asset browser
→ Prompt Graph asset enrichment
→ Dependency index
→ CAP/reference change propagation
→ Selective incremental compilation invalidation
```

## Certified capabilities

### Authoritative asset resolution

The phase verifies that approved project assets resolve through stable application contracts without exposing repository models to downstream production services.

### CAP and reference readiness

A production-ready asset must provide:

- an approved asset record;
- an approved CAP;
- the complete canonical description;
- visual identity and production notes;
- at least one approved canonical reference;
- an approved primary canonical reference.

### Asset browser selection

The resolution-aware browser exposes deterministic asset ordering and production-readiness metadata, including CAP version, canonical status, primary-reference identity, and approved-reference count.

### Prompt Graph enrichment

Selected assets contribute mandatory Prompt Graph nodes containing the authoritative CAP text. The certification explicitly protects detailed production facts such as dimensions, engine layout, visual effects, colours, and restrictions.

### Dependency indexing

Each enriched shot records the checksums of its asset, CAP, and selected canonical references. A reverse index identifies exactly which shots use a changed asset.

### Change propagation

When canonical data changes, only affected Prompt Graph sources are refreshed. Stable source IDs replace existing asset nodes rather than creating duplicates.

### Selective invalidation

Compiled items belonging to changed shots are marked invalid. Compiled items for unrelated shots remain reusable.

## Certification test

The primary end-to-end test is:

```text
tests/integration/test_asset_manager_integration_foundation.py
```

It creates a real test project with two production-ready assets, approved CAPs, approved primary references, two enriched shots, and two incremental compilation records. It then updates one CAP and verifies that:

- only the shot using that asset is reported as affected;
- only that Prompt Graph source is refreshed;
- the revised canonical text reaches the resolver;
- only the corresponding compiled item is invalidated;
- the unrelated shot remains reusable.

## Regression coverage

The final Phase 17.5 suite also retains coverage for:

- asset-resolution contracts;
- browser filtering and selection;
- CAP and canonical-reference resolution;
- Prompt Graph enrichment;
- dependency propagation;
- incremental compilation;
- application service registration;
- ACPP asset browsing and binding.

## Manual UI test plan

### Preconditions

Open a project containing:

- one approved asset with an approved CAP and approved primary reference;
- one incomplete asset without a primary reference;
- at least one saved shot and ACPP package.

### Test 1 — Production asset browser

1. Open the Story workspace.
2. Select a shot and open the ACPP Editor.
3. Open the Assets tab.
4. Click **Browse Assets…**.

Pass criteria:

- the browser opens without error;
- asset, CAP, canonical status, primary reference, and reference count are visible;
- search and category filters work;
- the Production-ready filter hides incomplete assets.

### Test 2 — Asset binding persistence

1. Select a production-ready asset.
2. Add it to the ACPP package.
3. Save and close the editor.
4. Reopen the same ACPP package.

Pass criteria:

- the stable Asset ID remains bound;
- its role remains correct;
- no duplicate binding is introduced;
- existing remove and save behaviour still works.

### Test 3 — Incomplete asset feedback

1. Reopen the production asset browser.
2. Select the incomplete asset with the Production-ready filter disabled.

Pass criteria:

- readiness is shown as Partial or Unresolved;
- missing CAP/reference information is explained in the detail area;
- enabling Production-ready removes the asset from the results.

## Deliberate exclusions

Phase 17.5 does not yet provide:

- automatic propagation triggered directly by Asset Manager edit events;
- persistence of the dependency index across application restarts;
- asset editing UI improvements;
- CAP-window contextual help or guided workflows;
- a complete trailer-production workflow dashboard.

These items belong to the agreed Phase 17.6 Production Workflow and Functional Consolidation review.

## Readiness decision

Phase 17.5 is complete when:

1. Ruff passes for the Asset Manager integration packages and certification test.
2. The full Phase 17.5 automated suite passes.
3. The manual UI checks above pass.

After certification, the technical boundary from Asset Manager through Prompt Graph and incremental invalidation is considered stable. Development should then move to Phase 17.6 for workflow consolidation, functional review, editing gaps, contextual help, and the end-to-end trailer production path.
