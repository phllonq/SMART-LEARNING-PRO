"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { questionsApi } from "@/lib/api/questions";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { MathKaTeX } from "@/components/shared/math-katex";
import { QuestionImportResponse } from "@/types";
import {
  FileQuestion,
  Search,
  CheckCircle2,
  Lightbulb,
  BookOpen,
  Upload,
  Download,
  AlertTriangle,
  FileSpreadsheet,
} from "lucide-react";

export default function TeacherQuestionsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>("");
  const [page, setPage] = useState(1);

  // Import modal states
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importIsPublic, setImportIsPublic] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<QuestionImportResponse | null>(null);
  const [importSuccessMsg, setImportSuccessMsg] = useState<string | null>(null);

  const {
    data: questionsData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["teacher-questions", searchTerm, selectedDifficulty, page],
    queryFn: () =>
      questionsApi.getQuestions({
        search: searchTerm || undefined,
        difficulty_level: selectedDifficulty || undefined,
        page,
        page_size: 15,
      }),
  });

  const questions = questionsData?.items || [];
  const total = questionsData?.total || 0;

  const resetImportModal = () => {
    setImportFile(null);
    setImportError(null);
    setPreviewResult(null);
    setImportSuccessMsg(null);
  };

  const handleDownloadTemplate = async () => {
    try {
      await questionsApi.downloadCsvTemplate();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Tải file mẫu thất bại.");
    }
  };

  const handlePreviewImport = async () => {
    if (!importFile) {
      setImportError("Vui lòng chọn file .xlsx, .csv, .json hoặc .docx.");
      return;
    }
    setImportError(null);
    setImportSuccessMsg(null);
    setIsPreviewing(true);
    try {
      const res = await questionsApi.importQuestionsFile({
        file: importFile,
        is_public: importIsPublic,
        dry_run: true,
      });
      setPreviewResult(res);
    } catch (err: unknown) {
      setImportError(
        err instanceof Error ? err.message : "Không thể đọc tệp câu hỏi."
      );
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!importFile) {
      setImportError("Vui lòng chọn file câu hỏi trước khi import.");
      return;
    }
    setImportError(null);
    setIsImporting(true);
    try {
      const res = await questionsApi.importQuestionsFile({
        file: importFile,
        is_public: importIsPublic,
        dry_run: false,
      });
      setPreviewResult(res);
      setImportSuccessMsg(
        `Đã thêm thành công ${res.imported_count}/${res.total_detected} câu hỏi vào ngân hàng.`
      );
      refetch();
    } catch (err: unknown) {
      setImportError(
        err instanceof Error ? err.message : "Import câu hỏi thất bại."
      );
    } finally {
      setIsImporting(false);
    }
  };

  const getDifficultyBadge = (level: string) => {
    switch (level) {
      case "RECOGNITION":
        return <Badge variant="secondary">Nhận biết</Badge>;
      case "COMPREHENSION":
        return <Badge variant="default">Thông hiểu</Badge>;
      case "APPLICATION":
        return <Badge variant="warning">Vận dụng</Badge>;
      case "HIGH_APPLICATION":
        return <Badge variant="destructive">Vận dụng cao</Badge>;
      default:
        return <Badge variant="outline">{level}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Ngân hàng Câu hỏi Chuẩn hóa
          </h2>
          <p className="text-sm text-slate-500">
            Kho câu hỏi trắc nghiệm và tự luận hỗ trợ công thức Toán học KaTeX chuẩn quốc tế ({total} câu)
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={handleDownloadTemplate}
            className="gap-1.5 text-xs sm:text-sm"
          >
            <Download className="h-4 w-4" />
            <span>Tải mẫu CSV</span>
          </Button>
          <Button
            onClick={() => {
              resetImportModal();
              setIsImportOpen(true);
            }}
            className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-xs sm:text-sm"
          >
            <Upload className="h-4 w-4" />
            <span>Import câu hỏi từ máy</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-3 items-center">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Tìm kiếm nội dung câu hỏi hoặc từ khóa..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="w-full sm:w-auto">
            <select
              value={selectedDifficulty}
              onChange={(e) => {
                setSelectedDifficulty(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-auto px-3.5 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-none focus:border-emerald-500"
            >
              <option value="">Tất cả cấp độ nhận thức</option>
              <option value="RECOGNITION">Nhận biết</option>
              <option value="COMPREHENSION">Thông hiểu</option>
              <option value="APPLICATION">Vận dụng</option>
              <option value="HIGH_APPLICATION">Vận dụng cao</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Questions List */}
      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-40 w-full rounded-xl" />
        </div>
      ) : questions.length === 0 ? (
        <EmptyState
          icon={FileQuestion}
          title="Không tìm thấy câu hỏi phù hợp"
          description="Thử thay đổi từ khóa tìm kiếm hoặc bỏ bộ lọc mức độ nhận thức."
        />
      ) : (
        <div className="space-y-4">
          {questions.map((q, index) => (
            <Card key={q.id} className="p-5 space-y-4 shadow-xs hover:border-emerald-200 transition-all">
              {/* Question Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                    Câu {(page - 1) * 15 + index + 1}
                  </span>
                  {getDifficultyBadge(q.difficulty_level)}
                  <span className="text-xs text-slate-400 font-mono">
                    ID: {q.id.slice(0, 8)}
                  </span>
                </div>
                {q.tags && (
                  <span className="text-xs text-indigo-600 font-medium">
                    #{q.tags}
                  </span>
                )}
              </div>

              {/* Question Content with KaTeX */}
              <div className="text-base text-slate-900 font-medium leading-relaxed">
                <MathKaTeX math={q.content} />
              </div>

              {/* Options */}
              {q.options && q.options.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                  {q.options.map((opt) => (
                    <div
                      key={opt.id}
                      className={`flex items-start gap-2.5 p-3 rounded-lg border text-sm transition-colors ${
                        opt.is_correct
                          ? "bg-emerald-50/80 border-emerald-300 text-emerald-900 font-medium"
                          : "bg-white border-slate-200 text-slate-700"
                      }`}
                    >
                      <span
                        className={`h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                          opt.is_correct
                            ? "bg-emerald-600 text-white"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {opt.option_key}
                      </span>
                      <div className="flex-1">
                        <MathKaTeX math={opt.content} />
                      </div>
                      {opt.is_correct && (
                        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Detailed Explanation / Hint if available */}
              {(q.explanation || q.hint) && (
                <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 text-xs text-slate-600 space-y-1.5">
                  {q.explanation && (
                    <div className="space-y-0.5">
                      <span className="font-semibold text-emerald-700 flex items-center gap-1">
                        <BookOpen className="h-3.5 w-3.5" />
                        Lời giải chuẩn chi tiết:
                      </span>
                      <div className="text-slate-700">
                        <MathKaTeX math={q.explanation} />
                      </div>
                    </div>
                  )}
                  {q.hint && (
                    <div className="pt-1.5 border-t border-slate-200/60 space-y-0.5">
                      <span className="font-semibold text-indigo-700 flex items-center gap-1">
                        <Lightbulb className="h-3.5 w-3.5" />
                        Gợi ý Socratic:
                      </span>
                      <p className="text-slate-600">{q.hint}</p>
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Import Questions Modal */}
      <Dialog
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        title="Import câu hỏi từ máy tính"
        description="Hỗ trợ tệp Excel (.xlsx), CSV (.csv), JSON (.json) hoặc Word (.docx) theo định dạng chuẩn"
        maxWidth="xl"
      >
        <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
          {importError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{importError}</span>
            </div>
          )}

          {importSuccessMsg && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800 flex items-start gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{importSuccessMsg}</span>
            </div>
          )}

          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
                <span>Chọn tệp câu hỏi (.xlsx, .csv, .json, .docx)</span>
              </label>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                className="text-xs font-medium text-emerald-700 hover:underline"
              >
                Tải file CSV mẫu
              </button>
            </div>
            <input
              type="file"
              accept=".xlsx,.csv,.json,.docx"
              onChange={(e) => {
                const picked = e.target.files?.[0] || null;
                setImportFile(picked);
                setPreviewResult(null);
                setImportError(null);
                setImportSuccessMsg(null);
              }}
              className="block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
            />
            <p className="text-[11px] text-slate-500 leading-relaxed">
              <strong>CSV/Excel:</strong> các cột <code>content, option_a, option_b, option_c, option_d, correct, explanation, hint, tags</code>.{" "}
              <strong>Word (.docx):</strong> đánh số <code>Câu 1: ...</code>, đáp án <code>A. B. C. D.</code>, dòng <code>Đáp án: C</code> và tùy chọn <code>Lời giải: ...</code>.
            </p>
          </div>

          <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={importIsPublic}
              onChange={(e) => setImportIsPublic(e.target.checked)}
              className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span>Công khai câu hỏi ngay sau khi import</span>
          </label>

          {previewResult && (
            <div className="space-y-3 rounded-xl border border-slate-200 p-3.5 bg-white">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline">
                  Phát hiện: {previewResult.total_detected} câu
                </Badge>
                <Badge variant="success">
                  Hợp lệ:{" "}
                  {previewResult.dry_run
                    ? previewResult.preview_questions.length
                    : previewResult.imported_count}
                </Badge>
                {previewResult.failed_count > 0 && (
                  <Badge variant="destructive">
                    Lỗi: {previewResult.failed_count}
                  </Badge>
                )}
              </div>

              {previewResult.errors.length > 0 && (
                <div className="space-y-1.5 rounded-lg bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-900">
                  <p className="font-semibold">Các dòng/câu không hợp lệ:</p>
                  <ul className="list-disc pl-4 space-y-1 max-h-28 overflow-y-auto">
                    {previewResult.errors.map((err, idx) => (
                      <li key={idx}>
                        Mục #{err.index}: {err.error}{" "}
                        {err.raw_preview ? `(${err.raw_preview})` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {previewResult.preview_questions.length > 0 && (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  <p className="text-xs font-semibold text-slate-700">
                    Xem trước câu hỏi hợp lệ:
                  </p>
                  {previewResult.preview_questions.slice(0, 10).map((pq, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-slate-200 p-2.5 text-xs space-y-1 bg-slate-50/50"
                    >
                      <div className="font-semibold text-slate-800">
                        Câu {i + 1}: <MathKaTeX math={pq.content} />
                      </div>
                      <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-600">
                        {pq.options.map((opt) => (
                          <div
                            key={opt.option_key}
                            className={
                              opt.is_correct
                                ? "text-emerald-700 font-semibold"
                                : ""
                            }
                          >
                            {opt.option_key}. <MathKaTeX math={opt.content} />
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  {previewResult.preview_questions.length > 10 && (
                    <p className="text-[11px] text-slate-500">
                      ...và {previewResult.preview_questions.length - 10} câu hỏi khác.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsImportOpen(false)}
            >
              Đóng
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handlePreviewImport}
              isLoading={isPreviewing}
              disabled={!importFile}
            >
              Kiểm tra & Xem trước
            </Button>
            <Button
              type="button"
              onClick={handleConfirmImport}
              isLoading={isImporting}
              disabled={!importFile}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              Xác nhận Import
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
