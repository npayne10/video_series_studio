"""Offline, traceable Story-to-CAP field candidates; never grants Canon authority.

Only text with approved Story authority may populate a missing required field.
This deliberately conservative extractor quotes source sentences; provider
inferences, Draft Shot text and unproved numerical dimensions remain proposals.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.context_preparation import CAPContextManifest, CAPContextSource
from vscs.application.caps.design_quality import DesignQualityIssue
from vscs.application.caps.provider_design_expansion import ProposedDesignField
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


class CAPFieldOrigin(StrEnum):
    STORY_CANDIDATE = "approved_story_candidate"
    MODEL_PROPOSAL = "model_proposal"
    OPERATOR_EDITED = "operator_edited"
    VERIFIED_SHOT = "verified_ready_shot"
    UNVERIFIED_SHOT = "unverified_shot"
    UNRESOLVED = "unresolved"


class CAPFieldProvenance(BaseModel):
    """One auditable advisory attribution, never an approved physical fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(min_length=1)
    value: str = ""
    origin: CAPFieldOrigin
    source_record_id: str = ""
    source_field: str = ""
    source_fingerprint: str = ""
    context_fingerprint: str = ""
    excerpt: str = ""
    shot_authority: str = ""
    shot_record_id: str = ""
    shot_field: str = ""
    shot_fingerprint: str = ""
    shot_excerpt: str = ""
    note: str = ""


# Keep source-based recommendations intentionally narrow. Category-specific
# requirements are owned by completeness.REQUIRED_FIELDS, not a second schema.
_MATERIAL = re.compile(
    r"\b(?:made of|constructed of|fabricated from|metal|steel|alumini?um|"
    r"alloy|graphite[- ]coated|powder[- ]coated|composite|plastic|polymer|"
    r"wood|glass|ceramic|elastomer|rubber)\b",
    re.IGNORECASE,
)
_PART = re.compile(
    r"\b(?:displays?|screens?|buttons?|dial|controls?|shelf|grips?|panels?|"
    r"worktop|frame|legs?|foot|feet|switch|knob|indicator|lettering|logos?|brands?)\b",
    re.IGNORECASE,
)
_GEOMETRY = re.compile(
    r"\b(?:rectangular|upright|horizontal|vertical|rounded|chamfer|"
    r"recess|ribbed|freestanding|shape|silhouette|housing|frame)\b",
    re.IGNORECASE,
)
_LIGHTING = re.compile(r"\b(?:light|lighting|illumination|lit|diffuse|overhead)\b", re.I)
_LAYOUT = re.compile(
    r"\b(?:room|bay|beside|separate|apart|to one side|contains|aboard|"
    r"located|stands|stationed|adjacent|unoccupied)\b",
    re.IGNORECASE,
)
_LOCATION_SURFACE = re.compile(r"\b(?:wall|ceiling|floor|panel|room|bay)\b", re.I)
_ROOM_SCOPE = re.compile(r"\b(?:room|bay|interior|chamber|compartment)\b", re.I)
_DIMENSION = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|metres?|meters?|ft|feet)\b",
    re.IGNORECASE,
)
_SIZE = re.compile(r"\b(?:width|height|depth|length|footprint|diameter|dimensions)\b", re.I)
_VESSEL = re.compile(r"\b(?:ship|vessel|hull|starship|spacecraft)\b", re.I)
_CONTAINED = re.compile(r"\b(?:bay|room|interior|workstation|console)\b", re.I)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_NAMED_PHYSICAL_PROPS = ("console", "workstation", "table", "robot", "camera")


def _asset_aliases(name: str, category: AssetCategory) -> tuple[str, ...]:
    # Long asset name preferred, generic aliases only for physical categories.
    words = re.findall(r"[\w-]+", name.casefold())
    aliases = [" ".join(words)] if words else []
    if category is AssetCategory.LOCATION:
        aliases.extend(("bay", "room", "interior"))
    elif category is AssetCategory.SHIP:
        aliases.extend(("ship", "vessel", "spacecraft"))
    elif category is AssetCategory.PROP:
        aliases.extend(word for word in words if word in {"console", "workstation", "table"})
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def _paragraphs(source: CAPContextSource, aliases: tuple[str, ...]) -> tuple[str, ...]:
    blocks = tuple(block.strip() for block in re.split(r"\n\s*\n", source.excerpt) if block.strip())
    return tuple(
        block
        for block in blocks
        if any(re.search(rf"\b{re.escape(alias)}\b", block, re.I) for alias in aliases)
    )


def _field_sentences(
    category: AssetCategory,
    field: str,
    paragraph: str,
    aliases: tuple[str, ...],
) -> tuple[str, ...]:
    sentences = tuple(s.strip() for s in _SENTENCE_BOUNDARY.split(paragraph) if s.strip())
    selected: list[str] = []
    target_active = False
    target_terms = {word for alias in aliases for word in alias.split()}
    for sentence in sentences:
        match = False
        if category in {AssetCategory.PROP, AssetCategory.TECHNOLOGY}:
            # Approved Story paragraphs often describe multiple adjacent props.
            # Preserve anaphoric 'Its front...' sentences only while the named
            # target is the active subject; never inherit a neighbour's design.
            names = tuple(
                name
                for name in _NAMED_PHYSICAL_PROPS
                if re.search(rf"\b{re.escape(name)}\b", sentence, re.I)
            )
            is_target = any(
                re.search(rf"\b{re.escape(alias)}\b", sentence, re.I) for alias in aliases
            )
            if names:
                target_active = bool(is_target and all(name in target_terms for name in names))
            elif is_target:
                target_active = True
            if not target_active:
                continue
            if field == "materials":
                match = bool(_MATERIAL.search(sentence))
            elif field == "components":
                match = bool(_PART.search(sentence))
            elif field == "geometry":
                match = bool(_GEOMETRY.search(sentence))
            elif field == "scale":
                match = bool(_SIZE.search(sentence) and _DIMENSION.search(sentence))
        elif category is AssetCategory.LOCATION:
            if field == "layout":
                match = bool(_LAYOUT.search(sentence))
            elif field == "lighting":
                match = bool(_LIGHTING.search(sentence))
            elif field == "materials":
                # 'Grey panels' gives a colour, *not* a material. A console's
                # metal housing does not establish the room's wall material.
                match = bool(
                    _MATERIAL.search(sentence)
                    and _LOCATION_SURFACE.search(sentence)
                    and not re.search(r"\b(?:console|workstation)\b", sentence, re.I)
                )
            elif field == "scale":
                # A console measurement mentioned in the bay paragraph does
                # not establish the bay's overall room dimensions.
                match = bool(
                    _ROOM_SCOPE.search(sentence)
                    and _SIZE.search(sentence)
                    and _DIMENSION.search(sentence)
                    and not re.search(r"\b(?:console|workstation)\b", sentence, re.I)
                )
        elif category is AssetCategory.SHIP:
            if field == "hull":
                match = bool(
                    _VESSEL.search(sentence)
                    and _MATERIAL.search(sentence)
                    and not _CONTAINED.search(sentence)
                )
            elif field == "silhouette":
                match = bool(
                    _VESSEL.search(sentence)
                    and _GEOMETRY.search(sentence)
                    and not _CONTAINED.search(sentence)
                )
            elif field == "dimensions":
                match = bool(
                    _VESSEL.search(sentence)
                    and _DIMENSION.search(sentence)
                    and not _CONTAINED.search(sentence)
                )
        if match:
            selected.append(sentence)
    return tuple(selected)


def _story_candidate(
    manifest: CAPContextManifest,
    asset_name: str,
    category: AssetCategory,
    field: str,
) -> CAPFieldProvenance | None:
    aliases = _asset_aliases(asset_name, category)
    # Prefer exact source text to the short Story description and never consume
    # unverified Shot excerpts as approved physical authority.
    sources = sorted(
        (s for s in manifest.sources if s.authority == "approved_story_context"),
        key=lambda s: (s.field != "source_text", s.field),
    )
    for source in sources:
        for paragraph in _paragraphs(source, aliases):
            sentences = _field_sentences(category, field, paragraph, aliases)
            if sentences:
                # Extract the exact sentences, without model paraphrase or new units.
                value = " ".join(sentences)
                return CAPFieldProvenance(
                    field=field,
                    value=value,
                    origin=CAPFieldOrigin.STORY_CANDIDATE,
                    source_record_id=source.record_id,
                    source_field=source.field,
                    source_fingerprint=source.fingerprint,
                    context_fingerprint=manifest.fingerprint,
                    excerpt=paragraph,
                    note="Verbatim approved Story candidate; operator must verify asset scope.",
                )
    return None


def _shot_candidate(
    manifest: CAPContextManifest,
    asset_name: str,
    category: AssetCategory,
    field: str,
) -> CAPFieldProvenance | None:
    """Expose Shot scope without ever auto-filling a canonical design field."""
    for source in manifest.sources:
        if source.authority not in {"verified_ready_shot", "unverified_shot"}:
            continue
        aliases = _asset_aliases(asset_name, category)
        for paragraph in _paragraphs(source, aliases):
            sentences = _field_sentences(category, field, paragraph, aliases)
            if sentences:
                value = " ".join(sentences)
                return CAPFieldProvenance(
                    field=field,
                    value=value,
                    origin=(
                        CAPFieldOrigin.VERIFIED_SHOT
                        if source.authority == "verified_ready_shot"
                        else CAPFieldOrigin.UNVERIFIED_SHOT
                    ),
                    source_record_id=source.record_id,
                    source_field=source.field,
                    source_fingerprint=source.fingerprint,
                    context_fingerprint=manifest.fingerprint,
                    excerpt=paragraph,
                    note="Shot-only context, never approved Story design authority.",
                )
    return None


def _with_shot_trace(
    primary: CAPFieldProvenance, shot: CAPFieldProvenance | None
) -> CAPFieldProvenance:
    if shot is None:
        return primary
    return primary.model_copy(
        update={
            "shot_authority": shot.origin.value,
            "shot_record_id": shot.source_record_id,
            "shot_field": shot.source_field,
            "shot_fingerprint": shot.source_fingerprint,
            "shot_excerpt": shot.value,
        }
    )


def reconcile_grounded_fields(
    specification: CAPStructuredSpecification,
    asset_name: str,
    manifest: CAPContextManifest,
    suggestions: tuple[ProposedDesignField, ...],
) -> tuple[
    CAPStructuredSpecification, tuple[CAPFieldProvenance, ...], tuple[DesignQualityIssue, ...]
]:
    """Fill only missing supported required fields, with source-bound proof.

    Existing proposal or operator-edited fields are not overwritten. The
    caller may store the result in the advisory cache; no CAP/Canon writes.
    """
    if manifest.asset_id != specification.asset_id:
        raise ValueError("Story grounding asset does not match the CAP proposal")
    required = REQUIRED_FIELDS.get(specification.category, ("identity",))
    attributes = dict(specification.canonical_attributes)
    choices = {item.field: item for item in suggestions}
    evidence: list[CAPFieldProvenance] = []
    issues: list[DesignQualityIssue] = []
    for field in dict.fromkeys((*required, *attributes, *choices)):
        story = _story_candidate(manifest, asset_name, specification.category, field)
        shot = _shot_candidate(manifest, asset_name, specification.category, field)
        current = attributes.get(field, "").strip()
        if not current and story is not None:
            # The value is an unapproved candidate, not a CAP specification save.
            attributes[field] = story.value
            evidence.append(_with_shot_trace(story, shot))
        elif current:
            # Model's bundled identity prose is not automatically Story canon.
            is_verbatim = bool(story and current in story.excerpt)
            source_provenance = (
                story.model_copy(update={"value": current})
                if is_verbatim and story is not None
                else CAPFieldProvenance(
                    field=field,
                    value=current,
                    origin=CAPFieldOrigin.MODEL_PROPOSAL,
                    context_fingerprint=manifest.fingerprint,
                    note="Existing unapproved proposal; precise Story support not proven.",
                )
            )
            evidence.append(_with_shot_trace(source_provenance, shot))
        elif field in choices:
            suggestion = choices[field]
            evidence.append(
                _with_shot_trace(
                    CAPFieldProvenance(
                        field=field,
                        value=suggestion.proposed_value,
                        origin=CAPFieldOrigin.MODEL_PROPOSAL,
                        context_fingerprint=manifest.fingerprint,
                        note=suggestion.rationale,
                    ),
                    shot,
                )
            )
        else:
            evidence.append(
                shot
                or CAPFieldProvenance(
                    field=field,
                    origin=CAPFieldOrigin.UNRESOLVED,
                    context_fingerprint=manifest.fingerprint,
                    note="No supported required attribute; defer unless reviewed evidence emerges.",
                )
            )
        if field in {"scale", "dimensions"} and (field in choices or current):
            proposal = choices[field].proposed_value if field in choices else current
            # A size mentioned elsewhere in the Story may refer to a different
            # physical asset, so compare with *this* asset's scoped candidate.
            approved_text = story.value if story is not None else ""
            proposed_units = set(_DIMENSION.findall(proposal.casefold()))
            if proposed_units and not proposed_units.issubset(
                set(_DIMENSION.findall(approved_text.casefold()))
            ):
                issues.append(
                    DesignQualityIssue(
                        field,
                        "unsourced_measurement",
                        "Proposed numerical dimensions are absent from approved Story; "
                        "Defer unless separately reviewed as design choices.",
                    )
                )
        if (
            specification.category is AssetCategory.SHIP
            and field == "dimensions"
            and field in choices
            and _CONTAINED.search(choices[field].proposed_value)
        ):
            issues.append(
                DesignQualityIssue(
                    field,
                    "contained_asset_scope",
                    "Proposed dimensions describe a room or contained object, not the ship; "
                    "do not assign them as overall vessel dimensions.",
                )
            )
    if "geometry" in attributes and "components" in choices:
        geometry = attributes["geometry"].casefold()
        if "unresolved" in geometry or "not specified" in geometry:
            issues.append(
                DesignQualityIssue(
                    "geometry",
                    "cross_field_inconsistency",
                    "Geometry is unresolved while proposed components describe physical form; "
                    "review their consistency without promoting invented hardware.",
                )
            )
    updated = specification.model_copy(update={"canonical_attributes": attributes})
    updated.validate_category_contract()
    return updated, tuple(evidence), tuple(issues)
