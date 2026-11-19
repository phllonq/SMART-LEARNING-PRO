# SMART LEARNING PRO

> **An Intelligent, Next-Generation EdTech Platform for Vietnamese Middle and High School Students (THCS & THPT)**  
> *Autonomous Full-Stack Product Built with Next.js, FastAPI, PostgreSQL, Redis, and Google Gemini AI.*

---

## 🌟 Core Value Proposition

SMART LEARNING PRO goes beyond traditional LMS platforms:
- **Root-Cause Analysis**: Don't just tell students what is wrong — teach them *why* they made the mistake and *how* to master the concept.
- **AI Tutor (Powered by Gemini)**: 24/7 personalized pedagogical explanations, step-by-step guidance, and dynamic practice generation without hallucinating or leaking test answers.
- **Adaptive Learning**: Real-time topic mastery tracking, knowledge gap detection, and personalized study roadmaps.
- **Unified Portals**: Tailored interfaces for Students, Teachers, and School Administrators.

---

## 🚀 Technology Stack

- **Frontend**: Next.js 14/15 (App Router), React 18/19, TypeScript, Tailwind CSS, Lucide Icons, Recharts, KaTeX math typesetting.
- **Backend**: Python 3.11, FastAPI (Modular Monolith), Pydantic v2, SQLAlchemy 2.0 Async, Alembic.
- **Database**: PostgreSQL 16 + pgvector (with dual-engine SQLite support for instant local development without Docker).
- **Caching & Queue**: Redis (with memory cache fallback).
- **AI Engine**: Google Gemini 1.5 Pro / Flash with Structured JSON Outputs & RAG Context Management.
- **Security**: Argon2id password hashing, JWT in HttpOnly secure cookies, Granular Role-Based Access Control (RBAC).

---

## 📁 Repository Structure

```
E:\SMART-LEARNING-PRO\
├── backend/            # FastAPI Modular Monolith (Auth, Courses, Exams, AI, Analytics)
├── frontend/           # Next.js Application (Landing, Student, Teacher, Admin Portals)
├── database/           # Migrations, Schemas, Seed data
├── docs/               # System Architecture, API Specs, Security Models
├── infrastructure/     # Dockerfiles, Docker Compose, Nginx, MinIO configs
├── scripts/            # Database seeding, Admin bootstrap, backup scripts
├── tests/              # Unit, Integration, and E2E test suites
├── .env.example        # Environment variable templates
├── docker-compose.yml  # Multi-service container orchestration
└── README.md           # Project documentation
```

---

## 🛠️ Quick Start Guide

### Prerequisites
- Python 3.11+
- Node.js v20+ or v22+
- Docker & Docker Compose (optional for production, dev fallback works natively)

### Backend Setup
```powershell
# In project root
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="E:\SMART-LEARNING-PRO\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Health Check: `http://localhost:8000/api/v1/health`  
Interactive Swagger Docs: `http://localhost:8000/docs`

### Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
Frontend App: `http://localhost:3000`

### Demo Accounts for Verification
| Portal | Role | Email | Password |
|---|---|---|---|
| Cổng Học Sinh | `STUDENT` | `student@smartlearning.vn` | `Password123!` |
| Cổng Giáo Viên | `TEACHER` | `teacher@smartlearning.vn` | `Password123!` |
| Cổng Quản Trị | `ADMIN` | `admin@smartlearning.vn` | `Password123!` |

---

## 🧪 Testing & Verification

Run complete backend test suite (31/31 suites):
```powershell
$env:PYTHONPATH="E:\SMART-LEARNING-PRO\backend"; .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests
```

Run frontend verification:
```powershell
cd frontend
npm run type-check   # TypeScript Strict Mode (0 errors)
npm run lint         # ESLint (0 errors, 0 warnings)
npm run build        # Production Build (21 routes generated)
```
```

### Frontend Setup
```powershell
cd frontend
npm install # or pnpm install
npm run dev
```

Visit:
- Frontend: `http://localhost:3000`
- Backend API Docs: `http://localhost:8000/docs`
