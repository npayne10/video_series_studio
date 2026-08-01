"""Scene and Shot Intelligence Engine public API."""
from .builder import ProductionPlanBuilder, SSIEBuildError
from .models import (
    ProductionPlan,
    Scene,
    ScenePlan,
    SceneTransition,
    ShotPlan,
    ShotPurpose,
)
from .protocols import ScenePlanner, ShotPlanner
from .scene_planner import RuleBasedScenePlanner, ScenePlanningError
from .shot_planner import (
    PacingProfile,
    RuleBasedShotPlanner,
    ScenePurpose,
    ShotPlannerConfig,
    ShotPlanningAnalysis,
)
from .validator import (
    SSIEValidationIssue,
    SSIEValidationResult,
    SSIEValidationSeverity,
    SSIEValidator,
)

__all__ = [
    "PacingProfile",
    "ProductionPlan",
    "ProductionPlanBuilder",
    "RuleBasedScenePlanner",
    "RuleBasedShotPlanner",
    "SSIEBuildError",
    "SSIEValidationIssue",
    "SSIEValidationResult",
    "SSIEValidationSeverity",
    "SSIEValidator",
    "Scene",
    "ScenePlan",
    "ScenePlanner",
    "ScenePlanningError",
    "ScenePurpose",
    "SceneTransition",
    "ShotPlan",
    "ShotPlanner",
    "ShotPlannerConfig",
    "ShotPlanningAnalysis",
    "ShotPurpose",
]
