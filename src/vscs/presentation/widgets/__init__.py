"""Reusable VSCS presentation widgets."""

from typing import Any, cast

from . import universal_production_description_compiler_workspace as _universal_workspace
from .governed_reference_suitability_workspace import GovernedReferenceSuitabilityWorkspace
from .production_package_review_workspace import (
    install_production_package_review_workspace,
)
from .production_planning_performance import install_production_planning_performance
from .production_planning_profiler import install_production_planning_profiler
from .scheduling_review_reset import install_scheduling_review_reset
from .story_analysis_workspace import StoryAnalysisWorkspaceDialog, StoryGraphView
from .story_intelligence_dashboard import StoryIntelligenceDashboardDialog

install_production_package_review_workspace()
install_production_planning_performance()
install_production_planning_profiler()
install_scheduling_review_reset()

# Production Planning extensions above patch the original Universal workspace. The
# suitability-aware subclass inherits those installed behaviours and then becomes the
# public workspace type consumed by story_integration and later installers.
workspace_module = cast(Any, _universal_workspace)
workspace_module.UniversalProductionDescriptionCompilerWorkspace = (
    GovernedReferenceSuitabilityWorkspace
)

__all__ = [
    "StoryAnalysisWorkspaceDialog",
    "StoryGraphView",
    "StoryIntelligenceDashboardDialog",
]
