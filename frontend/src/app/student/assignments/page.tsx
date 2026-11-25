"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { assignmentsApi } from "@/lib/api/assignments";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
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
  Paperclip,
  Download,
  Upload,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import { AssignmentSummary } from "@/types";

export default function StudentAssignmentsPage() {
  const router = useRouter();
  const [now] = useState(() => Date.now());
  const [startingId, setStartingId] = useState<string | null>(null);

  // Student file upload modal
  const [uploadTarget, setUploadTarget] = useState<AssignmentSummary | null>(null);
  const [submissionFile, setSubmissionFile] = useState<File | null>(null);
  const [submissionNote, setSubmissionNote] = useState("");
  const [isSubmittingFile, setIsSubmittingFile] = useState(false);
  const [submitFileError, setSubmitFileError] = useState<string | null>(null);

  const { data: classrooms = [], isLoading: isLoadingClassrooms } = useQuery({
    queryKey: ["student-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  // Fetch assignments for all enrolled classrooms
  const {
    data: assignments = [],
    isLoading: isLoadingAssignments,
    refetch: refetchAssignments,
  } = useQuery({
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

  const handleSubmitFile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadTarget) return;
    if (!submissionFile) {
      setSubmitFileError("Vui lòng chọn tệp bài làm để nộp.");
      return;
    }

    setSubmitFileError(null);
    setIsSubmittingFile(true);
    try {
      await assignmentsApi.submitFileAssignment(
        uploadTarget.id,
        submissionFile,
        submissionNote || undefined
      );
      setUploadTarget(null);
      setSubmissionFile(null);
      setSubmissionNote("");
      refetchAssignments();
    } catch (err: unknown) {
      setSubmitFileError(
        err instanceof Error ? err.message : "Nộp bài thất bại."
      );
    } finally {
      setIsSubmittingFile(false);
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
                    {assignment.assignment_type === "FILE" && (
                      <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200 gap-1">
                        <Paperclip className="h-3 w-3" />
                        <span>Bài tập tệp đính kèm</span>
                      </Badge>
                    )}
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

                  {assignment.assignment_type === "FILE" && assignment.my_file_submission && (
                    <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs space-y-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-slate-700">
                          Đã nộp: {assignment.my_file_submission.file_name}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            assignment.my_file_submission &&
                            assignmentsApi.downloadFileSubmission(
                              assignment.id,
                              assignment.my_file_submission.id,
                              assignment.my_file_submission.file_name
                            )
                          }
                          className="text-indigo-600 hover:underline font-medium"
                        >
                          Tải lại bài đã nộp
                        </button>
                      </div>
                      {assignment.my_file_submission.teacher_feedback && (
                        <p className="text-emerald-700">
                          Nhận xét của GV: {assignment.my_file_submission.teacher_feedback}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5 text-slate-400" />
                      Hạn nộp: {formatDate(assignment.due_date)}
                    </span>
                    {assignment.assignment_type !== "FILE" && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        Thời gian: {assignment.duration_minutes} phút
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <Award className="h-3.5 w-3.5 text-slate-400" />
                      Thang điểm: {assignment.total_points} đ
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
                  {assignment.assignment_type === "FILE" ? (
                    <>
                      {assignment.has_attachment && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-1.5"
                          onClick={() =>
                            assignmentsApi.downloadAssignmentAttachment(
                              assignment.id,
                              assignment.attachment_name || "de-bai"
                            )
                          }
                        >
                          <Download className="h-4 w-4" />
                          <span>Tải đề bài</span>
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className="gap-1.5 bg-emerald-600 hover:bg-emerald-700"
                        disabled={
                          (isOverdue && !assignment.allow_late_submission) ||
                          assignment.my_status === "GRADED"
                        }
                        onClick={() => {
                          setSubmitFileError(null);
                          setSubmissionFile(null);
                          setSubmissionNote("");
                          setUploadTarget(assignment);
                        }}
                      >
                        <Upload className="h-4 w-4" />
                        <span>
                          {assignment.my_file_submission
                            ? "Nộp lại bài"
                            : "Nộp bài từ máy"}
                        </span>
                      </Button>
                    </>
                  ) : (
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
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Submit File Assignment Modal */}
      <Dialog
        isOpen={Boolean(uploadTarget)}
        onClose={() => setUploadTarget(null)}
        title={uploadTarget ? `Nộp bài: ${uploadTarget.title}` : "Nộp bài tập"}
        description="Tải lên tệp bài làm (.pdf, .docx, ảnh chụp, .xlsx, .txt, .zip — tối đa 15MB)"
      >
        <form onSubmit={handleSubmitFile} className="space-y-4">
          {submitFileError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {submitFileError}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
              Chọn tệp bài làm
            </label>
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.txt,.zip"
              onChange={(e) => setSubmissionFile(e.target.files?.[0] || null)}
              required
              className="block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
              Ghi chú gửi giáo viên (Tùy chọn)
            </label>
            <textarea
              rows={3}
              value={submissionNote}
              onChange={(e) => setSubmissionNote(e.target.value)}
              placeholder="Ví dụ: Em đã hoàn thành đầy đủ phần tự luận..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setUploadTarget(null)}
            >
              Hủy
            </Button>
            <Button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700"
              isLoading={isSubmittingFile}
            >
              Gửi bài làm
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
