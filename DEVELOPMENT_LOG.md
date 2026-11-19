# DEVELOPMENT LOG — SMART LEARNING PRO

## Session 1: Environment Audit & Project Initialization (Phase 0 & 1)
- **Timestamp**: 2026-11-18 19:20:00 - 20:00:00
- **Action**:
  - Inspected root directory `E:\SMART-LEARNING-PRO`.
  - Audited existing system tools:
    - Python: 3.11.0 (Installed)
    - Node.js: v22.14.0, npm: 10.9.2, pnpm: 10.30.3 (Installed)
    - Docker: CLI 29.9.2 installed; Docker Desktop daemon not running.
    - PostgreSQL / Redis: Dual-mode architecture implemented (Async SQLite for native local dev; PostgreSQL + pgvector for Docker prod).
  - Created `.gitignore` and `.env.example`.
  - Initialized Phase 1 Architecture documents (`PRODUCT_SPECIFICATION.md`, `SITEMAP_AND_USER_FLOWS.md`, `SYSTEM_ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `API_SPECIFICATION.md`).

## Session 2: Recovery Audit & Core Backend Foundation (Phase 3)
- **Timestamp**: 2026-11-18 20:10:00 - 21:40:00
- **Action**:
  - Ran comprehensive Recovery Audit on `E:\SMART-LEARNING-PRO`.
  - Checked virtual environment `.venv`: verified `python.exe` and `pip.exe`.
  - Installed `greenlet>=3.0.0` for SQLAlchemy 2.0 asyncio support and `email-validator` for Pydantic v2 `EmailStr`.
  - Verified and executed baseline git commit: `3cac958`.
  - Inspected and verified 26 database models across 8 domain modules.
  - Verified table creation: All 26 tables successfully created in `database/smart_learning.db`.
  - Implemented Core Backend Foundation (`config.py`, `database.py`, `security.py`, `cache.py`, `exceptions.py`, `dependencies.py`, `main.py`).
  - Implemented and executed database seeder `scripts/seed_database.py`.
  - Built automated test suites (Auth, Health, RBAC) -> Git commit `a329d5c`.

## Session 3: Backend Verification & Curriculum Module (Phase 4)
- **Timestamp**: 2026-11-18 21:50:00 - 22:30:00
- **Action**:
  - Step A: Verified Git baseline (`3cac958`, `a329d5c`), verified 26 SQLite tables and foreign keys, verified seeded accounts and RBAC behavior.
  - Step B: Implemented Curriculum Module (`schemas.py`, `service.py`, `router.py`, registered in `main.py`).
  - Step C: Built `tests/test_curriculum.py` (8 test cases) -> 11/11 tests passing.
  - Step D: Updated documentation -> Git commit `f7e6945`.

## Session 4: Question Bank Module Implementation (Phase 4)
- **Timestamp**: 2026-11-18 22:38:00 - 23:05:00
- **Action**:
  - **Phase 1 Audit**: Inspected `Question` and `QuestionOption` models and SQLite schema. Added optional `lesson_id` and `tags` columns.
  - **Phase 2 & 3 Data Model & API**:
    - Created [backend/app/modules/questions/schemas.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/questions/schemas.py): Pydantic v2 schemas for question and options, including strict model validation (e.g. single choice exactly 1 correct, no duplicate keys). Separated `QuestionAdminResponse` and `QuestionStudentResponse` to enforce answer confidentiality.
    - Created [backend/app/modules/questions/service.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/questions/service.py): CRUD services with hierarchical curriculum joins (grade, subject, chapter, topic, lesson), keyword search, pagination, and teacher ownership boundary verification.
    - Created [backend/app/modules/questions/router.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/questions/router.py): REST endpoints under `/api/v1/questions` (`GET`, `POST`, `PATCH`, `DELETE`, `POST toggle-publish`).
    - Added `get_optional_current_user` in [backend/app/core/dependencies.py](file:///E:/SMART-LEARNING-PRO/backend/app/core/dependencies.py) to support role-adaptive responses.
    - Registered `questions_router` in [backend/app/main.py](file:///E:/SMART-LEARNING-PRO/backend/app/main.py).
  - **Phase 4 & 5 Security & Automated Tests**:
    - Built [backend/tests/test_questions.py](file:///E:/SMART-LEARNING-PRO/backend/tests/test_questions.py) with 6 comprehensive test suites:
      1. Pagination & multi-level filters & keyword search.
      2. Answer confidentiality: asserts `is_correct` is absent from student responses, present for teachers.
      3. Validation constraints: single choice 0/2 answers rejected, duplicate option keys rejected, student creation blocked (403).
      4. KaTeX mathematical formula rendering and persistence.
      5. Teacher ownership boundary: Teacher B blocked (403) from editing/deleting Teacher A's question; Admin override allowed (200, 204).
      6. Draft question hiding from students and toggle-publish functionality.
    - Executed complete backend test suite: **17/17 tests PASSED in 2.01s** (exit code 0).
  - **Phase 6 Documentation**: Updated `docs/DATABASE_SCHEMA.md`, `docs/API_SPECIFICATION.md`, `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`.

## Session 5: Online Examination Engine & Autosave Auto-Grading (Phase 4)
- **Timestamp**: 2026-11-18 23:20:00 - 2026-11-19 00:15:00
- **Action**:
  - **Phase 1 Recovery & Schema Evolution**:
    - Inspected `Exam`, `ExamQuestion`, `ExamAttempt`, `StudentAnswer`, and `ExamResult` models.
    - Applied non-destructive schema migrations to `database/smart_learning.db`: added `grade_id`, `start_time`, `end_time`, `status`, `updated_at` to `exams`; `deadline_at`, `maximum_score`, `questions_snapshot_json` to `exam_attempts`; `selected_option_ids_json`, `updated_at` to `student_answers`.
  - **Phase 2 & 3 Data Model & Engine Implementation**:
    - Created [backend/app/modules/exams/schemas.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/schemas.py): Pydantic v2 schemas for exam creation/update, student attempt start, autosave payload, automatic grading submission, and submission summaries.
    - Created [backend/app/modules/exams/service.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py):
      - Teacher exam management: draft/publish/archive, add/remove questions, enforce teacher ownership boundaries and admin override.
      - Student workflow: check eligibility & attempt limits (`max_attempts`), start attempt with immutable sanitized snapshot (`questions_snapshot_json`) hiding all answers and solutions.
      - Real-time autosave: upsert student answers on debounced background calls.
      - Server-side auto-grading engine: grade single choice, multiple choice, true/false, short answer; calculate points, total score, accuracy percentage, and persist `ExamResult`.
      - Submission review: allow review with full solutions only when `allow_review=true` after submission.
    - Created [backend/app/modules/exams/router.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/router.py): REST endpoints under `/api/v1/exams`.
    - Registered `exams_router` in [backend/app/main.py](file:///E:/SMART-LEARNING-PRO/backend/app/main.py).
  - **Phase 4 & 5 Security & Automated Tests**:
    - Created [backend/tests/test_exams.py](file:///E:/SMART-LEARNING-PRO/backend/tests/test_exams.py):
      - `test_teacher_exam_management_and_ownership`: Tests exam creation, blocking publication with 0 questions, adding questions, publishing, teacher ownership 403 boundary, and admin override.
      - `test_student_examination_flow_and_confidentiality`: Tests viewing available exams, starting attempt with answer confidentiality (sanitized snapshot), autosaving answers, submitting attempt, auto-grading calculation, accuracy percentage, and exam result review.
    - Resolved SQLAlchemy identity map in-memory relationship sync (`db.expire`, `populate_existing=True`) and keyword collision in `create_exam`.
    - Verified entire backend test suite: **19/19 tests PASSED in 2.91s** (exit code 0).
  - **Phase 6 Documentation**: Updated `docs/DATABASE_SCHEMA.md`, `docs/API_SPECIFICATION.md`, `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`.

## Session 6: Classroom & Homework Management (Phase 5)
- **Timestamp**: 2026-11-19 08:25:00 - 09:10:00
- **Action**:
  - **Phase 1 Preflight Audit & Database Migration**:
    - Inspected `Classroom`, `ClassroomMember`, `Assignment`, and `ExamAttempt` models and database schema.
    - Executed non-destructive migration script `scripts/migrate_phase5.py`:
      - `classrooms`: added `status` (ACTIVE/ARCHIVED), `is_archived`, `max_students` (default 50).
      - `classroom_members`: added `uq_classroom_member` unique constraint on `(classroom_id, student_id)`.
      - `assignments`: added `description`, `open_date`, `max_attempts`, `allow_late_submission`, `allow_review`, `status` (DRAFT/PUBLISHED/CANCELLED/CLOSED), `is_published`.
      - `exam_attempts`: added `assignment_id` foreign key and index `ix_exam_attempts_assignment_id`.
  - **Phase 2 & 3 Data Model, Service & API Implementation**:
    - Created [backend/app/modules/classrooms/schemas.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/classrooms/schemas.py): Pydantic v2 schemas for Classroom CRUD, invite code join, member rosters, classroom statistics, Assignment CRUD, and Gradebook submissions.
    - Created [backend/app/modules/classrooms/service.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/classrooms/service.py):
      - Classroom management: create with random unpredictable code (`SL-XXXXXX`), regenerate invite code, join with duplicate and capacity validation, member removal, leaving classroom, aggregate classroom statistics.
      - Homework assignment: link to published exams, configure open date/deadline/max attempts/late policy/review policy, publish/cancel, student start attempt with immutable sanitized snapshot, autosave, submission with auto-grading reuse, gradebook listing.
    - Created [backend/app/modules/classrooms/router.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/classrooms/router.py): REST endpoints under `/api/v1/classrooms` and `/api/v1/assignments`.
    - Registered routers in [backend/app/main.py](file:///E:/SMART-LEARNING-PRO/backend/app/main.py) and added central model registry import.
  - **Phase 4 & 5 Automated Testing**:
    - Created [backend/tests/test_classrooms.py](file:///E:/SMART-LEARNING-PRO/backend/tests/test_classrooms.py): 2 suites testing classroom creation, ownership boundary (403), Admin override, code regeneration, joining with code, duplicate prevention (409), capacity limit (403), member listing, leaving, and archive closure.
    - Created [backend/tests/test_assignments.py](file:///E:/SMART-LEARNING-PRO/backend/tests/test_assignments.py): 2 suites testing assignment lifecycle (DRAFT visibility), student start & answer confidentiality, autosaving, auto-grading submission, idempotency, attempt limit enforcement, and teacher gradebook.
    - Executed complete backend test suite: **23/23 tests PASSED in 5.46s** (exit code 0).
  - **Phase 6 Documentation**: Updated `docs/DATABASE_SCHEMA.md`, `docs/API_SPECIFICATION.md`, `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`.

## Session 7: Production Readiness & Concurrency Hardening Audit (Phase 5.1)
- **Timestamp**: 2026-11-19 09:30:00 - 10:15:00
- **Action**:
  - **Audit & Schema Hardening**:
    - Discovered SQLite connection defaulted to `PRAGMA foreign_keys=0`. Attached SQLAlchemy connection event listener `@event.listens_for(engine.sync_engine, "connect")` in `backend/app/core/database.py` executing `PRAGMA foreign_keys=ON`.
    - Created and executed idempotent migration `scripts/migrate_hardening.py`:
      - Added `answer_key_snapshot_json` column to `exam_attempts` for immutable server-side evaluation.
      - Added partial unique index `uq_active_exam_attempt` on `exam_attempts(student_id, exam_id) WHERE status = 'IN_PROGRESS' AND assignment_id IS NULL`.
      - Added partial unique index `uq_active_assignment_attempt` on `exam_attempts(student_id, assignment_id) WHERE status = 'IN_PROGRESS' AND assignment_id IS NOT NULL`.
  - **Concurrency & Logic Hardening**:
    - `start_exam_attempt`: Decoupled question evaluation by saving complete options and explanations into `answer_key_snapshot_json`. Handled concurrent start collision via `try ... except IntegrityError: db.rollback()` returning active attempt.
    - `submit_exam_attempt`: Grades against immutable `answer_key_snapshot_json` if present, preventing score mutation if questions in Question Bank are subsequently edited or deleted. Wrapped result flush in `try ... except IntegrityError: db.rollback()` for concurrent submit idempotency.
    - `autosave_answer`: Added out-of-order protection `if data.time_spent_seconds < answer.time_spent_seconds: return answer` discarding delayed network packets.
    - `join_classroom_by_code`: Added atomic post-flush capacity verification (`after_count > max_students -> delete new_member`) to prevent race condition when 2 students join a 1-seat classroom simultaneously.
    - `get_attempt_review`: Added `GET /api/v1/exams/attempts/{id}/review` with ownership verification, attempt completion check, and review policy enforcement.
    - `submit_assignment`: Allowed submission on cancelled assignments (`allow_cancelled=True`).
  - **Automated Testing & Evidence**:
    - Created `backend/tests/test_hardening_audit.py` with 8 comprehensive integration suites:
      1. Migration idempotency.
      2. Concurrent classroom join for same student (200 OK + 409 Conflict).
      3. Concurrent classroom join capacity limit (1 seat, 2 students -> 200 OK + 403 Forbidden).
      4. Concurrent exam attempt starts (resolves to single attempt without duplicates).
      5. Out-of-order autosave packet discarding.
      6. Question Bank edit decoupling & immutable snapshot grading.
      7. Submission review security & IDOR protection (403 for unauthorized students).
      8. Cancelled assignment submission safety.
    - Executed entire backend test suite: **31/31 tests PASSED in 8.22s** (exit code 0).
  - **Deliverables**: Created audit report `docs/PHASE_5_1_HARDENING_AUDIT.md`. Updated `DATABASE_SCHEMA.md`, `API_SPECIFICATION.md`, `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`.


## Session 8: Frontend Foundation Implementation (Phase 6)
- **Timestamp**: 2026-11-19 10:30:00 - 11:45:00
- **Action**:
  - **Preflight & Architecture Planning**:
    - Created `docs/PHASE_6_FRONTEND_PLAN.md` outlining project roadmap, routing architecture, and data contracts.
    - Verified Node.js v22.14.0, npm 10.9.2, and backend readiness.
  - **Frontend Scaffolding & Dependencies**:
    - Initialized Next.js 16.4.6 App Router project with TypeScript strict mode, Tailwind CSS v4, and ESLint in `frontend/`.
    - Installed core production dependencies: `@tanstack/react-query`, `lucide-react`, `clsx`, `tailwind-merge`, `react-hook-form`, `@hookform/resolvers`, `zod`, `katex`, `@types/katex`.
    - Configured `.env.example` and `.env.local` pointing to live backend `http://localhost:8000/api/v1`.
  - **Design System & Reusable Components**:
    - Configured custom theme variables and KaTeX styles in `frontend/src/app/globals.css`.
    - Created typed UI primitives under `frontend/src/components/ui/` (`Button`, `Card`, `Badge`, `Input`, `Dialog`, `Skeleton`).
    - Implemented shared domain components under `frontend/src/components/shared/`:
      - `MathKaTeX`: International KaTeX math formula parser supporting raw LaTeX, `$inline$`, and `$$display$$`.
      - `StatCard`: Visual KPI display cards.
      - `EmptyState`: Clean illustrated empty state views with actionable CTAs.
  - **API Client & Authentication Engine**:
    - Created `frontend/src/types/index.ts`: Strict TypeScript interfaces for Users, Classrooms, Assignments, Exams, Questions, and Curriculum.
    - Created `frontend/src/lib/api/client.ts`: Dual-mode client supporting both `Authorization: Bearer` and `credentials: "include"` for cookies, with structured error extraction.
    - Created domain API services: `auth.ts`, `classrooms.ts`, `assignments.ts`, `exams.ts`, `curriculum.ts`, `questions.ts`.
    - Created `frontend/src/lib/auth/auth-context.tsx`: React 19-safe authentication state machine with session recovery, role redirection, and logout.
    - Wrapped application in `Providers` (`QueryClientProvider` + `AuthProvider`) in `layout.tsx`.
  - **Portal Implementation**:
    - **Public Landing (`/`)**: Hero section, value propositions, and quick demo credentials.
    - **Authentication**: `/login` (with student, teacher, admin quick-fill pills) and `/register` (role-adaptive student/teacher signup).
    - **Student Portal (`/student/*`)**:
      - Dashboard: Gamification streak & XP cards, joined classrooms preview, available practice exams.
      - Classrooms: List joined classes, join by invite code modal (`SL-XXXXXX`), leave class action.
      - Assignments: Filter assignments, relative deadline status badges, duration, score.
      - Courses: Grade 6-12 GDPT 2018 subject explorer.
      - Exams: Exam lobby with duration, question count, and attempt launcher.
      - Profile: Student metrics, gamification level, join date, account details.
    - **Teacher Portal (`/teacher/*`)**:
      - Dashboard: Overview of owned classrooms, total students, exam & question bank metrics.
      - Classrooms: Owned classes list, "Create Classroom" modal (`POST /classrooms`).
      - Classroom Detail (`[id]`): Prominent invite code display with copy & regenerate code, student roster with removal, assignments tab with "Giao bài tập mới" modal.
      - Assignments: Cross-classroom homework overview, publish/cancel controls, and gradebook shortcuts.
      - Exams: Exam matrix bank, publish to practice controls, "Tạo đề thi mới" modal.
      - Questions: Question Bank explorer with KaTeX math rendering, difficulty filtering, search, and answer key highlights.
      - Students: Consolidated student roster across all classrooms.
      - Profile: Teacher certification and system details.
    - **Admin Portal (`/admin/*`)**: System telemetry, live backend health check monitor (`/health`), and fast portal switcher.
  - **Quality Gates & Verification**:
    - `npm run type-check` (`tsc --noEmit`): **0 errors, EXIT CODE 0**.
    - `npm run lint` (`eslint`): **0 errors, 0 warnings, EXIT CODE 0**.
    - `npm run build` (`next build`): **21/21 routes generated, EXIT CODE 0**.
    - Backend integration suite (`pytest -c backend/pytest.ini backend/tests`): **31/31 passed in 9.06s (100% PASS), EXIT CODE 0**.
  - **Documentation**:
    - Created `docs/FRONTEND_ARCHITECTURE.md` and `docs/FRONTEND_API_INTEGRATION.md`.
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`, `README.md`.


## Session 9: Frontend Functional Integration & RBAC Audit (Phase 6.1)
- **Timestamp**: 2026-11-19 12:00:00 - 12:35:00
- **Action**:
  - **Audit & Security Hardening**:
    - Audited token storage mechanism: Replaced persistent `localStorage` with `sessionStorage` in `frontend/src/lib/api/client.ts` to prevent token theft from XSS while maintaining full F5 page refresh capability and HttpOnly Cookie readiness.
    - Security audit on math rendering: Rewrote `frontend/src/components/shared/math-katex.tsx` using a strict regex delimiter tokenizer. Raw text chunks are escaped naturally via React DOM bindings, while math formulas are passed to `katex.renderToString(..., { throwOnError: false })`, completely eliminating DOM XSS injection vectors.
    - Aligned quick-fill authentication credentials with real seeded SQLite database records:
      - Student: `hocsinh.an@smartlearning.vn` / `StudentPassword123!`
      - Teacher: `giaovien.toan@smartlearning.vn` / `TeacherPassword123!`
      - Admin: `admin@smartlearning.vn` / `AdminSecurePassword123!`
    - Improved join classroom error handling in `frontend/src/app/student/classrooms/page.tsx` and `frontend/src/app/student/dashboard/page.tsx` to handle backend 404 responses gracefully with user-friendly Vietnamese notifications (`Mã mời không chính xác hoặc không tồn tại.`).
  - **Automated Real Browser E2E Test Suite**:
    - Installed `@playwright/test` and configured `frontend/playwright.config.ts` using system Google Chrome (`channel: 'chrome'`).
    - Created PowerShell test orchestrator `scripts/test_e2e.ps1` that manages simultaneous background processes for FastAPI (port 8000) and Next.js (port 3000), checks health endpoints, executes the test suite, and ensures clean termination of all child processes.
    - Created 18 end-to-end integration tests across 3 suites:
      - `frontend/e2e/auth-rbac.spec.ts`: Landing page, Student/Teacher/Admin login redirects, unauthenticated route protection, role guard isolation, and logout session clearance.
      - `frontend/e2e/student-workflow.spec.ts`: Live dashboard stats, enrolled classrooms, invalid invite code rejection, GDPT 2018 subject tree loading, exam lobby, and assignments list.
      - `frontend/e2e/teacher-workflow.spec.ts`: Live metrics, classrooms management, large invite code display & student roster, KaTeX math question bank with answer confidentiality, exams bank, and assignments overview.
    - Executed automated E2E test runner: **18/18 tests PASSED in 9.0s on Google Chrome (Exit Code 0)**.
  - **Quality Gates & Regression Verification**:
    - `cd frontend; npx tsc --noEmit`: **0 errors, EXIT CODE 0**.
    - `cd frontend; npm run lint`: **0 errors, 0 warnings, EXIT CODE 0**.
    - `cd frontend; npm run build`: **21/21 routes generated, EXIT CODE 0**.
    - Backend Pytest (`backend/tests`): **31/31 passed in 6.70s (100% PASS), EXIT CODE 0**.
  - **Documentation**:
    - Authored comprehensive audit report [docs/PHASE_6_1_FUNCTIONAL_AUDIT.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_1_FUNCTIONAL_AUDIT.md) with full API contract verification table, security findings, and execution evidence.
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, and `CHANGELOG.md`.

## Session 10: Critical Workflow & Security Verification (Phase 6.2)
- **Timestamp**: 2026-11-19 12:45:00 - 13:20:00
- **Action**:
  - **Stage A — Student Exam Lifecycle Verification**:
    - Created `frontend/e2e/exam-lifecycle.spec.ts` covering 11 critical test points:
      - Student opens published exams lobby (`PASS`).
      - Verified Phase 6 UI state: Interactive multi-question test-taking interface (`/student/exams/[id]`) is `NOT IMPLEMENTED` in Phase 6 frontend (clicking start alerts student to start attempt).
      - Live API validation of attempt creation, answer key confidentiality anti-leak defense (asserted 100% absence of `is_correct` in options and `explanation` in attempt snapshot), answer autosave persistence (`PUT /answers`), submit auto-grading calculation (`POST /submit`), idempotency (second submit returns existing graded result with HTTP 200), and review access authorization (`GET /review` returns 200 for owner, 403 for other students and 403 for in-progress attempts).
  - **Stage B — Teacher Mutations & Ownership Verification**:
    - Created `frontend/e2e/teacher-mutations.spec.ts` covering 10 mutation requirements:
      - Classroom creation in UI, listing, and navigation into detail view (`PASS`).
      - Exam creation in UI and publishing to practice lobby (`PASS`).
      - Adding questions via backend API (`PASS`); noted question matrix picker in UI is `NOT IMPLEMENTED`.
      - Assignment creation from exam in UI, cancellation with confirmation dialog in UI, and publishing draft assignment in UI (`PASS`).
      - Assignment gradebook API verification (`PASS`); noted detailed submissions table view in UI is `NOT IMPLEMENTED`.
      - Teacher Ownership Boundary Isolation: Verified that Teacher B receives HTTP 403 Forbidden attempting to access, regenerate code, modify exam, or archive Teacher A's resources (`PASS`).
  - **Stage C — Backend Authorization Matrix**:
    - Created `frontend/e2e/backend-authorization.spec.ts` testing 21 API endpoints across 4 distinct roles (Student, Teacher B, Admin, Unauthenticated). All 7 test suites passed with strict status assertions (200, 201, 204, 401, 403).
  - **Stage D — Authentication Architecture & XSS Code Review**:
    - Conducted code-backed security review answering 10 specific questions using direct code references (`client.ts`, `auth-context.tsx`, `auth/router.py`, `dependencies.py`, `math-katex.tsx`).
    - Explicitly clarified that `sessionStorage` mitigates persistent storage leakage across browser sessions but does NOT protect against in-session XSS exfiltration.
    - Classified risks: SEC-01 (Medium: Missing server-side token revocation blocklist), SEC-02 (Medium: Storage-based token transmission and lack of explicit anti-CSRF token headers), SEC-03 (Low: Passive expiration), SEC-04 (Low: KaTeX HTML rendering surface).
  - **Stage E — Regression Quality Gates**:
    - TypeScript strict check (`npx tsc --noEmit`): 0 errors (Exit code 0).
    - ESLint (`npm run lint`): 0 errors, 0 warnings (Exit code 0).
    - Next.js production build (`npm run build`): 21/21 routes generated (Exit code 0).
    - Pytest backend test suite (`pytest -c backend/pytest.ini backend/tests`): 31/31 passed in 5.92s (Exit code 0).
    - Playwright automated Chrome E2E suite (`scripts/test_e2e.ps1`): 34/34 passed in 13.4s across all 6 suites (Exit code 0).
  - **Stage F — Documentation & Deliverables**:
    - Authored comprehensive audit report [docs/PHASE_6_2_CRITICAL_VERIFICATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_2_CRITICAL_VERIFICATION.md).
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, and `CHANGELOG.md`.


## Session 11: Student Exam Interface Implementation (Phase 6.3)
- **Timestamp**: 2026-11-19 13:40:00 - 14:25:00
- **Action**:
  - **Types & Service API Extension**:
    - Extended `frontend/src/types/index.ts` with complete type definitions: `ExamAttemptQuestionOption`, `ExamAttemptQuestion`, `ExamStartResponse`, `SavedAnswerItem`, `AttemptDetailResponse`, `AutosaveAnswerRequest`, `AutosaveAnswerResponse`, `QuestionReviewItem`, and `ExamSubmitResponse`.
    - Extended `frontend/src/lib/api/exams.ts` with 5 strongly-typed methods: `startExam`, `getAttempt`, `autosaveAnswer`, `submitAttempt`, and `getAttemptReview`.
    - Extended `frontend/src/lib/api/assignments.ts` with typed `startAssignment`.
  - **Frontend UI Implementation**:
    - Created Exam Entry Page at `frontend/src/app/student/exams/[id]/page.tsx`: Displays exam overview (subject, grade, duration, question count, passing score, rules), error state handling, and start exam button triggering `POST /api/v1/exams/{id}/start` and navigating to `/student/exams/attempts/{attempt_id}`.
    - Updated Exam Lobby at `frontend/src/app/student/exams/page.tsx`: Converted "Bắt đầu làm bài" button into a direct Next.js link navigating to `/student/exams/${exam.id}`.
    - Created Active Examination Room & Review at `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`:
      - Sticky topbar with attempt number, progress indicator, countdown timer with color progression (< 5 min amber, < 1 min red pulse), save status indicator, and submit action.
      - Question matrix navigator supporting fast jumping with 4 distinct state badges (answered, unanswered, viewing, flagged).
      - Multi-question type support: single choice, multiple choice, true/false, and short answer.
      - Mathematical formula rendering via `MathKaTeX` for questions, options, and explanations.
      - Server-authoritative countdown timer with timezone normalization (`parseServerDate`) and auto-submission on expiration.
      - Debounced autosave mechanism with clear states (`SAVING`, `SAVED`, `ERROR`) and retry button.
      - Submit confirmation dialog with answer count summary and unanswered warnings.
      - Result and review screen displaying score, accuracy %, correct/wrong/skipped counts, pass/fail badge, feedback, and solution reviews.
      - Anti-IDOR security error view (HTTP 403) with red shield alert and back button.
    - Updated Assignment Take flow at `frontend/src/app/student/assignments/page.tsx` to launch directly into the exam attempt room.
  - **Automated Testing & E2E Verification**:
    - Implemented 16 comprehensive end-to-end scenarios in `frontend/e2e/exam-lifecycle.spec.ts`:
      1. Available exam entry from lobby.
      2. Attempt initialization and navigation into room.
      3. Option selection.
      4. Server-confirmed autosave.
      5. Forward question navigation.
      6. Backward navigation preserving selected state.
      7. Page reload (F5) state restoration.
      8. Countdown timer formatting and display.
      9. Submission confirmation modal.
      10. Server auto-grading result presentation.
      11. Idempotent submission verification.
      12. Anti-IDOR 403 Forbidden enforcement for another student's attempt.
      13. Review blocking on unsubmitted in-progress attempt.
      14. Answer confidentiality anti-leak verification during active exam.
      15. Network failure handling during autosave.
      16. Server authoritative duration constraint verification.
    - Executed automated E2E test runner (`scripts/test_e2e.ps1`): **36/36 tests PASSED in 15.3s on Google Chrome (Exit Code 0)**.
  - **Quality Gates & Regression Verification**:
    - TypeScript Strict Typecheck (`npx tsc --noEmit`): **0 errors (Exit code 0)**.
    - ESLint Check (`npm run lint`): **0 errors, 0 warnings (Exit code 0)**.
    - Next.js Production Build (`npm run build`): **23/23 routes generated (Exit code 0)**.
    - Backend Pytest Suite (`backend/tests`): **31/31 passed in 6.52s (Exit code 0)**.
  - **Documentation & Deliverables**:
    - Authored comprehensive report [docs/PHASE_6_3_STUDENT_EXAM_INTERFACE.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_STUDENT_EXAM_INTERFACE.md).
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, and `CHANGELOG.md`.

## Session 12: Post-Implementation Technical Audit (Phase 6.3.1)
- **Timestamp**: 2026-11-19 14:35:00 - 15:00:00
- **Action**:
  - Conducted an independent, read-only technical audit of Phase 6.3 implementation.
  - Inspected question type lifecycle for `SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `TRUE_FALSE`, and `SHORT_ANSWER`.
  - Identified 4 Critical / High-Risk defects:
    1. `SHORT_ANSWER` leaked accepted answer texts in active attempt payload.
    2. `student_answers` table lacked UniqueConstraint `(attempt_id, question_id)`.
    3. Autosave lacked text input debouncing and was vulnerable to out-of-order packet overwrite.
    4. Submitting and reviewing homework assignments bypassed assignment-level review and late submission policies.
  - Authored comprehensive audit report [docs/PHASE_6_3_1_POST_IMPLEMENTATION_AUDIT.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_1_POST_IMPLEMENTATION_AUDIT.md).

## Session 13: Exam Engine Hardening & Remediation (Phase 6.3.2)
- **Timestamp**: 2026-11-19 15:00:00 - 15:25:00
- **Action**:
  - **Database Migration (`scripts/migrate_phase632.py`)**:
    - Audited 81 existing rows in `student_answers` with zero duplicates.
    - Added `version INTEGER NOT NULL DEFAULT 1` to `student_answers`.
    - Created `UNIQUE INDEX IF NOT EXISTS uq_attempt_question_answer ON student_answers(attempt_id, question_id)`.
  - **Backend Hardening**:
    - `backend/app/modules/questions/schemas.py`: Enforced at least 1 correct option in `SHORT_ANSWER` creation.
    - `backend/app/modules/exams/models.py`: Added `version` column and `UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_answer")` to `StudentAnswer`.
    - `backend/app/modules/exams/schemas.py`: Extended schemas with `client_version`, `version`, `server_time`, `student_answer_text`, and `correct_answer_texts`.
    - `backend/app/modules/exams/service.py`:
      - `start_exam_attempt`: Stripped options for `SHORT_ANSWER` (`sanitized_opts = []`), preventing answer leakage while preserving grading keys in snapshot.
      - `autosave_answer`: Handled concurrent race conditions with `try ... db.flush() except IntegrityError: db.rollback()`, atomic version incrementing, and discarding stale requests with lower `client_version`.
      - `submit_exam_attempt` & `get_attempt_review`: Authoritative priority for assignment-level policies (`allow_review`, `allow_late_submission`).
    - `backend/app/modules/exams/router.py`: Server-side deadline check on `get_attempt` auto-submitting expired attempts; passed `version` in autosave response.
  - **Frontend Hardening**:
    - `frontend/src/types/index.ts`: Added `client_version`, `server_time`, `student_answer_text`, `correct_answer_texts`.
    - `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`:
      - Mitigated client clock skew using `serverTimeOffset = serverNowMs - Date.now()`.
      - Implemented 400ms debounce on `SHORT_ANSWER` text inputs via `handleTextChange`.
      - Sent `client_version` in autosave requests to reject stale out-of-order packets.
      - Displayed student answer text and acceptable correct answers in review for `SHORT_ANSWER`.
  - **Automated Testing & Full Quality Gates**:
    - Authored `backend/tests/test_hardening_632.py` covering:
      1. `test_short_answer_confidentiality_and_validation` (Confidentiality & 422 validation).
      2. `test_student_answers_unique_constraint_and_autosave_versions` (Versioning & race handling).
      3. `test_assignment_policy_enforcement` (Assignment policy priority 403 / 200).
      4. `test_all_four_question_types_e2e` (E2E grading of all 4 GDPT types with 10.0 score).
    - Pytest backend test suite: **35/35 PASSED in 11.92s (Exit code 0)**.
    - TypeScript compiler check: **0 errors (Exit code 0)**.
    - ESLint: **0 errors, 0 warnings (Exit code 0)**.
    - Next.js Production Build: **23/23 routes compiled (Exit code 0)**.
    - Playwright E2E Suite: **36/36 PASSED in 18.8s (Exit code 0)**.
  - **Documentation & Deliverables**:
    - Authored comprehensive report [docs/PHASE_6_3_2_HARDENING_REPORT.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_2_HARDENING_REPORT.md).
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, and `CHANGELOG.md`.

## Session 14: Independent Hardening Verification (Phase 6.3.3)
- **Timestamp**: 2026-11-19 16:30:00 - 17:15:00
- **Action**:
  - Conducted an independent, read-only technical audit of Phase 6.3.2 hardening implementation.
  - Inspected question type schemas, models, database migration, and frontend state synchronization.
  - Discovered critical autosave reload defect:
    - Frontend `versionCounters` reset to `{}` upon reload, causing subsequent autosaves to send `client_version=1`.
    - Server silently ignored updates as stale since DB had `version >= 2`, but returned `status="SAVED"`, producing silent answer loss and false success feedback.
  - Authored comprehensive audit report [docs/PHASE_6_3_3_INDEPENDENT_VERIFICATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_3_INDEPENDENT_VERIFICATION.md).

## Session 15: Autosave Versioning & Data Consistency Remediation (Phase 6.3.4)
- **Timestamp**: 2026-11-19 18:00:00 - 18:45:00
- **Action**:
  - **Database Backup**: Created snapshot `database/smart_learning.db.bak_phase634`.
  - **Backend OCC & Conditional Update**:
    - `backend/app/modules/exams/schemas.py`: Added `expected_version` to `AutosaveAnswerRequest`; added `selected_option_id`, `selected_option_ids`, `answer_text` to `AutosaveAnswerResponse`.
    - `backend/app/modules/exams/service.py`: Replaced Python memory version check with database-level atomic conditional update `update(StudentAnswer).where(StudentAnswer.id == answer.id, StudentAnswer.version == expected_version)`; differentiated statuses `SAVED`, `VERSION_CONFLICT`, `STALE_IGNORED`. Handled initial insert race condition with `try ... except IntegrityError: db.rollback()`.
    - `backend/app/modules/exams/router.py`: Returned explicit status from service without masquerading stale/conflicted writes as `SAVED`.
  - **Frontend State Recovery & Debounce Draining**:
    - `frontend/src/types/index.ts`: Updated `AutosaveAnswerRequest` and `AutosaveAnswerResponse` definitions.
    - `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`:
      - Synchronized `versionCounters.current` from `attempt.saved_answers[qid].version` on load and reload.
      - Implemented OCC request protocol passing `expected_version` and `client_version`.
      - Handled `VERSION_CONFLICT` / `CONFLICT` status with interactive retry badge, preserving local student input.
      - Tracked `pendingTextSaves.current` and flushed/drained all debounced text inputs prior to final submit.
  - **Automated Testing & Full Quality Gates**:
    - Authored `backend/tests/test_autosave_remediation_634.py` covering reload consistency, OCC conflict detection, stale request rejection, and short answer lifecycle (4/4 PASS in 1.44s).
    - Pytest backend test suite: **39/39 PASSED in 8.93s (Exit code 0)**.
    - TypeScript compiler check: **0 errors (Exit code 0)**.
    - ESLint: **0 errors, 0 warnings (Exit code 0)**.
    - Next.js Production Build: **23/23 routes compiled (Exit code 0)**.
    - Playwright E2E Suite: **36/36 PASSED in 16.0s (Exit code 0)**, including reload and answer re-selection scenario.
  - **Documentation & Deliverables**:
    - Authored comprehensive report [docs/PHASE_6_3_4_AUTOSAVE_REMEDIATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_4_AUTOSAVE_REMEDIATION.md).
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, and `CHANGELOG.md`.

## Session 16: Independent Concurrency & Submission Verification (Phase 6.3.5)
- **Timestamp**: 2026-11-19 18:45:00 - 18:52:00
- **Action**:
  - Conducted an independent, read-only technical audit of Phase 6.3.4 autosave remediation.
  - Inspected OCC database conditional updates, session rollback behavior, and frontend state synchronization.
  - Discovered critical submission integrity flaw at Gate E:
    - `handleFinalSubmit` executed `Promise.allSettled(flushPromises)` without checking results.
    - Floating in-flight autosave requests for choice questions were untracked and unawaited.
    - Submit was allowed while questions were in `SAVING`, `CONFLICT`, or `ERROR` states, exposing students to silent answer loss if submit completed before in-flight autosave reached backend.
  - Verdict: **FAIL** (as mandated by Gate E acceptance condition).
  - Authored comprehensive audit report [docs/PHASE_6_3_5_INDEPENDENT_VERIFICATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_5_INDEPENDENT_VERIFICATION.md).

## Session 17: Submission Barrier & Answer Persistence Guarantee (Phase 6.3.6)
- **Timestamp**: 2026-11-19 18:55:00 - 19:10:00
- **Action**:
  - **Frontend Centralized Autosave Tracking**:
    - Tracked in-flight autosave promises in `inFlightAutosavePromises.current` across all question types (`SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `TRUE_FALSE`, `SHORT_ANSWER`).
    - Handled promise resolution/cleanup in `executeAutosave().finally()`.
  - **6-Stage Submission Barrier (`handleFinalSubmit`)**:
    - Stage 1 Freeze: Locks UI (`isSubmitting = true`, disabling inputs, options, and anti-double-click).
    - Stage 2 Flush: Drains all debounced text inputs immediately.
    - Stage 3 Await: Waits for all active in-flight promises via `Promise.allSettled`.
    - Stage 4 Validate: Scans all answered questions; verifies 100% are confirmed `SAVED`; halts if any question is `SAVING`, `CONFLICT`, `ERROR`, or unpersisted.
    - Stage 5 Submit: Calls `examsApi.submitAttempt(attemptId)` only when 100% answers are validated.
    - Stage 6 Unlock: On validation failure or submit error, unlocks UI (`isSubmitting = false`), keeps local answers intact, and displays actionable error messages.
    - Dialog Barrier: Submit confirmation button disabled if `hasUnresolvedIssues` (`isAnyConflict || isAnyError || isAnySaving`).
  - **Backend Safety & Tests**:
    - Added `test_concurrent_first_insert_race_condition` to `backend/tests/test_autosave_remediation_634.py` using `asyncio.gather`.
    - Added `test_post_submit_autosave_rejected` verifying HTTP 403 on post-submit autosaves.
    - Updated Playwright E2E Scenario 15 proving submission barrier blocks submission on simulated network errors without calling submit API.
  - **Quality Gates Execution**:
    - Pytest backend test suite: **41/41 PASSED in 14.13s (Exit code 0)**.
    - TypeScript compiler check: **0 errors (Exit code 0)**.
    - ESLint: **0 errors, 0 warnings (Exit code 0)**.
    - Next.js Production Build: **23/23 routes compiled (Exit code 0)**.
    - Playwright E2E Suite: **36/36 PASSED in 18.8s (Exit code 0)**.
  - **Documentation & Deliverables**:
    - Authored comprehensive report [docs/PHASE_6_3_6_SUBMISSION_BARRIER.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_6_SUBMISSION_BARRIER.md).
    - Updated `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, and `CHANGELOG.md`.

## Session 18: Independent Verification (Phase 6.3.7)
- **Timestamp**: 2026-11-19 20:00:00 - 20:12:00
- **Action**:
  - Conducted strict read-only audit of commit `4819937`.
  - Confirmed Git HEAD and zero uncommitted modifications.
  - Audited Gates A through F in detail.
  - Identified P1-01 (Registry deletion race upon overlapping requests for the same question) and P1-02 (Backend transaction-level serialization gap on PostgreSQL).
  - Executed full test gates (41 Pytest, 36 Playwright E2E, Next.js build, ESLint, TypeScript).
  - Verdict: **CONDITIONAL PASS** (0 P0, 2 P1, 3 P2 test gaps).
  - Authored comprehensive report [docs/PHASE_6_3_7_INDEPENDENT_VERIFICATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_7_INDEPENDENT_VERIFICATION.md).

## Session 19: Targeted Concurrency Remediation (Phase 6.3.8)
- **Timestamp**: 2026-11-19 20:15:00 - 20:40:00
- **Action**:
  - **Task A (Frontend Promise Registry Race Remediation)**:
    - Replaced single-promise tracking with `Set<Promise<...>>` in `inFlightAutosavePromises.current`.
    - Added identity check `if (latestInFlightByQuestion.current[questionId] === currentPromise)` before per-question cleanup.
    - Updated Stage 3 barrier to drain via `while (inFlightAutosavePromises.current.size > 0)` awaiting all in-flight requests.
    - Added Playwright regression Scenario 17 reproducing overlapping requests where Request A finishes before Request B, proving submission waits for B.
  - **Task B (Backend Transaction Serialization & Row Locking)**:
    - Added `for_update: bool = False` to `get_attempt_detail`, applying `with_for_update()` on PostgreSQL while safely executing on SQLite.
    - Added conditional atomic touch in `autosave_answer`: `UPDATE exam_attempts SET time_spent_seconds = ... WHERE id = :id AND status = 'IN_PROGRESS'`.
    - Added immediate `await db.flush()` after updating `attempt.status = SUBMITTED` in `submit_exam_attempt`.
  - **Task C (Test Coverage Gaps Closed)**:
    - Playwright Scenario 17: Regression P1-01 overlapping autosave tracking (PASS).
    - Playwright Scenario 18: Delayed multiple-choice autosave during submit (PASS).
    - Playwright Scenario 19: SHORT_ANSWER submit inside debounce window (PASS).
    - Backend Pytest: Added `backend/tests/test_concurrency_remediation_638.py` (3 tests: Autosave first, Submit first, and `asyncio.gather` concurrent serialization) (PASS).
  - **Task D (Quality Gates Execution)**:
    - Backend Pytest: **44/44 PASSED in 14.32s (Exit code 0)**.
    - Frontend TypeScript: **0 errors (Exit code 0)**.
    - Frontend ESLint: **0 errors, 0 warnings (Exit code 0)**.
    - Next.js Production Build: **23/23 routes compiled (Exit code 0)**.
    - Playwright E2E Suite: **39/39 PASSED in 27.3s (Exit code 0)**.
  - **Task E (Documentation)**:
    - Authored [docs/PHASE_6_3_8_CONCURRENCY_REMEDIATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_8_CONCURRENCY_REMEDIATION.md).
