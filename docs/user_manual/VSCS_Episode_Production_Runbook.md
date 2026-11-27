# VSCS — End-to-End Episode Production Runbook

**Version:** 1.0 — 2026-11-26  
**Status:** Code-verified operator sequence; Windows end-to-end acceptance **not yet completed**.  
**Owner:** Neill Payne.  
**Use:** Start here for each Episode. The [MASTER delivery backlog](../roadmap/VSCS_MASTER_DELIVERY_BACKLOG.md) determines which work package is active; this runbook determines the **required in-app order**. Historical UI and architecture documents do not waive current readiness gates.

## Quick route — complete these gates in order

| # | Where in VSCS | Operator checkpoint | Required result before continuing |
|---|---|---|---|
| 1 | Project / Story | Open correct project, create/import Story; analyse; human-review and approve source | Current approved Story, stable IDs and intended Episode scope |
| 2 | Story → Automation, where applicable | Review/accept Episode, Scene, Shot proposals and **compile accepted proposals** | Persisted governed Episode/Scene/Shot plans; proposal-only success is insufficient |
| 3 | Story → Episode Planner → Scene Planner… → Shot Planner… | Select Episode, Scene and each Shot; inspect budgets, duration, continuity and **Mark Ready** | Current Ready Episode, Scene and Shot(s) |
| 4 | Shot Planner → **Asset Resolver…** | Review every visible-asset requirement and independent nonvisual scope exceptions | No unresolved/Draft/stale **visible** requirements; approved Asset + CAP + references for every visible binding |
| 5 | Shot Planner → **Camera Planner…** | Review suggested camera plan, edit, **Mark Ready** | Current Ready Camera Plan; Asset Resolver must already be ready |
| 6 | Shot Planner → **Lighting Planner…** | Review/prepare light, time and continuity; **Mark Ready** | Current Ready Lighting Plan, no stale upstream authority |
| 7 | Shot Planner → **Environment Planner…** | Review physical conditions/setting; **Mark Ready** | Current Ready Environment Plan |
| 8 | Shot Planner → **Planning Review…** | **Start Review**, inspect all checks, notes, **Approve Planning** | All planning checks Ready; current approved review and integrated renderer-neutral planning package |
| 9 | **Production Packages / Production Planning** workspace | Complete **Action & Performance**, **Assets**, **Universal Description**, **Provider Output**, **Production Review** tabs | Current compiled package and explicit **Approve for Production**; no stale tab or provider draft |
| 10 | Same workspace → **Production Tasks** | Compile Tasks, refresh readiness and check Shot/authority scope | Correct READY video ProductionTask; no obsolete task or false-ready marker |
| 11 | Same workspace → **Scheduling** (if queue-backed) | Register/select resource, refresh, create revision, review and **Approve Schedule**, **Compile Approved Queue** | Governed queue for the intended job; distinguish this from H3's separate direct-orchestration launch |
| 12 | **Production Execution** | Select task/profile/provider, compile execution package, validate provider readiness | READY with correct plan, required keyframes, current refs and resource; **no job yet** |
| 13 | **Production Execution** — separately authorized | One-use confirmation, run one real GPU job, reconcile job/output/recovery | Actual playable video, frame count/duration/provenance verified |
| 14 | **Generated Media** | Technical validation, **Submit for Review**, independent human **Approve**, **Select** | Approved, selected Shot-scoped GeneratedMedia; no candidate automatically approved |
| 15 | **Episode Assembly** | Resolve Shot Set, stage approved media, frame ranges, authorized immutable draft, verify/playback | Correct ordered and playable accepted multi-shot assembly |
| 16 | Post-Production / audio and delivery stages | Voice/dialogue, lip-sync where applicable, sound/mix, QC, final export | Reviewed synchronized mastered episode; do not treat architecture-only features as implemented |

**Execution rule:** Repeat steps 3–14 **per Shot** as appropriate; do not assume an Episode's one Ready Shot means the entire Episode is Ready. Refresh downstream artifacts whenever their upstream Shot/Asset/CAP/Camera/Lighting/Environment contracts change. Buttons disabled by policy are a signal to inspect the predecessor, **not** to bypass validation.

## A. Start a real Episode

1. Start VSCS and open the intended project. Confirm project path, Story title, Episode ID and whether you are in a disposable test project or genuine production. Preserve existing audit and approved-media history.
2. In **Story**, review the imported/entered text, story analysis, Story approval and automation proposals. When automation reports proposals created, **human-review and compile** accepted proposals into actual plans; no amount of proposal review makes a persisted Shot by itself.
3. In **Story → Episode Planner**, select the correct Episode and inspect duration/Ready/current. Open **Scene Planner…**, verify the Scene's allotted duration and Ready state, then **Shot Planner…** and inspect the individual Shot's duration, framing, continuity and Ready state. If any plan is Draft or stale, resolve it at its owning editor first.

## B. Asset Resolver — the current blocked stage

Open **Shot Planner → Asset Resolver…** for the selected Shot. The upper summary distinguishes (a) actual production-ready visible bindings, (b) unresolved/Draft/stale visible bindings and (c) independently reviewed **nonvisual** requirements. Press **Analyze Requirements** to review suggested canonical mappings; these are advisory. Each mapping must be evaluated on its own current Shot evidence.

1. For each **visible physical asset**, select its row and **Edit** if enabled. Confirm production role, category, requirement, project asset and the **Current resolution** diagnostic. Save correct mapping as Draft. *Merely* matching a CAP ID or seeing `Partial` in the table is **not** production-ready.
2. For every visible requirement, VSCS resolves an **approved Asset**, approved CAP and governed references; check and correct the originating **Assets / Canonical Profiles** records if the diagnostic is Partial, missing, changed or not approved. The default remains strict canonical references. For an explicitly cinematic Shot, the Draft binding editor now offers **Use human-accepted cinematic views for video (not canonical approval)**; this uses only fresh, human-reviewed cinematic references and still requires approved Asset/CAP and production readiness. Preserve locked MASTER authority. A human may approve valid canonical references under their own governance, but must never approve or invent unseen geometry merely to clear a dependency. [W2.3 acceptance procedure](../engineering/Issue_61_W2_3_Cinematic_CAP_Asset_Resolver_Integration.md).
3. Use **Review Visibility…** only for genuinely off-screen viewpoint instructions or surrounding setting context. Review actual Shot evidence, enter a reason and check the operator confirmation. This is a specific nonvisual classification, **not** a shortcut for a visible prop. Reopen if the Shot changes or the stored evidence becomes stale.
4. For each eligible **visible** Draft binding, use **Mark Ready** only when the required authority is genuinely Resolved/current. Do not create duplicate requirements to mask an unresolved one. After every change, **Refresh/reopen** and record summary counts and blockers.
5. Only proceed when **no required visible binding remains unresolved/Draft/stale** and the downstream Camera Planner permits readiness. Reviewed nonvisual entries may remain counted separately, without pretending that they are approved visible asset references.

**Observed CAP-PRP-002 first-shot checkpoint (2026-11-26 screenshot):** five declared bindings; **zero production-ready**, **three unresolved/Draft/stale**, **two reviewed nonvisual**. Visible physical assets are `CAP-LOC-001` (engineering bay), `CAP-PRP-002` (diagnostic console) and `CAP-PRP-001` (maintenance workstation); all show `Partial`/Draft. `CAP-SHP-001` is reviewed *setting context*, `CAP-TEC-001` is reviewed *camera viewpoint*. These latter classifications are existing human-review evidence; don't reset them without reason. **This Shot is NOT ready to advance merely because its upstream Shot Plan says Ready.** Next operator action: inspect the **Current resolution** diagnostic for each of those three visible Draft rows and resolve the specific CAP/Asset/reference authority gaps.

## C. Camera, Lighting, Environment and Planning Review

1. Return to **Shot Planner → Camera Planner…**. For an absent plan choose **Create Suggested Draft** (or **Create Blank Draft**), review Shot size, angle, movement, lens, height, screen direction, composition, focus and continuity. Edit the Draft if needed. **Mark Ready** is only enabled when the upstream Shot **and** Asset requirements are Ready. The previous imperfect Left/Right orthographic images do not by themselves authorize bad camera/planning inputs; prioritize cinematic proof once scope is valid.
2. Open **Lighting Planner…**. Prepare its suggested/blank Draft; inspect lighting conditions and continuity, then **Mark Ready**. If a dependency is blocked or stale, return to the prior gate.
3. Open **Environment Planner…**. Prepare its suggested/blank Draft; inspect setting, atmosphere, time, surfaces, motion and hazards; **Mark Ready**. It consumes Lighting authority without redefining the lighting plan.
4. Open **Planning Review…**. Click **Start Review**, inspect each Planning Area / Result / Detail, record reviewer notes, **Save Notes**, and only when every required check is ready use **Approve Planning**. This action also performs governed **Planning Integration** when available. Confirm **CURRENT** integrated renderer-neutral package. An approved but **Stale** review must be returned/reassessed before production compilation.

## D. Story → Production Packages / Production Planning

**Navigation note:** UI labels have evolved. The code's downstream workspace displays **Production Planning** and the manual has called its entry **Production Packages**. Open the production-package **compiler workspace**, not the **Episode Planner** again. Match the following actual tabs, not an old sidebar label.

For each integrated Shot, select the Shot on the workspace's left and complete the right-hand tabs in order:

1. **Action & Performance:** **Create from Shot** → inspect all fields → **Save Draft** if edited → **Mark Ready & Compile**. Use **Refresh from Current Shot** when upstream authority changed; never silently keep a stale package.
2. **Assets:** **Create from Package** → inspect every compiled asset binding/reference, retain notes → **Mark Ready & Compile**. An unresolved visible asset must be fixed at Asset Resolver/CAP, not hidden by downstream notes.
3. **Universal Description:** **Assemble from Governed Authority** → inspect generated, renderer-neutral description → optional review notes → **Mark Ready & Compile**. Correct the governed source rather than overriding source truth in prose.
4. **Provider Output:** select the intended provider → **Compile Provider Draft** → inspect prompt, slots, duration and limitations → **Mark Ready & Compile**. This is compilation only; it does **not** submit ComfyUI work.
5. **Production Review:** **Validate Package**; read readiness/blockers; enter human reviewer and notes; **Approve for Production** only after the actual package is current and complete. **Request Changes** returns work for correction; no automatic approval follows a technical PASS.
6. **Production Tasks:** **Compile Production Tasks**, then **Refresh Task Readiness**. Inspect the correct Episode/Scene/Shot, type, revision, package and GPU resource; optionally **Verify H3 Readiness (No Generation)**. Handle any obsolete task with governed **Supersede Obsolete Task**, preserving its provenance.
7. **Scheduling:** for queue-backed production select/register resource, **Refresh Readiness**, **Create Schedule Revision**, review and **Approve Schedule**, then **Compile Approved Queue**. H3 direct-orchestration also has its own provider readiness and launch-claim route; **do not** conflate compiling a schedule or queue with successful video generation.

## E. Video generation, review, multi-shot assembly, delivery

1. In **Production Execution**, choose the correct ProductionTask, execution profile and approved provider policy. **Compile Production Package**, then **Validate Provider Readiness**. A current `READY` state must still be rechecked against real Windows ComfyUI workflow/models, approved Introduction Keyframe, active project and GPU. See [W2.2 controlled first-video acceptance](../engineering/VSCS_W2_2_First_Governed_Video_Windows_Acceptance.md).
2. Only with **new explicit one-job authorization** use **Run Automated Span Orchestration** (for the selected H3 governed route) and the exact, copyable one-use phrase. Running H3 once is not automatic permission to retry, batch candidates, download models or change protected sources.
3. In **Generated Media**, confirm scope and provider provenance; complete technical checks; **Submit for Review** and independently **Approve** or **Reject** the correct file; then **Select** approved media for its Shot. Preserve old candidates and review history. Reconcile the ProductionTask against accepted media only through the governed UI.
4. For **Episode Assembly**, **Resolve Episode Shot Set**, stage *approved* media per Shot, use **Read Approved Media & Auto-Fill Frames** where appropriate, verify selected in/out frame ranges, request any required immutable planning snapshot, **Review and Publish Immutable Draft**, inspect/verify persisted revision, and **Play Verified Timeline**. An assembly page or draft does not itself constitute final mastered video.
5. **Post-Production** follows actual available UI/provider features for voice, dialogue, lip-sync (when a speaking face is visible), SFX/ambience, mixing, captions and export. These capabilities may still be roadmap items: follow their own current acceptance evidence rather than presuming the whole chain is operational. Reopen/verify the final episode export and manifest before human delivery approval.

## F. Per-Episode operator record (copy into the episode acceptance log)

| Gate | State / evidence to record |
|---|---|
| Project, Story approval, Episode/Scene ID | ID, approval, source revision, date |
| Each Shot | ID, duration, Ready/current, continuity, accepted scope |
| Asset Resolver | Declared / visible Ready / visible unresolved / reviewed nonvisual; exact blockers |
| Camera, Lighting, Environment | Plan ID, Ready/current, reviewer notes |
| Planning Review / Integration | Approved/current, integrated package ID |
| Production Package tabs | Action, Assets, Universal, Provider, Review PASS/current |
| Tasks / Schedule | Task ID, READY revision; schedule/queue authority where applicable |
| GPU job | Separate authorization, plan/job ID, result or blocker |
| Generated Media | File ID/hash, fps/frames/duration, technical QC, human decision, Shot selection |
| Assembly and export | Approved Shot coverage, persisted revision, timeline/playback QC, exported master |

**If a gate fails:** stop at that gate, preserve saved records, report the exact diagnostic, repair the owning upstream authority, and then revalidate affected downstream steps. Do not substitute tests, generated images, draft rows or screenshots of an enabled button for persisted production acceptance.

**Verification level:** UI control labels, dependencies and navigation were inspected from the repository source on 2026-11-26. The Asset Resolver counts are from Neill's real Windows screenshot. Other gate states in this runbook are **instructions**, not claims of current Windows acceptance. Validate the entire first-episode walkthrough during the next operator session and correct mismatched labels in this living manual.
