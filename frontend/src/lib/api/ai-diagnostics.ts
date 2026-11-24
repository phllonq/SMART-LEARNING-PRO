/**
 * AI Diagnostics API Client — Phase 7.2.4.2
 * SMART LEARNING PRO
 *
 * Provides typed access to the Wrong Answer Diagnostic Engine:
 * POST /api/v1/ai/diagnostics/wrong-answer
 *
 * Integrates directly with existing `apiClient` and `ApiClientError` in `@/lib/api/client`.
 */

import { apiClient, ApiClientError } from "./client";
import {
  WrongAnswerDiagnosticRequest,
  WrongAnswerDiagnosticResponse,
} from "@/types/ai-diagnostics";

/**
 * Relative endpoint path for wrong-answer diagnostics.
 * Note: `apiClient` automatically prepends `NEXT_PUBLIC_API_URL` (which defaults to `http://localhost:8000/api/v1`).
 * Therefore, this path MUST NOT include `/api/v1` to prevent prefix duplication (`/api/v1/api/v1`).
 */
export const DIAGNOSTICS_ENDPOINT = "/ai/diagnostics/wrong-answer";

export const aiDiagnosticsApi = {
  /**
   * Request an AI-powered diagnostic analysis for a student's incorrect answer.
   *
   * Security & Integrity:
   * - Only `attempt_id` and `question_id` are sent to the backend.
   * - Extraneous fields (such as client-guessed correctness or answers) are strictly stripped.
   * - Authentication token is attached automatically via `sessionStorage`.
   *
   * @param request - Object containing `attempt_id` and `question_id` (UUID v4 strings).
   * @returns Promise resolving to `WrongAnswerDiagnosticResponse`.
   * @throws `ApiClientError` when the server returns a non-2xx status code.
   */
  async diagnoseWrongAnswer(
    request: WrongAnswerDiagnosticRequest
  ): Promise<WrongAnswerDiagnosticResponse> {
    // Whitelist extraction: only transmit required database identifiers
    const sanitizedPayload: WrongAnswerDiagnosticRequest = {
      attempt_id: request.attempt_id,
      question_id: request.question_id,
    };

    return apiClient.post<WrongAnswerDiagnosticResponse>(
      DIAGNOSTICS_ENDPOINT,
      sanitizedPayload
    );
  },
};

/**
 * Checks whether an HTTP status code represents a non-retryable business rule
 * or client validation error (400, 401, 403, 404, 422).
 * These errors MUST NOT be automatically retried by TanStack Query.
 */
export function isBusinessRuleError(statusCode: number): boolean {
  return [400, 401, 403, 404, 422].includes(statusCode);
}

/**
 * Checks whether an HTTP status code represents a transient or infrastructure AI error (502, 503, 504, 0).
 * Status 0 represents network disconnect or connection failure.
 * These errors may be retried manually by the student via the UI with bounded attempts.
 */
export function isRetryableAIError(statusCode: number): boolean {
  return [502, 503, 504, 0].includes(statusCode);
}

/**
 * Maps an ApiClientError or generic error into a clean, educational Vietnamese message.
 * Ensures that raw provider exceptions, credentials, or internal stack traces are never shown to students.
 */
export function getDiagnosticErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    switch (error.status) {
      case 0:
        return "Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng của bạn và thử lại.";
      case 400:
        return error.message || "Bài thi chưa kết thúc hoặc câu hỏi này đã được trả lời chính xác.";
      case 401:
        return "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.";
      case 403:
        return "Bạn không có quyền truy cập chẩn đoán cho bài thi này.";
      case 404:
        return "Không tìm thấy dữ liệu bài thi hoặc câu hỏi tương ứng.";
      case 422:
        return error.message || "Dữ liệu yêu cầu không hợp lệ hoặc kết quả chấm điểm chưa sẵn sàng.";
      case 502:
        return "Hệ thống AI phản hồi không đúng cấu trúc quy định. Vui lòng thử lại.";
      case 503:
        return "Dịch vụ AI chẩn đoán hiện đang bận hoặc tạm thời không khả dụng. Vui lòng thử lại sau giây lát.";
      case 504:
        return "Quá thời gian phản hồi từ dịch vụ AI chẩn đoán. Vui lòng thử lại.";
      default:
        return error.message || `Đã xảy ra lỗi khi phân tích câu sai (Mã lỗi: ${error.status}).`;
    }
  }

  if (error instanceof Error) {
    // Prevent leaking network/fetch details
    if (error.message.includes("fetch") || error.message.includes("Failed to fetch")) {
      return "Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng của bạn.";
    }
    return error.message;
  }

  return "Đã xảy ra lỗi không xác định khi yêu cầu chẩn đoán lỗi sai.";
}
