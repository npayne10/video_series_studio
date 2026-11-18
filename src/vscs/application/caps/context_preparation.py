"""Offline, source-scoped CAP context assembly; no generation or authority promotion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.governed_planning_evidence import (
    ProductionPlanningContracts,
    discover_governed_shot_evidence,
    verified_governed_shot_evidence,
)


@dataclass(frozen=True)
class CAPContextSource:
    source_type: str
    record_id: str
    field: str
    excerpt: str
    authority: str
    fingerprint: str


@dataclass(frozen=True)
class CAPContextManifest:
    story_id: str
    asset_id: str
    story_fingerprint: str
    asset_fingerprint: str
    sources: tuple[CAPContextSource, ...]
    warnings: tuple[str, ...]
    fingerprint: str


def _digest(*items: object) -> str:
    encoded = json.dumps(items, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def assert_unique_planning_ownership(project_root: Path) -> None:
    """Fail closed when repeated plan IDs could link different Stories together."""
    for name, key, identity in (
        ("episode_plans.json", "episodes", "episode_id"),
        ("scene_plans.json", "scenes", "scene_id"),
        ("shot_plans.json", "shots", "shot_id"),
    ):
        path = project_root / "planning" / name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload[key]
            if not isinstance(records, list):
                raise ValueError("Invalid planning records")
            ids = [str(item[identity]) for item in records]
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise ShotTextAuthorityError(f"Invalid governed source: {name}") from exc
        if len(ids) != len(set(ids)):
            raise ShotTextAuthorityError(f"Ambiguous planning ownership: {name}")


def prepare_cap_context(
    project_root: Path,
    story_id: str,
    asset_id: str,
    story_description: str,
    story_fingerprint: str,
    asset_fingerprint: str,
    *,
    approved_story_source: str = "",
) -> CAPContextManifest:
    """Report source provenance without making Draft Shot text approved evidence.

    Caller must check approved Story authority and registered asset membership.
    Discovery establishes structural scope; real production contracts alone
    determine whether Shot narratives are verified.
    """
    assert_unique_planning_ownership(project_root)
    discovered = discover_governed_shot_evidence(project_root, story_id)
    linked = tuple(item for item in discovered.candidates if asset_id in item.bound_asset_ids)
    if not linked:
        raise ValueError(f"{asset_id}: no governed Shot binding in {story_id}")
    sources: list[CAPContextSource] = []
    if story_description.strip():
        sources.append(
            CAPContextSource(
                "approved_story",
                story_id,
                "description",
                story_description.strip(),
                "approved_story_context",
                _digest(story_id, story_fingerprint, story_description.strip()),
            )
        )
    if approved_story_source.strip():
        sources.append(
            CAPContextSource(
                "approved_story",
                story_id,
                "source_text",
                approved_story_source.strip(),
                "approved_story_context",
                _digest(story_id, story_fingerprint, approved_story_source.strip()),
            )
        )
    warnings = list(discovered.warnings[:-1])
    verified_by_id: dict[str, object] = {}
    try:
        verified = verified_governed_shot_evidence(
            project_root, story_id, ProductionPlanningContracts()
        )
        verified_by_id = {
            item.shot_id: item for item in verified if asset_id in item.bound_asset_ids
        }
    except (ShotTextAuthorityError, KeyError, TypeError, ValueError) as exc:
        warnings.append(f"Shot evidence unverified: {exc}")
    for shot in sorted(linked, key=lambda item: (item.episode_id, item.scene_id, item.shot_id)):
        authority = (
            "verified_ready_shot" if verified_by_id.get(shot.shot_id) == shot else "unverified_shot"
        )
        if authority == "unverified_shot" and not any(
            item.startswith("Shot evidence unverified:") for item in warnings
        ):
            warnings.append(f"{shot.shot_id}: Shot evidence is not verified")
        for field, excerpt in shot.text_fields:
            sources.append(
                CAPContextSource(
                    "governed_shot",
                    shot.shot_id,
                    field,
                    excerpt,
                    authority,
                    _digest(shot.shot_id, field, excerpt, shot.contract_hashes, authority),
                )
            )
    ordered = tuple(sources)
    fingerprint = _digest(
        story_id,
        asset_id,
        story_fingerprint,
        asset_fingerprint,
        [(item.source_type, item.record_id, item.field, item.fingerprint) for item in ordered],
        [(shot.shot_id, shot.contract_hashes, shot.binding_statuses) for shot in linked],
        tuple(dict.fromkeys(warnings)),
    )
    return CAPContextManifest(
        story_id,
        asset_id,
        story_fingerprint,
        asset_fingerprint,
        ordered,
        tuple(dict.fromkeys(warnings)),
        fingerprint,
    )


def render_approved_story_context(manifest: CAPContextManifest) -> str:
    """Render only approved Story authority for grounding and design validation."""
    approved = tuple(
        source for source in manifest.sources if source.authority == "approved_story_context"
    )
    if not approved:
        raise ValueError("CAP provider context has no approved Story source")
    return "\n\n".join(
        f"APPROVED STORY {source.record_id}.{source.field}:\n{source.excerpt}"
        for source in approved
    )


def render_cap_provider_context(manifest: CAPContextManifest) -> str:
    """Pass approved Story evidence and explicitly non-canonical Shot intent to AI."""
    approved = render_approved_story_context(manifest)
    supporting = tuple(
        source for source in manifest.sources if source.authority != "approved_story_context"
    )
    parts = [
        "Propose canonical design features only when supported by the APPROVED STORY "
        "or the registered asset description. Shot planning below is supporting "
        "context; unverified Shot evidence does not establish canonical geometry.",
        f"Selected asset: {manifest.asset_id}. Story: {manifest.story_id}.",
        approved,
    ]
    for source in supporting:
        label = (
            "VERIFIED READY SHOT"
            if source.authority == "verified_ready_shot"
            else "UNVERIFIED SHOT - NOT CANON"
        )
        parts.append(f"{label} {source.record_id}.{source.field}:\n{source.excerpt}")
    return "\n\n".join(parts)
