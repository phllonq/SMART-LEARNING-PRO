/**
 * TypeScript Contracts for Wrong Answer Diagnostic Engine — Phase 7.2.4.2
 * SMART LEARNING PRO
 *
 * Mapped directly from authoritative backend schemas:
 * `backend/app/modules/ai_engine/diagnostics/schemas.py`
 */

/**
 * Diagnostic error categories assigned by the AI engine.
 * Matches backend `ErrorCategory` enum.
 */
export type ErrorCategory =
  | "CONCEPTUAL_MISCONCEPTION"
  | "CALCULATION_ERROR"
  | "QUESTION_MISREAD"
  | "FORMULA_MISAPPLICATION"
  | "LOGICAL_GAP"
  | "INSUFFICIENT_INFORMATION";

export const ERROR_CATEGORIES: readonly ErrorCategory[] = [
  "CONCEPTUAL_MISCONCEPTION",
  "CALCULATION_ERROR",
  "QUESTION_MISREAD",
  "FORMULA_MISAPPLICATION",
  "LOGICAL_GAP",
  "INSUFFICIENT_INFORMATION",
] as const;

/**
 * Client-facing request contract.
 * Only database identifiers are accepted; no client-provided answers or prompts.
 * Matches backend `WrongAnswerDiagnosticRequest`.
 */
export interface WrongAnswerDiagnosticRequest {
  attempt_id: string;
  question_id: string;
}

/**
 * Structured diagnostic detail produced by the AI engine.
 * Matches backend `DiagnosticDetail`.
 */
export interface DiagnosticDetail {
  error_category: ErrorCategory;
  error_summary: string;
  misconception_analysis: string;
  step_by_step_guidance: string;
  key_takeaway: string;
  suggested_review?: string | null;
}

/**
 * Full API response envelope for wrong-answer diagnosis.
 * Matches backend `WrongAnswerDiagnosticResponse`.
 */
export interface WrongAnswerDiagnosticResponse {
  /**
   * Diagnostic detail. May be null/undefined when is_sufficient is false
   * (AI did not have enough evidence to diagnose reliably).
   */
  diagnostic?: DiagnosticDetail | null;
  /**
   * Whether this response was served from cache (distributed or in-memory).
   */
  cached: boolean;
  /**
   * Total generation latency in milliseconds (0.0 if cached).
   */
  latency_ms: number;
  /**
   * SemVer string of the prompt template used (e.g. "1.0.0").
   */
  prompt_version: string;
  /**
   * False when the AI reported INSUFFICIENT_INFORMATION.
   */
  is_sufficient: boolean;
}
