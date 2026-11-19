"use client";

import React, { useState } from "react";
import Link from "next/link";
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
  Copy,
  Check,
  FileCheck2,
  ArrowRight,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function TeacherClassroomsPage() {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [gradeId, setGradeId] = useState<number>(10);
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const {
    data: classrooms = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["teacher-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

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
      refetch();
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Quản lý Lớp học
          </h2>
          <p className="text-sm text-slate-500">
            Danh sách tất cả các lớp học do bạn làm chủ nhiệm hoặc phụ trách bộ môn
          </p>
        </div>
        <Button
          onClick={() => setIsCreateOpen(true)}
          className="gap-2 bg-emerald-600 hover:bg-emerald-700"
        >
          <PlusCircle className="h-4 w-4" />
          <span>Tạo lớp học mới</span>
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
          title="Bạn chưa có lớp học nào"
          description="Bắt đầu tạo lớp học để quản lý học sinh và giao bài tập số tự động chấm điểm."
          actionLabel="Tạo lớp học đầu tiên"
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {classrooms.map((c) => (
            <Card
              key={c.id}
              className="flex flex-col justify-between hover:border-emerald-300 transition-all shadow-xs"
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="success">Khối {c.grade_id || 10}</Badge>
                  <button
                    onClick={() => handleCopyCode(c.code)}
                    className="flex items-center gap-1 font-mono text-xs font-bold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-2 py-0.5 rounded border border-emerald-200 transition-colors"
                    title="Sao chép mã mời"
                  >
                    {copiedCode === c.code ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-600" />
                        <span>Đã chép</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 text-emerald-600" />
                        <span>{c.code}</span>
                      </>
                    )}
                  </button>
                </div>
                <CardTitle className="text-lg text-slate-900">
                  {c.name}
                </CardTitle>
                <CardDescription className="text-xs">
                  Tạo ngày: {formatDate(c.created_at)}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-0">
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

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-mono">
                    Sĩ số tối đa: {c.max_students}
                  </span>
                  <Link href={`/teacher/classrooms/${c.id}`}>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1 text-xs text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50"
                    >
                      <span>Vào lớp</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Classroom Modal */}
      <Dialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Tạo Lớp học mới"
        description="Điền thông tin cơ bản để thiết lập lớp học ảo"
      >
        <form onSubmit={handleCreateClassroom} className="space-y-4">
          {createError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {createError}
            </div>
          )}
          <Input
            label="Tên lớp học"
            placeholder="Ví dụ: 10A1 — Toán Đại số & Giải tích"
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
            label="Mô tả lớp học"
            placeholder="Giới thiệu nội dung trọng tâm hoặc ghi chú..."
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
