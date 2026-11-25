"""
Exceptions for AI Tutor Module - SMART LEARNING PRO
Defines typed exception hierarchy for conversation lifecycle, ownership, concurrency, and streaming failures.
"""

from typing import Optional


class AITutorException(Exception):
    """Base exception for all AI Tutor domain errors."""

    def __init__(self, message: str, status_code: int = 500, error_code: str = "AI_TUTOR_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ConversationNotFoundException(AITutorException):
    """Raised when a requested conversation does not exist or user lacks permission to view it."""

    def __init__(self, message: str = "Đoạn hội thoại không tồn tại hoặc bạn không có quyền truy cập."):
        super().__init__(message=message, status_code=404, error_code="CONVERSATION_NOT_FOUND")


class ConversationAccessDeniedException(AITutorException):
    """Raised when an authenticated principal attempts to access or mutate another user's conversation."""

    def __init__(self, message: str = "Bạn không có quyền thực hiện thao tác trên cuộc hội thoại này."):
        super().__init__(message=message, status_code=403, error_code="CONVERSATION_ACCESS_DENIED")


class ConversationBusyException(AITutorException):
    """Raised when a conversation is already actively generating a response (concurrent message locked)."""

    def __init__(self, message: str = "Cuộc hội thoại đang xử lý phản hồi từ một yêu cầu khác. Vui lòng đợi trong giây lát."):
        super().__init__(message=message, status_code=409, error_code="CONVERSATION_BUSY")


class InvalidMessageContentException(AITutorException):
    """Raised when user input violates validation boundaries (empty, whitespace-only, or oversized)."""

    def __init__(self, message: str = "Nội dung tin nhắn không hợp lệ."):
        super().__init__(message=message, status_code=400, error_code="INVALID_MESSAGE_CONTENT")


class InvalidMessageStateTransitionError(AITutorException):
    """Raised when attempting an unauthorized message lifecycle transition."""

    def __init__(self, current_status: str, target_status: str):
        message = f"Không thể chuyển đổi trạng thái tin nhắn từ '{current_status}' sang '{target_status}'."
        super().__init__(message=message, status_code=409, error_code="INVALID_STATE_TRANSITION")
        self.current_status = current_status
        self.target_status = target_status


class LockAcquisitionException(AITutorException):
    """Raised when distributed lock cannot be acquired within allowable timeout budget."""

    def __init__(self, message: str = "Không thể lấy khóa đồng thời cho cuộc hội thoại."):
        super().__init__(message=message, status_code=503, error_code="LOCK_ACQUISITION_FAILED")


class StaleWorkerException(AITutorException):
    """Raised when a worker attempts to write or finalize after its lock ownership expired or was transferred."""

    def __init__(self, message: str = "Worker đã mất quyền sở hữu khóa hội thoại; thao tác ghi bị hủy bỏ để bảo toàn dữ liệu."):
        super().__init__(message=message, status_code=409, error_code="STALE_WORKER_DETECTED")


class TutorProviderUnavailableException(AITutorException):
    """Raised when underlying AI Engine provider fails or is unreachable."""

    def __init__(self, message: str = "Dịch vụ AI Tutor hiện không khả dụng. Vui lòng thử lại sau."):
        super().__init__(message=message, status_code=503, error_code="TUTOR_PROVIDER_UNAVAILABLE")


class TutorTimeoutException(AITutorException):
    """Raised when AI Tutor streaming exceeds deadline."""

    def __init__(self, message: str = "Quá thời gian phản hồi từ dịch vụ AI Tutor. Vui lòng thử lại."):
        super().__init__(message=message, status_code=504, error_code="TUTOR_TIMEOUT")
