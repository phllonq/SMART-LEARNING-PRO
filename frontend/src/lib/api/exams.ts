import { apiClient } from "./client";
import { ExamDetail, ExamSummary, PaginatedResponse } from "@/types";

export const examsApi = {
  async getAvailableExams(): Promise<ExamSummary[]> {
    return apiClient.get<ExamSummary[]>("/exams/available");
  },

  async getExams(params?: {
    subject_id?: string;
    grade_id?: number;
    status_filter?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<ExamSummary>> {
    return apiClient.get<PaginatedResponse<ExamSummary>>("/exams", { params });
  },

  async getExam(id: string): Promise<ExamDetail> {
    return apiClient.get<ExamDetail>(`/exams/${id}`);
  },

  async createExam(data: {
    title: string;
    description?: string;
    subject_id?: string;
    grade_id?: number;
    duration_minutes?: number;
    total_points?: number;
    passing_points?: number;
    question_ids?: string[];
  }): Promise<ExamSummary> {
    return apiClient.post<ExamSummary>("/exams", data);
  },

  async publishExam(id: string): Promise<ExamSummary> {
    return apiClient.post<ExamSummary>(`/exams/${id}/publish`);
  },
};
