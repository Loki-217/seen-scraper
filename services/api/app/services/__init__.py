# services/api/app/services/__init__.py
"""V2 业务服务模块"""

from .pagination_detector import PaginationDetector
from .pagination_executor import PaginationExecutor

__all__ = [
    "PaginationDetector",
    "PaginationExecutor",
]
