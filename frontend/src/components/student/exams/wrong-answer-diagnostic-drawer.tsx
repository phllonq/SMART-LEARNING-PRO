"use client";

import React, { useEffect, useRef, useState, useCallback, useId } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  aiDiagnosticsApi,
  isBusinessRuleError,
  isRetryableAIError,
  getDiagnosticErrorMessage,
} from "@/lib/api/ai-diagnostics";
import { ApiClientError } from "@/lib/api/client";
import {
  ErrorCategory,
  WrongAnswerDiagnosticResponse,
} from "@/types/ai-diagnostics";
import { MathKaTeX } from "@/components/shared/math-katex";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sparkles,
  X,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  BookOpen,
  Lightbulb,
  HelpCircle,
  Brain,
  ListOrdered,
  BookmarkCheck,
  Zap,
} from "lucide-react";

export interface WrongAnswerDiagnosticDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  attemptId: string;
  questionId?: string | null | undefined;
  questionContent?: string | null | undefined;
  questionIndex?: number;
  triggerElementRef?: React.RefObject<HTMLElement | null>;
}

/**
 * Global in-flight promise map for request deduplication across concurrent calls.
 */
const inFlightRequestsMap = new Map<string, Promise<WrongAnswerDiagnosticResponse>>();

export const MAX_MANUAL_RETRIES = 3;

/**
 * Human-friendly Vietnamese mapping for technical ErrorCategory enum.
 */
export const ERROR_CATEGORY_LABELS: Record<
  ErrorCategory,
  { label: string; variant: "purple" | "warning" | "destructive" | "secondary" | "outline" | "default" }
> = {
  CONCEPTUAL_MISCONCEPTION: {
    label: "Quan niệm sai lầm về khái niệm",
    variant: "purple",
  },
  CALCULATION_ERROR: {
    label: "Lỗi tính toán sai số học / đại số",
    variant: "warning",
  },
  QUESTION_MISREAD: {
    label: "Đọc nhầm hoặc hiểu sai đề bài",
    variant: "secondary",
  },
  FORMULA_MISAPPLICATION: {
    label: "Áp dụng sai công thức / định lý",
    variant: "destructive",
  },
  LOGICAL_GAP: {
    label: "Thiếu bước lập luận hoặc suy luận logic",
    variant: "purple",
  },
  INSUFFICIENT_INFORMATION: {
    label: "Chưa đủ dữ liệu để kết luận",
    variant: "outline",
  },
};

type DrawerState =
  | "IDLE"
  | "LOADING"
  | "SUCCESS"
  | "INSUFFICIENT_INFORMATION"
  | "ERROR";

export function WrongAnswerDiagnosticDrawer({
  isOpen,
  onClose,
  attemptId,
  questionId,
  questionContent = "",
  questionIndex = 1,
  triggerElementRef,
}: WrongAnswerDiagnosticDrawerProps) {
  const queryClient = useQueryClient();
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const retryButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);

  const titleId = useId();
  const descId = useId();

  // Component states
  const [state, setState] = useState<DrawerState>("IDLE");
  const [data, setData] = useState<WrongAnswerDiagnosticResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [retryCount, setRetryCount] = useState<number>(0);

  // In-flight guard to block duplicate rapid requests
  const isInFlightRef = useRef(false);

  // Reset retry count when question or attempt changes
  useEffect(() => {
    setRetryCount(0);
  }, [attemptId, questionId]);

  // Query Key for TanStack Query Client Cache
  const queryKey = ["ai-diagnostic", attemptId, questionId];

  // Fetch or retrieve from cache
  const fetchDiagnostic = useCallback(
    async (forceRefresh = false) => {
      if (!attemptId || !questionId) {
        setState("ERROR");
        setErrorMessage("Thiếu định danh bài thi hoặc câu hỏi để thực hiện chẩn đoán.");
        return;
      }

      if (isInFlightRef.current) return;

      // 1. Check TanStack Query cache first (if not forcing refresh)
      if (!forceRefresh) {
        const cached = queryClient.getQueryData<WrongAnswerDiagnosticResponse>(queryKey);
        if (cached) {
          setData(cached);
          if (cached.is_sufficient === false || cached.diagnostic?.error_category === "INSUFFICIENT_INFORMATION") {
            setState("INSUFFICIENT_INFORMATION");
          } else {
            setState("SUCCESS");
          }
          return;
        }
      }

      // 2. Fetch fresh diagnostic from API with in-flight deduplication
      isInFlightRef.current = true;
      setState("LOADING");
      setErrorMessage(null);
      setErrorStatus(null);

      const requestKey = `${attemptId}:${questionId}`;

      try {
        let requestPromise = inFlightRequestsMap.get(requestKey);
        if (!requestPromise) {
          requestPromise = aiDiagnosticsApi.diagnoseWrongAnswer({
            attempt_id: attemptId,
            question_id: questionId,
          });
          inFlightRequestsMap.set(requestKey, requestPromise);
        }

        const response = await requestPromise;

        // 3. Cache successful response in TanStack Query
        queryClient.setQueryData(queryKey, response);
        setData(response);

        // 4. Determine state
        if (response.is_sufficient === false || response.diagnostic?.error_category === "INSUFFICIENT_INFORMATION") {
          setState("INSUFFICIENT_INFORMATION");
        } else {
          setState("SUCCESS");
        }
      } catch (err: unknown) {
        let status = 500;
        if (err instanceof ApiClientError) {
          status = err.status;
        } else if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
          status = 0; // Network connection failure
        }
        setErrorStatus(status);
        const userMsg = getDiagnosticErrorMessage(err);
        setErrorMessage(userMsg);
        setState("ERROR");
      } finally {
        isInFlightRef.current = false;
        inFlightRequestsMap.delete(requestKey);
      }
    },
    [attemptId, questionId, queryClient, queryKey]
  );

  // Trigger fetch whenever drawer opens for a question
  useEffect(() => {
    if (isOpen) {
      // Save previously focused element for focus restoration on close
      previouslyFocusedElementRef.current =
        (triggerElementRef?.current as HTMLElement) ||
        (document.activeElement as HTMLElement);

      fetchDiagnostic(false);
    } else {
      // Reset transient error when closed
      isInFlightRef.current = false;
    }
  }, [isOpen, fetchDiagnostic, triggerElementRef]);

  // Accessibility: Body scroll lock & Escape listener & Focus Trap
  useEffect(() => {
    if (!isOpen) return;

    // 1. Lock body scroll while preserving scroll position
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // 2. Initial focus: focus the close button after mount
    const timer = setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 50);

    // 3. Keydown handler for Escape and Focus Trap
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab") {
        const container = drawerRef.current;
        if (!container) return;

        const focusable = container.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;

        const firstElement = focusable[0];
        const lastElement = focusable[focusable.length - 1];

        if (e.shiftKey) {
          // Shift + Tab: if on first element, wrap to last
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          // Tab: if on last element, wrap to first
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = originalOverflow || "";
      window.removeEventListener("keydown", handleKeyDown);

      // Restore focus to opener element
      if (previouslyFocusedElementRef.current) {
        previouslyFocusedElementRef.current.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const diagnostic = data?.diagnostic;
  const isRetryable =
    errorStatus !== null &&
    isRetryableAIError(errorStatus) &&
    !isBusinessRuleError(errorStatus) &&
    retryCount < MAX_MANUAL_RETRIES;

  const handleManualRetry = () => {
    if (retryCount >= MAX_MANUAL_RETRIES) return;
    setRetryCount((prev) => prev + 1);
    fetchDiagnostic(true);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descId}
    >
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity duration-300"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over Drawer Panel */}
      <div
        ref={drawerRef}
        className="relative z-50 w-full sm:max-w-lg md:max-w-xl bg-white shadow-2xl flex flex-col h-full transform transition-transform duration-300 ease-out border-l border-slate-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4.5 border-b border-slate-100 bg-linear-to-r from-indigo-50/70 via-white to-purple-50/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-600 text-white shadow-xs">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2
                id={titleId}
                className="text-base font-bold text-slate-900 flex items-center gap-2"
              >
                <span>Phân tích lỗi sai bằng AI</span>
                <Badge variant="purple" className="text-[10px] font-semibold py-0 px-1.5">
                  Câu {questionIndex}
                </Badge>
              </h2>
              <p id={descId} className="text-xs text-slate-500 mt-0.5">
                Cùng tìm hiểu vì sao bạn chưa chọn được đáp án đúng
              </p>
            </div>
          </div>

          <Button
            ref={closeButtonRef}
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Đóng bảng phân tích lỗi sai"
            className="rounded-full h-8 w-8 hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Question Snapshot Preview (Compact) */}
        {questionContent && (
          <div className="px-6 py-3 bg-slate-50 border-b border-slate-100 flex items-start gap-2.5 text-xs text-slate-600">
            <HelpCircle className="h-4 w-4 text-indigo-500 shrink-0 mt-0.5" />
            <div className="line-clamp-2 leading-relaxed">
              <span className="font-semibold text-slate-800">Đề bài: </span>
              <MathKaTeX math={questionContent} />
            </div>
          </div>
        )}

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* 1. LOADING STATE */}
          {state === "LOADING" && (
            <div className="space-y-4 py-6" aria-busy="true" aria-live="polite">
              <div className="flex items-center gap-3 p-4 rounded-xl bg-indigo-50/60 border border-indigo-100 text-indigo-900 animate-pulse">
                <Brain className="h-6 w-6 text-indigo-600 animate-spin" />
                <div>
                  <p className="text-sm font-semibold">AI đang phân tích câu sai của bạn...</p>
                  <p className="text-xs text-indigo-700/80">Đối chiếu kiến thức và tìm ra quan niệm sai lệch</p>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <Skeleton className="h-5 w-1/3 rounded-md" />
                <Skeleton className="h-20 w-full rounded-xl" />
              </div>

              <div className="space-y-3">
                <Skeleton className="h-5 w-1/2 rounded-md" />
                <Skeleton className="h-28 w-full rounded-xl" />
              </div>

              <div className="space-y-3">
                <Skeleton className="h-5 w-2/5 rounded-md" />
                <Skeleton className="h-24 w-full rounded-xl" />
              </div>
            </div>
          )}

          {/* 2. ERROR STATE */}
          {state === "ERROR" && (
            <div className="space-y-4 py-6" role="alert" aria-live="assertive">
              <div className="p-4.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm text-rose-800">
                  <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
                  <span>Không thể hoàn tất chẩn đoán</span>
                </div>
                <p className="text-xs text-rose-700 leading-relaxed">
                  {errorMessage || "Đã xảy ra sự cố khi gọi dịch vụ AI. Vui lòng thử lại sau."}
                </p>
              </div>

              {/* Retry action for transient infrastructure errors */}
              {isRetryable ? (
                <div className="text-center pt-2">
                  <Button
                    ref={retryButtonRef}
                    onClick={handleManualRetry}
                    variant="default"
                    className="gap-2 bg-indigo-600 hover:bg-indigo-700 text-xs px-5 shadow-sm"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    <span>Thử lại phân tích ({retryCount}/{MAX_MANUAL_RETRIES})</span>
                  </Button>
                  <p className="text-[11px] text-slate-500 mt-2">
                    Lỗi kết nối tạm thời hoặc dịch vụ AI đang bận
                  </p>
                </div>
              ) : retryCount >= MAX_MANUAL_RETRIES ? (
                <div className="text-center pt-2 text-xs text-amber-700 bg-amber-50 p-3 rounded-xl border border-amber-200">
                  <p className="font-semibold">Đã đạt giới hạn thử lại ({MAX_MANUAL_RETRIES}/{MAX_MANUAL_RETRIES})</p>
                  <p className="text-[11px] mt-1 text-amber-800">
                    Dịch vụ AI hoặc đường truyền mạng tạm thời không phản hồi. Vui lòng thử lại sau.
                  </p>
                </div>
              ) : (
                <div className="text-center pt-1 text-xs text-slate-500">
                  {errorStatus && isBusinessRuleError(errorStatus)
                    ? "Yêu cầu không thể thực hiện do ràng buộc trạng thái bài thi hoặc phân quyền."
                    : "Vui lòng liên hệ quản trị viên nếu sự cố tiếp diễn."}
                </div>
              )}
            </div>
          )}

          {/* 3. INSUFFICIENT INFORMATION STATE */}
          {state === "INSUFFICIENT_INFORMATION" && (
            <div className="space-y-4 py-4" role="status" aria-live="polite">
              <div className="p-4.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-950 space-y-2.5">
                <div className="flex items-center gap-2 font-bold text-sm text-amber-900">
                  <HelpCircle className="h-5 w-5 text-amber-600 shrink-0" />
                  <span>Chưa đủ dữ liệu để kết luận chính xác</span>
                </div>
                <p className="text-xs text-amber-800 leading-relaxed">
                  {diagnostic?.error_summary ||
                    "Hệ thống AI chưa đủ thông tin hoặc cơ sở để chẩn đoán chính xác nguyên nhân sai sót cho câu hỏi này."}
                </p>
              </div>

              {diagnostic?.misconception_analysis && (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1.5">
                  <span className="font-semibold text-slate-900 block">Ghi chú từ AI:</span>
                  <div className="leading-relaxed">
                    <MathKaTeX math={diagnostic.misconception_analysis} />
                  </div>
                </div>
              )}

              <div className="p-4 rounded-xl bg-indigo-50/60 border border-indigo-100 text-xs text-indigo-900 space-y-1">
                <span className="font-semibold text-indigo-950 block">Lời khuyên dành cho bạn:</span>
                <p className="leading-relaxed text-indigo-800">
                  Hãy xem lại lời giải chi tiết của đề thi ở màn hình bên cạnh và đối chiếu từng bước tính toán.
                </p>
              </div>
            </div>
          )}

          {/* 4. SUCCESS STATE */}
          {state === "SUCCESS" && diagnostic && (
            <div className="space-y-5" aria-live="polite">
              {/* Category Badge & Summary Banner */}
              <div className="p-4 rounded-xl bg-linear-to-b from-indigo-50/80 to-white border border-indigo-100 shadow-2xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Nhận diện lỗi sai
                  </span>
                  <Badge
                    variant={
                      ERROR_CATEGORY_LABELS[diagnostic.error_category]?.variant || "purple"
                    }
                    className="text-xs font-semibold gap-1"
                  >
                    <Zap className="h-3 w-3" />
                    <span>
                      {ERROR_CATEGORY_LABELS[diagnostic.error_category]?.label ||
                        diagnostic.error_category}
                    </span>
                  </Badge>
                </div>

                <div className="text-sm font-semibold text-slate-900 leading-snug">
                  <MathKaTeX math={diagnostic.error_summary} />
                </div>
              </div>

              {/* Section 1: Misconception Analysis */}
              <Card className="border-slate-200 shadow-2xs">
                <CardContent className="p-4.5 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-indigo-950">
                    <Brain className="h-4 w-4 text-indigo-600" />
                    <span>Phân tích quan niệm sai & Lỗ hổng tư duy</span>
                  </div>
                  <div className="text-xs text-slate-700 leading-relaxed pt-1">
                    <MathKaTeX math={diagnostic.misconception_analysis} />
                  </div>
                </CardContent>
              </Card>

              {/* Section 2: Step-by-Step Guidance */}
              <Card className="border-slate-200 shadow-2xs">
                <CardContent className="p-4.5 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <ListOrdered className="h-4 w-4 text-emerald-600" />
                    <span>Hướng dẫn tư duy từng bước</span>
                  </div>
                  <div className="text-xs text-slate-700 leading-relaxed pt-1 whitespace-pre-line">
                    <MathKaTeX math={diagnostic.step_by_step_guidance} />
                  </div>
                </CardContent>
              </Card>

              {/* Section 3: Key Takeaway */}
              <div className="p-4.5 rounded-xl bg-emerald-50/80 border border-emerald-200 text-xs text-emerald-950 space-y-1.5 shadow-2xs">
                <div className="flex items-center gap-2 font-bold text-emerald-900">
                  <BookmarkCheck className="h-4 w-4 text-emerald-600" />
                  <span>Kiến thức cốt lõi cần nhớ</span>
                </div>
                <div className="text-emerald-900 leading-relaxed pt-0.5">
                  <MathKaTeX math={diagnostic.key_takeaway} />
                </div>
              </div>

              {/* Section 4: Suggested Review (Only if present and non-empty) */}
              {diagnostic.suggested_review && diagnostic.suggested_review.trim().length > 0 && (
                <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200 text-xs text-purple-950 space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-purple-900">
                    <BookOpen className="h-4 w-4 text-purple-600" />
                    <span>Đề xuất ôn tập thêm</span>
                  </div>
                  <div className="text-purple-900 leading-relaxed pt-0.5">
                    <MathKaTeX math={diagnostic.suggested_review} />
                  </div>
                </div>
              )}

              {/* Metadata Footer */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span className="flex items-center gap-1.5">
                  {data?.cached ? (
                    <Badge variant="outline" className="text-[10px] py-0 px-1 text-slate-500 border-slate-200">
                      ⚡ Đọc từ bộ nhớ đệm (Cache)
                    </Badge>
                  ) : (
                    <span>Tạo mới trong {data?.latency_ms?.toFixed(0)}ms</span>
                  )}
                </span>
                <span>Phiên bản: v{data?.prompt_version}</span>
              </div>
            </div>
          )}
        </div>

        {/* Drawer Footer Actions */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50/70 flex items-center justify-between">
          <p className="text-[11px] text-slate-400">
            Hệ thống hỗ trợ học tập thông minh — SMART LEARNING PRO
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            className="text-xs px-4 border-slate-200 hover:bg-slate-100"
          >
            Đóng lại
          </Button>
        </div>
      </div>
    </div>
  );
}

