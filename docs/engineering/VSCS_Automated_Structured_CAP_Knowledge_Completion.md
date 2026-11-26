# Automated Structured CAP Knowledge Completion — 2026-11-26

**Scope:** Reuse saved human-reviewed CAP specification evidence to propose Facts, limited visible capabilities and canonical Constraints without calling AI. Explicit operator review and CAP Save remain required. This does not approve CAP status, assets, images or unknown geometry.

## Operator procedure

1. In **Canonical Profiles**, select an existing Draft CAP and **Edit Selected**. Confirm its reviewed design/specification audit is saved and current.
2. In **Structured Production Knowledge**, select **Prepare from Reviewed CAP (Offline)…**. The button validates the saved human-review decisions against every current canonical attribute; deferred/rejected fields cannot become proposed canon. It supports reviews whose MASTER prompt was rebuilt after the original audit result fingerprint was recorded.
3. Inspect the proposal list and its evidence summary. The proposals are based only on accepted/edited reviewed canonical attributes and existing continuity rules. Limited visible display/control affordances are proposed where explicitly described; their software behavior is *unspecified*. In the absence of supported capability evidence, the proposal reports an unresolved question instead of inventing functionality.
4. **Cancel** if any proposal is not acceptable (no editor or project mutation). Choose **Accept Reviewed Entries** only after review. Entries merge into the editor; existing structured entries and protected production metadata remain intact. Newly accepted entries become human-reviewed **Approved** when the CAP editor is saved.
5. Inspect all **Facts, Capabilities, Constraints, Classification**, plus **Visual identity**. On explicit acceptance, an **empty** Visual identity field receives a draft summary of accepted reviewed attributes; existing operator-authored text is never overwritten. Review and refine it against the approved MASTER before **Save**, then reopen **Readiness** and record exact remaining blockers.
6. **AI Proposal (May Cost)…** is an optional, separate provider-backed action that displays an explicit possible-cost confirmation. It is not invoked by the offline button. Neither route changes asset/CAP status or approves reference viewpoints automatically.

## Safeguards and limitations

- Saves no provider queue, paid request or GPU output in the offline route.
- A missing/invalid saved human review, altered accepted field, unreviewed added attribute, or deferred/rejected canonical field fails closed. The historical result fingerprint need not equal the post-review MASTER prompt fingerprint; field values and review authority are verified instead.
- Source/evidence provenance is carried from the reviewed CAP specification into the structured entries; subsequent human edits are attributed to the editor.
- Existing knowledge is merged rather than replaced. Re-running the offline preparation does not duplicate identical keyed entries.
- Existing review audit and structured-specification metadata remain preserved by the general CAP editor.
- A simple description alone is not evidence for actual diagnostic software functions, communications or unseen components. Do not create capabilities without reviewed source support.
- The current CAP-PRP-002 Rear/Left/Right reference, CAP approval and Asset approval gates remain separate. No automatic production approval is implied.

**Next Windows checkpoint:** Use `CAP-PRP-002` and inspect the offline proposal, save only human-verified entries, then recheck CAP Readiness. If the CAP's persisted design review is stale or absent, resolve it with the existing governed review workflow. Proceed with Asset Resolver → Camera/Lighting/Environment → Planning Review → Production Packages before W2.2 real GPU work.
