"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GraduationCap, BookOpen, UserCheck, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const user = await login({ email, password });
      if (user.role === "STUDENT") {
        router.push("/student/dashboard");
      } else if (user.role === "TEACHER") {
        router.push("/teacher/dashboard");
      } else {
        router.push("/admin/dashboard");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Đăng nhập không thành công. Vui lòng kiểm tra lại thông tin.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickFill = (fillEmail: string, fillPass: string) => {
    setEmail(fillEmail);
    setPassword(fillPass);
    setError(null);
  };

  return (
    <div className="min-h-screen flex flex-col justify-center items-center px-4 py-12 sm:px-6 lg:px-8 bg-gradient-to-b from-indigo-50/50 via-slate-50 to-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-8">
        <Link href="/" className="inline-flex items-center gap-2.5 group">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 group-hover:scale-105 transition-transform">
            <GraduationCap className="h-7 w-7" />
          </div>
          <div className="text-left">
            <span className="text-xl font-black tracking-tight text-slate-900 block">
              SMART LEARNING
            </span>
            <span className="text-xs font-semibold text-indigo-600 tracking-wider uppercase block">
              Pro EdTech Platform
            </span>
          </div>
        </Link>
        <h2 className="mt-6 text-2xl font-bold tracking-tight text-slate-900">
          Đăng nhập vào tài khoản
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Chưa có tài khoản?{" "}
          <Link
            href="/register"
            className="font-semibold text-indigo-600 hover:text-indigo-500 hover:underline"
          >
            Đăng ký tài khoản mới
          </Link>
        </p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <Card className="shadow-lg border-slate-200">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Thông tin đăng nhập</CardTitle>
            <CardDescription>
              Nhập email và mật khẩu được cấp hoặc chọn tài khoản mẫu bên dưới
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="mb-4 rounded-lg bg-rose-50 border border-rose-200 p-3 text-sm text-rose-700">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Địa chỉ Email"
                type="email"
                placeholder="ten@vi-du.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />

              <Input
                label="Mật khẩu"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />

              <Button
                type="submit"
                className="w-full mt-2"
                size="lg"
                isLoading={isLoading}
              >
                Đăng nhập
              </Button>
            </form>

            <div className="mt-6 border-t border-slate-200 pt-5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider text-center mb-3">
                Hoặc thử nghiệm nhanh với tài khoản mẫu
              </p>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() =>
                    handleQuickFill("student@smartlearning.vn", "Password123!")
                  }
                  className="flex flex-col items-center justify-center p-2.5 rounded-xl border border-indigo-100 bg-indigo-50/60 hover:bg-indigo-100/80 text-indigo-700 text-xs font-medium transition-colors"
                >
                  <BookOpen className="h-4 w-4 mb-1 text-indigo-600" />
                  <span>Học sinh</span>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    handleQuickFill("teacher@smartlearning.vn", "Password123!")
                  }
                  className="flex flex-col items-center justify-center p-2.5 rounded-xl border border-emerald-100 bg-emerald-50/60 hover:bg-emerald-100/80 text-emerald-700 text-xs font-medium transition-colors"
                >
                  <UserCheck className="h-4 w-4 mb-1 text-emerald-600" />
                  <span>Giáo viên</span>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    handleQuickFill("admin@smartlearning.vn", "Password123!")
                  }
                  className="flex flex-col items-center justify-center p-2.5 rounded-xl border border-amber-100 bg-amber-50/60 hover:bg-amber-100/80 text-amber-700 text-xs font-medium transition-colors"
                >
                  <ShieldCheck className="h-4 w-4 mb-1 text-amber-600" />
                  <span>Quản trị</span>
                </button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
