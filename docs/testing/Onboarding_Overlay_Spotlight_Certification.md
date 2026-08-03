# VSCS Onboarding Overlay and Spotlight Certification

## Phase

16.2a.8.5.4.5.2.3 — Overlay and Spotlight Certification

## Objective

Certify that onboarding overlays remain correctly positioned, visually modal, target-accurate and stable during navigation, scrolling and resizing.

## Automated certification

Run:

```powershell
pytest `
    tests/certification/test_onboarding_overlay_spotlight_certification.py `
    tests/unit/test_guided_interface_tour.py `
    tests/certification/test_onboarding_responsive_layout_certification.py `
    tests/certification/test_onboarding_keyboard_focus_certification.py -v
```

## Certification matrix

### Welcome overlay coverage

- [ ] Overlay geometry matches the complete Scene Editor client area.
- [ ] Welcome card remains fully inside the overlay.
- [ ] Resizing the dialog updates overlay geometry immediately.

### Tour overlay coverage

- [ ] Tour overlay covers the complete Scene Editor client area.
- [ ] Tour card remains fully visible at compact and large sizes.
- [ ] Resize events do not expose interactive controls behind the overlay.

### Spotlight target accuracy

- [ ] Spotlight contains the centre of the selected workflow target.
- [ ] Spotlight uses the target's current global geometry.
- [ ] No parent-hierarchy mapping warnings are emitted.

### Card collision avoidance

- [ ] Card does not overlap a target in the upper-right placement area.
- [ ] Card moves to the lower-right when required.
- [ ] Repositioning remains inside the overlay.

### Missing target recovery

- [ ] A missing target produces a valid dimmed overlay without a spotlight.
- [ ] A hidden target produces a valid dimmed overlay without a spotlight.
- [ ] Navigation buttons remain usable.

### Scrolling and spotlight refresh

- [ ] Guided navigation scrolls distant controls into view.
- [ ] Spotlight follows the target after scrolling.
- [ ] Card remains visible after the scroll operation.

### Focus-safe redraw

- [ ] Resizing does not move keyboard focus behind the overlay.
- [ ] Active navigation control retains focus.
- [ ] Tab containment remains functional after redraw.

## Manual verification

1. Open **Story → New Scene** at approximately 900 × 680.
2. Confirm the Welcome card is centred and fully visible.
3. Resize the window repeatedly; confirm the dim layer always covers the full dialog.
4. Start the guide and move through each step.
5. Confirm the highlight surrounds the intended field or section.
6. Navigate to Production Settings and confirm the form scrolls before spotlighting it.
7. Resize while the tour card is visible and confirm focus and card placement remain stable.
8. Confirm the card never obscures the highlighted control when an alternative placement is available.

## Pass gate

Certification passes only when:

- Ruff is clean.
- All automated certification and referenced regression tests pass.
- Manual verification completes without clipping, incorrect spotlighting, focus loss or Qt geometry warnings.
- No unresolved blocking overlay or spotlight defect remains.
