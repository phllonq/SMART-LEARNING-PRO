"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import {
  GraduationCap,
  LayoutDashboard,
  Users,
  FileCheck2,
  BookOpen,
  Trophy,
  User,
  LogOut,
  Flame,
  Zap,
  Menu,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    } else if (!isLoading && user && user.role !== "STUDENT" && user.role !== "ADMIN" && user.role !== "SUPERADMIN") {
      router.push("/teacher/dashboard");
    }
  }, [user, isLoading, router]);

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium text-slate-500">Đang tải SMART LEARNING...</p>
        </div>
      </div>
    );
  }

  const navItems = [
    {
      name: "Tổng quan",
      href: "/student/dashboard",
      icon: LayoutDashboard,
    },
    {
      name: "Lớp học của tôi",
      href: "/student/classrooms",
      icon: Users,
    },
    {
      name: "Bài tập về nhà",
      href: "/student/assignments",
      icon: FileCheck2,
    },
    {
      name: "Môn học GDPT",
      href: "/student/courses",
      icon: BookOpen,
    },
    {
      name: "Phòng luyện thi",
      href: "/student/exams",
      icon: Trophy,
    },
    {
      name: "Hồ sơ cá nhân",
      href: "/student/profile",
      icon: User,
    },
  ];

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 border-r border-slate-200 bg-white z-30">
        <div className="flex h-16 items-center gap-2.5 px-6 border-b border-slate-200">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/20">
            <GraduationCap className="h-5 w-5" />
          </div>
          <div>
            <span className="text-base font-bold text-slate-900 leading-none block">
              SMART LEARNING
            </span>
            <span className="text-[10px] font-semibold text-indigo-600 tracking-wider uppercase">
              Cổng Học Sinh
            </span>
          </div>
        </div>

        {/* User Card Pill */}
        <div className="p-4 mx-3 my-3 rounded-xl bg-indigo-50/60 border border-indigo-100 flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-sm shrink-0">
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-slate-900 truncate">
              {user.full_name}
            </p>
            <p className="text-xs text-indigo-600 font-medium">
              Khối {user.grade_level || 10} • Cấp độ {user.current_level}
            </p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <Icon className={`h-5 w-5 ${isActive ? "text-white" : "text-slate-500"}`} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Logout Footer */}
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

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 w-64 bg-white shadow-xl flex flex-col z-50">
            <div className="flex h-16 items-center justify-between px-6 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <GraduationCap className="h-6 w-6 text-indigo-600" />
                <span className="font-bold text-slate-900">SMART LEARNING</span>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 rounded-lg text-slate-500 hover:bg-slate-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex-1 p-3 space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium ${
                      isActive
                        ? "bg-indigo-600 text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </nav>
            <div className="p-4 border-t border-slate-200">
              <Button
                variant="ghost"
                onClick={logout}
                className="w-full justify-start text-rose-600 hover:bg-rose-50 gap-2"
              >
                <LogOut className="h-4 w-4" />
                <span>Đăng xuất</span>
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="lg:pl-64 flex flex-col flex-1 min-w-0">
        {/* Top Navbar */}
        <header className="sticky top-0 z-20 h-16 border-b border-slate-200 bg-white/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="text-lg font-semibold text-slate-900 hidden sm:block">
              Cổng Học Sinh
            </h1>
          </div>

          {/* Gamification Status Bar */}
          <div className="flex items-center gap-2.5 sm:gap-4">
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs font-semibold">
              <Flame className="h-4 w-4 text-amber-500 fill-amber-500" />
              <span>{user.streak_days || 0} ngày</span>
            </div>

            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold">
              <Zap className="h-4 w-4 text-indigo-500 fill-indigo-500" />
              <span>{user.xp_points || 0} XP</span>
            </div>

            <Badge variant="purple" className="hidden sm:inline-flex">
              Level {user.current_level || 1}
            </Badge>

            <div className="h-8 w-px bg-slate-200 mx-1 hidden sm:block" />

            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
                {user.full_name.charAt(0)}
              </div>
              <span className="text-sm font-medium text-slate-700 hidden md:block">
                {user.full_name}
              </span>
            </div>
          </div>
        </header>

        {/* Page Content Outlet */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Suspense fallback={<div className="h-40 flex items-center justify-center text-sm text-slate-400">Đang tải nội dung...</div>}>
            {children}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
