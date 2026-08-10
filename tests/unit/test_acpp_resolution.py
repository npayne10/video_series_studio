"""Tests for ACPP asset, CAP, reference, and behaviour resolution."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.acpp import (
    ACPPResolutionError,
    ACPPResolverConfig,
    ACPPResourceResolver,
    AssetBinding,
    AssetBindingRole,
    AssetResolutionRecord,
    AudioSpecification,
    BehaviourResolutionRecord,
    CanonicalReferenceResolution,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderSpecification,
    ResolutionSeverity,
)


class AssetCatalog:
    """Small deterministic asset catalog used by resolver tests."""

    def __init__(self, records: dict[str, AssetResolutionRecord]) -> None:
        self.records = records

    def resolve_asset(self, asset_id: str) -> AssetResolutionRecord | None:
        return self.records.get(asset_id)


class BehaviourCatalog:
    """Small deterministic behaviour catalog used by resolver tests."""

    def __init__(self, records: dict[str, BehaviourResolutionRecord]) -> None:
        self.records = records

    def resolve_behaviour(self, package_id: str) -> BehaviourResolutionRecord | None:
        return self.records.get(package_id)


def _package(*, optional_missing: bool = False) -> ClipProductionPackage:
    assets = [
        AssetBinding(
            asset_id="LOC-MAURITANIA-BRIDGE",
            role=AssetBindingRole.LOCATION,
        ),
        AssetBinding(
            asset_id="CHR-JAMES",
            role=AssetBindingRole.SUBJECT,
            behaviour_package_ids=("BHV-COMMAND-PRESENCE",),
        ),
    ]
    if optional_missing:
        assets.append(
            AssetBinding(
                asset_id="PROP-OPTIONAL-DISPLAY",
                role=AssetBindingRole.PROP,
                required=False,
            )
        )
    return ClipProductionPackage(
        identity=ClipIdentity(
            clip_id="PROD-XORIX-SC002-SH004-CL001",
            production_id="PROD-XORIX",
            episode_id="EP-001",
            scene_id="SCN-002",
            shot_id="SCN-002-S004",
        ),
        render=RenderSpecification(
            width=1920,
            height=800,
            frames_per_second=24,
            frame_count=240,
        ),
        assets=tuple(assets),
        prompt=PromptSpecification(
            positive_visual_intent="James holds position on the bridge.",
        ),
        continuity=ContinuityBinding(),
        audio=AudioSpecification(),
        output=OutputSpecification(
            relative_directory="production/EP-001/SCN-002",
            filename_stem="PROD-XORIX-SC002-SH004-CL001",
        ),
    )


def _asset_records() -> dict[str, AssetResolutionRecord]:
    return {
        "LOC-MAURITANIA-BRIDGE": AssetResolutionRecord(
            asset_id="LOC-MAURITANIA-BRIDGE",
            cap_id="CAP-LOC-001",
            cap_version="2.0",
            cap_approved=True,
            canonical_references=(
                CanonicalReferenceResolution(
                    reference_id="REF-BRIDGE-PRIMARY",
                    path="assets/reference/bridge-primary.png",
                    role="primary",
                    checksum="bridge-checksum",
                ),
                CanonicalReferenceResolution(
                    reference_id="REF-BRIDGE-SECONDARY",
                    path="assets/reference/bridge-secondary.png",
                    role="secondary",
                ),
            ),
            checksum="cap-bridge-checksum",
        ),
        "CHR-JAMES": AssetResolutionRecord(
            asset_id="CHR-JAMES",
            cap_id="CAP-CHR-001",
            cap_version="3.1",
            cap_approved=True,
            canonical_references=(
                CanonicalReferenceResolution(
                    reference_id="REF-JAMES-PRIMARY",
                    path="assets/reference/james-primary.png",
                    role="primary",
                ),
            ),
        ),
    }


def _behaviour_records() -> dict[str, BehaviourResolutionRecord]:
    return {
        "BHV-COMMAND-PRESENCE": BehaviourResolutionRecord(
            package_id="BHV-COMMAND-PRESENCE",
            version="1.2",
            structurally_valid=True,
            manifest_path="assets/behaviours/command-presence/behaviour.json",
            prompt_package_ids=("PRM-COMMAND-STANCE",),
            dependency_ids=("TECH-GUILD-UNIFORM",),
            checksum="behaviour-checksum",
        )
    }


def _resolver(
    *,
    assets: dict[str, AssetResolutionRecord] | None = None,
    behaviours: dict[str, BehaviourResolutionRecord] | None = None,
    config: ACPPResolverConfig | None = None,
) -> ACPPResourceResolver:
    return ACPPResourceResolver(
        AssetCatalog(_asset_records() if assets is None else assets),
        BehaviourCatalog(_behaviour_records() if behaviours is None else behaviours),
        config,
    )


def test_resolver_enriches_asset_and_behaviour_bindings() -> None:
    result = _resolver().resolve(_package())

    assert result.passed is True
    assert result.diagnostics == ()
    bindings = {binding.asset_id: binding for binding in result.package.assets}
    assert bindings["LOC-MAURITANIA-BRIDGE"].canonical_reference_ids == (
        "REF-BRIDGE-PRIMARY",
        "REF-BRIDGE-SECONDARY",
    )
    assert bindings["CHR-JAMES"].canonical_reference_ids == ("REF-JAMES-PRIMARY",)
    assert bindings["CHR-JAMES"].behaviour_package_ids == ("BHV-COMMAND-PRESENCE",)
    assert "TECH-GUILD-UNIFORM" in result.package.dependencies
    assert result.package.metadata["resolution.status"] == "resolved"


def test_resolver_records_cap_reference_behaviour_and_prompt_provenance() -> None:
    result = _resolver().resolve(_package())
    provenance = {(item.resource_type, item.resource_id) for item in result.provenance}

    assert ("cap", "CAP-LOC-001") in provenance
    assert ("canonical_reference", "REF-BRIDGE-PRIMARY") in provenance
    assert ("behaviour_package", "BHV-COMMAND-PRESENCE") in provenance
    assert ("prompt_package", "PRM-COMMAND-STANCE") in provenance


def test_missing_required_asset_fails_resolution() -> None:
    records = _asset_records()
    del records["CHR-JAMES"]

    result = _resolver(assets=records).resolve(_package())

    assert result.passed is False
    assert result.package.metadata["resolution.status"] == "failed"
    assert any(
        item.code == "ASSET_NOT_RESOLVED" and item.severity is ResolutionSeverity.ERROR
        for item in result.diagnostics
    )


def test_missing_optional_asset_is_a_warning() -> None:
    result = _resolver().resolve(_package(optional_missing=True))

    assert result.passed is True
    warning = next(item for item in result.diagnostics if item.code == "ASSET_NOT_RESOLVED")
    assert warning.severity is ResolutionSeverity.WARNING


def test_invalid_behaviour_is_reported_and_can_raise() -> None:
    invalid = replace(
        _behaviour_records()["BHV-COMMAND-PRESENCE"],
        structurally_valid=False,
    )
    resolver = _resolver(behaviours={invalid.package_id: invalid})

    result = resolver.resolve(_package())

    assert result.passed is False
    assert any(item.code == "BEHAVIOUR_INVALID" for item in result.diagnostics)
    with pytest.raises(ACPPResolutionError) as error:
        resolver.resolve(_package(), raise_on_error=True)
    assert error.value.result == result


def test_policy_can_select_only_primary_references() -> None:
    resolver = _resolver(config=ACPPResolverConfig(include_secondary_references=False))

    result = resolver.resolve(_package())
    bridge = next(
        binding for binding in result.package.assets if binding.asset_id == "LOC-MAURITANIA-BRIDGE"
    )

    assert bridge.canonical_reference_ids == ("REF-BRIDGE-PRIMARY",)
