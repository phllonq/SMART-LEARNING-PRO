# SYSTEM ARCHITECTURE — SMART LEARNING PRO
## Modular Monolith Architecture & Engineering Specifications

---

## 1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG (SYSTEM OVERVIEW)

SMART LEARNING PRO áp dụng mô hình **Modular Monolith**. Kiến trúc này cân bằng hoàn hảo giữa tính tốc độ phát triển, khả năng bảo trì cao, triển khai đơn giản, đồng thời giữ ranh giới module (bounded contexts) rõ ràng để sẵn sàng tách microservices trong tương lai nếu lưu lượng người dùng tăng vọt.

```mermaid
graph TD
    subgraph Client Layer
        WebClient["Next.js 14/15 Frontend (App Router, Tailwind, KaTeX, Lucide)"]
    end

    subgraph Reverse Proxy & Gateway
        Nginx["Nginx / Gateway (SSL Termination, Rate Limiting, Static Caching)"]
    end

    subgraph Application Layer - FastAPI Modular Monolith
        Core["Core Module (Config, Security, DB Session, Base Models, Exceptions)"]
        AuthMod["Auth & RBAC Module (Argon2, JWT Cookie, Permission Guards)"]
        CurriculumMod["Curriculum Module (Grades, Subjects, Chapters, Topics, Lessons)"]
        QuestionMod["Question Bank & Exam Module (Questions, Exams, Submissions, Auto-Grading)"]
        ClassroomMod["Classroom & Assignment Module (Classes, Homework, Gradebook)"]
        AIEngine["AI Engine (Gemini 1.5, Prompt Orchestrator, RAG, Structured JSON)"]
        AnalyticsMod["Learning Analytics & Mastery (Gap Detection, Spaced Repetition)"]
        GamifyMod["Gamification & Notifications (Streak, XP, Badges, Inbox)"]
    end

    subgraph Data & Storage Layer
        Postgres[("PostgreSQL 16 + pgvector (Production DB)")]
        SQLite[("SQLite + aiosqlite (Zero-Config Dev DB)")]
        RedisCache[("Redis 7 (Sessions, Cache, Rate Limits)")]
        InMemCache[("In-Memory Cache Fallback (Dev Mode)")]
        Storage[("MinIO / Local File Storage (PDFs, Avatars, Media)")]
    end

    WebClient -->|HTTPS / REST API| Nginx
    Nginx --> Core
    Core --> AuthMod
    Core --> CurriculumMod
    Core --> QuestionMod
    Core --> ClassroomMod
    Core --> AIEngine
    Core --> AnalyticsMod
    Core --> GamifyMod

    AuthMod & CurriculumMod & QuestionMod & ClassroomMod & AnalyticsMod & GamifyMod --> Postgres
    AuthMod & CurriculumMod & QuestionMod & ClassroomMod & AnalyticsMod & GamifyMod -.-> SQLite
    AIEngine --> RedisCache
    AIEngine -.-> InMemCache
    AIEngine -->|RAG Embeddings| Postgres
    CurriculumMod --> Storage
```

---

## 2. THIẾT KẾ BACKEND (FASTAPI MODULAR MONOLITH)

Mỗi module độc lập gồm các thành phần chuẩn:
- `models.py`: Định nghĩa SQLAlchemy 2.0 ORM models.
- `schemas.py`: Định nghĩa Pydantic v2 validation schemas cho request/response.
- `service.py`: Chứa business logic thuần túy, không phụ thuộc vào framework HTTP.
- `router.py`: FastAPI APIRouter định nghĩa REST endpoints, dependency injection.

### Cấu trúc thư mục Backend:
```
backend/
├── app/
│   ├── main.py                     # Entry point, CORS, Middlewares, Exception Handlers
│   ├── config.py                   # Pydantic BaseSettings, load .env
│   ├── core/
│   │   ├── database.py             # SQLAlchemy Async Engine, SessionFactory
│   │   ├── security.py             # Argon2 hashing, JWT encode/decode
│   │   ├── dependencies.py         # Get DB session, get current user, RBAC role guard
│   │   ├── exceptions.py           # Custom Domain Exceptions & Error Handlers
│   │   └── cache.py                # Redis client with In-Memory fallback
│   ├── modules/
│   │   ├── auth/                   # Login, Register, Refresh, Me, RBAC
│   │   ├── curriculum/             # Grades, Subjects, Chapters, Topics, Lessons
│   │   ├── questions/              # Question Bank, Choices, Explanations, KaTeX
│   │   ├── exams/                  # Exam builder, Attempts, Autosave, Grading engine
│   │   ├── classrooms/             # Classes, Memberships, Assignments, Submissions
│   │   ├── ai_tutor/               # Gemini API client, Wrong Answer Diagnosis, RAG
│   │   ├── analytics/              # Mastery tracking, Knowledge gaps, Recommender
│   │   └── gamification/           # Daily quests, Streaks, XP, Achievements, Notifications
│   └── tests/                      # Pytest unit & integration tests
├── requirements.txt                # Production dependencies
└── Dockerfile                      # Production container image
```

---

## 3. THIẾT KẾ FRONTEND (NEXT.JS APP ROUTER)

Frontend áp dụng kiến trúc module dựa trên App Router của Next.js:
- **Design System Tokens**: Màu sắc thương hiệu (Primary `#635BFF`, Dark `#0F172A`, Light Bg `#F8FAFC`, Success `#10B981`, Warning `#F59E0B`, Error `#EF4444`).
- **Typography**: Phông chữ chuẩn Tiếng Việt: `Inter` hoặc `Be Vietnam Pro`.
- **Thư viện Toán học**: KaTeX rendering mượt mà các biểu thức phức tạp dạng inline `$f(x) = \int_0^1 x^2 dx$` và display block `$$...$$`.
- **Quản lý trạng thái (State Management)**: React Context + SWR/TanStack Query cho data fetching và caching.

### Cấu trúc thư mục Frontend:
```
frontend/
├── src/
│   ├── app/                        # Next.js App Router
│   │   ├── (public)/               # Landing, About, Features, Subjects, Login, Register
│   │   ├── student/                # Dashboard, Courses, Practice, Exams, AI Tutor, Analytics
│   │   ├── teacher/                # Dashboard, Classrooms, Question Bank, Exams, Grading
│   │   ├── admin/                  # Users, Curriculum, AI Monitoring, System Logs
│   │   ├── layout.tsx              # Root Layout with Font & Theme Providers
│   │   └── globals.css             # Tailwind base & Custom utility classes
│   ├── components/
│   │   ├── ui/                     # Button, Input, Modal, Dropdown, Table, Card, Badge...
│   │   ├── math/                   # KaTeX MathRenderer component
│   │   ├── layout/                 # Navbar, Sidebar, Footer, PageHeader
│   │   ├── exam/                   # QuestionPalette, ExamTimer, QuestionViewer
│   │   └── ai/                     # AITutorChat, WrongAnswerCard, DiagnosticBadge
│   ├── lib/
│   │   ├── api.ts                  # Axios / Fetch HTTP client with JWT interceptor
│   │   ├── auth-context.tsx        # Authentication & Role context
│   │   └── utils.ts                # Formatting, date helpers, cn utility
│   └── types/                      # TypeScript shared interfaces
├── tailwind.config.ts              # Tailwind CSS configuration
├── package.json                    # Dependencies & Scripts
└── tsconfig.json                   # TypeScript config
```

---

## 4. CHIẾN LƯỢC CƠ SỞ DỮ LIỆU & STORAGE DUAL-ENGINE

Để đảm bảo dự án chạy được ngay lập tức trên máy phát triển mà không bị phụ thuộc cứng vào việc Docker Desktop có đang khởi chạy hay không:
1. **Chế độ Dev Nhanh (Local Zero-Config)**:
   - Sử dụng `sqlite+aiosqlite:///./database/smart_learning.db`.
   - Lưu trữ file cục bộ trong thư mục `./storage/`.
   - Bộ đệm Cache in-memory tích hợp sẵn trong Python.
2. **Chế độ Môi trường Sản phẩm / Docker (Production)**:
   - Sử dụng `postgresql+asyncpg://postgres:postgres@localhost:5432/smart_learning_pro`.
   - Kích hoạt extension `pgvector` cho vector search tài liệu RAG.
   - Redis cluster/container cho session caching & rate limiting.
   - MinIO / AWS S3 cho lưu trữ tài liệu PDF và media dung lượng lớn.

Tất cả các model ORM được viết bằng **SQLAlchemy 2.0 cú pháp chuẩn**, hoàn toàn tương thích và di chuyển mượt mà giữa SQLite và PostgreSQL chỉ bằng 1 dòng cấu hình `DATABASE_URL` trong file `.env`.

---

## 5. THIẾT KẾ AI ENGINE (GOOGLE GEMINI INTEGRATION)

### 5.1. Mô hình và Cấu hình
- Sử dụng mô hình `gemini-1.5-flash` cho các tác vụ thời gian thực (giải thích bài, gợi ý gợi mở, phản hồi nhanh < 1.5s).
- Sử dụng mô hình `gemini-1.5-pro` cho các tác vụ phân tích đề thi nâng cao, chấm bài tự luận học sinh, và sinh đề thi tổng hợp.

### 5.2. Luồng Phân Tích Lỗi Sai (Wrong Answer Diagnostics Pipeline)
1. **Input Payload**:
   - Câu hỏi, phương án lựa chọn, đáp án học sinh chọn, đáp án đúng, lời giải mẫu.
   - Môn học, khối lớp, chủ đề, độ khó.
2. **System Prompt & Khung Sư Phạm Socratic**:
   - Thiết lập vai trò: Chuyên gia sư phạm chuẩn mực của Bộ Giáo dục & Đào tạo Việt Nam.
   - Nguyên tắc: Tuyệt đối không thay đổi đáp án đúng, không bịa thông tin khoa học, tôn trọng tư duy học sinh, khích lệ tự tin.
3. **Structured Outputs (Pydantic Schema)**:
   - Ép kiểu JSON nghiêm ngặt để frontend luôn render được giao diện đẹp mà không sợ output AI bị lỗi định dạng văn bản:
   ```json
   {
     "error_category": "MISAPPLIED_FORMULA",
     "misconception_explanation": "Em đã áp dụng nhầm công thức...",
     "step_by_step_solution": [
       "Bước 1: Xác định điều kiện xác định...",
       "Bước 2: Biến đổi phương trình..."
     ],
     "key_takeaway": "Ghi nhớ: Khi chia hai vế cho biểu thức chứa ẩn, phải xét trường hợp bằng 0.",
     "remedial_question": {
       "content": "Tìm tập nghiệm của phương trình...",
       "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
       "correct_option": "A",
       "explanation": "..."
     }
   }
   ```
4. **Kiểm Soát Chi Phí & Dự Phòng (Cost Control & Fallback)**:
   - Ghi nhận `ai_usage_logs` (user_id, prompt_tokens, candidate_tokens, model, cost_estimate, timestamp).
   - Rate limiting cho mỗi tài khoản học sinh (ví dụ: tối đa 50 lượt hỏi AI / ngày).
   - Dự phòng khi API Gemini mất mạng: Trả về lời giải chi tiết tĩnh trong ngân hàng câu hỏi kèm thông báo thân thiện.

---

## 6. MÔ HÌNH BẢO MẬT & PHÂN QUYỀN (SECURITY & RBAC)

1. **Mật khẩu**: Mã hóa một chiều bằng giải thuật **Argon2id** (giải thuật chiến thắng Password Hashing Competition, an toàn chống tấn công GPU/ASIC).
2. **Phiên đăng nhập**:
   - Sử dụng chuẩn JWT (JSON Web Token) ký bằng thuật toán HS256/RS256 với Secret Key tối thiểu 32 ký tự.
   - Token được lưu trữ trong **HttpOnly, Secure, SameSite=Lax Cookie** nhằm ngăn chặn 100% các cuộc tấn công đánh cắp token qua XSS.
   - Đồng thời hỗ trợ Header `Authorization: Bearer <token>` để tương thích với mobile app và automated testing.
3. **Phân quyền RBAC (Role-Based Access Control)**:
   - Hệ thống định nghĩa 4 vai trò chính:
     - `STUDENT`: Học bài, thi trắc nghiệm, hỏi AI, xem phân tích cá nhân.
     - `TEACHER`: Quản lý lớp học, ngân hàng câu hỏi, tạo bài thi, xem báo cáo lớp.
     - `ADMIN`: Quản trị hệ thống, duyệt khóa học, phân quyền, cấu hình AI.
     - `SUPERADMIN`: Toàn quyền hệ thống, audit log, cấu hình bảo mật.
4. **Cơ chế phòng thủ**:
   - Rate limiting theo IP và User ID chống brute-force đăng nhập.
   - Pydantic v2 Input Validation chặn SQL Injection và XSS.
   - CORS cấu hình chặt chẽ chỉ cho phép domain Frontend được chỉ định.
