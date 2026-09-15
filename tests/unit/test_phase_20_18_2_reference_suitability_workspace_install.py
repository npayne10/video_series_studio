from __future__ import annotations

from vscs.presentation.widgets import universal_production_description_compiler_workspace
from vscs.presentation.widgets.governed_reference_suitability_workspace import (
    GovernedReferenceSuitabilityWorkspace,
)


def test_production_planning_uses_governed_reference_suitability_workspace() -> None:
    assert (
        universal_production_description_compiler_workspace.UniversalProductionDescriptionCompilerWorkspace
        is GovernedReferenceSuitabilityWorkspace
    )
