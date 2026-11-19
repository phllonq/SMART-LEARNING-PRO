import { apiClient } from "./client";
import {
  ClassroomCreate,
  ClassroomDetail,
  ClassroomMember,
  ClassroomSummary,
} from "@/types";

export const classroomsApi = {
  async getClassrooms(isArchived?: boolean): Promise<ClassroomSummary[]> {
    return apiClient.get<ClassroomSummary[]>("/classrooms", {
      params: isArchived !== undefined ? { is_archived: isArchived } : undefined,
    });
  },

  async getClassroom(id: string): Promise<ClassroomDetail> {
    return apiClient.get<ClassroomDetail>(`/classrooms/${id}`);
  },

  async createClassroom(data: ClassroomCreate): Promise<ClassroomSummary> {
    return apiClient.post<ClassroomSummary>("/classrooms", data);
  },

  async joinClassroom(code: string): Promise<ClassroomSummary> {
    return apiClient.post<ClassroomSummary>("/classrooms/join", { code });
  },

  async leaveClassroom(id: string): Promise<void> {
    return apiClient.post<void>(`/classrooms/${id}/leave`);
  },

  async regenerateInviteCode(id: string): Promise<{ code: string }> {
    return apiClient.post<{ code: string }>(`/classrooms/${id}/regenerate-invite-code`);
  },

  async archiveClassroom(id: string): Promise<ClassroomSummary> {
    return apiClient.post<ClassroomSummary>(`/classrooms/${id}/archive`);
  },

  async getClassroomMembers(id: string): Promise<ClassroomMember[]> {
    return apiClient.get<ClassroomMember[]>(`/classrooms/${id}/members`);
  },

  async removeStudent(id: string, studentId: string): Promise<void> {
    return apiClient.delete<void>(`/classrooms/${id}/members/${studentId}`);
  },
};
