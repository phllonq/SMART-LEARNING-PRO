"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Users } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function TeacherStudentsPage() {
  const { data: classrooms = [], isLoading: isLoadingClassrooms } = useQuery({
    queryKey: ["teacher-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  const { data: classDetails = [], isLoading: isLoadingMembers } = useQuery({
    queryKey: ["teacher-classrooms-with-members", classrooms.map((c) => c.id).join(",")],
    queryFn: async () => {
      if (classrooms.length === 0) return [];
      return Promise.all(
        classrooms.map((c) => classroomsApi.getClassroom(c.id).catch(() => null))
      );
    },
    enabled: classrooms.length > 0 || !isLoadingClassrooms,
  });

  const isLoading = isLoadingClassrooms || isLoadingMembers;

  // Flatten students with classroom info
  const allStudents = classDetails
    .filter((c) => c !== null)
    .flatMap((c) =>
      (c!.members || []).map((m) => ({
        ...m,
        classroomName: c!.name,
        classroomCode: c!.code,
      }))
    );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Danh sách Học sinh
        </h2>
        <p className="text-sm text-slate-500">
          Tổng hợp toàn bộ học sinh đang theo học tại các lớp học của bạn ({allStudents.length} học sinh)
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
        </div>
      ) : allStudents.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Chưa có học sinh nào"
          description="Học sinh sẽ xuất hiện tại đây khi các em nhập mã mời và tham gia vào các lớp học của bạn."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                <tr>
                  <th className="px-6 py-3.5">Học sinh</th>
                  <th className="px-6 py-3.5">Địa chỉ Email</th>
                  <th className="px-6 py-3.5">Lớp học</th>
                  <th className="px-6 py-3.5">Ngày gia nhập</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {allStudents.map((s, idx) => (
                  <tr key={`${s.student_id}-${s.classroomCode}-${idx}`} className="hover:bg-slate-50/70">
                    <td className="px-6 py-4 flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center shrink-0">
                        {s.student_name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-semibold text-slate-900">{s.student_name}</p>
                        <p className="text-[11px] text-slate-400 font-mono">
                          ID: {s.student_id.slice(0, 8)}...
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-600 font-mono text-xs">
                      {s.student_email}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      <span className="font-medium">{s.classroomName}</span>
                      <span className="ml-2 font-mono text-xs text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100">
                        {s.classroomCode}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {formatDate(s.joined_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
