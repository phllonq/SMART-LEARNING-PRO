"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import {
  ShieldAlert,
  LayoutDashboard,
  GraduationCap,
  Users,
  LogOut,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    } else if (
      !isLoading &&
      user &&
      user.role !== "ADMIN" &&
      user.role !== "SUPERADMIN"
    ) {
      router.push("/student/dashboard");
    }
  }, [user, isLoading, router]);

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 border-4 border-amber-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium text-slate-500">Đang tải SMART LEARNING ADMIN...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 border-r border-slate-200 bg-white z-30">
        <div className="flex h-16 items-center gap-2.5 px-6 border-b border-slate-200">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-600 text-white shadow-md shadow-amber-600/20">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <span className="text-base font-bold text-slate-900 leading-none block">
              SMART LEARNING
            </span>
            <span className="text-[10px] font-semibold text-amber-600 tracking-wider uppercase">
              Quản Trị Hệ Thống
            </span>
          </div>
        </div>

        {/* User Card */}
        <div className="p-4 mx-3 my-3 rounded-xl bg-amber-50/60 border border-amber-100 flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-amber-600 text-white flex items-center justify-center font-bold text-sm shrink-0">
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-slate-900 truncate">
              {user.full_name}
            </p>
            <p className="text-xs text-amber-700 font-medium">
              Administrator ({user.role})
            </p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
          <Link
            href="/admin/dashboard"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
              pathname === "/admin/dashboard"
                ? "bg-amber-600 text-white shadow-xs"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <LayoutDashboard className="h-5 w-5" />
            <span>Tổng quan Quản trị</span>
          </Link>

          <div className="pt-4 pb-2 px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Chuyển nhanh phân hệ
          </div>

          <Link
            href="/teacher/dashboard"
            className="flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            <div className="flex items-center gap-3">
              <Users className="h-5 w-5 text-emerald-600" />
              <span>Cổng Giáo viên</span>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </Link>

          <Link
            href="/student/dashboard"
            className="flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            <div className="flex items-center gap-3">
              <GraduationCap className="h-5 w-5 text-indigo-600" />
              <span>Cổng Học sinh</span>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </Link>
        </nav>

        {/* Logout */}
        <div className="p-4 border-t border-slate-200">
          <Button
            variant="ghost"
            onClick={logout}
            className="w-full justify-start text-slate-600 hover:text-rose-600 hover:bg-rose-50 gap-2"
          >
            <LogOut className="h-4 w-4" />
            <span>Đăng xuất</span>
          </Button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="lg:pl-64 flex flex-col flex-1 min-w-0">
        <header className="sticky top-0 z-20 h-16 border-b border-slate-200 bg-white/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-slate-900">
            Bảng Điều Khiển Quản Trị Hệ Thống
          </h1>
          <Badge variant="warning">ADMIN PRIVILEGE</Badge>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
