"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/auth-context";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { examsApi } from "@/lib/api/exams";
import { questionsApi } from "@/lib/api/questions";
import { StatCard } from "@/components/shared/stat-card";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Users,
  UserCheck,
  Trophy,
  FileQuestion,
  PlusCircle,
  ArrowRight,
  Copy,
  Check,
  FileCheck2,
} from "lucide-react";

export default function TeacherDashboardPage() {
  const { user } = useAuth();
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [gradeId, setGradeId] = useState<number>(10);
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const {
    data: classrooms = [],
    isLoading: isLoadingClassrooms,
    refetch: refetchClassrooms,
  } = useQuery({
    queryKey: ["teacher-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  const { data: examsData, isLoading: isLoadingExams } = useQuery({
    queryKey: ["teacher-exams-count"],
    queryFn: () => examsApi.getExams({ page: 1, page_size: 1 }),
  });

  const { data: questionsData, isLoading: isLoadingQuestions } = useQuery({
    queryKey: ["teacher-questions-count"],
    queryFn: () => questionsApi.getQuestions({ page: 1, page_size: 1 }),
  });

  const totalStudents = classrooms.reduce(
    (acc, curr) => acc + (curr.member_count || 0),
    0
  );

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const handleCreateClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setIsCreating(true);

    try {
      await classroomsApi.createClassroom({
        name,
        grade_id: gradeId,
        description,
        max_students: 50,
      });
      setIsCreateOpen(false);
      setName("");
      setDescription("");
      refetchClassrooms();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setCreateError(err.message);
      } else {
        setCreateError("Tạo lớp học không thành công.");
      }
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-700 to-indigo-700 p-6 sm:p-8 text-white shadow-lg shadow-emerald-600/20">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <span className="inline-block px-3 py-1 rounded-full bg-white/20 text-xs font-semibold backdrop-blur-xs mb-3">
              Không gian Giảng viên • Năm học 2025 - 2026
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Xin chào, Thầy/Cô {user?.full_name}! 👋
            </h2>
            <p className="mt-2 text-emerald-100 text-sm max-w-xl">
              Quản lý lớp học, giao bài tập về nhà và theo dõi tiến độ làm bài của học sinh thời gian thực.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => setIsCreateOpen(true)}
              variant="secondary"
              className="bg-white text-emerald-800 hover:bg-emerald-50 border-0 shadow-sm gap-2"
            >
              <PlusCircle className="h-4 w-4" />
              <span>Tạo lớp học mới</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Lớp học phụ trách"
          value={isLoadingClassrooms ? "..." : classrooms.length}
          subtitle="Đang giảng dạy"
          icon={Users}
          iconColor="emerald"
        />
        <StatCard
          title="Tổng số học sinh"
          value={isLoadingClassrooms ? "..." : totalStudents}
          subtitle="Đã tham gia vào các lớp"
          icon={UserCheck}
          iconColor="indigo"
        />
        <StatCard
          title="Đề thi hệ thống"
          value={isLoadingExams ? "..." : examsData?.total || 0}
          subtitle="Đề thi trong kho lưu trữ"
          icon={Trophy}
          iconColor="purple"
        />
        <StatCard
          title="Ngân hàng câu hỏi"
          value={isLoadingQuestions ? "..." : questionsData?.total || 0}
          subtitle="Câu hỏi chuẩn KaTeX"
          icon={FileQuestion}
          iconColor="blue"
        />
      </div>

      {/* Classrooms List Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              Lớp học đang quản lý
            </h3>
            <p className="text-xs text-slate-500">
              Mã mời lớp học dùng để học sinh nhập và gia nhập tự động
            </p>
          </div>
          <Link href="/teacher/classrooms">
            <Button variant="ghost" size="sm" className="gap-1 text-emerald-700">
              <span>Xem tất cả lớp</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>

        {isLoadingClassrooms ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-40 rounded-xl" />
          </div>
        ) : classrooms.length === 0 ? (
          <Card className="p-8 text-center border-dashed">
            <Users className="h-10 w-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm font-semibold text-slate-700">
              Bạn chưa tạo lớp học nào
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Bấm nút bên dưới để tạo lớp học đầu tiên và nhận mã mời cung cấp cho học sinh.
            </p>
            <Button
              size="sm"
              className="mt-4 gap-1.5 bg-emerald-600 hover:bg-emerald-700"
              onClick={() => setIsCreateOpen(true)}
            >
              <PlusCircle className="h-4 w-4" />
              <span>Tạo lớp học mới</span>
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {classrooms.map((c) => (
              <Card
                key={c.id}
                className="p-5 flex flex-col justify-between hover:border-emerald-300 transition-all shadow-xs"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant="success">Khối {c.grade_id || 10}</Badge>
                    <button
                      onClick={() => handleCopyCode(c.code)}
                      className="flex items-center gap-1 font-mono text-xs font-bold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-2.5 py-1 rounded border border-emerald-200 transition-colors"
                      title="Bấm để sao chép mã mời"
                    >
                      {copiedCode === c.code ? (
                        <>
                          <Check className="h-3 w-3 text-emerald-600" />
                          <span className="text-emerald-700">Đã chép!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3 text-emerald-600" />
                          <span>{c.code}</span>
                        </>
                      )}
                    </button>
                  </div>

                  <Link href={`/teacher/classrooms/${c.id}`}>
                    <h4 className="font-bold text-slate-900 hover:text-emerald-700 transition-colors">
                      {c.name}
                    </h4>
                  </Link>

                  {c.description && (
                    <p className="text-xs text-slate-500 mt-1 line-clamp-1">
                      {c.description}
                    </p>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
                  <span className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5 text-slate-400" />
                    {c.member_count} học sinh
                  </span>
                  <span className="flex items-center gap-1 font-medium text-emerald-700">
                    <FileCheck2 className="h-3.5 w-3.5" />
                    {c.assignment_count} bài tập
                  </span>
                  <Link href={`/teacher/classrooms/${c.id}`}>
                    <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-emerald-700">
                      Chi tiết
                    </Button>
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create Classroom Modal */}
      <Dialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Tạo Lớp học mới"
        description="Hệ thống sẽ tự động cấp một mã mời (Invite Code) độc nhất cho lớp học"
      >
        <form onSubmit={handleCreateClassroom} className="space-y-4">
          {createError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {createError}
            </div>
          )}
          <Input
            label="Tên lớp học"
            placeholder="Ví dụ: Lớp 10A1 — Chuyên đề Hình học"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
              Khối lớp
            </label>
            <select
              value={gradeId}
              onChange={(e) => setGradeId(Number(e.target.value))}
              className="flex h-10 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            >
              {[6, 7, 8, 9, 10, 11, 12].map((g) => (
                <option key={g} value={g}>
                  Khối Lớp {g}
                </option>
              ))}
            </select>
          </div>

          <Input
            label="Mô tả lớp học (Tùy chọn)"
            placeholder="Kế hoạch học tập, mục tiêu kỳ thi..."
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
              Tạo lớp học
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
