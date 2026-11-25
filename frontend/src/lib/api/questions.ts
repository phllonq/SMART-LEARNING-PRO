import { apiClient } from "./client";
import { PaginatedResponse, Question, QuestionImportResponse } from "@/types";

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

  async importQuestionsFile(params: {
    file: File;
    topic_id?: string;
    lesson_id?: string;
    is_public?: boolean;
    dry_run?: boolean;
  }): Promise<QuestionImportResponse> {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.topic_id) formData.append("topic_id", params.topic_id);
    if (params.lesson_id) formData.append("lesson_id", params.lesson_id);
    formData.append("is_public", String(params.is_public ?? true));
    formData.append("dry_run", String(params.dry_run ?? false));
    return apiClient.postForm<QuestionImportResponse>("/questions/import", formData);
  },

  async downloadCsvTemplate(): Promise<void> {
    return apiClient.downloadFile(
      "/questions/import-template/csv",
      "smart_learning_question_template.csv"
    );
  },
};
