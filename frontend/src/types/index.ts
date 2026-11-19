export type UserRole = "STUDENT" | "TEACHER" | "ADMIN" | "SUPERADMIN";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  avatar_url?: string | null;
  grade_level?: number | null;
  xp_points: number;
  current_level: number;
  streak_days: number;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
  grade_level?: number | null;
}

export interface ClassroomSummary {
  id: string;
  name: string;
  code: string;
  grade_id?: number | null;
  teacher_id: string;
  teacher_name?: string | null;
  description?: string | null;
  status: string;
  is_archived: boolean;
  max_students: number;
  member_count: number;
  assignment_count: number;
  created_at: string;
  updated_at: string;
}

export interface ClassroomMember {
  id: string;
  student_id: string;
  student_name: string;
  student_email: string;
  student_avatar?: string | null;
  joined_at: string;
}

export interface ClassroomDetail extends ClassroomSummary {
  members: ClassroomMember[];
}

export interface ClassroomCreate {
  name: string;
  grade_id?: number | null;
  description?: string | null;
  max_students?: number;
}

export interface AssignmentSummary {
  id: string;
  classroom_id: string;
  classroom_name?: string | null;
  exam_id: string;
  exam_title?: string | null;
  title: string;
  description?: string | null;
  open_date?: string | null;
  due_date: string;
  max_attempts: number;
  allow_late_submission: boolean;
  allow_review: boolean;
  status: string;
  is_published: boolean;
  total_points: number;
  duration_minutes: number;
  question_count: number;
  my_status?: "NOT_STARTED" | "IN_PROGRESS" | "SUBMITTED" | "GRADED" | null;
  my_score?: number | null;
  my_attempts_count: number;
  created_at: string;
  updated_at: string;
}

export interface AssignmentCreate {
  exam_id: string;
  title: string;
  description?: string | null;
  open_date?: string | null;
  due_date: string;
  max_attempts?: number;
  allow_late_submission?: boolean;
  allow_review?: boolean;
  status?: "DRAFT" | "PUBLISHED";
}

export interface AssignmentSubmissionItem {
  student_id: string;
  student_name: string;
  student_email: string;
  status: string;
  attempt_id?: string | null;
  attempt_number: number;
  score?: number | null;
  maximum_score: number;
  is_passed: boolean;
  started_at?: string | null;
  submitted_at?: string | null;
  time_spent_seconds: number;
}

export interface AssignmentSubmissionsResponse {
  assignment_id: string;
  assignment_title: string;
  due_date: string;
  total_students: number;
  submitted_count: number;
  in_progress_count: number;
  not_started_count: number;
  average_score: number;
  items: AssignmentSubmissionItem[];
}

export interface ExamSummary {
  id: string;
  title: string;
  description?: string | null;
  subject_id?: string | null;
  grade_id?: number | null;
  creator_id?: string | null;
  duration_minutes: number;
  total_points: number;
  passing_points: number;
  max_attempts: number;
  status: string;
  is_published: boolean;
  start_time?: string | null;
  end_time?: string | null;
  question_count: number;
  created_at: string;
}

export interface ExamDetail extends ExamSummary {
  questions: Array<{
    id: string;
    question_id: string;
    points: number;
    order_index: number;
    content: string;
    question_type: string;
    difficulty_level: string;
    options_count: number;
  }>;
}

export type QuestionType =
  | "SINGLE_CHOICE"
  | "MULTIPLE_CHOICE"
  | "TRUE_FALSE"
  | "SHORT_ANSWER"
  | "ESSAY";

export type DifficultyLevel =
  | "RECOGNITION"
  | "COMPREHENSION"
  | "APPLICATION"
  | "HIGH_APPLICATION";

export interface QuestionOption {
  id: string;
  question_id: string;
  option_key: string;
  content: string;
  order_index: number;
  is_correct?: boolean;
}

export interface Question {
  id: string;
  topic_id?: string | null;
  lesson_id?: string | null;
  question_type: QuestionType;
  content: string;
  difficulty_level: DifficultyLevel;
  explanation?: string | null;
  hint?: string | null;
  tags?: string | null;
  is_public?: boolean;
  options: QuestionOption[];
  creator_id?: string | null;
  creator_name?: string | null;
  topic_title?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface Grade {
  id: number;
  name: string;
  description?: string | null;
  order_index: number;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  grade_id: number;
  icon?: string | null;
  color?: string | null;
  is_published: boolean;
  order_index?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string | Array<{ msg: string; loc: string[] }>;
}
