import { apiClient } from "./client";
import { Grade, PaginatedResponse, Subject } from "@/types";

export const curriculumApi = {
  async getGrades(): Promise<Grade[]> {
    return apiClient.get<Grade[]>("/curriculum/grades");
  },

  async getSubjects(params?: {
    grade_id?: number;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Subject>> {
    return apiClient.get<PaginatedResponse<Subject>>("/curriculum/subjects", {
      params,
    });
  },

  async getSubject(id: string): Promise<Subject> {
    return apiClient.get<Subject>(`/curriculum/subjects/${id}`);
  },
};
