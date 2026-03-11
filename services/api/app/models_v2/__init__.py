# services/api/app/models/__init__.py
"""V2 数据模型"""

from .actions import (
    ActionType,
    Action,
    ActionResult,
    InteractiveElement,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionState,
)

from .pagination import (
    PaginationType,
    PaginationConfig,
    PaginationResult,
    DetectedPagination,
    PaginationDetectRequest,
    PaginationDetectResponse,
)

from .schedule import (
    ScheduleFrequency,
    RunStatus,
    Schedule,
    ScheduledRun,
    Robot,
    FieldConfig,
    CreateScheduleRequest,
    UpdateScheduleRequest,
    ScheduleResponse,
    ScheduleListResponse,
    RunResponse,
    RunListResponse,
)

__all__ = [
    # Actions
    "ActionType",
    "Action",
    "ActionResult",
    "InteractiveElement",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "SessionState",
    # Pagination
    "PaginationType",
    "PaginationConfig",
    "PaginationResult",
    "DetectedPagination",
    "PaginationDetectRequest",
    "PaginationDetectResponse",
    # Schedule
    "ScheduleFrequency",
    "RunStatus",
    "Schedule",
    "ScheduledRun",
    "Robot",
    "FieldConfig",
    "CreateScheduleRequest",
    "UpdateScheduleRequest",
    "ScheduleResponse",
    "ScheduleListResponse",
    "RunResponse",
    "RunListResponse",
]
