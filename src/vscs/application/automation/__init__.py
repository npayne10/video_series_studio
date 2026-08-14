"""Public contracts for governed VSCS production automation."""

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
    "EpisodeProposalDraft",
    "EpisodeSceneProposalAutomationService",
    "EpisodeSceneProposalDraft",
    "EpisodeSceneProposalProvider",
    "SceneProposalDraft",
    "SemanticProductionProvider",
    "SemanticStoryInterpretation",
    "SemanticStoryInterpretationService",
    "TemplateEpisodeSceneProposalProvider",
    "TemplateSemanticProductionProvider",
]
