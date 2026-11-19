"use client";

import React from "react";
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
  Calendar,
  Clock,
  Award,
  CheckCircle2,
  XCircle,
  Eye,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import { AssignmentSummary } from "@/types";

export default function TeacherAssignmentsPage() {
  const { data: classrooms = [], isLoading: isLoadingClassrooms } = useQuery({
    queryKey: ["teacher-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  const { data: assignments = [], isLoading: isLoadingAssignments, refetch } = useQuery({
    queryKey: ["teacher-all-assignments", classrooms.map((c) => c.id).join(",")],
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

  const handlePublish = async (id: string) => {
    try {
      await assignmentsApi.publishAssignment(id);
      refetch();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Xuất bản thất bại.");
    }
  };

  const handleCancel = async (id: string) => {
    if (!confirm("Xác nhận hủy bài tập này?")) return;
    try {
      await assignmentsApi.cancelAssignment(id);
      refetch();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Hủy bài tập thất bại.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Quản lý Bài tập
        </h2>
        <p className="text-sm text-slate-500">
          Toàn bộ các bài tập đã giao trên tất cả các lớp học bạn phụ trách
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      ) : assignments.length === 0 ? (
        <EmptyState
          icon={FileCheck2}
          title="Chưa có bài tập nào được tạo"
          description="Để giao bài tập, hãy truy cập vào từng lớp học cụ thể và bấm 'Giao bài tập mới'."
        />
      ) : (
        <div className="space-y-3">
          {assignments.map((a) => (
            <Card
              key={a.id}
              className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-emerald-300 transition-all shadow-xs"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      a.status === "PUBLISHED"
                        ? "success"
                        : a.status === "CANCELLED"
                        ? "destructive"
                        : "secondary"
                    }
                  >
                    {a.status === "PUBLISHED"
                      ? "Đang phát hành"
                      : a.status === "CANCELLED"
                      ? "Đã hủy"
                      : "Bản nháp"}
                  </Badge>
                  <span className="text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                    {a.classroom_name || a.classroom_id}
                  </span>
                </div>

                <h3 className="text-base font-bold text-slate-900">{a.title}</h3>

                {a.description && (
                  <p className="text-xs text-slate-600 line-clamp-1">
                    {a.description}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5 text-slate-400" />
                    Hạn chót: {formatDate(a.due_date)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                    Thời gian: {a.duration_minutes} phút
                  </span>
                  <span className="flex items-center gap-1">
                    <Award className="h-3.5 w-3.5 text-slate-400" />
                    Thang điểm: {a.total_points} đ
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
                {a.status === "DRAFT" && (
                  <Button
                    size="sm"
                    onClick={() => handlePublish(a.id)}
                    className="bg-emerald-600 hover:bg-emerald-700 text-xs"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                    <span>Phát hành</span>
                  </Button>
                )}
                {a.status === "PUBLISHED" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleCancel(a.id)}
                    className="text-xs text-rose-600 hover:bg-rose-50 border-rose-200"
                  >
                    <XCircle className="h-3.5 w-3.5 mr-1" />
                    <span>Hủy bài</span>
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    alert(`Đang mở sổ điểm chi tiết của bài tập "${a.title}".`)
                  }
                  className="text-xs gap-1"
                >
                  <Eye className="h-3.5 w-3.5" />
                  <span>Sổ điểm</span>
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
