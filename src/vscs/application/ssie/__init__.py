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
from .shot_planner import RuleBasedShotPlanner
from .validator import (
    SSIEValidationIssue,
    SSIEValidationResult,
    SSIEValidationSeverity,
    SSIEValidator,
)

__all__ = [
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
    "SceneTransition",
    "ShotPlan",
    "ShotPlanner",
    "ShotPurpose",
]
