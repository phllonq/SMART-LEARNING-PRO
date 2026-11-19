"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/auth-context";
import { useQuery } from "@tanstack/react-query";
import { classroomsApi } from "@/lib/api/classrooms";
import { examsApi } from "@/lib/api/exams";
import { StatCard } from "@/components/shared/stat-card";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ExamSummary } from "@/types";
import {
  Flame,
  Zap,
  Users,
  Trophy,
  ArrowRight,
  Clock,
  PlusCircle,
  FileCheck2,
} from "lucide-react";

export default function StudentDashboardPage() {
  const { user } = useAuth();
  const [isJoinOpen, setIsJoinOpen] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [joinError, setJoinError] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  const {
    data: classrooms = [],
    isLoading: isLoadingClassrooms,
    refetch: refetchClassrooms,
  } = useQuery({
    queryKey: ["student-classrooms"],
    queryFn: () => classroomsApi.getClassrooms(),
  });

  const { data: availableExams = [], isLoading: isLoadingExams } = useQuery({
    queryKey: ["student-available-exams"],
    queryFn: () => examsApi.getAvailableExams(),
  });

  const handleJoinClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError(null);
    setIsJoining(true);
    try {
      await classroomsApi.joinClassroom(inviteCode.trim().toUpperCase());
      setIsJoinOpen(false);
      setInviteCode("");
      refetchClassrooms();
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.includes("not found") || err.message.includes("ClassroomCode")) {
          setJoinError("Mã mời không chính xác hoặc không tồn tại.");
        } else {
          setJoinError(err.message);
        }
      } else {
        setJoinError("Mã mời không hợp lệ hoặc bạn đã ở trong lớp này.");
      }
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-indigo-600 via-indigo-700 to-purple-700 p-6 sm:p-8 text-white shadow-lg shadow-indigo-600/20">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <span className="inline-block px-3 py-1 rounded-full bg-white/20 text-xs font-semibold backdrop-blur-xs mb-3">
              Khối {user?.grade_level || 10} • Năm học 2025 - 2026
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Chào mừng trở lại, {user?.full_name}! 👋
            </h2>
            <p className="mt-2 text-indigo-100 text-sm max-w-xl">
              Hôm nay là thời điểm lý tưởng để luyện đề và hoàn thành các bài tập về nhà.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => setIsJoinOpen(true)}
              variant="secondary"
              className="bg-white text-indigo-700 hover:bg-indigo-50 border-0 shadow-sm gap-2"
            >
              <PlusCircle className="h-4 w-4" />
              <span>Tham gia lớp học</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Gamification Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Chuỗi học liên tục"
          value={`${user?.streak_days || 0} ngày`}
          subtitle="Duy trì học tập mỗi ngày"
          icon={Flame}
          iconColor="amber"
        />
        <StatCard
          title="Điểm kinh nghiệm"
          value={`${user?.xp_points || 0} XP`}
          subtitle={`Cấp độ ${user?.current_level || 1}`}
          icon={Zap}
          iconColor="indigo"
        />
        <StatCard
          title="Lớp học tham gia"
          value={isLoadingClassrooms ? "..." : classrooms.length}
          subtitle="Lớp học đang hoạt động"
          icon={Users}
          iconColor="emerald"
        />
        <StatCard
          title="Đề thi sẵn sàng"
          value={isLoadingExams ? "..." : availableExams.length}
          subtitle="Đề thi mở phòng luyện"
          icon={Trophy}
          iconColor="purple"
        />
      </div>

      {/* Main Grid: Classrooms & Available Exams */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Enrolled Classrooms Section */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                Lớp học của tôi
              </h3>
              <p className="text-xs text-slate-500">
                Các lớp bạn đang là thành viên
              </p>
            </div>
            <Link href="/student/classrooms">
              <Button variant="ghost" size="sm" className="gap-1 text-indigo-600">
                <span>Xem tất cả</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {isLoadingClassrooms ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Skeleton className="h-36 rounded-xl" />
              <Skeleton className="h-36 rounded-xl" />
            </div>
          ) : classrooms.length === 0 ? (
            <Card className="p-8 text-center border-dashed">
              <Users className="h-10 w-10 text-slate-300 mx-auto mb-3" />
              <p className="text-sm font-semibold text-slate-700">
                Bạn chưa tham gia lớp học nào
              </p>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Nhập mã mời do giáo viên cung cấp để bắt đầu nhận bài tập và tham gia thảo luận.
              </p>
              <Button
                size="sm"
                className="mt-4 gap-1.5"
                onClick={() => setIsJoinOpen(true)}
              >
                <PlusCircle className="h-4 w-4" />
                <span>Nhập mã lớp</span>
              </Button>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {classrooms.slice(0, 4).map((c) => (
                <Card
                  key={c.id}
                  className="p-5 flex flex-col justify-between hover:border-indigo-300 transition-all cursor-pointer group"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="default">Khối {c.grade_id || 10}</Badge>
                      <span className="text-xs font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                        {c.code}
                      </span>
                    </div>
                    <h4 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                      {c.name}
                    </h4>
                    <p className="text-xs text-slate-500 mt-1">
                      GV: {c.teacher_name || "Giáo viên bộ môn"}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Users className="h-3.5 w-3.5" />
                      {c.member_count} học sinh
                    </span>
                    <span className="flex items-center gap-1 font-medium text-indigo-600">
                      <FileCheck2 className="h-3.5 w-3.5" />
                      {c.assignment_count} bài tập
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Available Exams & Practice List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-900">
              Đề thi đề xuất
            </h3>
            <Link href="/student/exams">
              <Button variant="ghost" size="sm" className="gap-1 text-indigo-600">
                <span>Tất cả đề</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          <Card className="divide-y divide-slate-100">
            {isLoadingExams ? (
              <div className="p-4 space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : availableExams.length === 0 ? (
              <div className="p-6 text-center">
                <Trophy className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                <p className="text-xs text-slate-500">
                  Hiện chưa có đề thi tự do nào được mở.
                </p>
              </div>
            ) : (
              availableExams.slice(0, 5).map((exam: ExamSummary) => (
                <div
                  key={exam.id}
                  className="p-4 hover:bg-slate-50 transition-colors flex items-center justify-between"
                >
                  <div className="space-y-1 pr-2">
                    <p className="text-sm font-semibold text-slate-900 line-clamp-1">
                      {exam.title}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {exam.duration_minutes} phút
                      </span>
                      <span>•</span>
                      <span>{exam.question_count || 10} câu hỏi</span>
                    </div>
                  </div>
                  <Link href="/student/exams">
                    <Button size="sm" variant="outline" className="shrink-0 text-xs">
                      Làm bài
                    </Button>
                  </Link>
                </div>
              ))
            )}
          </Card>
        </div>
      </div>

      {/* Join Classroom Modal */}
      <Dialog
        isOpen={isJoinOpen}
        onClose={() => setIsJoinOpen(false)}
        title="Tham gia Lớp học mới"
        description="Nhập mã mời gồm 6-8 ký tự do giáo viên cung cấp (ví dụ: SL-ABC123)"
      >
        <form onSubmit={handleJoinClassroom} className="space-y-4">
          {joinError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {joinError}
            </div>
          )}
          <Input
            label="Mã mời lớp học (Invite Code)"
            placeholder="SL-XXXXXX"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
            required
            className="uppercase font-mono tracking-wider text-base"
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
              Tham gia ngay
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
