# VSCS Onboarding Keyboard and Focus Certification

## Phase

16.2a.8.5.4.5.2.2 — Keyboard and Focus Certification

## Objective

Certify that the Scene Editor onboarding workflow can be completed using only the keyboard, that focus always moves to the intended control, and that no overlay or guided action creates a focus trap.

## Automated certification areas

| Area | Pass criteria |
|---|---|
| Welcome keyboard entry | Start Guide activates with Enter. |
| Welcome focus containment | Tab and Shift+Tab remain inside the visible welcome overlay. |
| Tour keyboard navigation | Enter advances and Space activates Previous. |
| Tour focus containment | Tab and Shift+Tab remain inside the visible tour card. |
| Try It focus handoff | Space activates Try It and focuses the exact target control. |
| Uninterrupted identity entry | Scene Name and Heading accept complete text without the guide stealing focus. |
| Focus restoration | Closing an overlay releases focus to the editor. |
| Escape recovery | Escape closes the Scene Editor without leaving a hidden focus owner. |
| Checklist keyboard activation | Enter activates workflow checklist navigation. |

## Manual test procedure

### 1. Welcome overlay

1. Open **Story → New Scene** with onboarding reset.
2. Confirm **Start Guide** has the visible focus indicator.
3. Press Tab and Shift+Tab.
4. Confirm focus remains on **Start Guide** or **Skip**.
5. Press Enter on **Start Guide**.

Expected result: the Guided Tour opens and focus moves to its primary action.

### 2. Guided Tour navigation

1. Press Enter on **Next**.
2. Move focus to **Previous** and press Space.
3. Tab repeatedly through the tour card.
4. Press Shift+Tab repeatedly.

Expected result: navigation works and focus never moves behind the visible overlay.

### 3. Try It workflow

1. Navigate to **Scene Identity**.
2. Focus **Try It** and press Space.
3. Type the complete Scene Name.
4. Press Tab.
5. Type the complete Heading.
6. Press Tab.

Expected result: typing is uninterrupted, focus moves from Scene Name to Heading, and the guide returns only after Heading is complete.

### 4. Overlay exit and recovery

1. Reopen the welcome overlay.
2. Activate **Skip** using Space.
3. Tab into the Scene Editor and edit Scene Name.
4. Reopen the dialog and press Escape from the welcome overlay.

Expected result: focus is released to the editor after Skip, and Escape closes the dialog cleanly.

## Certification gate

This phase passes only when:

- Ruff passes for the keyboard/focus matrix and certification tests.
- All automated keyboard/focus certification tests pass.
- Existing guided-navigation and guided-first-scene regression tests pass.
- Manual keyboard-only traversal is completed on Windows with the supported PySide6 runtime.
- No focus trap or unexpected focus theft remains.
