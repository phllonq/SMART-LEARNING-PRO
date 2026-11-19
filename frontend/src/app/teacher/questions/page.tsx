"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { questionsApi } from "@/lib/api/questions";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { MathKaTeX } from "@/components/shared/math-katex";
import {
  FileQuestion,
  Search,
  CheckCircle2,
  Lightbulb,
  BookOpen,
} from "lucide-react";

export default function TeacherQuestionsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>("");
  const [page, setPage] = useState(1);

  const { data: questionsData, isLoading } = useQuery({
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
    </div>
  );
}
