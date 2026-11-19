"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { classroomsApi } from "@/lib/api/classrooms";
import { examsApi } from "@/lib/api/exams";
import { questionsApi } from "@/lib/api/questions";
import { StatCard } from "@/components/shared/stat-card";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  ShieldAlert,
  Server,
  Database,
  Users,
  Trophy,
  FileQuestion,
  ArrowRight,
} from "lucide-react";

export default function AdminDashboardPage() {
  const { data: healthData, isLoading: isLoadingHealth } = useQuery({
    queryKey: ["admin-health"],
    queryFn: () => apiClient.get<Record<string, unknown>>("/health"),
  });

  const { data: classrooms = [] } = useQuery({
    queryKey: ["admin-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  const { data: examsData } = useQuery({
    queryKey: ["admin-exams"],
    queryFn: () => examsApi.getExams({ page_size: 1 }),
  });

  const { data: questionsData } = useQuery({
    queryKey: ["admin-questions"],
    queryFn: () => questionsApi.getQuestions({ page_size: 1 }),
  });

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-amber-600 to-orange-700 p-6 sm:p-8 text-white shadow-lg shadow-amber-600/20">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <span className="inline-block px-3 py-1 rounded-full bg-white/20 text-xs font-semibold backdrop-blur-xs mb-3">
              Trạng thái Hạ tầng Hệ thống: Hoạt động Tốt (HEALTHY)
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Trung Tâm Điều Hành Toàn Hệ Thống
            </h2>
            <p className="mt-2 text-amber-100 text-sm max-w-xl">
              Giám sát tình trạng hoạt động của FastAPI backend, kết nối cơ sở dữ liệu SQLite/PostgreSQL và phiên bản phần mềm.
            </p>
          </div>
        </div>
      </div>

      {/* Infrastructure Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Trạng thái Backend"
          value={isLoadingHealth ? "Đang kiểm tra..." : healthData ? "HOẠT ĐỘNG (OK)" : "DISCONNECTED"}
          subtitle="FastAPI v0.115 / Uvicorn"
          icon={Server}
          iconColor="emerald"
        />
        <StatCard
          title="Lớp học hệ thống"
          value={classrooms.length}
          subtitle="Toàn bộ các lớp trên nền tảng"
          icon={Users}
          iconColor="indigo"
        />
        <StatCard
          title="Kho đề thi tổng hợp"
          value={examsData?.total || 0}
          subtitle="Đề thi đã khởi tạo"
          icon={Trophy}
          iconColor="purple"
        />
        <StatCard
          title="Tổng số câu hỏi"
          value={questionsData?.total || 0}
          subtitle="Ngân hàng câu hỏi KaTeX"
          icon={FileQuestion}
          iconColor="blue"
        />
      </div>

      {/* System Specifications Card */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Database className="h-5 w-5 text-indigo-600" />
              <span>Thông số Cấu hình Hạ tầng</span>
            </CardTitle>
            <CardDescription>Cơ sở dữ liệu & Công nghệ vận hành</CardDescription>
          </CardHeader>
          <CardContent className="divide-y divide-slate-100 text-sm">
            <div className="py-2.5 flex justify-between">
              <span className="text-slate-500">Môi trường:</span>
              <span className="font-semibold text-slate-900">Development / Production-Ready</span>
            </div>
            <div className="py-2.5 flex justify-between">
              <span className="text-slate-500">Database Engine:</span>
              <span className="font-mono text-xs text-slate-800">
                SQLAlchemy 2.0 Async (SQLite / Postgres Compatible)
              </span>
            </div>
            <div className="py-2.5 flex justify-between">
              <span className="text-slate-500">Chuẩn mã hóa:</span>
              <span className="text-emerald-700 font-medium">Argon2id Password Hashing</span>
            </div>
            <div className="py-2.5 flex justify-between">
              <span className="text-slate-500">Phiên xác thực:</span>
              <span className="text-slate-800 font-medium">
                Dual Mode: HttpOnly Cookie & Authorization Bearer
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-600" />
              <span>Chuyển quyền Quản lý Nhanh</span>
            </CardTitle>
            <CardDescription>
              Kiểm tra trải nghiệm người dùng với các vai trò thực tế
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/student/dashboard" className="block">
              <div className="p-3.5 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/40 transition-all flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm">
                    Trực tiếp vào Cổng Học sinh
                  </h4>
                  <p className="text-xs text-slate-500">
                    Trải nghiệm giao diện làm bài, tham gia lớp và bảng điểm
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </div>
            </Link>

            <Link href="/teacher/dashboard" className="block">
              <div className="p-3.5 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/40 transition-all flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm">
                    Trực tiếp vào Cổng Giáo viên
                  </h4>
                  <p className="text-xs text-slate-500">
                    Quản lý lớp học, cấp mã mời và giao bài tập số
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </div>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
