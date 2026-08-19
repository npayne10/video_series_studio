"""Generated Media application services for VSCS Phase 20."""

from vscs.domain.generated_media import GeneratedMediaKind

from .completion_reconciliation import (
    ProductionTaskCompletionAssessment,
    ProductionTaskCompletionEvidence,
    ProductionTaskCompletionFinding,
    ProductionTaskCompletionReconciliationError,
    ProductionTaskCompletionReconciliationResult,
    ProductionTaskCompletionReconciliationService,
    ProductionTaskCompletionSeverity,
    ProductionTaskOutputContractResolver,
    ProductionTaskOutputRequirement,
)
from .governance import (
    GeneratedMediaGovernanceError,
    GeneratedMediaGovernanceIssue,
    GeneratedMediaGovernanceResult,
    GeneratedMediaGovernanceService,
    GeneratedMediaGovernanceSeverity,
)
from .ingestion import (
    GeneratedMediaFileStore,
    GeneratedMediaIngestionError,
    GeneratedMediaIngestionResult,
    GeneratedMediaIngestionService,
)
from .persistence import GeneratedMediaPersistenceService
from .repository import GeneratedMediaRepository, GeneratedMediaRepositoryError
from .review import (
    GeneratedMediaReviewActor,
    GeneratedMediaReviewDecision,
    GeneratedMediaReviewError,
    GeneratedMediaReviewResult,
    GeneratedMediaReviewService,
    GeneratedMediaReviewSubmission,
    ReviewAuthorityType,
)
from .selection import (
    GeneratedMediaSelection,
    GeneratedMediaSelectionError,
    GeneratedMediaSelectionEvent,
    GeneratedMediaSelectionRepository,
    GeneratedMediaSelectionService,
    GeneratedMediaSupersessionResult,
)
from .technical_validation import (
    GeneratedMediaTechnicalRequirements,
    GeneratedMediaTechnicalValidationError,
    GeneratedMediaTechnicalValidationResult,
    GeneratedMediaTechnicalValidationService,
    TechnicalMediaInspector,
    TechnicalMediaObservation,
    TechnicalValidationIssue,
    TechnicalValidationSeverity,
)
from .ui_service import (
    GeneratedMediaDetailView,
    GeneratedMediaListItem,
    GeneratedMediaUiError,
    GeneratedMediaUiService,
)

__all__ = [
    "GeneratedMediaDetailView",
    "GeneratedMediaFileStore",
    "GeneratedMediaGovernanceError",
    "GeneratedMediaGovernanceIssue",
    "GeneratedMediaGovernanceResult",
    "GeneratedMediaGovernanceService",
    "GeneratedMediaGovernanceSeverity",
    "GeneratedMediaIngestionError",
    "GeneratedMediaIngestionResult",
    "GeneratedMediaIngestionService",
    "GeneratedMediaKind",
    "GeneratedMediaListItem",
    "GeneratedMediaPersistenceService",
    "GeneratedMediaRepository",
    "GeneratedMediaRepositoryError",
    "GeneratedMediaReviewActor",
    "GeneratedMediaReviewDecision",
    "GeneratedMediaReviewError",
    "GeneratedMediaReviewResult",
    "GeneratedMediaReviewService",
    "GeneratedMediaReviewSubmission",
    "GeneratedMediaSelection",
    "GeneratedMediaSelectionError",
    "GeneratedMediaSelectionEvent",
    "GeneratedMediaSelectionRepository",
    "GeneratedMediaSelectionService",
    "GeneratedMediaSupersessionResult",
    "GeneratedMediaTechnicalRequirements",
    "GeneratedMediaTechnicalValidationError",
    "GeneratedMediaTechnicalValidationResult",
    "GeneratedMediaTechnicalValidationService",
    "GeneratedMediaUiError",
    "GeneratedMediaUiService",
    "ProductionTaskCompletionAssessment",
    "ProductionTaskCompletionEvidence",
    "ProductionTaskCompletionFinding",
    "ProductionTaskCompletionReconciliationError",
    "ProductionTaskCompletionReconciliationResult",
    "ProductionTaskCompletionReconciliationService",
    "ProductionTaskCompletionSeverity",
    "ProductionTaskOutputContractResolver",
    "ProductionTaskOutputRequirement",
    "ReviewAuthorityType",
    "TechnicalMediaInspector",
    "TechnicalMediaObservation",
    "TechnicalValidationIssue",
    "TechnicalValidationSeverity",
]
