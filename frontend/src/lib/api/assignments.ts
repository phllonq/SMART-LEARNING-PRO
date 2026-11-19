import { apiClient } from "./client";
import {
  AssignmentCreate,
  AssignmentSubmissionsResponse,
  AssignmentSummary,
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

  async startAssignment(id: string): Promise<unknown> {
    return apiClient.post(`/assignments/${id}/start`);
  },
};
