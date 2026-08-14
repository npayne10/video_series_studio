"""Public contracts for governed VSCS production automation."""

from .canonical_entity import CanonicalEntityAssetResolutionAutomationService
from .contracts import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    SemanticProductionProvider,
    TemplateSemanticProductionProvider,
)
from .episode_scene import (
    EpisodeProposalDraft,
    EpisodeSceneProposalAutomationService,
    EpisodeSceneProposalDraft,
    EpisodeSceneProposalProvider,
    SceneProposalDraft,
    TemplateEpisodeSceneProposalProvider,
)
from .scene_shot import (
    SceneShotProposalAutomationService,
    SceneShotProposalDraft,
    SceneShotProposalProvider,
    ShotProposalDraft,
    TemplateSceneShotProposalProvider,
)
from .semantic_interpretation import (
    SemanticStoryInterpretation,
    SemanticStoryInterpretationService,
)
from .service import AutomationProposalError, AutomationProposalService

__all__ = [
    "AutomationProposal",
    "AutomationProposalError",
    "AutomationProposalService",
    "AutomationProposalStatus",
    "AutomationProposalType",
    "AutomationProvenance",
    "AutomationSourceKind",
    "CanonicalEntityAssetResolutionAutomationService",
    "EpisodeProposalDraft",
    "EpisodeSceneProposalAutomationService",
    "EpisodeSceneProposalDraft",
    "EpisodeSceneProposalProvider",
    "SceneProposalDraft",
    "SceneShotProposalAutomationService",
    "SceneShotProposalDraft",
    "SceneShotProposalProvider",
    "SemanticProductionProvider",
    "SemanticStoryInterpretation",
    "SemanticStoryInterpretationService",
    "ShotProposalDraft",
    "TemplateEpisodeSceneProposalProvider",
    "TemplateSceneShotProposalProvider",
    "TemplateSemanticProductionProvider",
]
