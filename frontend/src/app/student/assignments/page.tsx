"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { assignmentsApi } from "@/lib/api/assignments";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import {
  FileCheck2,
  Clock,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Award,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import { AssignmentSummary } from "@/types";

export default function StudentAssignmentsPage() {
  const router = useRouter();
  const [now] = useState(() => Date.now());
  const [startingId, setStartingId] = useState<string | null>(null);

  const { data: classrooms = [], isLoading: isLoadingClassrooms } = useQuery({
    queryKey: ["student-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  // Fetch assignments for all enrolled classrooms
  const { data: assignments = [], isLoading: isLoadingAssignments } = useQuery({
    queryKey: ["student-assignments", classrooms.map((c) => c.id).join(",")],
    queryFn: async () => {
      if (classrooms.length === 0) return [];
      const results = await Promise.all(
        classrooms.map((c) =>
          assignmentsApi
            .getClassroomAssignments(c.id)
            .catch(() => [] as AssignmentSummary[])
        )
      );
      return results.flat();
    },
    enabled: classrooms.length > 0 || !isLoadingClassrooms,
  });

  const isLoading = isLoadingClassrooms || isLoadingAssignments;

  const getStatusBadge = (status?: string | null, score?: number | null) => {
    switch (status) {
      case "GRADED":
        return (
          <Badge variant="success" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            <span>Đã chấm: {score ?? 10} đ</span>
          </Badge>
        );
      case "SUBMITTED":
        return (
          <Badge variant="purple" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            <span>Đã nộp bài</span>
          </Badge>
        );
      case "IN_PROGRESS":
        return (
          <Badge variant="warning" className="gap-1">
            <Clock className="h-3 w-3" />
            <span>Đang làm dở</span>
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary" className="gap-1">
            <AlertCircle className="h-3 w-3" />
            <span>Chưa làm</span>
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Bài tập về nhà
        </h2>
        <p className="text-sm text-slate-500">
          Danh sách các bài tập giáo viên giao theo từng lớp học
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      ) : assignments.length === 0 ? (
        <EmptyState
          icon={FileCheck2}
          title="Chưa có bài tập nào được giao"
          description="Hiện tại các lớp học của bạn chưa có bài tập về nhà mới. Hãy quay lại sau khi giáo viên đăng bài nhé!"
        />
      ) : (
        <div className="space-y-4">
          {assignments.map((assignment) => {
            const dueTime = new Date(assignment.due_date).getTime();
            const isDueSoon = dueTime - now < 48 * 3600 * 1000;
            const isOverdue = dueTime < now;

            return (
              <Card
                key={assignment.id}
                className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-indigo-300 transition-all shadow-xs"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="text-slate-600 bg-slate-50 font-medium">
                      {assignment.classroom_name || "Lớp học"}
                    </Badge>
                    {getStatusBadge(assignment.my_status, assignment.my_score)}
                    {isOverdue ? (
                      <span className="text-xs font-semibold text-rose-600 bg-rose-50 px-2 py-0.5 rounded border border-rose-100">
                        Hết hạn nộp
                      </span>
                    ) : isDueSoon ? (
                      <span className="text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-100">
                        Sắp hết hạn
                      </span>
                    ) : null}
                  </div>

                  <h3 className="text-base font-bold text-slate-900">
                    {assignment.title}
                  </h3>

                  {assignment.description && (
                    <p className="text-xs text-slate-600 line-clamp-1">
                      {assignment.description}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5 text-slate-400" />
                      Hạn nộp: {formatDate(assignment.due_date)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-slate-400" />
                      Thời gian: {assignment.duration_minutes} phút
                    </span>
                    <span className="flex items-center gap-1">
                      <Award className="h-3.5 w-3.5 text-slate-400" />
                      Thang điểm: {assignment.total_points} đ
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
                  <Button
                    size="sm"
                    className="w-full md:w-auto gap-1.5"
                    disabled={(isOverdue && !assignment.allow_late_submission) || startingId === assignment.id}
                    onClick={async () => {
                      setStartingId(assignment.id);
                      try {
                        const res = await assignmentsApi.startAssignment(assignment.id);
                        router.push(`/student/exams/attempts/${res.attempt_id}`);
                      } catch (err: unknown) {
                        setStartingId(null);
                        const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
                        alert(
                          apiErr.response?.data?.detail ||
                            apiErr.message ||
                            "Không thể khởi tạo bài tập."
                        );
                      }
                    }}
                  >
                    {startingId === assignment.id ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Đang vào bài...</span>
                      </>
                    ) : (
                      <>
                        <span>Làm bài ngay</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
