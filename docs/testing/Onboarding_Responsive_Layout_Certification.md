# VSCS Onboarding Responsive Layout Certification

## Phase

16.2a.8.5.4.5.2.1 — Responsive Layout Certification

## Objective

Certify that the Scene Editor onboarding experience remains usable, stable and visually coherent across supported window sizes and resize transitions without reducing the central editing workspace to an impractical area.

## Automated certification matrix

| Area | Requirement | Expected result |
|---|---|---|
| Compact laptop layout | The editor remains scrollable at 800 × 640 and Save/Cancel remain visible. | PASS |
| Standard desktop layout | The central editor receives more vertical space than Workflow and Support combined. | PASS |
| Large desktop layout | Extra space expands the editor while support panels remain collapsed. | PASS |
| Live resize | Repeated resizing preserves all splitter structures and action controls. | PASS |
| Welcome overlay fit | The welcome overlay covers the current dialog and keeps its card inside the window. | PASS |
| Tour overlay fit | The guided tour overlay and card remain inside the current dialog. | PASS |
| Responsive persistence | Collapse states and splitter preferences restore at a different window size. | PASS |

## Supported certification sizes

- Compact laptop: 800 × 640
- Standard desktop: 1100 × 760
- Intermediate resize: 1024 × 700
- Large desktop: 1400 × 900
- Extended desktop: 1600 × 1000

## Pass criteria

Responsive Layout Certification passes only when:

1. Ruff reports no violations in the responsive certification files.
2. All responsive certification tests pass.
3. Existing adaptive-workspace tests still pass.
4. The central editor remains visible and receives non-zero splitter space at every tested size.
5. Save and Cancel remain visible at compact size.
6. The form remains vertically scrollable when all content cannot fit.
7. Welcome and tour overlays track the dialog geometry after resize.
8. Persisted user layout preferences restore without destroying workspace usability.

## Manual verification

1. Launch VSCS and open **Story → New Scene**.
2. Resize the dialog to approximately 800 × 640.
3. Confirm the central form has a vertical scrollbar.
4. Confirm Save/Create Scene and Cancel remain visible.
5. Expand and collapse Workflow, Summary and Validation.
6. Drag both vertical and horizontal splitter handles.
7. Resize the dialog to a large desktop size.
8. Close and reopen the dialog.
9. Confirm the selected panel states and splitter proportions are restored.
10. Start the onboarding guide and resize the dialog while both the Welcome and Guided Tour overlays are visible.
11. Confirm the overlay cards remain fully inside the dialog.

## Certification command

```powershell
pytest `
    tests/certification/test_onboarding_responsive_layout_certification.py `
    tests/unit/test_adaptive_workspace_layout.py -v
```

## Certification status

Pending execution on the target Windows/PySide6 environment.
