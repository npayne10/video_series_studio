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

__all__ = [
    "PRODUCTION_TASK_ID_METADATA_KEY",
    "ProductionAuthorityType",
    "ProductionCapability",
    "ProductionTask",
    "ProductionTaskAttemptPolicy",
    "ProductionTaskAuthority",
    "ProductionTaskCompilationContext",
    "ProductionTaskCompilationError",
    "ProductionTaskCompilerService",
    "ProductionTaskGovernanceError",
    "ProductionTaskGovernanceIssue",
    "ProductionTaskGovernanceResult",
    "ProductionTaskGovernanceService",
    "ProductionTaskGovernanceSeverity",
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
