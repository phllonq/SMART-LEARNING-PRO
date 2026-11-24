"""
Dependencies for AI Diagnostics Module — Phase 7.2.3
SMART LEARNING PRO

Provides:
- get_current_student: Authentication & role enforcement (STUDENT only).
- get_diagnostic_service: Dependency provider for WrongAnswerDiagnosticService.
"""

from fastapi import Depends

from app.core.dependencies import get_current_user
from app.core.exceptions import PermissionDeniedException
from app.modules.ai_engine.diagnostics.service import WrongAnswerDiagnosticService
from app.modules.auth.models import User, UserRole


async def get_current_student(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure that the authenticated user has the STUDENT role.
    Restricts access to students; teachers and admins are denied.
    """
    if current_user.role != UserRole.STUDENT.value:
        raise PermissionDeniedException(
            f"Tính năng chẩn đoán chỉ dành riêng cho học sinh (STUDENT). Vai trò hiện tại của bạn: {current_user.role}"
        )
    return current_user


def get_diagnostic_service() -> WrongAnswerDiagnosticService:
    """
    Dependency provider for WrongAnswerDiagnosticService.
    Reuses existing provider factory and CacheService singleton.
    Enables clean dependency overrides in pytest (app.dependency_overrides).
    """
    return WrongAnswerDiagnosticService()
