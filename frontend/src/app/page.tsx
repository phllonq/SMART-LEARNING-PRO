"use client";

import Link from "next/link";
import {
  GraduationCap,
  BookOpen,
  UserCheck,
  Award,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  FileQuestion,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Navigation Header */}
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/20">
              <GraduationCap className="h-6 w-6" />
            </div>
            <div>
              <span className="text-lg font-bold text-slate-900 leading-tight block">
                SMART LEARNING
              </span>
              <span className="text-[10px] font-semibold text-indigo-600 tracking-wider uppercase block">
                PRO EDTECH
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="outline" size="sm">
                Đăng nhập
              </Button>
            </Link>
            <Link href="/register">
              <Button variant="default" size="sm">
                Bắt đầu học ngay
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="relative overflow-hidden pt-12 pb-20 lg:pt-20 lg:pb-28">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold mb-6 animate-fade-in">
              <Sparkles className="h-4 w-4" />
              <span>Nền tảng Học tập Thông minh Chuẩn Chương trình GDPT 2018</span>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-slate-900 max-w-4xl mx-auto leading-tight">
              Học tập thông minh, bứt phá điểm số cùng{" "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">
                SMART LEARNING PRO
              </span>
            </h1>

            <p className="mt-6 max-w-2xl mx-auto text-lg text-slate-600 leading-relaxed">
              Tích hợp công nghệ AI Socratic, ngân hàng câu hỏi công thức chuẩn KaTeX, hệ thống lớp học ảo và phòng luyện thi tự động cho học sinh THCS & THPT.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/login" className="w-full sm:w-auto">
                <Button size="lg" className="w-full sm:w-auto gap-2 text-base px-8 py-6 rounded-xl shadow-lg shadow-indigo-600/25">
                  <BookOpen className="h-5 w-5" />
                  <span>Vào cổng Học sinh</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/login" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full sm:w-auto gap-2 text-base px-8 py-6 rounded-xl bg-white hover:bg-slate-50"
                >
                  <UserCheck className="h-5 w-5 text-indigo-600" />
                  <span>Cổng Giáo viên & Giảng dạy</span>
                </Button>
              </Link>
            </div>

            {/* Quick Demo Credentials Info */}
            <div className="mt-12 p-4 rounded-xl bg-white border border-slate-200 shadow-xs max-w-xl mx-auto text-left">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-2">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                <span>Tài khoản mẫu đã tích hợp sẵn dữ liệu thực:</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                  <span className="font-semibold text-slate-900 block">Học sinh (Lớp 10):</span>
                  <code className="text-indigo-600 text-[11px]">student@smartlearning.vn</code>
                </div>
                <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                  <span className="font-semibold text-slate-900 block">Giáo viên Toán & Tin:</span>
                  <code className="text-indigo-600 text-[11px]">teacher@smartlearning.vn</code>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Grid */}
        <section className="py-16 bg-white border-t border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-14">
              <Badge variant="purple" className="mb-2">Tính năng cốt lõi</Badge>
              <h2 className="text-3xl font-bold tracking-tight text-slate-900">
                Hệ sinh thái số toàn diện cho trường học
              </h2>
              <p className="mt-3 text-slate-600 text-sm sm:text-base">
                Được thiết kế tỉ mỉ đáp ứng cả học sinh tự luyện và giáo viên quản lý lớp học.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <Card className="p-6 rounded-2xl hover:border-indigo-200 transition-all">
                <div className="h-12 w-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-5">
                  <Layers className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  Chương trình Khung GDPT 2018
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Cấu trúc phân cấp chuẩn từ Khối lớp (6-12), Môn học, Chương mục tới từng Bài học và Chủ đề kiến thức.
                </p>
              </Card>

              <Card className="p-6 rounded-2xl hover:border-indigo-200 transition-all">
                <div className="h-12 w-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 mb-5">
                  <FileQuestion className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  Ngân hàng Đề thi & KaTeX Math
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Hỗ trợ công thức Toán, Lý, Hóa qua KaTeX chuẩn quốc tế. Hệ thống chấm điểm tự động bảo mật cao.
                </p>
              </Card>

              <Card className="p-6 rounded-2xl hover:border-indigo-200 transition-all">
                <div className="h-12 w-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 mb-5">
                  <Award className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  Lớp học số & Bài tập về nhà
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Gia nhập lớp bằng mã code SL-XXXXXX, giáo viên giao bài theo thời hạn, chấm điểm và quản lý sổ điểm thời gian thực.
                </p>
              </Card>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-slate-100 py-8 text-center text-sm text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          <p>© 2026 SMART LEARNING PRO — Sản phẩm EdTech thế hệ mới cho học sinh Việt Nam.</p>
        </div>
      </footer>
    </div>
  );
}
