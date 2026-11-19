import type { Metadata } from "next";
import { Suspense } from "react";
import { Providers } from "@/lib/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "SMART LEARNING PRO — Nền tảng Học tập & Đánh giá Năng lực Thông minh",
  description:
    "Hệ sinh thái học tập và luyện thi thông minh dành cho học sinh THCS và THPT",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans bg-slate-50 text-slate-900">
        <Providers>
          <Suspense fallback={null}>
            {children}
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
