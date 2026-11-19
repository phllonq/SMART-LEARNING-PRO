# TASK TRACKER — SMART LEARNING PRO

## Phase 0: Initialization & Environment
- [x] Check environment & workspace (`E:\SMART-LEARNING-PRO`)
- [x] Verify Git repository (Branch `master`, Initial commit `3cac958`)
- [x] Check runtimes: Python 3.11.0, Node.js v22.14.0, npm, pnpm
- [x] Setup `.gitignore` and `.env.example`
- [x] Setup virtual environment `.venv` with `greenlet` and all dependencies
- [x] Setup tracking documents

## Phase 1: Product & Architecture Design
- [x] Write Product Requirements Document (PRD) (`docs/PRODUCT_SPECIFICATION.md`)
- [x] Design Sitemap & User Flows (`docs/SITEMAP_AND_USER_FLOWS.md`)
- [x] Design Modular Monolith Architecture (`docs/SYSTEM_ARCHITECTURE.md`)
- [x] Design Complete Database Schema with 26 tables (`docs/DATABASE_SCHEMA.md`)
- [x] Define REST API endpoints & contracts (`docs/API_SPECIFICATION.md`)

## Phase 2 & 6: Frontend Foundation & Design System
- [x] Setup Next.js 16 App Router with TypeScript Strict Mode, Tailwind CSS v4, Lucide icons, KaTeX
- [x] Implement Design System tokens and custom colors in `globals.css`
- [x] Create atomic UI component library (`Button`, `Card`, `Input`, `Dialog/Modal`, `Badge`, `Skeleton`)
- [x] Create shared domain components (`MathKaTeX`, `StatCard`, `EmptyState`)
- [x] Build central API client with Bearer + Cookie authentication & error handling (`lib/api/client.ts`)
- [x] Build typed API services (`auth.ts`, `classrooms.ts`, `assignments.ts`, `exams.ts`, `curriculum.ts`, `questions.ts`)
- [x] Setup TanStack Query and React 19-safe AuthContext state machine
- [x] Build Public Landing Page (`/`) with role entry points and demo accounts
- [x] Build Authentication pages: `/login` (with quick-fill pills) and `/register` (role-adaptive)
- [x] Build Student Portal (`/student/*`): Dashboard, Classrooms with join modal, Assignments with due countdown, GDPT 2018 Courses, Exams lobby, Profile
- [x] Build Teacher Portal (`/teacher/*`): Dashboard, Classrooms CRUD with invite code generator, Classroom Detail view with member roster & assignments, Assignment manager & gradebook, Exam bank, Question bank with KaTeX math formula preview, Aggregate students list, Profile
- [x] Build Admin Portal (`/admin/*`): Telemetry dashboard, Backend health monitor, Fast portal switcher
- [x] Run Frontend Quality Gates: TypeScript check (0 errors), ESLint (0 errors, 0 warnings), Next.js Build (21/21 routes generated, EXIT CODE 0)

## Phase 3: Core Foundation (Backend & Auth)
- [x] Setup FastAPI Modular Monolith backend structure
- [x] Implement SQLAlchemy 2.0 async models (26 tables across 8 modules)
- [x] Implement Argon2id password hashing & verification
- [x] Implement JWT token creation & decoding (Access + Refresh)
- [x] Implement Auth dependencies (Header & HttpOnly cookie support)
- [x] Implement Granular RBAC (Roles: STUDENT, TEACHER, ADMIN, SUPERADMIN)
- [x] Build Auth APIs (`/register`, `/login`, `/me`, `/logout`)
- [x] Build Health check API (`/api/v1/health`)
- [x] Build Seeding Script (`scripts/seed_database.py`) with test accounts & Vietnamese curriculum
- [x] Write & pass automated tests (Pytest: `test_auth.py`, `test_health.py`, `test_rbac.py`)

## Phase 4: Learning Modules
- [x] Curriculum models & sample data seeded (Grades 10-12, Math/Physics/Chem, Chapters, Topics, Lessons, KaTeX)
- [x] Curriculum API Router (`/api/v1/curriculum/*` - Grades, Subjects, Chapters, Topics, Lessons, KaTeX, RBAC, Pagination)
- [x] Curriculum Automated Tests (8 test suites, 100% pass)
- [x] Question Bank models & sample KaTeX questions seeded
- [x] Question Bank API Router (`/api/v1/questions/*` - CRUD, search, filters, publish toggle, teacher ownership, answer confidentiality)
- [x] Question Bank Automated Tests (6 test suites, 100% pass)
- [x] Examination models & 45-minute sample exam seeded
- [x] Exam Taking & Autosave API Router (`/api/v1/exams/*` - Student start, autosave debounce, submit, review)
- [x] Automatic Grading Engine & Result computation (`ExamResult`, scoring, accuracy, passing check)
- [x] Teacher Exam Management & RBAC (`/api/v1/exams` - CRUD, add/remove questions, publish/archive, submissions review)
- [x] Examination Automated Tests (2 comprehensive test suites, 100% pass)

## Phase 5: Teacher & Admin Backend Modules
- [x] Classroom & Assignment models seeded & evolved with migration
- [x] Classroom API Router (`/api/v1/classrooms/*` - CRUD, invite code generation, join with capacity validation, member management, leaving, statistics)
- [x] Homework Assignment API Router (`/api/v1/assignments/*` - Create, publish, cancel, student take, submissions gradebook)
- [x] Classroom & Assignment Automated Tests (4 test suites, 100% pass)

## Phase 5.1: Concurrency & Hardening Audit
- [x] SQLite active foreign keys (`PRAGMA foreign_keys=ON`) via SQLAlchemy connection listener
- [x] Concurrency safety: atomic classroom join capacity limit & single-student uniqueness
- [x] Exam attempt isolation: immutable answer key snapshot (`answer_key_snapshot_json`) decoupled from Question Bank edits
- [x] Out-of-order network autosave packet protection
- [x] Idempotent migration verification & 31/31 backend tests passing

## Phase 7: AI Engine (Next Phase)
- [ ] Gemini API integration for automated question diagnosis
- [ ] Socratic AI Tutor interactive chat
- [ ] Spaced repetition and adaptive learning suggestions
