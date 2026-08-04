"""Tests for hierarchical continuity-state contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vscs.application.rendering import (
    ContinuityEntityKind,
    ContinuityFrameReference,
    ContinuityPackage,
    ContinuityScope,
    ContinuityStateRegistry,
    EntityContinuityState,
    ScopedContinuityState,
)


def _entity(entity_id: str, uniform: str) -> EntityContinuityState:
    return EntityContinuityState(
        entity_id=entity_id,
        kind=ContinuityEntityKind.CHARACTER,
        canonical_asset_id=entity_id,
        state_values=(("uniform", uniform),),
        mandatory_traits=("approved facial identity",),
        prohibited_changes=("no costume changes",),
    )


def test_continuity_package_resolves_narrower_scope_overrides() -> None:
    series = ScopedContinuityState(
        state_id="SERIES-XORIX",
        scope=ContinuityScope.SERIES,
        production_id="XORIX",
        entities=(_entity("CHR-JAMES", "Guild command uniform"),),
    )
    shot = ScopedContinuityState(
        state_id="SHOT-001",
        scope=ContinuityScope.SHOT,
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        entities=(_entity("CHR-JAMES", "Guild EVA suit"),),
    )
    package = ContinuityPackage(
        package_id="CONT-SHT-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        series_state=series,
        shot_state=shot,
        previous_frame=ContinuityFrameReference(
            reference_id="FRAME-0001",
            relative_path="continuity/shot-000/end.png",
            frame_number=239,
        ),
    )

    resolved = package.resolved_entities()
    assert len(resolved) == 1
    assert resolved[0].value("uniform") == "Guild EVA suit"
    assert package.previous_frame is not None


def test_continuity_scope_and_reference_paths_are_validated() -> None:
    with pytest.raises(ValueError, match="scene_id"):
        ScopedContinuityState(
            state_id="SCENE-BAD",
            scope=ContinuityScope.SCENE,
            production_id="XORIX",
            container_id="EP-001",
        )
    with pytest.raises(ValueError, match="project-relative"):
        ContinuityFrameReference(
            reference_id="FRAME-BAD",
            relative_path="../outside.png",
        )


def test_continuity_registry_and_models_are_stable() -> None:
    state = ScopedContinuityState(
        state_id="EP-001",
        scope=ContinuityScope.EPISODE,
        production_id="XORIX",
        container_id="EP-001",
    )
    registry = ContinuityStateRegistry()
    registry.register(state)

    assert registry.get("EP-001") is state
    assert registry.list(ContinuityScope.EPISODE) == (state,)
    with pytest.raises(FrozenInstanceError):
        state.state_id = "CHANGED"  # type: ignore[misc]
