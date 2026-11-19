"use client";

import React from "react";
import { useAuth } from "@/lib/auth/auth-context";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/shared/stat-card";
import { formatDate } from "@/lib/utils";
import {
  Mail,
  Flame,
  Zap,
  ShieldCheck,
  Award,
} from "lucide-react";

export default function StudentProfilePage() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Hồ sơ Học sinh
        </h2>
        <p className="text-sm text-slate-500">
          Thông tin cá nhân và tiến trình học tập của bạn
        </p>
      </div>

      {/* Main Profile Info Card */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="h-20 w-20 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-bold text-3xl shadow-lg shadow-indigo-600/30">
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div className="text-center sm:text-left space-y-1">
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
              <h3 className="text-xl font-bold text-slate-900">{user.full_name}</h3>
              <Badge variant="default">Học sinh</Badge>
              <Badge variant="success">Đang hoạt động</Badge>
            </div>
            <p className="text-sm text-slate-500 flex items-center justify-center sm:justify-start gap-1.5">
              <Mail className="h-4 w-4" />
              <span>{user.email}</span>
            </p>
            <p className="text-xs text-indigo-600 font-semibold">
              Học sinh Khối {user.grade_level || 10} • Trường THPT Trọng Điểm
            </p>
          </div>
        </div>
      </Card>

      {/* Gamification Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Chuỗi ngày học"
          value={`${user.streak_days || 0} ngày`}
          subtitle="Chỉ số duy trì chuyên cần"
          icon={Flame}
          iconColor="amber"
        />
        <StatCard
          title="Điểm tích lũy"
          value={`${user.xp_points || 0} XP`}
          subtitle="Tích lũy từ bài tập & kỳ thi"
          icon={Zap}
          iconColor="indigo"
        />
        <StatCard
          title="Cấp bậc danh hiệu"
          value={`Cấp độ ${user.current_level || 1}`}
          subtitle="Thành viên tích cực"
          icon={Award}
          iconColor="purple"
        />
      </div>

      {/* Account Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Chi tiết tài khoản</CardTitle>
          <CardDescription>Thông tin hệ thống và quyền truy cập</CardDescription>
        </CardHeader>
        <CardContent className="divide-y divide-slate-100 text-sm">
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Mã định danh (ID):</span>
            <span className="font-mono text-xs text-slate-700">{user.id}</span>
          </div>
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Ngày tham gia hệ thống:</span>
            <span className="text-slate-700 font-medium">
              {formatDate(user.created_at)}
            </span>
          </div>
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Khối lớp mặc định:</span>
            <span className="text-slate-700 font-medium">
              Khối {user.grade_level || 10}
            </span>
          </div>
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Chế độ bảo mật:</span>
            <span className="text-emerald-600 font-medium flex items-center gap-1">
              <ShieldCheck className="h-4 w-4" />
              Argon2id + Dual JWT Cookie Token
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
