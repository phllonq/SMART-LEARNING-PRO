"""
REST API Router for AI Diagnostics — Phase 7.2.3
SMART LEARNING PRO

Official Endpoint:
POST /api/v1/ai/diagnostics/wrong-answer

Security & Invariants:
- Authenticated STUDENT only (via get_current_student dependency).
- Authoritative student ownership verified against database records.
- Input strictly limited to database UUID identifiers (no client-provided answers or prompts).
- Strict read-only invariant on examination entities (ExamAttempt, StudentAnswer, Question, ExamResult).
- Error-mapped domain exceptions returning structured JSON responses without leaking internal traces.
"""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.ai_engine.diagnostics.dependencies import (
    get_current_student,
    get_diagnostic_service,
)
from app.modules.ai_engine.diagnostics.schemas import (
    WrongAnswerDiagnosticRequest,
    WrongAnswerDiagnosticResponse,
)
from app.modules.ai_engine.diagnostics.service import WrongAnswerDiagnosticService
from app.modules.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/diagnostics", tags=["AI Diagnostics"])


@router.post(
    "/wrong-answer",
    response_model=WrongAnswerDiagnosticResponse,
    status_code=status.HTTP_200_OK,
    summary="Chẩn đoán nguyên nhân câu trả lời sai của học sinh",
    description=(
        "Phân tích câu trả lời sai của học sinh cho một câu hỏi cụ thể trong bài thi đã nộp/chấm điểm. "
        "Sử dụng AI Engine để chỉ ra quan niệm sai lệch, hướng dẫn từng bước và đề xuất ôn tập."
    ),
    responses={
        200: {
            "description": "Chẩn đoán lỗi sai thành công.",
            "model": WrongAnswerDiagnosticResponse,
        },
        400: {
            "description": "Bài thi chưa nộp hoặc câu trả lời đã đúng.",
            "content": {"application/json": {"example": {"detail": "Câu hỏi đã được trả lời chính xác."}}},
        },
        401: {
            "description": "Chưa xác thực hoặc token không hợp lệ.",
            "content": {"application/json": {"example": {"detail": "Authentication required. Please log in."}}},
        },
        403: {
            "description": "Không có quyền truy cập bài thi hoặc không phải là học sinh.",
            "content": {"application/json": {"example": {"detail": "Bạn không phải chủ sở hữu của bài thi này."}}},
        },
        404: {
            "description": "Không tìm thấy bài thi hoặc câu hỏi không thuộc bài thi.",
            "content": {"application/json": {"example": {"detail": "Bài thi với mã '...' không tồn tại."}}},
        },
        422: {
            "description": "Dữ liệu yêu cầu không hợp lệ hoặc thiếu kết quả chấm điểm.",
            "content": {"application/json": {"example": {"detail": "Kết quả chấm điểm chưa sẵn sàng."}}},
        },
        502: {
            "description": "Phản hồi từ AI không đúng cấu trúc yêu cầu.",
            "content": {"application/json": {"example": {"detail": "Phản hồi từ AI không đúng cấu trúc yêu cầu."}}},
        },
        503: {
            "description": "Dịch vụ AI chẩn đoán hiện không khả dụng.",
            "content": {"application/json": {"example": {"detail": "Dịch vụ AI chẩn đoán hiện không khả dụng."}}},
        },
        504: {
            "description": "Quá thời gian phản hồi từ dịch vụ AI chẩn đoán.",
            "content": {"application/json": {"example": {"detail": "Quá thời gian phản hồi từ dịch vụ AI chẩn đoán."}}},
        },
    },
)
async def diagnose_wrong_answer(
    request: WrongAnswerDiagnosticRequest,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
    service: WrongAnswerDiagnosticService = Depends(get_diagnostic_service),
) -> WrongAnswerDiagnosticResponse:
    """
    Endpoint chẩn đoán lỗi sai cho học sinh.
    1. Xác thực học sinh (STUDENT role required).
    2. Nạp dữ liệu bài thi và kiểm tra quyền sở hữu (Read-Only).
    3. Tra cứu Cache hoặc điều phối Distributed Lock (Redis).
    4. Gọi AI Engine phân tích và ghi nhận Usage Telemetry.
    5. Trả về kết quả chẩn đoán chi tiết.
    """
    logger.info(
        "Diagnostic request received: student_id=%s, attempt_id=%s, question_id=%s",
        current_user.id,
        request.attempt_id,
        request.question_id,
    )
    return await service.diagnose_wrong_answer(
        db=db,
        attempt_id=request.attempt_id,
        question_id=request.question_id,
        student=current_user,
    )
