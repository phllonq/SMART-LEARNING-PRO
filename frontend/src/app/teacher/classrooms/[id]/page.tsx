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
import { ExamFileConverterModal } from "@/components/teacher/exam-file-converter";
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
  Upload,
  Paperclip,
  Download,
  FileText,
  Sparkles,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import { AssignmentSubmissionsResponse } from "@/types";

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
  const [isQuizConvertOpen, setIsQuizConvertOpen] = useState(false);
  const [assignMode, setAssignMode] = useState<"EXAM" | "FILE">("EXAM");
  const [assignTitle, setAssignTitle] = useState("");
  const [assignExamId, setAssignExamId] = useState("");
  const [assignFile, setAssignFile] = useState<File | null>(null);
  const [assignTotalPoints, setAssignTotalPoints] = useState<number>(10);
  const [assignAllowLate, setAssignAllowLate] = useState(false);
  const [assignDueDate, setAssignDueDate] = useState("");
  const [assignDescription, setAssignDescription] = useState("");
  const [isCreatingAssign, setIsCreatingAssign] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  // Submissions & Grading Modal
  const [submissionsModalOpen, setSubmissionsModalOpen] = useState(false);
  const [selectedAssignId, setSelectedAssignId] = useState<string | null>(null);
  const [submissionsData, setSubmissionsData] =
    useState<AssignmentSubmissionsResponse | null>(null);
  const [isLoadingSubmissions, setIsLoadingSubmissions] = useState(false);
  const [gradeDrafts, setGradeDrafts] = useState<
    Record<string, { score: string; feedback: string }>
  >({});
  const [gradingSubmissionId, setGradingSubmissionId] = useState<string | null>(
    null
  );

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
    if (!assignDueDate) {
      setAssignError("Vui lòng chọn hạn chót nộp bài.");
      return;
    }
    if (assignMode === "EXAM" && !assignExamId) {
      setAssignError("Vui lòng chọn một đề thi từ danh sách.");
      return;
    }
    if (assignMode === "FILE" && !assignFile) {
      setAssignError("Vui lòng chọn tệp bài tập từ máy tính.");
      return;
    }

    setIsCreatingAssign(true);
    try {
      if (assignMode === "EXAM") {
        await assignmentsApi.createAssignment(classroomId, {
          exam_id: assignExamId,
          title: assignTitle,
          description: assignDescription,
          due_date: new Date(assignDueDate).toISOString(),
          allow_late_submission: assignAllowLate,
          status: "PUBLISHED",
        });
      } else if (assignFile) {
        await assignmentsApi.createFileAssignment(classroomId, {
          file: assignFile,
          title: assignTitle,
          description: assignDescription || undefined,
          due_date: new Date(assignDueDate).toISOString(),
          allow_late_submission: assignAllowLate,
          total_points: assignTotalPoints,
          status: "PUBLISHED",
        });
      }
      setIsCreateAssignOpen(false);
      setAssignTitle("");
      setAssignExamId("");
      setAssignFile(null);
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

  const handleOpenSubmissions = async (assignmentId: string) => {
    setSelectedAssignId(assignmentId);
    setSubmissionsModalOpen(true);
    setIsLoadingSubmissions(true);
    try {
      const data = await assignmentsApi.getAssignmentSubmissions(assignmentId);
      setSubmissionsData(data);
      const initialDrafts: Record<string, { score: string; feedback: string }> = {};
      data.items.forEach((item) => {
        if (item.file_submission) {
          initialDrafts[item.file_submission.id] = {
            score:
              item.file_submission.score !== null &&
              item.file_submission.score !== undefined
                ? String(item.file_submission.score)
                : "",
            feedback: item.file_submission.teacher_feedback || "",
          };
        }
      });
      setGradeDrafts(initialDrafts);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Không thể tải danh sách bài nộp.");
      setSubmissionsModalOpen(false);
    } finally {
      setIsLoadingSubmissions(false);
    }
  };

  const handleGradeFileSubmission = async (submissionId: string) => {
    if (!selectedAssignId) return;
    const draft = gradeDrafts[submissionId];
    const parsedScore = Number(draft?.score);
    if (!draft || draft.score.trim() === "" || Number.isNaN(parsedScore)) {
      alert("Vui lòng nhập điểm hợp lệ.");
      return;
    }

    setGradingSubmissionId(submissionId);
    try {
      await assignmentsApi.gradeFileSubmission(selectedAssignId, submissionId, {
        score: parsedScore,
        teacher_feedback: draft.feedback || undefined,
      });
      const updated = await assignmentsApi.getAssignmentSubmissions(selectedAssignId);
      setSubmissionsData(updated);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Lưu điểm thất bại.");
    } finally {
      setGradingSubmissionId(null);
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
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setIsQuizConvertOpen(true)}
              className="gap-2 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
            >
              <Sparkles className="h-4 w-4" />
              <span>Up đề -&gt; Chuyển thành Trắc nghiệm</span>
            </Button>
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
                    <div className="flex flex-wrap items-center gap-2">
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
                      {a.assignment_type === "FILE" ? (
                        <Badge variant="outline" className="gap-1 bg-indigo-50 text-indigo-700 border-indigo-200">
                          <Paperclip className="h-3 w-3" />
                          <span>File: {a.attachment_name || "Đính kèm"}</span>
                        </Badge>
                      ) : (
                        <span className="text-xs text-slate-500">
                          Đề thi: {a.exam_title || a.exam_id}
                        </span>
                      )}
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
                      {a.assignment_type !== "FILE" && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5 text-slate-400" />
                          Thời gian: {a.duration_minutes} phút
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Award className="h-3.5 w-3.5 text-slate-400" />
                        Thang điểm: {a.total_points} đ
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
                    {a.assignment_type === "FILE" && a.has_attachment && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          assignmentsApi.downloadAssignmentAttachment(
                            a.id,
                            a.attachment_name || "bai-tap"
                          )
                        }
                        className="text-xs gap-1"
                      >
                        <Download className="h-3.5 w-3.5" />
                        <span>Tải đề</span>
                      </Button>
                    )}

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
                      onClick={() => handleOpenSubmissions(a.id)}
                      className="text-xs"
                    >
                      <span>
                        {a.assignment_type === "FILE"
                          ? "Xem & Chấm bài nộp"
                          : "Xem sổ điểm"}
                      </span>
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
        description="Chọn đề thi trực tuyến hoặc tải tệp bài tập từ máy tính để giao cho học sinh"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateAssignment} className="space-y-4">
          {assignError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {assignError}
            </div>
          )}

          {/* Mode Toggle */}
          <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-100">
            <button
              type="button"
              onClick={() => {
                setAssignMode("EXAM");
                setAssignError(null);
              }}
              className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                assignMode === "EXAM"
                  ? "bg-white text-emerald-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <FileText className="h-3.5 w-3.5" />
              <span>Chọn Đề thi trực tuyến</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setAssignMode("FILE");
                setAssignError(null);
              }}
              className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                assignMode === "FILE"
                  ? "bg-white text-emerald-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Up file bài tập từ máy</span>
            </button>
          </div>

          <Input
            label="Tiêu đề bài tập"
            placeholder="Ví dụ: Bài tập tuần 3 — Phương trình Lượng giác"
            value={assignTitle}
            onChange={(e) => setAssignTitle(e.target.value)}
            required
          />

          {assignMode === "EXAM" ? (
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
          ) : (
            <div className="space-y-3 rounded-xl border border-dashed border-emerald-300 bg-emerald-50/40 p-3.5">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700">
                  Tệp bài tập đính kèm (.pdf, .docx, .xlsx, ảnh, .txt, .zip — tối đa 15MB)
                </label>
                <input
                  type="file"
                  accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.txt,.zip"
                  onChange={(e) => {
                    const picked = e.target.files?.[0] || null;
                    setAssignFile(picked);
                    if (picked && !assignTitle) {
                      setAssignTitle(picked.name.replace(/\.[^/.]+$/, ""));
                    }
                  }}
                  required
                  className="block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700"
                />
              </div>
              <Input
                label="Thang điểm tối đa"
                type="number"
                step="0.5"
                min={1}
                max={100}
                value={assignTotalPoints}
                onChange={(e) => setAssignTotalPoints(Number(e.target.value))}
                required
              />
            </div>
          )}

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

          <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={assignAllowLate}
              onChange={(e) => setAssignAllowLate(e.target.checked)}
              className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span>Cho phép học sinh nộp muộn sau hạn chót</span>
          </label>

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

      {/* Submissions & Grading Modal */}
      <Dialog
        isOpen={submissionsModalOpen}
        onClose={() => setSubmissionsModalOpen(false)}
        title={
          submissionsData
            ? `Bài nộp: ${submissionsData.assignment_title}`
            : "Sổ điểm & Bài nộp học sinh"
        }
        description={
          submissionsData
            ? `Đã nộp: ${submissionsData.submitted_count}/${submissionsData.total_students} học sinh • Điểm trung bình: ${submissionsData.average_score}`
            : undefined
        }
        maxWidth="xl"
      >
        {isLoadingSubmissions ? (
          <div className="space-y-3 py-4">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : !submissionsData || submissionsData.items.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            Lớp chưa có học sinh nào để hiển thị bài nộp.
          </p>
        ) : (
          <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
            {submissionsData.items.map((item) => {
              const fs = item.file_submission;
              const draft = fs ? gradeDrafts[fs.id] : undefined;

              return (
                <div
                  key={item.student_id}
                  className="rounded-xl border border-slate-200 p-3.5 space-y-2.5 bg-slate-50/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        {item.student_name}
                      </p>
                      <p className="text-xs text-slate-500">{item.student_email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          item.status === "GRADED"
                            ? "success"
                            : item.status === "SUBMITTED"
                            ? "purple"
                            : item.status === "IN_PROGRESS"
                            ? "warning"
                            : "secondary"
                        }
                      >
                        {item.status === "GRADED"
                          ? `Đã chấm: ${item.score ?? 0}/${item.maximum_score} đ`
                          : item.status === "SUBMITTED"
                          ? "Đã nộp bài"
                          : item.status === "IN_PROGRESS"
                          ? "Đang làm"
                          : "Chưa nộp"}
                      </Badge>
                      {submissionsData.assignment_type !== "FILE" &&
                        item.score !== null &&
                        item.score !== undefined && (
                          <span className="text-xs font-bold text-emerald-700">
                            {item.score}/{item.maximum_score} đ
                          </span>
                        )}
                    </div>
                  </div>

                  {fs && (
                    <div className="rounded-lg bg-white border border-slate-200 p-3 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-1.5 text-slate-700 font-medium">
                          <Paperclip className="h-3.5 w-3.5 text-indigo-600" />
                          <span>{fs.file_name}</span>
                          <span className="text-slate-400">
                            ({Math.max(1, Math.round(fs.file_size / 1024))} KB)
                          </span>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            assignmentsApi.downloadFileSubmission(
                              submissionsData.assignment_id,
                              fs.id,
                              fs.file_name
                            )
                          }
                          className="h-7 text-xs gap-1"
                        >
                          <Download className="h-3 w-3" />
                          <span>Tải bài làm</span>
                        </Button>
                      </div>

                      {fs.student_note && (
                        <p className="text-xs text-slate-600 italic">
                          Ghi chú của HS: &ldquo;{fs.student_note}&rdquo;
                        </p>
                      )}

                      <div className="grid grid-cols-1 sm:grid-cols-12 gap-2 pt-1">
                        <div className="sm:col-span-3">
                          <input
                            type="number"
                            step="0.25"
                            min={0}
                            max={item.maximum_score}
                            placeholder={`Điểm / ${item.maximum_score}`}
                            value={draft?.score ?? ""}
                            onChange={(e) =>
                              setGradeDrafts((prev) => ({
                                ...prev,
                                [fs.id]: {
                                  score: e.target.value,
                                  feedback: prev[fs.id]?.feedback ?? "",
                                },
                              }))
                            }
                            className="w-full h-8 rounded-lg border border-slate-300 px-2.5 text-xs focus:border-emerald-500 focus:outline-none"
                          />
                        </div>
                        <div className="sm:col-span-7">
                          <input
                            type="text"
                            placeholder="Nhận xét của giáo viên..."
                            value={draft?.feedback ?? ""}
                            onChange={(e) =>
                              setGradeDrafts((prev) => ({
                                ...prev,
                                [fs.id]: {
                                  score: prev[fs.id]?.score ?? "",
                                  feedback: e.target.value,
                                },
                              }))
                            }
                            className="w-full h-8 rounded-lg border border-slate-300 px-2.5 text-xs focus:border-emerald-500 focus:outline-none"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <Button
                            size="sm"
                            onClick={() => handleGradeFileSubmission(fs.id)}
                            isLoading={gradingSubmissionId === fs.id}
                            className="w-full h-8 text-xs bg-emerald-600 hover:bg-emerald-700"
                          >
                            Lưu điểm
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Dialog>
      {/* Auto-Convert Uploaded Exam File -> Multiple-Choice Quiz Assignment */}
      <ExamFileConverterModal
        isOpen={isQuizConvertOpen}
        onClose={() => setIsQuizConvertOpen(false)}
        classroomId={classroomId}
        defaultGradeId={classroom.grade_id || 10}
        onSuccess={() => {
          refetchAssignments();
          refetchClassroom();
        }}
      />
    </div>
  );
}
