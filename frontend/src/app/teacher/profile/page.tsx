"use client";

import React from "react";
import { useAuth } from "@/lib/auth/auth-context";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import {
  Mail,
  ShieldCheck,
} from "lucide-react";

export default function TeacherProfilePage() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Hồ sơ Giáo viên
        </h2>
        <p className="text-sm text-slate-500">
          Thông tin tài khoản và chứng thực giảng dạy
        </p>
      </div>

      <Card className="p-6">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="h-20 w-20 rounded-2xl bg-emerald-600 text-white flex items-center justify-center font-bold text-3xl shadow-lg shadow-emerald-600/30">
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div className="text-center sm:text-left space-y-1">
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
              <h3 className="text-xl font-bold text-slate-900">
                Thầy/Cô {user.full_name}
              </h3>
              <Badge variant="success">Giáo viên xác thực</Badge>
              <Badge variant="default">Quyền Quản trị Lớp</Badge>
            </div>
            <p className="text-sm text-slate-500 flex items-center justify-center sm:justify-start gap-1.5">
              <Mail className="h-4 w-4" />
              <span>{user.email}</span>
            </p>
            <p className="text-xs text-emerald-700 font-semibold">
              Hệ thống Giáo dục Thông minh SMART LEARNING PRO
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Thông tin hệ thống</CardTitle>
          <CardDescription>Chi tiết tài khoản và định danh giáo viên</CardDescription>
        </CardHeader>
        <CardContent className="divide-y divide-slate-100 text-sm">
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Mã định danh (ID):</span>
            <span className="font-mono text-xs text-slate-700">{user.id}</span>
          </div>
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Vai trò RBAC:</span>
            <span className="font-semibold text-emerald-700">{user.role}</span>
          </div>
          <div className="py-3 flex justify-between">
            <span className="text-slate-500">Ngày tham gia hệ thống:</span>
            <span className="text-slate-700 font-medium">
              {formatDate(user.created_at)}
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
