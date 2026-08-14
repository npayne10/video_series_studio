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
from .service import AutomationProposalError, AutomationProposalService

__all__ = [
    "AutomationProposal",
    "AutomationProposalError",
    "AutomationProposalService",
    "AutomationProposalStatus",
    "AutomationProposalType",
    "AutomationProvenance",
    "AutomationSourceKind",
    "SemanticProductionProvider",
    "TemplateSemanticProductionProvider",
]
