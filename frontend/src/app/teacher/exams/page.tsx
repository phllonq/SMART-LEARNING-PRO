"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { examsApi } from "@/lib/api/exams";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ExamFileConverterModal } from "@/components/teacher/exam-file-converter";
import {
  Trophy,
  PlusCircle,
  Clock,
  Award,
  HelpCircle,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function TeacherExamsPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [gradeId, setGradeId] = useState<number>(10);
  const [durationMinutes, setDurationMinutes] = useState<number>(45);
  const [totalPoints, setTotalPoints] = useState<number>(10.0);
  const [passingPoints, setPassingPoints] = useState<number>(5.0);
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Convert uploaded file to multiple-choice exam modal
  const [isImportOpen, setIsImportOpen] = useState(false);

  const {
    data: examsData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["teacher-exams-list"],
    queryFn: () => examsApi.getExams({ page_size: 50 }),
  });

  const exams = examsData?.items || [];

  const handleCreateExam = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setIsCreating(true);

    try {
      await examsApi.createExam({
        title,
        grade_id: gradeId,
        duration_minutes: durationMinutes,
        total_points: totalPoints,
        passing_points: passingPoints,
        description,
      });
      setIsCreateOpen(false);
      setTitle("");
      setDescription("");
      refetch();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setCreateError(err.message);
      } else {
        setCreateError("Tạo đề thi thất bại.");
      }
    } finally {
      setIsCreating(false);
    }
  };

  const handlePublishExam = async (examId: string) => {
    try {
      await examsApi.publishExam(examId);
      refetch();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Xuất bản đề thi thất bại.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Ngân hàng Đề thi
          </h2>
          <p className="text-sm text-slate-500">
            Kho đề thi và bài kiểm tra định kỳ chuẩn ma trận năng lực
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setIsImportOpen(true)}
            className="gap-2 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
          >
            <Sparkles className="h-4 w-4" />
            <span>Up đề -&gt; Chuyển thành Trắc nghiệm</span>
          </Button>
          <Button
            onClick={() => setIsCreateOpen(true)}
            className="gap-2 bg-emerald-600 hover:bg-emerald-700"
          >
            <PlusCircle className="h-4 w-4" />
            <span>Tạo đề thi mới</span>
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      ) : exams.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="Chưa có đề thi nào trong kho"
          description="Khởi tạo đề thi mới và chọn các câu hỏi từ ngân hàng câu hỏi để hoàn thiện ma trận đề."
          actionLabel="Tạo đề thi mới"
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {exams.map((exam) => (
            <Card
              key={exam.id}
              className="flex flex-col justify-between hover:border-emerald-300 transition-all shadow-xs"
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="purple">Khối {exam.grade_id || 10}</Badge>
                  <Badge
                    variant={
                      exam.status === "PUBLISHED" ? "success" : "secondary"
                    }
                  >
                    {exam.status === "PUBLISHED" ? "Đã xuất bản" : "Bản nháp"}
                  </Badge>
                </div>
                <CardTitle className="text-base text-slate-900 line-clamp-1">
                  {exam.title}
                </CardTitle>
                <CardDescription className="text-xs">
                  Tạo ngày: {formatDate(exam.created_at)}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-0">
                {exam.description && (
                  <p className="text-xs text-slate-600 line-clamp-2">
                    {exam.description}
                  </p>
                )}

                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                    <span>{exam.duration_minutes} phút</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
                    <span>{exam.question_count} câu hỏi</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Award className="h-3.5 w-3.5 text-slate-400" />
                    <span>Thang {exam.total_points} đ</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-slate-400" />
                    <span>Đạt: {exam.passing_points} đ</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                  {exam.status === "DRAFT" ? (
                    <Button
                      size="sm"
                      onClick={() => handlePublishExam(exam.id)}
                      className="bg-emerald-600 hover:bg-emerald-700 text-xs w-full"
                    >
                      <span>Xuất bản mở phòng luyện</span>
                    </Button>
                  ) : (
                    <span className="text-xs text-emerald-700 font-medium">
                      ✓ Sẵn sàng để giao bài
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Exam Modal */}
      <Dialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Tạo Đề thi mới"
        description="Thiết lập các thông số cơ bản cho đề thi"
      >
        <form onSubmit={handleCreateExam} className="space-y-4">
          {createError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {createError}
            </div>
          )}

          <Input
            label="Tên đề thi"
            placeholder="Ví dụ: Đề kiểm tra 1 tiết — Đại số 10"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />

          <div className="grid grid-cols-2 gap-3">
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
              label="Thời lượng (Phút)"
              type="number"
              min={5}
              max={300}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Thang điểm tối đa"
              type="number"
              step="0.5"
              value={totalPoints}
              onChange={(e) => setTotalPoints(Number(e.target.value))}
              required
            />
            <Input
              label="Điểm đạt tối thiểu"
              type="number"
              step="0.5"
              value={passingPoints}
              onChange={(e) => setPassingPoints(Number(e.target.value))}
              required
            />
          </div>

          <Input
            label="Mô tả đề thi"
            placeholder="Phạm vi kiến thức, đối tượng học sinh..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateOpen(false)}
            >
              Hủy
            </Button>
            <Button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700"
              isLoading={isCreating}
            >
              Tạo đề thi
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Convert Exam File To Interactive Multiple-Choice Quiz */}
      <ExamFileConverterModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onSuccess={() => refetch()}
      />
    </div>
  );
}
