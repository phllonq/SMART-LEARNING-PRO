"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { examsApi } from "@/lib/api/exams";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Trophy, Clock, HelpCircle, Award, Play } from "lucide-react";
import { ExamSummary } from "@/types";

export default function StudentExamsPage() {
  const { data: availableExams = [], isLoading } = useQuery({
    queryKey: ["student-available-exams"],
    queryFn: () => examsApi.getAvailableExams(),
  });

  const handleStartExam = (exam: ExamSummary) => {
    const ok = confirm(
      `Bạn chuẩn bị bắt đầu làm bài thi "${exam.title}".\n\n` +
      `• Thời gian: ${exam.duration_minutes} phút\n` +
      `• Số câu hỏi: ${exam.question_count || 10} câu\n` +
      `• Thang điểm: ${exam.total_points || 10.0} đ\n\n` +
      `Đồng hồ bấm giờ sẽ tự động đếm lùi khi bạn bắt đầu.`
    );
    if (ok) {
      alert(`Đang khởi tạo phiên thi trực tuyến cho đề "${exam.title}"!`);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Phòng Luyện thi & Đánh giá Năng lực
        </h2>
        <p className="text-sm text-slate-500">
          Các đề thi chuẩn cấu trúc Bộ GD&ĐT dành cho học sinh tự luyện và kiểm tra định kỳ
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      ) : availableExams.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="Chưa có đề thi mở phòng luyện"
          description="Hiện tại chưa có đề thi tự do nào được công bố. Vui lòng kiểm tra lại sau hoặc kiểm tra mục Bài tập về nhà của lớp học."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {availableExams.map((exam: ExamSummary) => (
            <Card
              key={exam.id}
              className="flex flex-col justify-between hover:border-indigo-300 transition-all shadow-xs"
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="purple">Khối {exam.grade_id || 10}</Badge>
                  <span className="flex items-center gap-1 text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-100">
                    <Clock className="h-3 w-3" />
                    {exam.duration_minutes} phút
                  </span>
                </div>
                <CardTitle className="text-base text-slate-900 line-clamp-1">
                  {exam.title}
                </CardTitle>
                <CardDescription className="text-xs">
                  Điểm đạt: {exam.passing_points || 5.0} / {exam.total_points || 10.0} đ
                </CardDescription>
              </CardHeader>

              <CardContent className="pt-0 space-y-4">
                {exam.description && (
                  <p className="text-xs text-slate-600 line-clamp-2">
                    {exam.description}
                  </p>
                )}

                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
                    <span>{exam.question_count || 10} câu hỏi</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Award className="h-3.5 w-3.5 text-slate-400" />
                    <span>Tối đa {exam.max_attempts || 1} lần làm</span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100">
                  <Button
                    onClick={() => handleStartExam(exam)}
                    className="w-full gap-2 shadow-sm"
                  >
                    <Play className="h-4 w-4 fill-current" />
                    <span>Bắt đầu làm bài</span>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
