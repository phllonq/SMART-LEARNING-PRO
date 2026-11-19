"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Users,
  PlusCircle,
  LogOut,
  FileCheck2,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function StudentClassroomsPage() {
  const [isJoinOpen, setIsJoinOpen] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [joinError, setJoinError] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState(false);
  const [leavingId, setLeavingId] = useState<string | null>(null);

  const {
    data: classrooms = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["student-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  const handleJoinClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError(null);
    setIsJoining(true);
    try {
      await classroomsApi.joinClassroom(inviteCode.trim().toUpperCase());
      setIsJoinOpen(false);
      setInviteCode("");
      refetch();
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.includes("not found") || err.message.includes("ClassroomCode")) {
          setJoinError("Mã mời không chính xác hoặc không tồn tại.");
        } else {
          setJoinError(err.message);
        }
      } else {
        setJoinError("Mã mời không chính xác hoặc bạn đã ở trong lớp này.");
      }
    } finally {
      setIsJoining(false);
    }
  };

  const handleLeaveClassroom = async (classroomId: string) => {
    if (!confirm("Bạn có chắc chắn muốn rời khỏi lớp học này không?")) return;
    setLeavingId(classroomId);
    try {
      await classroomsApi.leaveClassroom(classroomId);
      refetch();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Rời lớp học thất bại.");
    } finally {
      setLeavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Lớp học của tôi
          </h2>
          <p className="text-sm text-slate-500">
            Danh sách các lớp học trực tuyến bạn đang tham gia
          </p>
        </div>
        <Button onClick={() => setIsJoinOpen(true)} className="gap-2">
          <PlusCircle className="h-4 w-4" />
          <span>Tham gia lớp học mới</span>
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      ) : classrooms.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Bạn chưa tham gia lớp học nào"
          description="Hãy liên hệ giáo viên bộ môn để nhận mã mời tham gia lớp học (ví dụ: SL-MATH10) và bấm nút bên dưới."
          actionLabel="Nhập mã mời tham gia lớp"
          onAction={() => setIsJoinOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {classrooms.map((c) => (
            <Card
              key={c.id}
              className="flex flex-col justify-between hover:border-indigo-300 transition-all shadow-xs"
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between mb-1.5">
                  <Badge variant="default">Khối {c.grade_id || 10}</Badge>
                  <span className="font-mono text-xs font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                    {c.code}
                  </span>
                </div>
                <CardTitle className="text-base text-slate-900">
                  {c.name}
                </CardTitle>
                <CardDescription className="text-xs">
                  Giáo viên: {c.teacher_name || "Chưa cập nhật"}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-3 pt-0">
                {c.description && (
                  <p className="text-xs text-slate-600 line-clamp-2">
                    {c.description}
                  </p>
                )}

                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5 text-slate-400" />
                    <span>{c.member_count} học sinh</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <FileCheck2 className="h-3.5 w-3.5 text-slate-400" />
                    <span>{c.assignment_count} bài tập</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <span className="text-[11px] text-slate-400">
                    Gia nhập: {formatDate(c.created_at)}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleLeaveClassroom(c.id)}
                    isLoading={leavingId === c.id}
                    className="text-xs text-slate-500 hover:text-rose-600 hover:bg-rose-50 h-7 px-2"
                  >
                    <LogOut className="h-3.5 w-3.5 mr-1" />
                    <span>Rời lớp</span>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Join Dialog */}
      <Dialog
        isOpen={isJoinOpen}
        onClose={() => setIsJoinOpen(false)}
        title="Tham gia Lớp học mới"
        description="Nhập mã mời gồm chữ và số do giáo viên bộ môn cung cấp"
      >
        <form onSubmit={handleJoinClassroom} className="space-y-4">
          {joinError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {joinError}
            </div>
          )}
          <Input
            label="Mã mời lớp học"
            placeholder="SL-XXXXXX"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
            required
            className="uppercase font-mono tracking-widest text-base"
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsJoinOpen(false)}
            >
              Hủy
            </Button>
            <Button type="submit" isLoading={isJoining}>
              Gia nhập ngay
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
