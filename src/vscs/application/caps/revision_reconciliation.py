"""Offline, source-grounded reconciliation after a human CAP design revision."""

from __future__ import annotations

import json
from dataclasses import dataclass

from vscs.application.caps.design_revision import REVISION_HISTORY_KEY, REVISION_REFRESH_KEY
from vscs.application.caps.review_snapshot import load_review_snapshot
from vscs.application.caps.structured_knowledge import StructuredKnowledgeProposal
from vscs.domain.caps import (
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    StructuredCAPKnowledge,
)

REVISION_RECONCILED_KEY = "vscs.cap_design_revision_reconciled.v1"


@dataclass(frozen=True)
class CAPRevisionReconciliation:
    """An in-memory, human-reviewable replacement; does not persist anything."""

    knowledge: StructuredCAPKnowledge
    visual_identity: str
    production_notes: str
    changes: tuple[tuple[str, str, str], ...]
    fingerprint: str


def plan_revision_reconciliation(
    metadata: dict[str, str],
    existing: StructuredCAPKnowledge,
    proposal: StructuredKnowledgeProposal,
    visual_identity: str,
    production_notes: str,
) -> CAPRevisionReconciliation:
    """Replace exact superseded reviewed values; leave unrelated authored data alone.

    Ambiguous modified entries are rejected instead of silently overwriting an
    operator's previously approved work.
    """
    spec, review, diagnostic = load_review_snapshot(metadata)
    if spec is None or review is None:
        raise ValueError(f"No verifiable revised design: {diagnostic}")
    refresh = json.loads(metadata.get(REVISION_REFRESH_KEY, "null"))
    history = json.loads(metadata.get(REVISION_HISTORY_KEY, "[]"))
    if not isinstance(refresh, dict) or not isinstance(history, list) or not history:
        raise ValueError("No pending design revision reconciliation")
    prior = json.loads(metadata.get(REVISION_RECONCILED_KEY, "null"))
    completed = prior.get("history_count", 0) if isinstance(prior, dict) else 0
    if not isinstance(completed, int) or completed < 0 or completed >= len(history):
        raise ValueError("Revision reconciliation history is inconsistent")
    if refresh.get("specification_fingerprint") != spec.fingerprint():
        raise ValueError("Design revision changed; reopen and prepare the current proposal")
    if proposal.asset_id != spec.asset_id or proposal.source_summary != (
        f"reviewed-cap-specification:{spec.fingerprint()}"
    ):
        raise ValueError("Offline proposal is not bound to the current reviewed specification")

    changes: list[tuple[str, str, str]] = []
    replacements: dict[str, tuple[str, str]] = {}
    for record in history[completed:]:
        if not isinstance(record, dict):
            raise ValueError("Corrupt revision history")
        key, old = record.get("field"), record.get("old_value")
        if not isinstance(key, str) or not isinstance(old, str):
            raise ValueError("Incomplete revision history")
        if key not in spec.canonical_attributes:
            raise ValueError("Revised field is no longer accepted")
        new = spec.canonical_attributes[key]
        # Multiple revisions of one field may have occurred before reconciliation.
        replacements.setdefault(key, (old, new))
    for key, (old, _) in tuple(replacements.items()):
        replacements[key] = (old, spec.canonical_attributes[key])

    facts_by_key = {item.key: item for item in existing.facts}
    proposed_facts = {item.key: item for item in proposal.knowledge.facts}
    for key, (old, new) in replacements.items():
        previous = facts_by_key.get(key)
        if previous is not None:
            if previous.value != old and previous.value != new:
                raise ValueError(f"Conflicting authored fact '{key}'; reconcile it independently")
            if previous.value != new:
                changes.append((f"Fact: {key}", previous.value, new))
        current = proposed_facts.get(key)
        if current is None or current.value != new:
            raise ValueError(f"No verified current proposal for field '{key}'")
        facts_by_key[key] = current.model_copy(update={"authority": KnowledgeAuthority.APPROVED})

    constraints: list[PersistedCanonicalConstraint] = []
    for item in existing.constraints:
        superseded = False
        for key, (old, new) in replacements.items():
            if item.rule == f"Preserve reviewed {key}: {old}":
                if not item.source.startswith("reviewed-cap-specification:"):
                    raise ValueError(
                        f"Conflicting authored constraint '{key}'; reconcile it independently"
                    )
                changes.append((f"Constraint: {key}", item.rule, f"Preserve reviewed {key}: {new}"))
                superseded = True
                break
        if not superseded:
            constraints.append(item)
    for key in replacements:
        match = next(
            (
                item
                for item in proposal.knowledge.constraints
                if item.rule == f"Preserve reviewed {key}: {spec.canonical_attributes[key]}"
            ),
            None,
        )
        if match is None:
            raise ValueError(f"No verified replacement constraint for '{key}'")
        if not any(item.rule == match.rule and item.kind == match.kind for item in constraints):
            constraints.append(match.model_copy(update={"authority": KnowledgeAuthority.APPROVED}))

    def replace_guidance(label: str, text: str) -> str:
        revised = text
        for key, (old, new) in replacements.items():
            # Only generated, exact field-bound lines are eligible for replacement.
            prefixes = (
                f"{key.replace('_', ' ').title()}: ",
                f"Preserve reviewed {key.replace('_', ' ')}: ",
            )
            for prefix in prefixes:
                before, after = prefix + old, prefix + new
                if before in revised:
                    revised = revised.replace(before, after)
                    changes.append((label, before, after))
            # Retain unrelated prose, but never silently accept obsolete reviewed text.
            if old != new and old in revised:
                raise ValueError(f"{label} has an ambiguous old requirement; review it manually")
        return revised

    identity = replace_guidance("Visual Identity", visual_identity)
    notes = replace_guidance("Production Notes", production_notes)
    if not identity.strip():
        identity = proposal.visual_identity
        changes.append(("Visual Identity", "(empty)", identity))
    if not notes.strip():
        notes = proposal.production_notes
        changes.append(("Production Notes", "(empty)", notes))

    return CAPRevisionReconciliation(
        knowledge=existing.model_copy(
            update={
                "facts": tuple(facts_by_key.values()),
                "constraints": tuple(constraints),
            }
        ),
        visual_identity=identity,
        production_notes=notes,
        changes=tuple(changes),
        fingerprint=spec.fingerprint(),
    )
