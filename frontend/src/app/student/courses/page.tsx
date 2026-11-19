"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { curriculumApi } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-context";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import {
  BookOpen,
  ArrowRight,
  Layers,
} from "lucide-react";

export default function StudentCoursesPage() {
  const { user } = useAuth();
  const [selectedGrade, setSelectedGrade] = useState<number>(
    user?.grade_level || 10
  );

  const { data: subjectsData, isLoading } = useQuery({
    queryKey: ["curriculum-subjects", selectedGrade],
    queryFn: () => curriculumApi.getSubjects({ grade_id: selectedGrade, page_size: 50 }),
  });

  const subjects = subjectsData?.items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Chương trình GDPT 2018
        </h2>
        <p className="text-sm text-slate-500">
          Khám phá cây kiến thức chuẩn theo từng khối lớp và môn học
        </p>
      </div>

      {/* Grade Selector Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {[6, 7, 8, 9, 10, 11, 12].map((g) => (
          <button
            key={g}
            onClick={() => setSelectedGrade(g)}
            className={`px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
              selectedGrade === g
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            Khối Lớp {g}
          </button>
        ))}
      </div>

      {/* Subject Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Skeleton className="h-44 rounded-xl" />
          <Skeleton className="h-44 rounded-xl" />
          <Skeleton className="h-44 rounded-xl" />
        </div>
      ) : subjects.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title={`Chưa có dữ liệu môn học cho Lớp ${selectedGrade}`}
          description="Hiện tại khối lớp này đang được ban chuyên môn cập nhật ngân hàng kiến thức."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {subjects.map((sub) => (
            <Card
              key={sub.id}
              className="flex flex-col justify-between hover:border-indigo-300 transition-all shadow-xs group"
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                    {sub.code}
                  </span>
                  <Badge variant="success">GDPT 2018</Badge>
                </div>
                <CardTitle className="text-lg text-slate-900 group-hover:text-indigo-600 transition-colors">
                  {sub.name}
                </CardTitle>
                <CardDescription className="text-xs">
                  Chương trình trọng tâm Lớp {selectedGrade}
                </CardDescription>
              </CardHeader>

              <CardContent className="pt-0 space-y-4">
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs text-slate-600 space-y-1.5">
                  <div className="flex items-center gap-1.5 font-medium text-slate-700">
                    <Layers className="h-3.5 w-3.5 text-indigo-500" />
                    <span>Hệ thống chủ đề kiến thức</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Bao gồm lý thuyết trọng tâm, ví dụ mẫu KaTeX và bài tập rèn luyện tương ứng.
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <span className="text-xs text-slate-500">Tự luyện thông minh</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1 text-xs text-indigo-600 hover:text-indigo-700"
                    onClick={() =>
                      alert(`Đang mở lộ trình kiến thức môn ${sub.name} Lớp ${selectedGrade}`)
                    }
                  >
                    <span>Xem bài học</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
