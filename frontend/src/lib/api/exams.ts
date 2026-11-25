import { apiClient } from "./client";
import {
  ExamDetail,
  ExamImportResponse,
  ExamConvertPreviewResponse,
  ExamConvertConfirmRequest,
  ExamConvertConfirmResponse,
  ExamSummary,
  PaginatedResponse,
  ExamStartResponse,
  AttemptDetailResponse,
  AutosaveAnswerRequest,
  AutosaveAnswerResponse,
  ExamSubmitResponse,
} from "@/types";

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

  async importExamFromFile(params: {
    file: File;
    title: string;
    description?: string;
    grade_id?: number;
    subject_id?: string;
    duration_minutes?: number;
    total_points?: number;
    passing_points?: number;
    publish_immediately?: boolean;
  }): Promise<ExamImportResponse> {
    const formData = new FormData();
    formData.append("file", params.file);
    formData.append("title", params.title);
    if (params.description) formData.append("description", params.description);
    if (params.grade_id !== undefined) formData.append("grade_id", String(params.grade_id));
    if (params.subject_id) formData.append("subject_id", params.subject_id);
    formData.append("duration_minutes", String(params.duration_minutes ?? 45));
    formData.append("total_points", String(params.total_points ?? 10));
    formData.append("passing_points", String(params.passing_points ?? 5));
    formData.append("publish_immediately", String(params.publish_immediately ?? false));
    return apiClient.postForm<ExamImportResponse>("/exams/import", formData);
  },

  async previewConvertExamFile(
    file: File,
    useAi: boolean = true
  ): Promise<ExamConvertPreviewResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("use_ai", String(useAi));
    return apiClient.postForm<ExamConvertPreviewResponse>(
      "/exams/convert-preview",
      formData
    );
  },

  async confirmConvertExamToQuiz(
    data: ExamConvertConfirmRequest
  ): Promise<ExamConvertConfirmResponse> {
    return apiClient.post<ExamConvertConfirmResponse>(
      "/exams/convert-confirm",
      data
    );
  },

  async publishExam(id: string): Promise<ExamSummary> {
    return apiClient.post<ExamSummary>(`/exams/${id}/publish`);
  },

  async startExam(examId: string): Promise<ExamStartResponse> {
    return apiClient.post<ExamStartResponse>(`/exams/${examId}/start`);
  },

  async getAttempt(attemptId: string): Promise<AttemptDetailResponse> {
    return apiClient.get<AttemptDetailResponse>(`/exams/attempts/${attemptId}`);
  },

  async autosaveAnswer(
    attemptId: string,
    questionId: string,
    data: AutosaveAnswerRequest
  ): Promise<AutosaveAnswerResponse> {
    return apiClient.put<AutosaveAnswerResponse>(
      `/exams/attempts/${attemptId}/answers/${questionId}`,
      data
    );
  },

  async submitAttempt(attemptId: string): Promise<ExamSubmitResponse> {
    return apiClient.post<ExamSubmitResponse>(
      `/exams/attempts/${attemptId}/submit`
    );
  },

  async getAttemptReview(attemptId: string): Promise<ExamSubmitResponse> {
    return apiClient.get<ExamSubmitResponse>(
      `/exams/attempts/${attemptId}/review`
    );
  },
};
