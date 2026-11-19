"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { examsApi } from "@/lib/api/exams";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Clock,
  HelpCircle,
  Award,
  ArrowLeft,
  Play,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  BookOpen,
} from "lucide-react";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function StudentExamEntryPage({ params }: PageProps) {
  const { id: examId } = use(params);
  const router = useRouter();
  const [isStarting, setIsStarting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    data: exam,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["student-exam-detail", examId],
    queryFn: () => examsApi.getExam(examId),
    retry: false,
  });

  const handleStartExam = async () => {
    setIsStarting(true);
    setErrorMessage(null);
    try {
      const response = await examsApi.startExam(examId);
      router.push(`/student/exams/attempts/${response.attempt_id}`);
    } catch (err: unknown) {
      setIsStarting(false);
      const apiErr = err as {
        status?: number;
        message?: string;
        data?: { detail?: string };
        response?: { data?: { detail?: string } };
      };
      const msg =
        apiErr.data?.detail ||
        apiErr.response?.data?.detail ||
        apiErr.message ||
        "Không thể khởi tạo bài thi. Vui lòng kiểm tra lại.";
      setErrorMessage(msg);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto py-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full rounded-2xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  if (isError || !exam) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center space-y-4">
        <div className="inline-flex p-3 rounded-full bg-red-100 text-red-600 mb-2">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">Không tìm thấy đề thi</h2>
        <p className="text-sm text-slate-600">
          Đề thi không tồn tại hoặc bạn không có quyền truy cập vào bài thi này.
        </p>
        <div className="pt-4">
          <Link href="/student/exams">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              <span>Quay lại phòng luyện thi</span>
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const isPublished = exam.is_published && exam.status === "PUBLISHED";

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-2">
      {/* Top back navigation */}
      <div>
        <Link
          href="/student/exams"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Quay lại danh mục đề thi</span>
        </Link>
      </div>

      {/* Main Exam Overview Card */}
      <Card className="border-slate-200/80 shadow-sm overflow-hidden">
        <div className="h-3 bg-linear-to-r from-indigo-500 via-purple-500 to-pink-500" />
        <CardHeader className="pb-4">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Badge variant="purple" className="text-xs px-2.5 py-0.5">
              Khối {exam.grade_id || 10}
            </Badge>
            {isPublished ? (
              <Badge variant="success" className="text-xs px-2.5 py-0.5 gap-1">
                <CheckCircle2 className="h-3 w-3" />
                Đang mở thi
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-xs px-2.5 py-0.5 gap-1">
                <AlertTriangle className="h-3 w-3 text-amber-500" />
                Chưa mở thi
              </Badge>
            )}
          </div>
          <CardTitle className="text-2xl font-bold text-slate-900 leading-snug">
            {exam.title}
          </CardTitle>
          {exam.description && (
            <CardDescription className="text-sm text-slate-600 pt-1 leading-relaxed">
              {exam.description}
            </CardDescription>
          )}
        </CardHeader>

        <CardContent className="space-y-6 pt-2">
          {/* Key metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                <Clock className="h-3.5 w-3.5 text-amber-500" />
                Thời gian làm bài
              </span>
              <p className="text-lg font-bold text-slate-800">
                {exam.duration_minutes} phút
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                <HelpCircle className="h-3.5 w-3.5 text-indigo-500" />
                Số lượng câu hỏi
              </span>
              <p className="text-lg font-bold text-slate-800">
                {exam.question_count || 10} câu
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                <Award className="h-3.5 w-3.5 text-emerald-500" />
                Thang điểm tối đa
              </span>
              <p className="text-lg font-bold text-slate-800">
                {exam.total_points || 10.0} điểm
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                <BookOpen className="h-3.5 w-3.5 text-purple-500" />
                Điểm đạt tối thiểu
              </span>
              <p className="text-lg font-bold text-slate-800">
                {exam.passing_points || 5.0} điểm
              </p>
            </div>
          </div>

          {/* Exam Rules & Guidelines */}
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 space-y-3">
            <h4 className="text-sm font-semibold text-indigo-900 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-indigo-600" />
              Quy định & Hướng dẫn làm bài thi trực tuyến
            </h4>
            <ul className="text-xs text-slate-700 space-y-2 list-disc list-inside leading-relaxed">
              <li>
                Thời gian làm bài tính từ thời điểm bạn bấm <strong>&ldquo;Bắt đầu làm bài&rdquo;</strong>.
              </li>
              <li>
                Mỗi khi bạn chọn một phương án trả lời, hệ thống sẽ tự động gửi và lưu dữ liệu (autosave) trực tiếp lên máy chủ.
              </li>
              <li>
                Nếu vô tình đóng trình duyệt hoặc tải lại trang, bạn có thể tiếp tục làm bài thi mà không bị mất các câu trả lời đã lưu.
              </li>
              <li>
                Khi hết thời gian quy định, bài thi sẽ tự động được thu hồi và chấm điểm tự động.
              </li>
            </ul>
          </div>

          {/* Error Notice if any */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0 text-red-500 mt-0.5" />
              <div>
                <p className="font-semibold">Không thể bắt đầu bài thi</p>
                <p className="text-xs mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {!isPublished && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
              <div>
                <p className="font-semibold">Đề thi tạm thời không khả dụng</p>
                <p className="text-xs mt-0.5">
                  Đề thi này hiện chưa được xuất bản hoặc đã lưu trữ. Vui lòng quay lại sau.
                </p>
              </div>
            </div>
          )}

          {/* Action button */}
          <div className="pt-2 flex flex-col sm:flex-row gap-3">
            <Button
              onClick={handleStartExam}
              disabled={!isPublished || isStarting}
              size="lg"
              className="gap-2 sm:flex-1 shadow-md hover:shadow-lg transition-all"
            >
              <Play className="h-4 w-4 fill-current" />
              <span>{isStarting ? "Đang chuẩn bị đề thi..." : "Bắt đầu làm bài thi ngay"}</span>
            </Button>
            <Link href="/student/exams">
              <Button variant="outline" size="lg" className="w-full sm:w-auto">
                Quay lại
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
