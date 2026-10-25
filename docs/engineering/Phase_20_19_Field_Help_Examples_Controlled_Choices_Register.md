# VSCS Phase 20.19 — Field Help, Examples & Controlled-Choice Register

**Status:** Living discovery artifact; not yet implemented as application Help.  
**Purpose:** Retain evidence gathered during UI and golden-path audits so comprehensive contextual Help can be delivered without re-investigation.

## UX design principles

1. Every field should provide **what it means**, **when it is used**, **whether required**, **an accurate example**, **validation/error conditions**, **source of authority**, **dependency prerequisites**, and **where it appears downstream**.
2. Distinguish **freeform creative text** from **controlled choices**. Replace free-entry with search-backed dropdowns/selection dialogs where the domain is finite and values must be exact (provider, state, resource, approved reference, asset, reviewer identity). Do not turn narrative direction into a forced dropdown.
3. Populate controlled choices from persisted project registries and capability policy where possible; avoid hard-coded sets that drift from model/provider readiness.
4. Missing prerequisites should explain *why* disabled and link to the upstream work area; no auto-approval or governance bypass.
5. Each help item should link to end-to-end workflow stage and documentation; provide a one-click example insertion only when it cannot overwrite approved data.
6. Guide beginners by default and keep full engineering diagnostics accessible to advanced operators.

## Captured UI field/control inventory

| Area | Field/control | Observed UI status | Example / Help candidate | Future control proposal |
|---|---|---|---|---|
| New Story | Title* | Required visual indicator | `Stationary Console Acceptance`; identify the Story independently of productions | Free text with duplicate-title guidance |
| New Story | Description | Free text | `Synthetic story for isolated production-pipeline validation` | Multiline with example |
| New Story | Source Type | Dropdown: Original, Docx, Pdf, Markdown, Screenplay, Plain Text, Other | Choose **Original** for direct drafting, **Docx** for manuscript association | Controlled list retained; parser support validated separately |
| New Story | Source Path / Browse | Present | Select source manuscript; importing content differs from merely linking | File picker with supported format explanation and preview |
| New Story | Synopsis | Multiline | `A stationary diagnostic console holds during a subtle change in display illumination.` | Free text and genre-aware examples |
| New Story | Genres / Themes / Keywords | Comma-separated fields | `science fiction, technical drama`; `continuity, discovery` | Autocomplete chips with arbitrary custom entries |
| New Story | Target Audience | Text entry | `Adult science-fiction viewers` | Optional suggestions, not constrained without a policy |
| New Story | Language | Displays English | `English` | Locale selector from supported TTS/subtitle languages, allow unknown/custom as necessary |
| New Story | Author | Text entry | `S.S. Drake` (sample only) | Suggest project-linked author identity, do not auto-assume |
| New Story | Estimated runtime (minutes) | Unestimated numeric widget | `1` for a short demo | Numeric range; story-level estimate distinct from production schedule duration |
| Story Definition | Navigation action | Silent return with no Story | `Select a Story or use New Story / Import Story` | UI-034 approved label & prerequisite help |
| Story → Production Planning | Navigation action | Silent return with no eligible Story | `Approve a Story before creating episode and scene plans` | UI-035 approved label & prerequisite help; actual eligibility rule must be verified |
| Production Planning — Action Performance | Temporal narrative | Large multiline control | `The locked camera holds. A small blue diagnostic indicator pulses once.` | Free text; annotated example |
| Action Performance | Spoken content/dialogue | Multiline | `None (no dialogue in this test shot)` | Allow explicit no-dialogue action; link dialogue registry for scripted lines |
| Action Performance | Performance direction | Multiline | `No character activity; screen pulse remains subtle.` | Free text |
| Action Performance | Opening/Closing state | Multiline | `Screen idle` → `indicator dimmed` | Suggest approved continuity state picker + freeform commentary |
| Action Performance | Timing notes | Multiline | `24 fps; duration to be resolved against selected provider` | Native frame/fps validator; not freeform truth source |
| Production Tasks | Production/Episode/Scene IDs | Production defaults to project label; empty episode/scene | Never type invented IDs; show selected governed object labels and IDs | Read-only derived bindings/selectors |
| Production Tasks | Approved by | Blank in empty project | Approval should derive from actual review provenance | Controlled reviewer identity, not arbitrary authority |
| Production Tasks | UPD authority revision | Defaults to 1 | Revision of current approved UPD | Read-only generated revision when authority bound |
| Production Tasks | Scheduling priority | Dropdown Low observed | Explain operational priorities and rescheduling impact | Exact policy-backed enum; options beyond Low not yet verified |
| Scheduling | Resource ID | Free entry | `LOCAL-GPU-01` is illustrative, not a persisted ID | Selector from registered available resources |
| Scheduling | Capabilities | Text: video_generation, image_generation, audio_generation | Explain resource claims vs validated capabilities | Multi-select from controlled capability registry; validate against actual hardware/provider |
| Scheduling | Resource State | Dropdown Available observed | Availability is resource state, not provider success | Controlled enum with descriptions; other options not yet verified |
| Scheduling | Reviewer / notes | Fields present | `Reviewed local GPU allocation; no execution authorized` | Reviewer identity from authenticated provenance; notes freeform |
| Production Review | Reviewer / Review notes | Fields present | `Package meets static-shot continuity constraints` | Same governed reviewer policy |
| Production Execution | Profile | Production visible | Differentiate Preview, Production, Master; policy/options must be inspected | Controlled profile registry |
| Generated Media | Review / Approve / Reject / Select | Disabled in empty project | Explain requirements and immutable revision identity | Keep separate quality approval from selected media designation |
| Episode Assembly | Episode selector / revision selector | Empty state | Explain governed shot coverage and media-selection prerequisites | Controlled persisted identity selectors |
| Episode Assembly | Technical audio readiness | Read-only | Identify codec/channel/sample-rate validation vs artistic sound mixing | Context Help: inspection is not audio-production |

## Help requirements to capture during Phase 20.19.3

For each actual field capture: owning QWidget/objectName, label, datatype, default value, full dropdown option set, requiredness, validation code/regex/range, disabled-state rules, saved model property, authoritative service, error message, positive and negative examples, help ID, access/readability considerations, and supporting screenshot.

Do not infer dropdown options from a screenshot that shows only one selected value. Do not claim a format parses correctly merely because it appears in Story Source Type.

## Future implementation plan (after audit)

- Help schema: stable `help_id` attached to field/action; text, examples, constraints, dependencies, next steps, and source revision.
- Context-sensitive tooltips plus Help sidebar with **Why blocked?**, **Show example**, **See downstream effect**.
- Validated dropdowns for finite domain fields; searchable selectors for governed IDs; autocomplete rather than forced selection for creative tags.
- UI regression tests: help coverage for required fields, valid/invalid options, disabled action guidance, accessible navigation and zero silent no-ops.
- Preserve all existing data; any field migration/choice restriction requires legacy-value compatibility test and explicit approval.

**Next evidence gate:** Native Story-to-ProductionTask golden path in a separate disposable audit project. Keep H3 hold active.
