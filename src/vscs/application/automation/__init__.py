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
from .functional_acceptance import (
    AcceptanceCriterion,
    AcceptanceState,
    FunctionalAcceptanceReport,
    FunctionalAcceptanceService,
)
from .orchestration import (
    AutoCompilationReport,
    AutomationCompilationError,
    ProposalAcceptanceError,
    ProposalAcceptanceService,
    ProposalAcceptanceSummary,
)
from .review_gaps import (
    ProposalReviewGapDetectionService,
    ProposalReviewReport,
    ReviewGap,
    ReviewGapSeverity,
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
from .xpd_binding import (
    CanonicalLibraryImportReport,
    CanonicalLibraryImportService,
    ShotAssetBinding,
    ShotAssetBindingReport,
    ShotAssetBindingService,
)

__all__ = [
    "AcceptanceCriterion",
    "AcceptanceState",
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
    "CanonicalLibraryImportReport",
    "CanonicalLibraryImportService",
    "ContinuityProposalAutomationService",
    "EnvironmentProposalAutomationService",
    "EnvironmentProposalDraft",
    "EnvironmentProposalProvider",
    "EpisodeProposalDraft",
    "EpisodeSceneProposalAutomationService",
    "EpisodeSceneProposalDraft",
    "EpisodeSceneProposalProvider",
    "FunctionalAcceptanceReport",
    "FunctionalAcceptanceService",
    "LightingProposalDraft",
    "ProposalAcceptanceError",
    "ProposalAcceptanceService",
    "ProposalAcceptanceSummary",
    "ProposalAutoCompilationOrchestrator",
    "ProposalReviewGapDetectionService",
    "ProposalReviewReport",
    "ReviewGap",
    "ReviewGapSeverity",
    "SceneProposalDraft",
    "SceneShotProposalAutomationService",
    "SceneShotProposalDraft",
    "SceneShotProposalProvider",
    "SemanticProductionProvider",
    "SemanticStoryInterpretation",
    "SemanticStoryInterpretationService",
    "ShotAssetBinding",
    "ShotAssetBindingReport",
    "ShotAssetBindingService",
    "ShotProposalDraft",
    "TemplateActionPerformanceProposalProvider",
    "TemplateCameraLightingProposalProvider",
    "TemplateEnvironmentProposalProvider",
    "TemplateEpisodeSceneProposalProvider",
    "TemplateSceneShotProposalProvider",
    "TemplateSemanticProductionProvider",
]
