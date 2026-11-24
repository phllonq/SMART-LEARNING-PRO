"""
Exceptions for Wrong Answer Diagnostic Engine — Phase 7.2.2

Service-level exceptions representing specific domain and infrastructure errors.
None of these exceptions expose internal database queries, credentials, or provider details.
"""

from typing import Optional


class DiagnosticError(Exception):
    """Base exception for all Wrong Answer Diagnostic operations."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AttemptNotFoundException(DiagnosticError):
    """Raised when the specified ExamAttempt does not exist in the database."""

    def __init__(self, attempt_id: str):
        super().__init__(f"Bài thi với mã '{attempt_id}' không tồn tại.", status_code=404)
        self.attempt_id = attempt_id


class DiagnosticUnauthorizedException(DiagnosticError):
    """Raised when student does not own the attempt or tenant scope does not match."""

    def __init__(self, message: str = "Bạn không có quyền truy cập chẩn đoán cho bài thi này."):
        super().__init__(message, status_code=403)


class AttemptNotSubmittedException(DiagnosticError):
    """Raised when the attempt is still in progress or not in an allowed terminal state."""

    def __init__(self, status: str):
        super().__init__(
            f"Bài thi chưa kết thúc hoặc chưa nộp (trạng thái hiện tại: {status}). "
            "Chỉ có thể chẩn đoán sau khi bài thi đã được nộp hoặc chấm điểm.",
            status_code=400,
        )
        self.status = status


class QuestionNotInAttemptException(DiagnosticError):
    """Raised when the question is not part of the exam attempt."""

    def __init__(self, question_id: str):
        super().__init__(f"Câu hỏi '{question_id}' không thuộc về bài thi này.", status_code=404)
        self.question_id = question_id


class QuestionAlreadyCorrectException(DiagnosticError):
    """Raised when student answered the question correctly (no wrong-answer diagnosis needed)."""

    def __init__(self, question_id: str):
        super().__init__(
            f"Câu hỏi '{question_id}' đã được trả lời chính xác, không cần chẩn đoán lỗi sai.",
            status_code=400,
        )
        self.question_id = question_id


class GradingUnavailableException(DiagnosticError):
    """Raised when authoritative grading result is missing or answer has not been evaluated."""

    def __init__(self, question_id: str):
        super().__init__(
            f"Kết quả chấm điểm cho câu hỏi '{question_id}' chưa sẵn sàng hoặc không tồn tại.",
            status_code=422,
        )
        self.question_id = question_id


class InsufficientEvidenceException(DiagnosticError):
    """Raised when diagnostic evidence is insufficient to evaluate."""

    def __init__(self, message: str = "Không đủ dữ liệu để tiến hành chẩn đoán lỗi sai."):
        super().__init__(message, status_code=422)


class AIProviderUnavailableException(DiagnosticError):
    """Raised when LLM provider fails, returns rate limits, or is unconfigured."""

    def __init__(self, message: str = "Dịch vụ AI chẩn đoán hiện không khả dụng. Vui lòng thử lại sau."):
        super().__init__(message, status_code=503)


class AITimeoutException(DiagnosticError):
    """Raised when the AI generation call times out."""

    def __init__(self, message: str = "Quá thời gian phản hồi từ dịch vụ AI chẩn đoán."):
        super().__init__(message, status_code=504)


class AIMalformedOutputException(DiagnosticError):
    """Raised when the AI returns invalid or unparseable JSON."""

    def __init__(self, message: str = "Phản hồi từ AI không đúng cấu trúc yêu cầu."):
        super().__init__(message, status_code=502)


class CacheCoordinationException(DiagnosticError):
    """Raised when distributed lock or cache coordination times out or fails."""

    def __init__(self, message: str = "Không thể đồng bộ xử lý yêu cầu chẩn đoán. Vui lòng thử lại."):
        super().__init__(message, status_code=503)
