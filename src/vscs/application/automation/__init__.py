"""Public contracts for governed VSCS production automation."""

from .action_performance import (
    ActionPerformanceProposalAutomationService,
    ActionPerformanceProposalDraft,
    ActionPerformanceProposalProvider,
    TemplateActionPerformanceProposalProvider,
)
from .camera_lighting import (
    CameraLightingProposalAutomationService,
    CameraLightingProposalDraft,
    CameraLightingProposalProvider,
    CameraProposalDraft,
    LightingProposalDraft,
    TemplateCameraLightingProposalProvider,
)
from .canonical_entity import CanonicalEntityAssetResolutionAutomationService
from .continuity import ContinuityProposalAutomationService
from .contracts import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    SemanticProductionProvider,
    TemplateSemanticProductionProvider,
)
from .environment import (
    EnvironmentProposalAutomationService,
    EnvironmentProposalDraft,
    EnvironmentProposalProvider,
    TemplateEnvironmentProposalProvider,
)
from .episode_scene import (
    EpisodeProposalDraft,
    EpisodeSceneProposalAutomationService,
    EpisodeSceneProposalDraft,
    EpisodeSceneProposalProvider,
    SceneProposalDraft,
    TemplateEpisodeSceneProposalProvider,
)
from .orchestration import (
    AutoCompilationReport,
    AutomationCompilationError,
    ProposalAcceptanceError,
    ProposalAcceptanceService,
    ProposalAcceptanceSummary,
)
from .runtime_reconciled_orchestration import ProposalAutoCompilationOrchestrator
from .scene_shot import (
    SceneShotProposalAutomationService,
    SceneShotProposalDraft,
    SceneShotProposalProvider,
    ShotProposalDraft,
    TemplateSceneShotProposalProvider,
)
from .semantic_interpretation import SemanticStoryInterpretation, SemanticStoryInterpretationService
from .service import AutomationProposalError, AutomationProposalService

__all__ = [
    "ActionPerformanceProposalAutomationService",
    "ActionPerformanceProposalDraft",
    "ActionPerformanceProposalProvider",
    "AutoCompilationReport",
    "AutomationCompilationError",
    "AutomationProposal",
    "AutomationProposalError",
    "AutomationProposalService",
    "AutomationProposalStatus",
    "AutomationProposalType",
    "AutomationProvenance",
    "AutomationSourceKind",
    "CameraLightingProposalAutomationService",
    "CameraLightingProposalDraft",
    "CameraLightingProposalProvider",
    "CameraProposalDraft",
    "CanonicalEntityAssetResolutionAutomationService",
    "ContinuityProposalAutomationService",
    "EnvironmentProposalAutomationService",
    "EnvironmentProposalDraft",
    "EnvironmentProposalProvider",
    "EpisodeProposalDraft",
    "EpisodeSceneProposalAutomationService",
    "EpisodeSceneProposalDraft",
    "EpisodeSceneProposalProvider",
    "LightingProposalDraft",
    "ProposalAcceptanceError",
    "ProposalAcceptanceService",
    "ProposalAcceptanceSummary",
    "ProposalAutoCompilationOrchestrator",
    "SceneProposalDraft",
    "SceneShotProposalAutomationService",
    "SceneShotProposalDraft",
    "SceneShotProposalProvider",
    "SemanticProductionProvider",
    "SemanticStoryInterpretation",
    "SemanticStoryInterpretationService",
    "ShotProposalDraft",
    "TemplateActionPerformanceProposalProvider",
    "TemplateCameraLightingProposalProvider",
    "TemplateEnvironmentProposalProvider",
    "TemplateEpisodeSceneProposalProvider",
    "TemplateSceneShotProposalProvider",
    "TemplateSemanticProductionProvider",
]
