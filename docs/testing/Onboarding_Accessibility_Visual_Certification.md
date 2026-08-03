# VSCS Onboarding Accessibility and Visual Consistency Certification

## Phase

16.2a.8.5.4.5.2.4 — Accessibility and Visual Consistency

## Objective

Verify that onboarding remains understandable, operable and visually coherent without relying on colour, mouse input or one fixed application palette.

## Automated certification

Run:

```powershell
pytest `
    tests/certification/test_onboarding_accessibility_visual_certification.py `
    tests/certification/test_onboarding_keyboard_focus_certification.py `
    tests/certification/test_onboarding_overlay_spotlight_certification.py `
    tests/unit/test_beginner_mode_persistence.py `
    tests/unit/test_validation_explanations.py -v
```

Run Ruff:

```powershell
ruff check `
    tests/certification/accessibility_visual_matrix.py `
    tests/certification/test_onboarding_accessibility_visual_certification.py
```

## Certification checklist

### Accessible identity

- [ ] Welcome overlay exposes a meaningful accessible name.
- [ ] Guided Tour overlay exposes a meaningful accessible name.
- [ ] Beginner Mode exposes a meaningful accessible name.
- [ ] Restart Tour exposes a meaningful accessible name.

### Descriptive controls

- [ ] Primary onboarding actions have stable object names.
- [ ] Primary onboarding actions have descriptive tooltips.
- [ ] Scene Name, Heading and Location provide field guidance.

### Visual language

- [ ] Welcome actions use Start Guide and Skip consistently.
- [ ] Tour actions use Previous, Next, Try It and Skip Tour consistently.
- [ ] The final action clearly reads Create Scene.
- [ ] Beginner and Expert modes preserve the same core editor and documentation tools.

### Focus visibility

- [ ] Welcome assigns focus to Start Guide.
- [ ] Guided Tour assigns focus to its primary available action.
- [ ] Blocked required steps assign focus to Try It.
- [ ] Native Qt focus indication remains visible in the active palette.

### Palette resilience

- [ ] Welcome card renders under a light palette.
- [ ] Welcome card renders under a dark palette.
- [ ] Guided Tour card renders under a light palette.
- [ ] Guided Tour card renders under a dark palette.
- [ ] Cards use palette roles rather than fixed light backgrounds.

### Non-colour communication

- [ ] Validation includes textual issue counts.
- [ ] Blocking state is not communicated by red colour alone.
- [ ] Buttons retain readable text labels.

## Pass criteria

Certification passes when Ruff and all automated tests pass, the manual checklist is complete, and no blocking accessibility or visual-consistency defect remains.
