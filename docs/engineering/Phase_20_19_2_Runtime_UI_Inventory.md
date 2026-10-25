# Phase 20.19.2 — Runtime UI & Capability Inventory

**Status:** Instrumentation implemented; local runtime verification and full audit sign-off pending.

## Scope and authority

The approved VSCS Video Production Workflow V2 is the desired 23-step story-to-release process. The UI inventory must distinguish static shell elements from the dynamically installed application after `ApplicationContext.create_main_window()` invokes `install_story_browser()`. That installer replaces base Story and Production Planning placeholders and registers governed services; reporting placeholders from `main_window.py` alone is incomplete.

Phase 20.19.1's disposable MiniMax H3 hold remains active. **Do not remove** `D:\VSCS\H3_ACCEPTANCE\Q3_1_3_5_8\RUN-001\.vscs_h3_live_hold.json`. The inventory command neither opens that project nor calls a provider. Original TSR2 production and QC records are out of scope.

## Preservation of the user's architecture review

The previously drafted local document `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` is **untracked in the operator's checkout**. It must be reviewed, retained and incorporated as a predecessor review without overwriting it or misrepresenting its contents. The document itself has not been uploaded to this GitHub branch by this phase. After examination, commit it as an explicitly reviewed source document under `docs/`, keeping this inventory as new runtime evidence. Avoid `git clean -fd`.

## Instrumentation

`src/vscs/presentation/runtime_ui_inventory.py` collects the instantiated window's:
- top-level Qt menus and their direct entries, enabled state, separators and nested-menu presence;
- sidebar workspace labels and each corresponding stacked widget's actual class, module, object name, placeholder state and enabled state;
- toolbar action labels;
- menu labels also present in sidebar (potential aliases, **not proof of redundant behavior**).

Collection is read-only; no QAction is triggered. The standalone command uses a fresh temporary test-mode configuration, disables plugin load and external environment validation, and **does not provide evidence about user-installed optional plugins or production-mode integrations**. That remaining runtime comparison needs supervised manual verification in the actual application.

## Non-submitting command

Run from the repository with an output path outside any VSCS project:

```powershell
python -m vscs.presentation.runtime_ui_inventory --output "D:\VSCS\UI_AUDIT\runtime-ui-inventory.json"
```

Create the parent folder beforehand. The output file is write-once and should not already exist. For additional runs use a new filename.

## Classification protocol

For each runtime workspace capture: current display name; actual QWidget class; entry point and toolbar/menu aliases; application services; persisted records; available controls; manual opening evidence; and one of `functional`, `partial`, `placeholder`, `duplicate-navigation`, `unreachable`, `not-tested`. Mark menu-name duplication as `potential duplicate-navigation` pending handler verification. Any missing UI capability must be corroborated by its operational workflow, not just its label.

## Operator runtime walk-through

1. Capture the test-mode inventory and attach the JSON.
2. Open the real VSCS application normally and list the menu labels and sidebar names in the order shown.
3. In the *disposable* H3 Isolated Acceptance project, navigate without approving or submitting any production jobs. Check Story, Planning, Assets, Canonical Profiles, Production Execution, Generated Media, Provider Validation and Episode Assembly. Record disabled actions/errors.
4. Compare the actual application to test-mode JSON; list additional installed plugin controls and conditional pages separately.
5. Trace UI destinations and backed services for each workflow stage. Mark unverified where direct UI interaction is not yet observed.
6. Do not consolidate, remove or rename a menu until Phase 20.19.4's preservation map is approved.

## Acceptance gates

- Focused tests and 2,204+ full regression tests pass; Ruff lint/format and mypy clean.
- Test-mode inventory generated with no project opened and no provider submission.
- Live-application screenshot and manual feature check supplied, with discrepancies annotated.
- Untracked earlier audit retained and reconciled.
- No deletion of menus, production data or providers.
- H3 hold marker remains in place and was not modified.

**Next:** build the verified menu/action/handler/service map and report; then run Phase 20.19.3 story-to-task golden path.
