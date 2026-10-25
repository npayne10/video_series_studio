# VSCS Phase 20.19.2 — UI-to-Capability Audit and 20.19.3 Entry Gate

**Status:** Repository routing verified; screenshots observed; operational golden path not yet run.  
**Source of truth:** Approved VSCS Video Production Workflow V2.  
**Safety:** H3 acceptance hold remains active. No H3 POST or project data mutation authorized.

## Evidence classes

- **R (repository verified):** action/installer mapping inspected in checked-in Python.
- **S (screenshot observed):** operator-facing control visible on 2026-10-25 in H3 Isolated Acceptance.
- **T (test observed):** operator reported 2,206 pytest passes, mypy clean across 629 source files, Ruff clean.
- **U (unverified):** actual operation, persistence, success-path transitions, optional plugin behavior.

Do not equate presence of a widget with end-to-end readiness.

## Main navigation and handler/capability mapping

| Entry point | Repository/runtime implementation | Capability and disposition | Evidence |
|---|---|---|---|
| File: New/Open/Save/Close Project | `MainWindow` actions → `ProjectService` | Retain, lifecycle actions | R,S |
| File: Exit | MainWindow close | Retain | R,S |
| View: Dashboard, Assets, Canonical Profiles, Behaviour Profiles, Production Execution, Generated Media, Provider Validation | Selects corresponding navigation index in `MainWindow` | Seven menu/sidebar aliases; preserve until menu redesign | R,S |
| Tools: Settings, Plugin Manager | Dedicated dialogs in MainWindow | Retain technical tools | R,S |
| Help: About | About dialog | Existing only; comprehensive field-level help required | R,S |
| Story → Workspace | Dynamic `AutomationStoryWorkspaceWidget` at stack index 2 | New/Import Story; lifecycle actions visible; actual import not tested | R,S,U |
| Story → Story Definition | `story.definition` → `_button_action(object_name="editStory")` | Silent no-op with no eligible selected Story; **UI-034 approved**: rename Edit Story Definition and explain prerequisite | R,S |
| Story → Story Analysis | `story.analysis` → Analyse Story button | Requires suitable story; functional path untested | R,U |
| Story → Planning Proposals / Shot Proposals | `generatePlanningProposals` / `generateShotProposals` | Advisory planning proposal generation; untested | R,U |
| Story → Performance / Environment / Camera & Lighting / Continuity | respective `generate*Proposals` actions | Guided automation, untested | R,U |
| Story → AI Review & Gap Detection | `reviewAutomationGaps` | Advisory gap review, untested | R,U |
| Story → Canonical Library | Import XPD, Resolve Story Entities, Review XPD Matches, Bind Shot Assets | Dedicated helpers/services, untested | R,U |
| Story → Proposal Review | `reviewAutomationProposals` | Review approvals vs proposals, untested | R,U |
| Story → Production Planning | `story.episode_planning` → `episode_planner_button` installed by `install_episode_planner` | Silent no-op without eligible Story; **UI-035 approved**: rename Episode & Scene Planning and explain prerequisite | R,S |
| Story → Integration & Functional Acceptance | `FunctionalAcceptanceService.evaluate` → report dialog | Requires Story; untested | R,U |
| Assets | `AssetManagerWidget` | Asset registry and lifecycle; functional audit pending | R,U |
| Canonical Profiles | `CAPManagerWidget` with multiple runtime installers | Identity, canonical references, readiness; preserve all subcontrols | R,U |
| Behaviour Profiles | `BehaviourProfileManagerWidget` | Asset behavior definitions; untested | R,U |
| Top-level Production Planning | `UniversalProductionDescriptionCompilerWorkspace` inserted at stack index 6 | Shot specification, universal description, provider output, review, tasks, scheduling | R,S |
| Production Review tab | Final validation; Approve for Production/Request Changes | Screenshot shows no shot selected and approval blocked | S,U |
| Production Tasks tab | Compile Planned tasks; readiness, reconciliation, H3 diagnostics | Requires approved shot/package; IDs/status transition untested | S,U |
| Scheduling tab | Resource register, readiness, schedule revision, approve/reject, queue monitoring | Requires ready task and approved schedule; no resources in empty project | S,U |
| Production Execution | `ProductionExecutionWorkspace`, service-backed | Scheduling, provider preflight, H3 boundaries, manual recovery, live status | R,S,U |
| Generated Media | `GeneratedMediaWorkspaceWidget`, `GeneratedMediaUiService` with JSON registries | Filter, review, approve/reject, select/supersede; empty project | R,S,U |
| Provider Validation | `ProviderCapabilityValidationWorkspace` | Exists; normal-mode functional evidence pending | R,U |
| Episode Assembly | `EpisodeAssemblyWorkspace`, governed authority service tuple | Coverage, draft staging, persisted timeline revisions, technical audio inspections | R,S,U |
| Projects | Base `QLabel` placeholder | Confirmed placeholder, not proof ProjectService missing | R,T |
| Post-Production | Base `QLabel` placeholder | Confirmed placeholder; audio/mix/master still to operationalize | R,T |

**Dynamic-navigation caveat:** The first inventory JSON captured the hidden flat `navigation` and stacked pages, not the visible `hierarchicalNavigationTree`. The latter installs action keys, nonselectable headings and hidden toolbar shortcuts. The following audit iteration must inventory nested nodes, action keys, button prereqs, QTabWidget tabs, and service links. No menu edits in 20.19.2.

## Approved UX decisions reserved for 20.19.4

1. UI-034: Story Definition → **Edit Story Definition**, clear no-story prerequisite feedback.
2. UI-035: Story → Production Planning → **Episode & Scene Planning**, clear no-story prerequisite feedback, preserve installed planner.
3. Production Execution: **Production Queue → Generation Readiness → Generate Video → Monitor & Review → Advanced Controls**.
4. Production Tasks: **Compile → Validate → Assign → Schedule → Execute → Review**.
5. Production Planning: **Shot Definition → Production Package → Production Approval → Tasks & Scheduling**, advanced controls retained.
6. Generated Media remains independent governance, within **Generate → Review → Approve → Select → Assemble**.
7. All seven View/sidebar label duplicates are only *navigation aliases* until exact action/handler equivalence is verified. No deletion authorized.

## 20.19.3 Golden Path — entry gate and test requirements

Use a **new disposable audit project**, separate from H3 Isolated Acceptance and all TSR2 projects. Create a short synthetic story via VSCS New Story or Import Story. No hand-crafted production JSON, no forced approvals and no provider submission.

1. **Story:** create/import, verify persisted source, metadata, analysis provenance and human approval.
2. **Episode:** enter through Episode & Scene Planning's existing action, create governed episode and scene, record generated identities and hierarchy.
3. **Shot:** create one 24-fps static shot; validate action, camera, lighting, reference assignments and continuity states.
4. **Assets:** register synthetic canonical asset/reference in UI, review and approve according to real CAP/reference policy.
5. **Planning:** persist the governed planning decision and Universal Production Description, compile and validate package.
6. **Production Review:** human approval provenance; confirm review fingerprint.
7. **Production Tasks:** compile exactly one PLANNED task with generated ID; validate readiness and identify blocking prerequisites.
8. **Stop:** collect snapshot of IDs, hashes, task state, validation evidence. No scheduling approval or provider execution required to prove Story-to-Task creation; further non-submitting readiness may be separately audited.

For each step record the UI click path, backing service, inputs/required fields, persisted data paths, identity, validation output, exact blockers, retry behavior and screenshots. A blocked step is a diagnostic result, **not permission to fabricate records**.

## Preservation of prior review

Operator's local `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` remains untracked. Its full bytes are unavailable through this GitHub-only view; **do not replace or claim to have merged its content**. Review and commit it deliberately after obtaining its actual contents, alongside this addendum.

## Remaining 20.19.2 acceptance

- Verify normal-mode nested navigation controls, tab names and disabled-state prerequisites against the installed tree.
- Attach user-provided UI screenshots and test-mode inventory JSON to audit archive (without exposing production secrets).
- Reconcile and version-control the earlier untracked audit.
- Produce service/field coverage and final menu-preservation matrix for 20.19.4.
- Hold must stay active until separate review authorization.
