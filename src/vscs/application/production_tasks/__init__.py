"""VSCS vNext ProductionTask domain, compilation and governance public API."""

from .compatibility import PRODUCTION_TASK_ID_METADATA_KEY, ProductionTaskLegacyBridge
from .compiler import (
    ProductionTaskCompilationContext,
    ProductionTaskCompilationError,
    ProductionTaskCompilerService,
)
from .governance import (
    ProductionTaskGovernanceError,
    ProductionTaskGovernanceIssue,
    ProductionTaskGovernanceResult,
    ProductionTaskGovernanceService,
    ProductionTaskGovernanceSeverity,
)
from .graph import (
    ProductionTaskDependencyDisposition,
    ProductionTaskGraph,
    ProductionTaskGraphError,
    ProductionTaskGraphIntegrationService,
    ProductionTaskGraphRefreshResult,
)
from .lifecycle import (
    ProductionTaskLifecycleService,
    ProductionTaskStageService,
    ProductionTaskTransition,
    ProductionTaskTransitionError,
)
from .models import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAttemptPolicy,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from .repository import ProductionTaskRepository, ProductionTaskRepositoryError
from .service import ProductionTaskApplicationService

__all__ = [
    "PRODUCTION_TASK_ID_METADATA_KEY",
    "ProductionAuthorityType",
    "ProductionCapability",
    "ProductionTask",
    "ProductionTaskApplicationService",
    "ProductionTaskAttemptPolicy",
    "ProductionTaskAuthority",
    "ProductionTaskCompilationContext",
    "ProductionTaskCompilationError",
    "ProductionTaskCompilerService",
    "ProductionTaskDependencyDisposition",
    "ProductionTaskGovernanceError",
    "ProductionTaskGovernanceIssue",
    "ProductionTaskGovernanceResult",
    "ProductionTaskGovernanceService",
    "ProductionTaskGovernanceSeverity",
    "ProductionTaskGraph",
    "ProductionTaskGraphError",
    "ProductionTaskGraphIntegrationService",
    "ProductionTaskGraphRefreshResult",
    "ProductionTaskLegacyBridge",
    "ProductionTaskLifecycleService",
    "ProductionTaskPriority",
    "ProductionTaskRepository",
    "ProductionTaskRepositoryError",
    "ProductionTaskStageService",
    "ProductionTaskState",
    "ProductionTaskTransition",
    "ProductionTaskTransitionError",
    "ProductionTaskType",
]
