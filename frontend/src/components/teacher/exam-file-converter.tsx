"use client";

import React, { useState } from "react";
import { examsApi } from "@/lib/api/exams";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { MathKaTeX } from "@/components/shared/math-katex";
import {
  DraftQuizQuestion,
  ExamConvertConfirmResponse,
  ExamConvertPreviewResponse,
} from "@/types";
import {
  Upload,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  Loader2,
  FileText,
} from "lucide-react";

interface ExamFileConverterModalProps {
  isOpen: boolean;
  onClose: () => void;
  classroomId?: string;
  defaultGradeId?: number;
  onSuccess: (result: ExamConvertConfirmResponse) => void;
}

export function ExamFileConverterModal({
  isOpen,
  onClose,
  classroomId,
  defaultGradeId = 10,
  onSuccess,
}: ExamFileConverterModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [useAi, setUseAi] = useState(true);
  const [isParsing, setIsParsing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [previewMeta, setPreviewMeta] =
    useState<ExamConvertPreviewResponse | null>(null);
  const [drafts, setDrafts] = useState<DraftQuizQuestion[]>([]);

  // Exam & optional classroom assignment settings
  const [title, setTitle] = useState("");
  const [gradeId, setGradeId] = useState<number>(defaultGradeId);
  const [durationMinutes, setDurationMinutes] = useState<number>(45);
  const [totalPoints, setTotalPoints] = useState<number>(10);
  const [passingPoints, setPassingPoints] = useState<number>(5);
  const [description, setDescription] = useState("");
  const [publishNow, setPublishNow] = useState(true);
  const [dueDate, setDueDate] = useState("");
  const [allowLate, setAllowLate] = useState(false);

  const handleFilePicked = async (file: File | null) => {
    setSelectedFile(file);
    setErrorMsg(null);
    setPreviewMeta(null);
    setDrafts([]);

    if (!file) return;

    setIsParsing(true);
    try {
      const res = await examsApi.previewConvertExamFile(file, useAi);
      setPreviewMeta(res);
      setDrafts(res.draft_questions);
      setTitle(res.suggested_title);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Không thể phân tích tệp đề thi tải lên."
      );
    } finally {
      setIsParsing(false);
    }
  };

  const handleSelectCorrectOption = (qIndex: number, optionKey: string) => {
    setDrafts((prev) =>
      prev.map((q, idx) => {
        if (idx !== qIndex) return q;
        const isMulti = q.question_type === "MULTIPLE_CHOICE";
        const updatedOptions = q.options.map((opt) => {
          if (isMulti) {
            return opt.option_key === optionKey
              ? { ...opt, is_correct: !opt.is_correct }
              : opt;
          }
          return { ...opt, is_correct: opt.option_key === optionKey };
        });
        const hasCorrect = updatedOptions.some((o) => o.is_correct);
        return {
          ...q,
          options: updatedOptions,
          has_correct_answer: hasCorrect,
          warning: hasCorrect
            ? null
            : "Vui lòng chọn ít nhất 1 đáp án đúng cho câu hỏi này.",
        };
      })
    );
  };

  const handleRemoveQuestion = (qIndex: number) => {
    setDrafts((prev) => prev.filter((_, idx) => idx !== qIndex));
  };

  const missingAnswerCount = drafts.filter((q) => !q.has_correct_answer).length;

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (drafts.length === 0) {
      setErrorMsg("Chưa có câu hỏi nào để tạo đề trắc nghiệm.");
      return;
    }
    if (missingAnswerCount > 0) {
      setErrorMsg(
        `Còn ${missingAnswerCount} câu chưa có đáp án đúng. Vui lòng bấm chọn đáp án (A/B/C/D) ở danh sách bên dưới trước khi tạo đề.`
      );
      return;
    }
    if (classroomId && !dueDate) {
      setErrorMsg("Vui lòng chọn hạn chót nộp bài cho lớp học.");
      return;
    }

    setIsSaving(true);
    try {
      const res = await examsApi.confirmConvertExamToQuiz({
        title: title.trim(),
        description: description.trim() || undefined,
        grade_id: gradeId,
        duration_minutes: durationMinutes,
        total_points: totalPoints,
        passing_points: passingPoints,
        publish_now: publishNow,
        questions: drafts.map((q) => ({
          content: q.content,
          question_type: q.question_type,
          difficulty_level: q.difficulty_level,
          options: q.options,
          explanation: q.explanation ?? null,
          hint: q.hint ?? null,
          tags: q.tags ?? null,
          is_public: true,
        })),
        classroom_id: classroomId,
        assignment_title: classroomId ? title.trim() : undefined,
        due_date:
          classroomId && dueDate ? new Date(dueDate).toISOString() : undefined,
        allow_late_submission: allowLate,
      });
      onSuccess(res);
      onClose();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Không thể lưu đề trắc nghiệm. Vui lòng kiểm tra lại."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const extractionLabel = (method: string) => {
    switch (method) {
      case "ai_gemini":
        return "AI Gemini Tự động";
      case "heuristic_docx":
        return "Word Thông minh";
      case "heuristic_txt":
        return "Văn bản Thông minh";
      case "heuristic_pdf":
        return "PDF Văn bản";
      default:
        return "Bảng tính / JSON chuẩn";
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={
        classroomId
          ? "Up đề từ máy -> Tự chuyển thành Bài Trắc nghiệm"
          : "Chuyển tệp đề thi thành Đề Trắc nghiệm trực tuyến"
      }
      description="Tải lên tệp Word (.docx), .txt, .pdf, ảnh chụp hoặc Excel/CSV/JSON — hệ thống tự động tách câu hỏi & đáp án để chấm điểm tự động và dùng AI Tutor"
      maxWidth="xl"
    >
      <form
        onSubmit={handleConfirm}
        className="space-y-4 max-h-[78vh] overflow-y-auto pr-1"
      >
        {errorMsg && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* File Picker Box */}
        <div className="rounded-xl border border-dashed border-emerald-300 bg-emerald-50/40 p-4 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Upload className="h-4 w-4 text-emerald-600" />
              <span>Chọn tệp đề từ máy (.docx, .txt, .pdf, ảnh, .xlsx, .csv, .json)</span>
            </label>
            <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(e) => setUseAi(e.target.checked)}
                className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              <span>Tự động nhận diện thông minh / AI</span>
            </label>
          </div>

          <input
            type="file"
            accept=".docx,.txt,.pdf,.png,.jpg,.jpeg,.webp,.xlsx,.csv,.json"
            onChange={(e) => handleFilePicked(e.target.files?.[0] || null)}
            className="block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700"
          />

          <p className="text-[11px] text-slate-500 leading-relaxed">
            Hỗ trợ tự nhận diện câu hỏi <code>Câu 1: ... A. B. C. D.</code>, đáp án đánh dấu <code>*A.</code>, gạch chân/tô màu/in đậm trong Word, hoặc bảng <code>ĐÁP ÁN</code> ở cuối đề.
          </p>
        </div>

        {isParsing && (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-emerald-700">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Đang tách câu hỏi và chuyển đổi sang trắc nghiệm...</span>
          </div>
        )}

        {previewMeta && !isParsing && (
          <>
            {/* Summary Badges */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="outline" className="gap-1">
                <FileText className="h-3 w-3" />
                <span>{extractionLabel(previewMeta.extraction_method)}</span>
              </Badge>
              <Badge variant="success">
                Nhận diện: {drafts.length} câu hỏi
              </Badge>
              {missingAnswerCount > 0 ? (
                <Badge variant="warning">
                  Cần chọn đáp án: {missingAnswerCount} câu
                </Badge>
              ) : (
                <Badge variant="success" className="gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Đầy đủ đáp án</span>
                </Badge>
              )}
              {selectedFile && (
                <span className="text-slate-400 truncate max-w-[200px]">
                  {selectedFile.name}
                </span>
              )}
            </div>

            {/* Exam Metadata Settings */}
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-3">
              <Input
                label={classroomId ? "Tên bài tập / Đề trắc nghiệm" : "Tên đề thi"}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-700">
                    Khối lớp
                  </label>
                  <select
                    value={gradeId}
                    onChange={(e) => setGradeId(Number(e.target.value))}
                    className="flex h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none"
                  >
                    {[6, 7, 8, 9, 10, 11, 12].map((g) => (
                      <option key={g} value={g}>
                        Khối {g}
                      </option>
                    ))}
                  </select>
                </div>

                <Input
                  label="Thời lượng (phút)"
                  type="number"
                  min={5}
                  max={300}
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Number(e.target.value))}
                  required
                />
                <Input
                  label="Thang điểm"
                  type="number"
                  step="0.5"
                  min={1}
                  max={100}
                  value={totalPoints}
                  onChange={(e) => setTotalPoints(Number(e.target.value))}
                  required
                />
                <Input
                  label="Điểm đạt"
                  type="number"
                  step="0.5"
                  min={0}
                  max={100}
                  value={passingPoints}
                  onChange={(e) => setPassingPoints(Number(e.target.value))}
                  required
                />
              </div>

              {classroomId ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-slate-700">
                      Hạn chót nộp bài (Due Date)
                    </label>
                    <input
                      type="datetime-local"
                      value={dueDate}
                      onChange={(e) => setDueDate(e.target.value)}
                      required
                      className="flex h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                  <div className="flex items-end pb-2">
                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={allowLate}
                        onChange={(e) => setAllowLate(e.target.checked)}
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      <span>Cho phép học sinh nộp muộn sau hạn chót</span>
                    </label>
                  </div>
                </div>
              ) : (
                <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={publishNow}
                    onChange={(e) => setPublishNow(e.target.checked)}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Xuất bản đề thi ngay để có thể giao cho lớp</span>
                </label>
              )}

              <Input
                label="Mô tả (Tùy chọn)"
                placeholder="Hướng dẫn làm bài hoặc phạm vi kiến thức..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            {/* Interactive Extracted Questions Preview */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-700">
                  Xem trước & Chỉnh nhanh đáp án đúng ({drafts.length} câu):
                </p>
                <span className="text-[11px] text-slate-500">
                  Bấm vào phương án A/B/C/D để đặt hoặc đổi đáp án đúng
                </span>
              </div>

              <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                {drafts.map((q, qIdx) => (
                  <div
                    key={qIdx}
                    className={`rounded-xl border p-3 text-xs space-y-2 ${
                      q.has_correct_answer
                        ? "border-slate-200 bg-slate-50/50"
                        : "border-amber-300 bg-amber-50/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold text-slate-900 leading-relaxed">
                        <span className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 text-[11px]">
                          Câu {qIdx + 1}
                        </span>
                        <MathKaTeX math={q.content} />
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveQuestion(qIdx)}
                        title="Bỏ câu này"
                        className="text-slate-400 hover:text-rose-600 p-1 shrink-0"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    {!q.has_correct_answer && (
                      <p className="text-[11px] font-medium text-amber-800">
                        {q.warning || "Chưa có đáp án đúng — vui lòng bấm chọn bên dưới:"}
                      </p>
                    )}

                    {q.options.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                        {q.options.map((opt) => (
                          <button
                            key={opt.option_key}
                            type="button"
                            onClick={() =>
                              handleSelectCorrectOption(qIdx, opt.option_key)
                            }
                            className={`flex items-start gap-2 text-left rounded-lg border px-2.5 py-1.5 transition-colors ${
                              opt.is_correct
                                ? "bg-emerald-50 border-emerald-400 text-emerald-900 font-semibold"
                                : "bg-white border-slate-200 text-slate-700 hover:border-emerald-300"
                            }`}
                          >
                            <span
                              className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                                opt.is_correct
                                  ? "bg-emerald-600 text-white"
                                  : "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {opt.option_key}
                            </span>
                            <span className="flex-1">
                              <MathKaTeX math={opt.content} />
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
          <Button type="button" variant="outline" onClick={onClose}>
            Đóng
          </Button>
          <Button
            type="submit"
            disabled={isParsing || drafts.length === 0}
            isLoading={isSaving}
            className="bg-emerald-600 hover:bg-emerald-700 gap-1.5"
          >
            <Sparkles className="h-4 w-4" />
            <span>
              {classroomId
                ? "Tạo Trắc nghiệm & Giao cho lớp"
                : "Lưu thành Đề Trắc nghiệm"}
            </span>
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
