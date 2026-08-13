"""Reusable VSCS presentation widgets."""

from .production_planning_performance import install_production_planning_performance
from .story_analysis_workspace import StoryAnalysisWorkspaceDialog, StoryGraphView
from .story_intelligence_dashboard import StoryIntelligenceDashboardDialog

install_production_planning_performance()

__all__ = [
    "StoryAnalysisWorkspaceDialog",
    "StoryGraphView",
    "StoryIntelligenceDashboardDialog",
]
