"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { assignmentsApi } from "@/lib/api/assignments";
import { examsApi } from "@/lib/api/exams";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Users,
  Copy,
  Check,
  RefreshCw,
  FileCheck2,
  PlusCircle,
  ArrowLeft,
  Trash2,
  Calendar,
  Clock,
  Award,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function TeacherClassroomDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: classroomId } = React.use(params);

  const [activeTab, setActiveTab] = useState<"members" | "assignments">("members");
  const [copiedCode, setCopiedCode] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Assignment Modal
  const [isCreateAssignOpen, setIsCreateAssignOpen] = useState(false);
  const [assignTitle, setAssignTitle] = useState("");
  const [assignExamId, setAssignExamId] = useState("");
  const [assignDueDate, setAssignDueDate] = useState("");
  const [assignDescription, setAssignDescription] = useState("");
  const [isCreatingAssign, setIsCreatingAssign] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  // Fetch Classroom Detail
  const {
    data: classroom,
    isLoading: isLoadingClassroom,
    refetch: refetchClassroom,
  } = useQuery({
    queryKey: ["teacher-classroom", classroomId],
    queryFn: () => classroomsApi.getClassroom(classroomId),
  });

  // Fetch Classroom Assignments
  const {
    data: assignments = [],
    isLoading: isLoadingAssignments,
    refetch: refetchAssignments,
  } = useQuery({
    queryKey: ["teacher-classroom-assignments", classroomId],
    queryFn: () => assignmentsApi.getClassroomAssignments(classroomId),
  });

  // Fetch Available Exams to assign
  const { data: examsData } = useQuery({
    queryKey: ["teacher-exams-selection"],
    queryFn: () => examsApi.getExams({ page_size: 50 }),
  });

  const availableExams = examsData?.items || [];

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleRegenerateCode = async () => {
    if (!confirm("Bạn có chắc chắn muốn tạo mã mời mới? Mã cũ sẽ mất hiệu lực.")) return;
    setIsRegenerating(true);
    try {
      await classroomsApi.regenerateInviteCode(classroomId);
      refetchClassroom();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Tạo mã thất bại.");
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleRemoveStudent = async (studentId: string, name: string) => {
    if (!confirm(`Xác nhận xóa học sinh "${name}" khỏi lớp học?`)) return;
    try {
      await classroomsApi.removeStudent(classroomId, studentId);
      refetchClassroom();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Xóa học sinh thất bại.");
    }
  };

  const handlePublishAssignment = async (assignId: string) => {
    try {
      await assignmentsApi.publishAssignment(assignId);
      refetchAssignments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Xuất bản bài tập thất bại.");
    }
  };

  const handleCancelAssignment = async (assignId: string) => {
    if (!confirm("Bạn có chắc chắn muốn hủy bài tập này?")) return;
    try {
      await assignmentsApi.cancelAssignment(assignId);
      refetchAssignments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Hủy bài tập thất bại.");
    }
  };

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    setAssignError(null);
    if (!assignExamId) {
      setAssignError("Vui lòng chọn một đề thi từ danh sách.");
      return;
    }
    if (!assignDueDate) {
      setAssignError("Vui lòng chọn hạn chót nộp bài.");
      return;
    }

    setIsCreatingAssign(true);
    try {
      await assignmentsApi.createAssignment(classroomId, {
        exam_id: assignExamId,
        title: assignTitle,
        description: assignDescription,
        due_date: new Date(assignDueDate).toISOString(),
        status: "PUBLISHED",
      });
      setIsCreateAssignOpen(false);
      setAssignTitle("");
      setAssignExamId("");
      setAssignDescription("");
      setAssignDueDate("");
      refetchAssignments();
      refetchClassroom();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAssignError(err.message);
      } else {
        setAssignError("Tạo bài tập thất bại.");
      }
    } finally {
      setIsCreatingAssign(false);
    }
  };

  if (isLoadingClassroom) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (!classroom) {
    return (
      <EmptyState
        icon={Users}
        title="Không tìm thấy lớp học"
        description="Lớp học này không tồn tại hoặc bạn không có quyền truy cập."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div>
        <Link
          href="/teacher/classrooms"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Quay lại danh sách lớp học</span>
        </Link>
      </div>

      {/* Classroom Hero Card with Invite Code Banner */}
      <div className="rounded-2xl bg-white border border-slate-200 p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="success">Khối {classroom.grade_id || 10}</Badge>
              <Badge variant={classroom.is_archived ? "secondary" : "default"}>
                {classroom.is_archived ? "Đã lưu trữ" : "Đang mở"}
              </Badge>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
              {classroom.name}
            </h2>
            {classroom.description && (
              <p className="text-sm text-slate-600 max-w-2xl leading-relaxed">
                {classroom.description}
              </p>
            )}
            <div className="flex items-center gap-4 text-xs text-slate-500 pt-1">
              <span>{classroom.member_count} học sinh đã tham gia</span>
              <span>•</span>
              <span>Sĩ số tối đa: {classroom.max_students}</span>
              <span>•</span>
              <span>{classroom.assignment_count} bài tập đã giao</span>
            </div>
          </div>

          {/* Large Invite Code Box */}
          <div className="rounded-xl border-2 border-dashed border-emerald-300 bg-emerald-50/50 p-5 flex flex-col items-center justify-center text-center shrink-0 min-w-[240px]">
            <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">
              Mã mời lớp học (Invite Code)
            </p>
            <div className="mt-2 text-3xl font-black font-mono tracking-widest text-emerald-700">
              {classroom.code}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleCopyCode(classroom.code)}
                className="h-8 text-xs bg-white text-emerald-700 hover:bg-emerald-50 border-emerald-200 gap-1.5"
              >
                {copiedCode ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Đã chép</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    <span>Sao chép mã</span>
                  </>
                )}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleRegenerateCode}
                isLoading={isRegenerating}
                title="Đổi sang mã mới"
                className="h-8 text-xs text-slate-500 hover:text-emerald-700 hover:bg-emerald-100/50"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-1">
        <button
          onClick={() => setActiveTab("members")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === "members"
              ? "border-emerald-600 text-emerald-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Users className="h-4 w-4" />
          <span>Danh sách Học sinh ({classroom.members?.length || 0})</span>
        </button>
        <button
          onClick={() => setActiveTab("assignments")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === "assignments"
              ? "border-emerald-600 text-emerald-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <FileCheck2 className="h-4 w-4" />
          <span>Bài tập của Lớp ({assignments.length})</span>
        </button>
      </div>

      {/* Tab 1: Member Roster */}
      {activeTab === "members" && (
        <Card className="overflow-hidden">
          {classroom.members && classroom.members.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                  <tr>
                    <th className="px-6 py-3.5">Học sinh</th>
                    <th className="px-6 py-3.5">Địa chỉ Email</th>
                    <th className="px-6 py-3.5">Ngày tham gia</th>
                    <th className="px-6 py-3.5 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {classroom.members.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-6 py-4 flex items-center gap-3">
                        <div className="h-9 w-9 rounded-full bg-emerald-100 text-emerald-800 font-bold text-xs flex items-center justify-center shrink-0">
                          {m.student_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">
                            {m.student_name}
                          </p>
                          <p className="text-xs text-slate-400">ID: {m.student_id.slice(0, 8)}...</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-600 font-mono text-xs">
                        {m.student_email}
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-xs">
                        {formatDate(m.joined_at)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveStudent(m.student_id, m.student_name)}
                          className="h-8 text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                        >
                          <Trash2 className="h-3.5 w-3.5 mr-1" />
                          <span>Xóa khỏi lớp</span>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center">
              <Users className="h-10 w-10 text-slate-300 mx-auto mb-3" />
              <p className="text-sm font-semibold text-slate-700">
                Chưa có học sinh nào gia nhập lớp
              </p>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Cung cấp mã mời <span className="font-mono font-bold text-emerald-700">{classroom.code}</span> cho học sinh để các em tự nhập và tham gia.
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Tab 2: Assignments */}
      {activeTab === "assignments" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button
              onClick={() => setIsCreateAssignOpen(true)}
              className="gap-2 bg-emerald-600 hover:bg-emerald-700"
            >
              <PlusCircle className="h-4 w-4" />
              <span>Giao bài tập mới</span>
            </Button>
          </div>

          {isLoadingAssignments ? (
            <div className="space-y-3">
              <Skeleton className="h-24 w-full rounded-xl" />
              <Skeleton className="h-24 w-full rounded-xl" />
            </div>
          ) : assignments.length === 0 ? (
            <EmptyState
              icon={FileCheck2}
              title="Chưa có bài tập nào được giao"
              description="Bấm 'Giao bài tập mới' để chọn một đề thi chuẩn từ ngân hàng đề và đặt thời hạn nộp cho học sinh lớp này."
              actionLabel="Giao bài tập ngay"
              onAction={() => setIsCreateAssignOpen(true)}
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
                      <span className="text-xs text-slate-500">
                        Đề thi: {a.exam_title || a.exam_id}
                      </span>
                    </div>

                    <h4 className="text-base font-bold text-slate-900">
                      {a.title}
                    </h4>

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
                        onClick={() => handlePublishAssignment(a.id)}
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
                        onClick={() => handleCancelAssignment(a.id)}
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
                        alert(
                          `Đang tải sổ điểm thời gian thực của bài tập "${a.title}"...`
                        )
                      }
                      className="text-xs"
                    >
                      <span>Xem sổ điểm</span>
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create Assignment Modal */}
      <Dialog
        isOpen={isCreateAssignOpen}
        onClose={() => setIsCreateAssignOpen(false)}
        title="Giao Bài tập về nhà mới"
        description="Chọn đề thi từ Ngân hàng đề và thiết lập thời hạn nộp bài"
      >
        <form onSubmit={handleCreateAssignment} className="space-y-4">
          {assignError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {assignError}
            </div>
          )}

          <Input
            label="Tiêu đề bài tập"
            placeholder="Ví dụ: Bài tập tuần 3 — Phương trình Lượng giác"
            value={assignTitle}
            onChange={(e) => setAssignTitle(e.target.value)}
            required
          />

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
              Chọn đề thi mẫu
            </label>
            <select
              value={assignExamId}
              onChange={(e) => setAssignExamId(e.target.value)}
              required
              className="flex h-10 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            >
              <option value="">-- Chọn đề thi --</option>
              {availableExams.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title} ({e.duration_minutes} phút, {e.question_count || 10} câu)
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
              Hạn chót nộp bài (Due Date)
            </label>
            <input
              type="datetime-local"
              value={assignDueDate}
              onChange={(e) => setAssignDueDate(e.target.value)}
              required
              className="flex h-10 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>

          <Input
            label="Hướng dẫn làm bài (Tùy chọn)"
            placeholder="Ghi chú thêm về quy chế nộp bài hoặc yêu cầu đặc biệt..."
            value={assignDescription}
            onChange={(e) => setAssignDescription(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateAssignOpen(false)}
            >
              Hủy
            </Button>
            <Button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700"
              isLoading={isCreatingAssign}
            >
              Giao bài ngay
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
