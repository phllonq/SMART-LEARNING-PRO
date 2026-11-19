"use client";

import React, { use, useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { examsApi } from "@/lib/api/exams";
import { MathKaTeX } from "@/components/shared/math-katex";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Flag,
  Send,
  ShieldAlert,
  Trophy,
  RotateCcw,
  Home,
  Check,
  X,
  Loader2,
} from "lucide-react";
import {
  ExamAttemptQuestion,
  ExamSubmitResponse,
  SavedAnswerItem,
} from "@/types";

function parseServerDate(dateStr?: string | null): number {
  if (!dateStr) return Date.now();
  if (dateStr.endsWith("Z") || dateStr.includes("+") || dateStr.lastIndexOf("-") > 10) {
    return new Date(dateStr).getTime();
  }
  return new Date(dateStr + "Z").getTime();
}

interface PageProps {
  params: Promise<{ attemptId: string }>;
}

export default function StudentExamAttemptPage({ params }: PageProps) {
  const { attemptId } = use(params);
  const queryClient = useQueryClient();

  // Navigation & interaction state
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [localAnswers, setLocalAnswers] = useState<Record<string, SavedAnswerItem>>({});
  const [localSaveStatuses, setLocalSaveStatuses] = useState<
    Record<string, "SAVED" | "SAVING" | "ERROR" | "CONFLICT">
  >({});
  const versionCounters = useRef<Record<string, number>>({});
  const textDebounceTimers = useRef<Record<string, NodeJS.Timeout>>({});
  const pendingTextSaves = useRef<Record<string, { text: string; flagged?: boolean }>>({});
  const inFlightAutosavePromises = useRef<
    Record<string, Promise<{ status: string; version: number }>>
  >({});

  // Clean up debounce timers on unmount
  useEffect(() => {
    const timers = textDebounceTimers.current;
    return () => {
      Object.values(timers).forEach((t) => clearTimeout(t));
    };
  }, []);

  // Timer & submission state
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [submitResult, setSubmitResult] = useState<ExamSubmitResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [startTimeRef] = useState<number>(() => Date.now());

  // Fetch attempt detail
  const {
    data: attempt,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["student-attempt", attemptId],
    queryFn: () => examsApi.getAttempt(attemptId),
    retry: false,
  });

  // Synchronize versionCounters from server state on load and reload
  useEffect(() => {
    if (attempt?.saved_answers) {
      for (const [qid, ans] of Object.entries(attempt.saved_answers)) {
        const serverVer = typeof ans.version === "number" ? ans.version : 1;
        if (serverVer > (versionCounters.current[qid] || 0)) {
          versionCounters.current[qid] = serverVer;
        }
      }
    }
  }, [attempt?.saved_answers]);

  // Merge server saved answers with local interactive answers
  const selectedAnswers = useMemo(() => {
    return {
      ...(attempt?.saved_answers || {}),
      ...localAnswers,
    };
  }, [attempt?.saved_answers, localAnswers]);

  // Derive save status: local status takes precedence, otherwise if in server saved_answers it's SAVED
  const getSaveStatus = useCallback(
    (qid: string): "SAVED" | "SAVING" | "ERROR" | "CONFLICT" | "IDLE" => {
      if (localSaveStatuses[qid]) return localSaveStatuses[qid];
      if (attempt?.saved_answers?.[qid]) return "SAVED";
      return "IDLE";
    },
    [localSaveStatuses, attempt?.saved_answers]
  );

  // Safe Autosave Handler with atomic OCC versioning & centralized promise tracking
  const handleSaveAnswer = useCallback(
    (
      questionId: string,
      optionId?: string | null,
      optionIds?: string[] | null,
      text?: string | null,
      flagged?: boolean
    ): Promise<{ status: string; version: number }> => {
      if (!attempt || attempt.status !== "IN_PROGRESS") {
        return Promise.resolve({ status: "IDLE", version: 0 });
      }

      // Base version from versionCounters or server saved_answers
      const baseVersion = Math.max(
        versionCounters.current[questionId] || 0,
        attempt.saved_answers?.[questionId]?.version || 0
      );
      const expectedVersion = baseVersion > 0 ? baseVersion : undefined;
      const clientVersion = baseVersion + 1;
      versionCounters.current[questionId] = clientVersion;

      // Update local state immediately for responsive UI
      const existing = selectedAnswers[questionId] || {
        is_flagged: false,
        time_spent_seconds: 0,
      };

      const newAnswer: SavedAnswerItem = {
        selected_option_id:
          optionId !== undefined ? optionId : existing.selected_option_id,
        selected_option_ids:
          optionIds !== undefined ? optionIds : existing.selected_option_ids,
        answer_text: text !== undefined ? text : existing.answer_text,
        is_flagged: flagged !== undefined ? flagged : existing.is_flagged,
        time_spent_seconds: Math.floor((Date.now() - startTimeRef) / 1000),
        version: clientVersion,
      };

      setLocalAnswers((prev) => ({
        ...prev,
        [questionId]: newAnswer,
      }));

      setLocalSaveStatuses((prev) => ({
        ...prev,
        [questionId]: "SAVING",
      }));

      const executeAutosave = async (): Promise<{ status: string; version: number }> => {
        try {
          const response = await examsApi.autosaveAnswer(attemptId, questionId, {
            selected_option_id: newAnswer.selected_option_id,
            selected_option_ids: newAnswer.selected_option_ids,
            answer_text: newAnswer.answer_text,
            is_flagged: newAnswer.is_flagged,
            time_spent_seconds: newAnswer.time_spent_seconds,
            client_version: clientVersion,
            expected_version: expectedVersion,
          });

          // Sync authoritative version from server
          if (response.version && response.version > (versionCounters.current[questionId] || 0)) {
            versionCounters.current[questionId] = response.version;
          }

          // Only update UI status if this response corresponds to the latest requested version
          if (
            versionCounters.current[questionId] === response.version ||
            versionCounters.current[questionId] === clientVersion
          ) {
            if (response.status === "SAVED") {
              setLocalSaveStatuses((prev) => ({
                ...prev,
                [questionId]: "SAVED",
              }));
            } else if (
              response.status === "VERSION_CONFLICT" ||
              response.status === "STALE_IGNORED"
            ) {
              setLocalSaveStatuses((prev) => ({
                ...prev,
                [questionId]: "CONFLICT",
              }));
            } else {
              setLocalSaveStatuses((prev) => ({
                ...prev,
                [questionId]: "ERROR",
              }));
            }
          }

          return { status: response.status, version: response.version };
        } catch {
          if (versionCounters.current[questionId] === clientVersion) {
            setLocalSaveStatuses((prev) => ({
              ...prev,
              [questionId]: "ERROR",
            }));
          }
          return { status: "ERROR", version: clientVersion };
        } finally {
          delete inFlightAutosavePromises.current[questionId];
        }
      };

      const savePromise = executeAutosave();
      inFlightAutosavePromises.current[questionId] = savePromise;
      return savePromise;
    },
    [attempt, attemptId, selectedAnswers, startTimeRef]
  );

  // Debounced Short Answer text handler (400ms debounce)
  const handleTextChange = useCallback(
    (questionId: string, text: string) => {
      if (isSubmitting) return;

      const existing = selectedAnswers[questionId] || {
        is_flagged: false,
        time_spent_seconds: 0,
      };

      const newAnswer: SavedAnswerItem = {
        ...existing,
        answer_text: text,
        time_spent_seconds: Math.floor((Date.now() - startTimeRef) / 1000),
      };

      setLocalAnswers((prev) => ({
        ...prev,
        [questionId]: newAnswer,
      }));

      setLocalSaveStatuses((prev) => ({
        ...prev,
        [questionId]: "SAVING",
      }));

      // Record pending save for drain/flush before submit
      pendingTextSaves.current[questionId] = {
        text,
        flagged: existing.is_flagged,
      };

      if (textDebounceTimers.current[questionId]) {
        clearTimeout(textDebounceTimers.current[questionId]);
      }

      textDebounceTimers.current[questionId] = setTimeout(() => {
        delete pendingTextSaves.current[questionId];
        delete textDebounceTimers.current[questionId];
        handleSaveAnswer(
          questionId,
          undefined,
          undefined,
          text,
          existing.is_flagged
        );
      }, 400);
    },
    [handleSaveAnswer, isSubmitting, selectedAnswers, startTimeRef]
  );

  // Submission Barrier: Flush, Await, Validate, and Submit Execution
  const handleFinalSubmit = useCallback(async () => {
    // Stage 1 — Freeze: Prevent double-click or simultaneous submissions
    if (isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      // Stage 2 — Flush: Drain all pending debounce queues immediately
      for (const [qid, pending] of Object.entries(pendingTextSaves.current)) {
        if (textDebounceTimers.current[qid]) {
          clearTimeout(textDebounceTimers.current[qid]);
          delete textDebounceTimers.current[qid];
        }
        delete pendingTextSaves.current[qid];
        handleSaveAnswer(qid, undefined, undefined, pending.text, pending.flagged);
      }

      // Stage 3 — Await: Wait for ALL in-flight autosave requests across ALL question types
      const activePromises = Object.values(inFlightAutosavePromises.current);
      if (activePromises.length > 0) {
        await Promise.allSettled(activePromises);
      }

      // Stage 4 — Validate: Verify every answered question is persisted and confirmed SAVED
      const questionsList = attempt?.questions || [];
      const failedQuestions: { index: number; reason: string }[] = [];

      for (let i = 0; i < questionsList.length; i++) {
        const q = questionsList[i];
        const qid = q.question_id;
        const ans = selectedAnswers[qid];

        // Check if question has been answered (choice selected or text provided)
        const isAnswered =
          !!ans?.selected_option_id ||
          (ans?.selected_option_ids && ans.selected_option_ids.length > 0) ||
          (typeof ans?.answer_text === "string" && ans.answer_text.trim().length > 0);

        if (isAnswered) {
          const status = getSaveStatus(qid);
          if (status === "SAVING") {
            failedQuestions.push({
              index: i + 1,
              reason: "Vẫn đang được lưu vào máy chủ",
            });
          } else if (status === "CONFLICT") {
            failedQuestions.push({
              index: i + 1,
              reason: "Xung đột phiên bản",
            });
          } else if (status === "ERROR") {
            failedQuestions.push({
              index: i + 1,
              reason: "Lỗi kết nối khi lưu",
            });
          } else if (status !== "SAVED") {
            failedQuestions.push({
              index: i + 1,
              reason: "Chưa xác nhận lưu thành công",
            });
          }
        }
      }

      // If any answered question failed validation, DO NOT SUBMIT!
      if (failedQuestions.length > 0) {
        const errorDetails = failedQuestions
          .map((f) => `Câu ${f.index} (${f.reason})`)
          .join(", ");
        setSubmitError(
          `Không thể nộp bài do một số câu trả lời chưa được lưu thành công trên máy chủ: ${errorDetails}. Vui lòng kiểm tra và bấm "Thử lại" trên các câu hỏi bị lỗi trước khi nộp bài.`
        );
        setIsSubmitting(false); // Stage 6 — Unlock on validation failure
        return;
      }

      // Stage 5 — Submit: Guaranteed that all valid answers are persisted as SAVED
      const result = await examsApi.submitAttempt(attemptId);
      setSubmitResult(result);
      setIsSubmitModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["student-attempt", attemptId] });
      queryClient.invalidateQueries({ queryKey: ["student-available-exams"] });
    } catch (err: unknown) {
      // Stage 6 — Unlock on submit API error
      setIsSubmitting(false);
      const apiErr = err as {
        status?: number;
        message?: string;
        data?: { detail?: string };
        response?: { data?: { detail?: string } };
      };
      setSubmitError(
        apiErr.data?.detail ||
          apiErr.response?.data?.detail ||
          apiErr.message ||
          "Không thể nộp bài thi. Vui lòng thử lại."
      );
    }
  }, [
    attempt,
    attemptId,
    getSaveStatus,
    handleSaveAnswer,
    isSubmitting,
    queryClient,
    selectedAnswers,
  ]);

  // If attempt was already submitted/graded before opening, fetch review or submit result
  useEffect(() => {
    if (attempt && attempt.status !== "IN_PROGRESS" && !submitResult) {
      examsApi
        .submitAttempt(attemptId)
        .then((res) => setSubmitResult(res))
        .catch(() => {
          examsApi.getAttemptReview(attemptId).then((rev) => setSubmitResult(rev)).catch(() => {});
        });
    }
  }, [attempt, attemptId, submitResult]);

  // Authoritative Countdown Timer with Server Clock Skew Mitigation
  useEffect(() => {
    if (!attempt || attempt.status !== "IN_PROGRESS") return;

    const deadlineMs = parseServerDate(attempt.deadline_at);
    const serverNowMs = attempt.server_time ? parseServerDate(attempt.server_time) : Date.now();
    const serverTimeOffset = serverNowMs - Date.now();

    const updateTimer = () => {
      const nowMs = Date.now() + serverTimeOffset;
      const diffSec = Math.max(0, Math.floor((deadlineMs - nowMs) / 1000));
      setRemainingSeconds(diffSec);

      if (diffSec <= 0 && !isSubmitting) {
        // Automatically submit when deadline expired
        handleFinalSubmit();
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [attempt, handleFinalSubmit, isSubmitting]);

  // Format seconds into MM:SS or HH:MM:SS
  const formatTimer = (totalSeconds: number | null): string => {
    if (totalSeconds === null) return "--:--";
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours.toString().padStart(2, "0")}:${minutes
        .toString()
        .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
    }
    return `${minutes.toString().padStart(2, "0")}:${seconds
      .toString()
      .padStart(2, "0")}`;
  };

  // Toggle Flag on Question
  const handleToggleFlag = (questionId: string) => {
    const isCurrentlyFlagged = selectedAnswers[questionId]?.is_flagged || false;
    handleSaveAnswer(questionId, undefined, undefined, undefined, !isCurrentlyFlagged);
  };

  // ---------------------------------------------------------------------------
  // 1. Loading & Error Boundary
  // ---------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto py-6">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-10 w-32 rounded-xl" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-4">
            <Skeleton className="h-64 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-72 rounded-2xl" />
          </div>
        </div>
      </div>
    );
  }

  if (isError || !attempt) {
    const errStatus =
      (error as { status?: number })?.status ||
      (error as { response?: { status?: number } })?.response?.status;
    const isForbidden = errStatus === 403;

    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <div className="inline-flex p-3 rounded-full bg-red-100 text-red-600 mb-2">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">
          {isForbidden ? "Không có quyền truy cập" : "Không tìm thấy bài thi"}
        </h2>
        <p className="text-sm text-slate-600">
          {isForbidden
            ? "Bạn không phải chủ sở hữu của lượt thi này hoặc bài thi không được phép xem lại theo quy định bảo mật."
            : "Lượt thi không tồn tại hoặc đã bị xóa."}
        </p>
        <div className="pt-4">
          <Link href="/student/exams">
            <Button variant="outline" className="gap-2">
              <ChevronLeft className="h-4 w-4" />
              <span>Quay lại phòng luyện thi</span>
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 2. Graded / Submitted Result & Review State
  // ---------------------------------------------------------------------------
  if (submitResult || (attempt.status !== "IN_PROGRESS" && attempt.status)) {
    const res = submitResult;
    const isPassed = res?.is_passed ?? false;
    const totalScore = res?.total_score ?? 0;
    const maxScore = res?.maximum_score ?? 10.0;
    const passingScore = res?.passing_score ?? 5.0;
    const accuracy = res?.accuracy_percentage ?? 0;
    const correctCount = res?.correct_answers_count ?? 0;
    const wrongCount = res?.wrong_answers_count ?? 0;
    const skippedCount = res?.skipped_answers_count ?? 0;
    const reviews = res?.question_reviews || [];
    const reviewAllowed = res?.review_allowed ?? false;

    return (
      <div className="space-y-8 max-w-4xl mx-auto py-4">
        {/* Result Header Banner */}
        <Card
          className={`border overflow-hidden shadow-sm ${
            isPassed
              ? "border-emerald-200 bg-linear-to-b from-emerald-50/60 to-white"
              : "border-indigo-200 bg-linear-to-b from-indigo-50/60 to-white"
          }`}
        >
          <div
            className={`h-2.5 ${
              isPassed
                ? "bg-linear-to-r from-emerald-500 to-teal-500"
                : "bg-linear-to-r from-indigo-500 to-purple-500"
            }`}
          />
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-2 p-3 rounded-full bg-white shadow-xs inline-block">
              {isPassed ? (
                <Trophy className="h-10 w-10 text-emerald-500" />
              ) : (
                <CheckCircle2 className="h-10 w-10 text-indigo-500" />
              )}
            </div>
            <CardTitle className="text-2xl font-bold text-slate-900">
              {isPassed
                ? "Chúc mừng! Bạn đã hoàn thành bài thi!"
                : "Bạn đã hoàn thành bài thi!"}
            </CardTitle>
            <CardDescription className="text-sm">
              Trạng thái bài nộp:{" "}
              <Badge variant={isPassed ? "success" : "purple"}>
                {attempt.status === "AUTO_SUBMITTED"
                  ? "Tự động nộp khi hết giờ"
                  : "Đã nộp thành công"}
              </Badge>
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Score statistics grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-xl bg-white border border-slate-200/80 shadow-2xs">
              <div className="text-center space-y-1">
                <span className="text-xs text-slate-500 font-medium">Điểm số</span>
                <p className="text-2xl font-black text-indigo-600">
                  {totalScore} <span className="text-sm font-normal text-slate-400">/ {maxScore}</span>
                </p>
                <span className="text-[11px] text-slate-400 block">
                  Điểm đạt: {passingScore} đ
                </span>
              </div>
              <div className="text-center space-y-1">
                <span className="text-xs text-slate-500 font-medium">Độ chính xác</span>
                <p className="text-2xl font-black text-slate-800">{accuracy}%</p>
                <span className="text-[11px] text-slate-400 block">
                  {isPassed ? "Đạt chuẩn yêu cầu" : "Cần ôn tập thêm"}
                </span>
              </div>
              <div className="text-center space-y-1">
                <span className="text-xs text-slate-500 font-medium">Số câu đúng</span>
                <p className="text-2xl font-black text-emerald-600">
                  {correctCount}
                  <span className="text-sm font-normal text-slate-400">
                    /{correctCount + wrongCount + skippedCount}
                  </span>
                </p>
                <span className="text-[11px] text-emerald-600 font-medium block">
                  ✓ Trả lời chính xác
                </span>
              </div>
              <div className="text-center space-y-1">
                <span className="text-xs text-slate-500 font-medium">Sai / Bỏ qua</span>
                <p className="text-2xl font-black text-rose-500">
                  {wrongCount + skippedCount}
                </p>
                <span className="text-[11px] text-slate-400 block">
                  {wrongCount} sai, {skippedCount} chưa làm
                </span>
              </div>
            </div>

            {/* Feedback message */}
            {res?.feedback_summary && (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-sm leading-relaxed">
                <p className="font-semibold text-slate-900 mb-1">Đánh giá kết quả:</p>
                <p>{res.feedback_summary}</p>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex flex-wrap gap-3 justify-center pt-2">
              <Link href="/student/exams">
                <Button variant="default" className="gap-2">
                  <RotateCcw className="h-4 w-4" />
                  <span>Quay về danh sách đề thi</span>
                </Button>
              </Link>
              <Link href="/student/dashboard">
                <Button variant="outline" className="gap-2">
                  <Home className="h-4 w-4" />
                  <span>Trang chủ học sinh</span>
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Detailed Question Review Section */}
        {reviewAllowed && reviews.length > 0 ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">
                Xem lại chi tiết đáp án & Lời giải
              </h3>
              <Badge variant="secondary">{reviews.length} câu hỏi</Badge>
            </div>

            <div className="space-y-4">
              {reviews.map((q, idx) => (
                <Card
                  key={q.question_id || idx}
                  className={`border shadow-2xs ${
                    q.is_correct ? "border-emerald-200" : "border-rose-200"
                  }`}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-slate-500">
                        Câu {idx + 1}
                      </span>
                      <div className="flex items-center gap-2">
                        {q.is_correct ? (
                          <Badge variant="success" className="gap-1 text-xs">
                            <Check className="h-3 w-3" /> Đúng (+{q.points_awarded} đ)
                          </Badge>
                        ) : (
                          <Badge variant="destructive" className="gap-1 text-xs">
                            <X className="h-3 w-3" /> Sai (0 đ / {q.max_points} đ)
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="text-sm font-medium text-slate-900 pt-1">
                      <MathKaTeX math={q.content} />
                    </div>
                  </CardHeader>

                  <CardContent className="pt-2 space-y-3">
                    {/* Student's answer text for SHORT_ANSWER */}
                    {q.question_type === "SHORT_ANSWER" && (
                      <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs">
                        <span className="font-semibold text-slate-700">Câu trả lời của bạn: </span>
                        <span className={`font-bold ${q.is_correct ? "text-emerald-700" : "text-rose-600"}`}>
                          {q.student_answer_text || "(Chưa trả lời)"}
                        </span>
                      </div>
                    )}

                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs">
                      <span className="font-semibold text-slate-700">Đáp án đúng: </span>
                      <span className="font-bold text-emerald-700">
                        {q.correct_answer_texts && q.correct_answer_texts.length > 0
                          ? q.correct_answer_texts.join(" / ")
                          : q.correct_option_keys?.join(", ") || "Đáp án chuẩn"}
                      </span>
                    </div>

                    {q.explanation && (
                      <div className="p-3.5 rounded-lg bg-indigo-50/70 border border-indigo-100 text-xs space-y-1">
                        <span className="font-semibold text-indigo-900 block">
                          Lời giải chi tiết:
                        </span>
                        <div className="text-slate-700 leading-relaxed">
                          <MathKaTeX math={q.explanation} />
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ) : (
          <Card className="border-slate-200 bg-slate-50/60 p-6 text-center text-sm text-slate-600">
            <p className="font-semibold text-slate-800">
              Chế độ bảo mật đề thi
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Đề thi này không mở xem lại đáp án chi tiết theo thiết lập của giáo viên.
            </p>
          </Card>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 3. Active Examination Mode (IN_PROGRESS)
  // ---------------------------------------------------------------------------
  const questions: ExamAttemptQuestion[] = attempt.questions || [];
  const currentQuestion = questions[currentQIndex];
  const totalQuestions = questions.length;

  if (totalQuestions === 0) {
    return (
      <div className="max-w-md mx-auto py-16 text-center space-y-4">
        <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto" />
        <h2 className="text-lg font-bold text-slate-900">Đề thi không có câu hỏi</h2>
        <p className="text-sm text-slate-600">
          Đề thi này chưa được cấu hình câu hỏi nào.
        </p>
        <Link href="/student/exams">
          <Button variant="outline">Quay lại</Button>
        </Link>
      </div>
    );
  }

  const currentQId = currentQuestion?.question_id;
  const currentSaved = currentQId ? selectedAnswers[currentQId] : undefined;
  const currentSaveStatus = currentQId ? getSaveStatus(currentQId) : undefined;
  const isFlagged = currentSaved?.is_flagged || false;

  const answeredCount = questions.filter(
    (q) =>
      selectedAnswers[q.question_id]?.selected_option_id ||
      (selectedAnswers[q.question_id]?.selected_option_ids &&
        selectedAnswers[q.question_id].selected_option_ids!.length > 0) ||
      (typeof selectedAnswers[q.question_id]?.answer_text === "string" &&
        selectedAnswers[q.question_id].answer_text!.trim().length > 0)
  ).length;
  const unansweredCount = totalQuestions - answeredCount;

  const isAnySaving = Object.values(localSaveStatuses).some((s) => s === "SAVING");
  const isAnyConflict = Object.values(localSaveStatuses).some((s) => s === "CONFLICT");
  const isAnyError = Object.values(localSaveStatuses).some((s) => s === "ERROR");
  const hasUnresolvedIssues = isAnyConflict || isAnyError || isAnySaving;

  // Active Save Status text & icon
  const renderSaveStatus = () => {
    if (currentSaveStatus === "SAVING") {
      return (
        <span className="flex items-center gap-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-100">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Đang lưu...</span>
        </span>
      );
    }
    if (currentSaveStatus === "CONFLICT") {
      return (
        <button
          onClick={() =>
            currentQId &&
            handleSaveAnswer(
              currentQId,
              currentSaved?.selected_option_id,
              currentSaved?.selected_option_ids,
              currentSaved?.answer_text,
              currentSaved?.is_flagged
            )
          }
          title="Xung đột phiên bản lưu bài. Bấm để thử lại và ghi đè."
          className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200 hover:bg-amber-100 transition-colors"
        >
          <AlertTriangle className="h-3 w-3 text-amber-600" />
          <span>Xung đột lưu (Thử lại)</span>
        </button>
      );
    }
    if (currentSaveStatus === "ERROR") {
      return (
        <button
          onClick={() =>
            currentQId &&
            handleSaveAnswer(
              currentQId,
              currentSaved?.selected_option_id,
              currentSaved?.selected_option_ids,
              currentSaved?.answer_text,
              currentSaved?.is_flagged
            )
          }
          className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 bg-rose-50 px-2.5 py-1 rounded-full border border-rose-200 hover:bg-rose-100 transition-colors"
        >
          <AlertTriangle className="h-3 w-3" />
          <span>Lỗi lưu (Thử lại)</span>
        </button>
      );
    }
    if (currentSaveStatus === "SAVED") {
      return (
        <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-100">
          <Check className="h-3 w-3" />
          <span>Đã lưu máy chủ</span>
        </span>
      );
    }
    return (
      <span className="text-xs text-slate-400">
        Chưa chọn
      </span>
    );
  };

  const isTimerCritical = remainingSeconds !== null && remainingSeconds < 300; // < 5 mins
  const isTimerDanger = remainingSeconds !== null && remainingSeconds < 60; // < 1 min

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-2">
      {/* Authoritative Sticky Top Navigation Bar */}
      <div className="sticky top-2 z-30 rounded-2xl bg-white/95 backdrop-blur-md border border-slate-200/80 shadow-md p-3 sm:p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Badge variant="purple" className="hidden sm:inline-flex">
            Lượt thi #{attempt.attempt_number || 1}
          </Badge>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium hidden sm:inline">
              Tiến độ:
            </span>
            <span className="text-sm font-bold text-slate-800">
              {answeredCount}/{totalQuestions} câu
            </span>
          </div>
        </div>

        {/* Authoritative Countdown Timer */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border font-mono font-bold text-sm sm:text-base transition-colors ${
            isTimerDanger
              ? "bg-rose-100 text-rose-700 border-rose-300 animate-pulse"
              : isTimerCritical
              ? "bg-amber-50 text-amber-700 border-amber-200"
              : "bg-slate-50 text-slate-800 border-slate-200"
          }`}
        >
          <Clock className={`h-4 w-4 ${isTimerDanger ? "text-rose-600" : isTimerCritical ? "text-amber-600" : "text-slate-500"}`} />
          <span>{formatTimer(remainingSeconds)}</span>
        </div>

        {/* Status & Submit CTA */}
        <div className="flex items-center gap-2.5">
          <div className="hidden sm:block">{renderSaveStatus()}</div>
          <Button
            onClick={() => setIsSubmitModalOpen(true)}
            size="sm"
            className="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs font-semibold"
          >
            <Send className="h-3.5 w-3.5" />
            <span>Nộp bài</span>
          </Button>
        </div>
      </div>

      {/* Main Examination View Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Left Column: Current Question Interactive Card */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-base text-indigo-700">
                    Câu hỏi {currentQIndex + 1}
                  </span>
                  <span className="text-xs text-slate-400">/ {totalQuestions}</span>
                  <Badge variant="secondary" className="text-[11px] font-normal">
                    {currentQuestion.points} điểm
                  </Badge>
                </div>

                <div className="flex items-center gap-2">
                  <div className="sm:hidden">{renderSaveStatus()}</div>
                  <Button
                    variant={isFlagged ? "default" : "outline"}
                    size="sm"
                    disabled={isSubmitting}
                    onClick={() => handleToggleFlag(currentQId)}
                    className={`h-8 gap-1.5 text-xs ${
                      isFlagged
                        ? "bg-amber-500 hover:bg-amber-600 text-white border-amber-500"
                        : "text-slate-600"
                    }`}
                  >
                    <Flag className={`h-3 w-3 ${isFlagged ? "fill-current" : ""}`} />
                    <span>{isFlagged ? "Đã gắn cờ" : "Gắn cờ"}</span>
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="pt-5 space-y-6">
              {/* Question Content (KaTeX formula supported) */}
              <div className="text-base text-slate-900 leading-relaxed font-normal">
                <MathKaTeX math={currentQuestion.content} />
              </div>

              {/* Options selection based on question type */}
              <div className="space-y-3 pt-2">
                {currentQuestion.question_type === "SINGLE_CHOICE" ||
                currentQuestion.question_type === "TRUE_FALSE" ? (
                  currentQuestion.options.map((opt) => {
                    const isSelected = currentSaved?.selected_option_id === opt.id;
                    return (
                      <div
                        key={opt.id}
                        onClick={() => {
                          if (isSubmitting) return;
                          handleSaveAnswer(
                            currentQId,
                            opt.id,
                            undefined,
                            undefined,
                            currentSaved?.is_flagged
                          );
                        }}
                        className={`group flex items-start gap-3.5 p-3.5 sm:p-4 rounded-xl border transition-all ${
                          isSubmitting ? "cursor-not-allowed opacity-75" : "cursor-pointer"
                        } ${
                          isSelected
                            ? "bg-indigo-50/80 border-indigo-400 text-indigo-950 ring-2 ring-indigo-200/50 shadow-2xs"
                            : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-800"
                        }`}
                      >
                        <div
                          className={`flex items-center justify-center shrink-0 w-7 h-7 rounded-full text-xs font-bold transition-colors ${
                            isSelected
                              ? "bg-indigo-600 text-white shadow-xs"
                              : "bg-slate-100 text-slate-600 group-hover:bg-slate-200"
                          }`}
                        >
                          {opt.option_key}
                        </div>
                        <div className="text-sm font-normal pt-0.5 leading-relaxed flex-1">
                          <MathKaTeX math={opt.content} />
                        </div>
                      </div>
                    );
                  })
                ) : currentQuestion.question_type === "MULTIPLE_CHOICE" ? (
                  currentQuestion.options.map((opt) => {
                    const currentSelectedIds = currentSaved?.selected_option_ids || [];
                    const isChecked = currentSelectedIds.includes(opt.id);

                    const toggleOption = () => {
                      if (isSubmitting) return;
                      const updated = isChecked
                        ? currentSelectedIds.filter((id: string) => id !== opt.id)
                        : [...currentSelectedIds, opt.id];
                      handleSaveAnswer(
                        currentQId,
                        undefined,
                        updated,
                        undefined,
                        currentSaved?.is_flagged
                      );
                    };

                    return (
                      <div
                        key={opt.id}
                        onClick={toggleOption}
                        className={`group flex items-start gap-3.5 p-3.5 sm:p-4 rounded-xl border transition-all ${
                          isSubmitting ? "cursor-not-allowed opacity-75" : "cursor-pointer"
                        } ${
                          isChecked
                            ? "bg-indigo-50/80 border-indigo-400 text-indigo-950 ring-2 ring-indigo-200/50 shadow-2xs"
                            : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-800"
                        }`}
                      >
                        <div
                          className={`flex items-center justify-center shrink-0 w-6 h-6 rounded-md text-xs font-bold transition-colors ${
                            isChecked
                              ? "bg-indigo-600 text-white shadow-xs"
                              : "bg-slate-100 text-slate-600 group-hover:bg-slate-200"
                          }`}
                        >
                          {isChecked ? <Check className="h-3.5 w-3.5" /> : opt.option_key}
                        </div>
                        <div className="text-sm font-normal pt-0.5 leading-relaxed flex-1">
                          <MathKaTeX math={opt.content} />
                        </div>
                      </div>
                    );
                  })
                ) : currentQuestion.question_type === "SHORT_ANSWER" ? (
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-600">
                      Nhập câu trả lời ngắn:
                    </label>
                    <input
                      type="text"
                      disabled={isSubmitting}
                      value={currentSaved?.answer_text || ""}
                      onChange={(e) => handleTextChange(currentQId, e.target.value)}
                      placeholder="Gõ đáp án của bạn tại đây..."
                      className="w-full rounded-xl border border-slate-300 p-3 text-sm focus:border-indigo-500 focus:outline-hidden focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100 disabled:cursor-not-allowed"
                    />
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">
                    Dạng câu hỏi chưa được hỗ trợ trả lời tự động.
                  </p>
                )}
              </div>

              {/* Prev / Next Bottom Action Controls */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentQIndex === 0}
                  onClick={() => setCurrentQIndex((prev) => Math.max(0, prev - 1))}
                  className="gap-1.5"
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span>Câu trước</span>
                </Button>

                {currentQIndex < totalQuestions - 1 ? (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() =>
                      setCurrentQIndex((prev) => Math.min(totalQuestions - 1, prev + 1))
                    }
                    className="gap-1.5"
                  >
                    <span>Câu tiếp theo</span>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => setIsSubmitModalOpen(true)}
                    className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <span>Kiểm tra & Nộp bài</span>
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Question Matrix Navigation Card */}
        <div className="space-y-4">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-bold text-slate-900 flex items-center justify-between">
                <span>Ma trận câu hỏi</span>
                <span className="text-xs font-medium text-slate-500">
                  {Math.round((answeredCount / totalQuestions) * 100)}%
                </span>
              </CardTitle>
              {/* Progress bar */}
              <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
                <div
                  className="bg-indigo-600 h-1.5 rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.round((answeredCount / totalQuestions) * 100)}%`,
                  }}
                />
              </div>
            </CardHeader>

            <CardContent className="space-y-4 pt-1">
              {/* Matrix of clickable numbers */}
              <div className="grid grid-cols-5 gap-2">
                {questions.map((q, idx) => {
                  const ans = selectedAnswers[q.question_id];
                  const isAnswered =
                    !!ans?.selected_option_id ||
                    (ans?.selected_option_ids && ans.selected_option_ids.length > 0) ||
                    !!ans?.answer_text;
                  const isCurrent = currentQIndex === idx;
                  const isQFlagged = ans?.is_flagged || false;

                  return (
                    <button
                      key={q.question_id}
                      onClick={() => setCurrentQIndex(idx)}
                      className={`relative flex items-center justify-center h-10 rounded-xl text-xs font-semibold transition-all ${
                        isCurrent
                          ? "ring-2 ring-indigo-600 ring-offset-1 text-white bg-indigo-600 shadow-sm"
                          : isAnswered
                          ? "bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
                          : "bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100"
                      }`}
                    >
                      <span>{idx + 1}</span>
                      {isQFlagged && (
                        <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-amber-500 rounded-full ring-2 ring-white" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Legend */}
              <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-[11px] text-slate-500">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-md bg-indigo-50 border border-indigo-200 inline-block" />
                  <span>Đã làm ({answeredCount})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-md bg-slate-50 border border-slate-200 inline-block" />
                  <span>Chưa làm ({unansweredCount})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-md bg-indigo-600 inline-block" />
                  <span>Đang xem</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
                  <span>Đã gắn cờ</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Submit Confirmation Dialog */}
      <Dialog
        isOpen={isSubmitModalOpen}
        onClose={() => !isSubmitting && setIsSubmitModalOpen(false)}
        title="Xác nhận nộp bài thi"
        description="Vui lòng kiểm tra lại số lượng câu hỏi đã hoàn thành trước khi gửi bài chấm điểm."
      >
        <div className="space-y-4 pt-2">
          {/* Summary Box */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">Tổng số câu hỏi:</span>
              <span className="font-semibold text-slate-900">{totalQuestions} câu</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Đã trả lời:</span>
              <span className="font-semibold text-emerald-600">{answeredCount} câu</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Chưa trả lời:</span>
              <span className={`font-semibold ${unansweredCount > 0 ? "text-amber-600" : "text-slate-900"}`}>
                {unansweredCount} câu
              </span>
            </div>
            <div className="flex justify-between pt-2 border-t border-slate-200">
              <span className="text-slate-600">Thời gian còn lại:</span>
              <span className="font-mono font-bold text-slate-800">
                {formatTimer(remainingSeconds)}
              </span>
            </div>
          </div>

          {unansweredCount > 0 && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
              <span>
                Cảnh báo: Bạn vẫn còn <strong>{unansweredCount} câu chưa chọn đáp án</strong>. Bài thi sẽ chỉ chấm các câu bạn đã hoàn thành.
              </span>
            </div>
          )}

          {hasUnresolvedIssues && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
              <span>
                Cảnh báo: Có câu hỏi chưa được lưu thành công trên máy chủ (Xung đột hoặc Lỗi kết nối). Vui lòng đóng hộp thoại và bấm &quot;Thử lại&quot; trước khi nộp bài.
              </span>
            </div>
          )}

          {submitError && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-3">
            <Button
              type="button"
              variant="outline"
              disabled={isSubmitting}
              onClick={() => setIsSubmitModalOpen(false)}
            >
              Tiếp tục làm bài
            </Button>
            <Button
              type="button"
              variant="default"
              disabled={isSubmitting || hasUnresolvedIssues}
              onClick={() => handleFinalSubmit()}
              className="gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Đang xác nhận & nộp...</span>
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  <span>Xác nhận nộp bài</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
