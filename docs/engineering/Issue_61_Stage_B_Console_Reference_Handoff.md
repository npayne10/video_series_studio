# Issue #61 Stage B — approved Diagnostic Console MASTER handoff and acceptance

**Status (2026-11-23):** A ChatGPT-created *image* has been approved by Neill
after visual inspection. It has **not** been downloaded into the Windows
project, registered in Assets, locked in VSCS or used for derived generation.
Stage A offline UI/non-mutation was formally accepted; Stage B remains open.
This is an operator runbook, not permission for an automated GPU or paid call.

## Approved human-visible source

| Field | Evidence / intent |
| --- | --- |
| Asset | `CAP-PRP-002` — Diagnostic console (`Prop`) |
| Source | Image generated in the ChatGPT conversation; human visually approved by Neill on 2026-11-23 |
| Image format | PNG, 1024 × 1536 RGB |
| SHA-256 **of the original generated PNG bytes** | `C9741D39D1713E7EDDB600A15DD8D8D1B7A5C353225445CE2E4444589B9A3A38` |
| Approved visual identity | Upright rectangular matte graphite-coated housing; ribbed side grip panels; one broad cobalt-blue display; shelf with exactly three small circular buttons in a row, then exactly one dial recessed below shelf plane; no lettering or extra controls |
| Still unresolved | Absolute dimensions/scale and any other deferred CAP attributes. Image proportions are approved visually; a specific real-world measurement is **not** thereby accepted. |
| Intended governed role | MASTER, Primary, Approved and Locked **only after** explicit in-app registration and verification |

The SHA above identifies this exact original image file, not a visually similar
re-encoded/downloaded copy. If a browser produces different bytes, **STOP**:
record both hashes, inspect export/transcoding and obtain a fresh operator
decision. Do not quietly substitute a different PNG or overwrite the master.
ChatGPT source conversation/prompt and human approval are provenance evidence,
but are not cryptographic proof of generation origin.

## Current supported Stage B procedure (Windows, operator controlled)

### 0. Preflight / protected baseline

1. Confirm VSCS is running the Issue #61 branch from [draft PR #66](https://github.com/npayne10/video_series_studio/pull/66); Ruff, Mypy,
   targeted and full regression passed on Windows. Use the existing project
   `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`, not a reconstructed copy.
2. **Close VSCS** and capture a new BEFORE inventory of the prior `Get-Issue61Snapshot`
   scope (planning asset resolutions, `.vscs/cap_reference_library.json`,
   Console and Workstation `Canonical Assets` trees), plus source image paths,
   current CAP/Asset status and any project SQLite authority records you are
   able to inspect read-only. Preserve historical Console Candidate 4, existing
   C2/C2.1 masks, reviews and governed attempts.
3. Mark the next operation as **intentional image-source import**: unlike Stage
   A, specific new files and reference/library/asset records are *expected* to
   change. No existing review/image source is allowed to change silently.

   Capture the protected-file baseline using an **independent PowerShell
   session with VSCS closed** (do not reuse an AFTER value as BEFORE):

   ```powershell
   $projectRoot = 'D:\VSCS\C4B2B_DISPOSABLE_GPU_01'
   function Get-Issue61ProtectedSnapshot {
       param([string]$ProjectRoot)
       $paths = [System.Collections.Generic.List[string]]::new()
       $paths.Add((Join-Path $ProjectRoot 'planning\asset_resolutions.json'))
       $paths.Add((Join-Path $ProjectRoot '.vscs\cap_reference_library.json'))
       foreach ($assetId in @('CAP-PRP-002', 'CAP-PRP-001')) {
           $dir = Join-Path $ProjectRoot "Canonical Assets\$assetId"
           if (Test-Path -LiteralPath $dir -PathType Container) {
               Get-ChildItem -LiteralPath $dir -File -Recurse |
                   ForEach-Object { $paths.Add($_.FullName) }
           }
       }
       $referenceDir = Join-Path $ProjectRoot 'references'
       if (Test-Path -LiteralPath $referenceDir -PathType Container) {
           Get-ChildItem -LiteralPath $referenceDir -File -Recurse |
               ForEach-Object { $paths.Add($_.FullName) }
       }
       foreach ($path in ($paths | Sort-Object -Unique)) {
           $sha = if (Test-Path -LiteralPath $path -PathType Leaf) {
               (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
           } else { '<MISSING>' }
           [PSCustomObject]@{ Path = $path; SHA256 = $sha }
       }
   }
   $beforeIssue61StageB = @(Get-Issue61ProtectedSnapshot -ProjectRoot $projectRoot)
   "BEFORE: $($beforeIssue61StageB.Count) monitored paths"
   ```

   Keep `$beforeIssue61StageB` in this terminal until final comparison. The
   operator may add other protected source/DB paths to the manifest, but must
   not omit existing historical Candidates or change the baseline after work.

### 1. Download and seal the operator-approved image

1. Download the **actual ChatGPT-generated PNG** displayed in the conversation
   (not the previous local ComfyUI supplementary Candidate). Keep a separate
   copy of the unmodified download and the ChatGPT prompt/approval record.
2. Identify the real downloaded file path in PowerShell, for example:

   ```powershell
   $projectRoot = 'D:\VSCS\C4B2B_DISPOSABLE_GPU_01'
   $approvedDownload = 'REPLACE-WITH-THE-EXACT-DOWNLOADED-PNG-PATH'
   $expectedSha = 'C9741D39D1713E7EDDB600A15DD8D8D1B7A5C353225445CE2E4444589B9A3A38'
   $sourceSha = (Get-FileHash -LiteralPath $approvedDownload -Algorithm SHA256).Hash
   if ($sourceSha -ne $expectedSha) { throw 'STOP: downloaded image does not match approved source bytes' }
   ```

3. Choose a **new, never-used** versioned path *inside* the project. The
   following is a suggested filename, not an assertion that it exists:

   ```powershell
   $masterPath = Join-Path $projectRoot 'references\CAP-PRP-002_CHATGPT_MASTER_v1_20261123.png'
   if (Test-Path -LiteralPath $masterPath) { throw 'STOP: MASTER filename already exists; choose a new version' }
   New-Item -ItemType Directory -Path (Split-Path -Parent $masterPath) -Force | Out-Null
   Copy-Item -LiteralPath $approvedDownload -Destination $masterPath -ErrorAction Stop
   $masterSha = (Get-FileHash -LiteralPath $masterPath -Algorithm SHA256).Hash
   if ($masterSha -ne $expectedSha) { throw 'STOP: copied MASTER bytes differ from approved image' }
   Write-Host "PASS: approved source copied unchanged: $masterSha" -ForegroundColor Green
   ```

4. Do not rename/re-save the original Candidate 1 or historical Candidate 4,
   re-encode this MASTER through an image editor, or place it outside the
   active project. Capture destination, hash and byte count in the audit log.

### 2. Register the human-approved MASTER

1. Launch `vscs`, open the same project and **View → Assets**.
2. Select **Diagnostic console — `CAP-PRP-002` → Edit Selected**. Confirm the
   existing Asset ID, `Prop` category and current `MASTER Status: Missing`.
   Do **not** create another asset or promote the local supplementary Candidate.
3. Click **Browse…**, select the *exact* sealed new PNG, inspect its path,
   then check **“I confirm the selected replacement is the approved ChatGPT
   Master Canonical Reference.”** This is Neill's already stated visual
   approval applied to the exact verified source file. Capture a screenshot.
4. Click **Save once**. Existing VSCS code coordinates registration of a legacy
   `Role=Primary`, `Status=Approved`, `Locked=True` canonical reference and
   the governed `MASTER`, origin `chatgpt_master`, lifecycle `LOCKED`. It does
   **not** approve the Draft CAP or resolve missing structured requirements.
5. Reopen Assets and CAP Gallery. Confirm file/path, `Locked canonical
   authority`, gallery MASTER `Role: Primary`, `Approved — Locked`, governed
   `MASTER — Locked`, provenance and version. The old local Candidate must
   remain a separate unregistered Supplementary Candidate.
6. Reopen CAP Readiness. The specific MASTER missing/lock blocker should
   resolve, but Front/Rear/Left/Right, CAP Approved, visual identity and
   structured capability/constraint blockers may remain. An automatic 100%
   readiness result is **FAIL** unless every independent gate is truly met.

### 3. Derived-reference acceptance (separate consent per generation)

1. Open **Canonical Profiles → `CAP-PRP-002` → Generate Production
   References**. Confirm `MASTER authority verified` and required views
   `MASTER`, `Front`, `Rear`, `Left`, `Right`; Top and Detail are recommended.
   The two Generate controls must only become usable once source authority
   is genuinely consistent. Opening the dialog does **not** make a GPU call.
2. **Stop for explicit provider/model/GPU and one-view-generation consent.**
   Do not click Generate Selected or Generate Missing Required Views merely
   because they are enabled. Initial supervised proposal: generate only Front,
   inspect and approve/reject, then proceed individually to other views.
3. Every new view must appear as a `Supplementary Candidate`, not as an
   already approved reference. Verify image features against this MASTER,
   inspect the model/seed/version/parent evidence and quality report, record
   independent human approval (or rejection and fresh correction consent).
4. Reopen the Gallery and CAP Readiness after each decision. Only explicitly
   approved required views count toward reference readiness. Neither a local
   Candidate's prior score nor a gallery-only Primary changes MASTER status.

### 4. Final evidence and safe stop

After closing VSCS capture AFTER hashes, current CAP/readiness/reference
counts, new MASTER/version and derived history. Separate **expected** new
Master/library/asset/source entries from **unexpected** changes to historical
Candidate 4, C2 masks, C2.1 reviews, saved evaluations, attempt counters and
asset-resolution bindings. Treat an unexpected mutation or missing provenance
as failure, not an invitation to hand-edit the project database.

In the same PowerShell session:

```powershell
$afterIssue61StageB = @(Get-Issue61ProtectedSnapshot -ProjectRoot $projectRoot)
$stageBChanges = @(
    Compare-Object -ReferenceObject $beforeIssue61StageB `
        -DifferenceObject $afterIssue61StageB -Property Path,SHA256
)
$stageBChanges | Format-Table -AutoSize
```

**Do not expect zero changes** after deliberately adding a MASTER. Review and
account for every changed path; accept only the specific new source and
governance/asset records the operator actually authorised. The test fails if
an existing protected Candidate or review record changed, even if the MASTER
registration succeeded.

**STOP before actual video clips.** The separately approved future workflow
for automated API-created MASTER Candidates is specified in
[Governed OpenAI MASTER generation v1.0](Governed_OpenAI_MASTER_Generation_Specification_V1.md) and tracked as
[Issue #67](https://github.com/npayne10/video_series_studio/issues/67). The
full VSCS outstanding-fix/UAT/end-to-end production backlog will be rebuilt
**after** this real reference lifecycle is proven, as Neill directed.
