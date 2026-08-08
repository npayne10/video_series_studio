# Phase 18.2.11.2.4 — Edit Selected completion

The Asset Manager exposes **Edit Selected** beside Add Asset. Asset ID remains immutable. Name, category, status, tags and description remain editable, and category changes require an explicit warning because they may affect later reference-template/readiness rules.

The Edit Asset dialog now also exposes **Browse…** beside **Master Canonical Reference**. This is a governed canonical action rather than a generic file-path edit:

- if the Asset has no MASTER, Browse can select the approved ChatGPT MASTER and VSCS seeds a Draft CAP if necessary, creates the structured reference, registers it as MASTER, approves it and locks it;
- if the Asset already has a MASTER, Browse proposes a new MASTER revision and requires explicit confirmation that the selected image is the approved ChatGPT master;
- the previous MASTER is archived rather than overwritten, and the new MASTER receives an incremented reference version;
- replacement is blocked while active derived references still depend on the current MASTER, preserving lineage and preventing silent continuity breakage;
- the Asset's stored MASTER path is updated only after the governed MASTER operation succeeds.

Canonical facts, visual identity, constraints, derived references and broader reference governance remain in **Canonical Profiles**, and the edit dialog retains **Open Canonical Profile** for that purpose.
