import { apiClient } from "./client";
import {
  AssignmentCreate,
  AssignmentSubmissionsResponse,
  AssignmentSummary,
  ExamStartResponse,
  FileSubmission,
} from "@/types";

export const assignmentsApi = {
  async getClassroomAssignments(classroomId: string): Promise<AssignmentSummary[]> {
    return apiClient.get<AssignmentSummary[]>(`/classrooms/${classroomId}/assignments`);
  },

  async createAssignment(
    classroomId: string,
    data: AssignmentCreate
  ): Promise<AssignmentSummary> {
    return apiClient.post<AssignmentSummary>(
      `/classrooms/${classroomId}/assignments`,
      data
    );
  },

  async createFileAssignment(
    classroomId: string,
    params: {
      file: File;
      title: string;
      description?: string;
      open_date?: string;
      due_date: string;
      allow_late_submission?: boolean;
      total_points?: number;
      status?: "DRAFT" | "PUBLISHED";
    }
  ): Promise<AssignmentSummary> {
    const formData = new FormData();
    formData.append("file", params.file);
    formData.append("title", params.title);
    if (params.description) formData.append("description", params.description);
    if (params.open_date) formData.append("open_date", params.open_date);
    formData.append("due_date", params.due_date);
    formData.append(
      "allow_late_submission",
      String(params.allow_late_submission ?? false)
    );
    formData.append("total_points", String(params.total_points ?? 10));
    formData.append("status", params.status ?? "PUBLISHED");
    return apiClient.postForm<AssignmentSummary>(
      `/classrooms/${classroomId}/assignments/upload`,
      formData
    );
  },

  async getAssignment(id: string): Promise<AssignmentSummary> {
    return apiClient.get<AssignmentSummary>(`/assignments/${id}`);
  },

  async publishAssignment(id: string): Promise<AssignmentSummary> {
    return apiClient.post<AssignmentSummary>(`/assignments/${id}/publish`);
  },

  async cancelAssignment(id: string): Promise<AssignmentSummary> {
    return apiClient.post<AssignmentSummary>(`/assignments/${id}/cancel`);
  },

  async getAssignmentSubmissions(
    id: string
  ): Promise<AssignmentSubmissionsResponse> {
    return apiClient.get<AssignmentSubmissionsResponse>(
      `/assignments/${id}/submissions`
    );
  },

  async startAssignment(id: string): Promise<ExamStartResponse> {
    return apiClient.post<ExamStartResponse>(`/assignments/${id}/start`);
  },

  async downloadAssignmentAttachment(
    assignmentId: string,
    filename?: string
  ): Promise<void> {
    return apiClient.downloadFile(
      `/assignments/${assignmentId}/attachment`,
      filename || "bai-tap"
    );
  },

  async submitFileAssignment(
    assignmentId: string,
    file: File,
    note?: string
  ): Promise<FileSubmission> {
    const formData = new FormData();
    formData.append("file", file);
    if (note) formData.append("note", note);
    return apiClient.postForm<FileSubmission>(
      `/assignments/${assignmentId}/file-submission`,
      formData
    );
  },

  async downloadFileSubmission(
    assignmentId: string,
    submissionId: string,
    filename?: string
  ): Promise<void> {
    return apiClient.downloadFile(
      `/assignments/${assignmentId}/file-submissions/${submissionId}/download`,
      filename || "bai-nop"
    );
  },

  async gradeFileSubmission(
    assignmentId: string,
    submissionId: string,
    data: { score: number; teacher_feedback?: string }
  ): Promise<FileSubmission> {
    return apiClient.post<FileSubmission>(
      `/assignments/${assignmentId}/file-submissions/${submissionId}/grade`,
      data
    );
  },
};
