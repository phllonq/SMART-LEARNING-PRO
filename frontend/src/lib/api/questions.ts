import { apiClient } from "./client";
import { PaginatedResponse, Question } from "@/types";

export const questionsApi = {
  async getQuestions(params?: {
    grade_id?: number;
    subject_id?: string;
    difficulty_level?: string;
    question_type?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Question>> {
    return apiClient.get<PaginatedResponse<Question>>("/questions", { params });
  },

  async getQuestion(id: string): Promise<Question> {
    return apiClient.get<Question>(`/questions/${id}`);
  },
};
