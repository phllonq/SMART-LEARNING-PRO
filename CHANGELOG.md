# CHANGELOG — SMART LEARNING PRO

## [0.2.0] - 2026-11-18
### Added
- Completed Phase 1 Product & System Architecture documentation in `docs/`.
- Verified and established Git repository baseline commit `3cac958`.
- Set up dedicated Python 3.11 virtual environment (`.venv`) with all production dependencies.
- Installed `greenlet>=3.0.0` for SQLAlchemy 2.0 Asyncio engine and `email-validator` for Pydantic v2.
- Created complete domain models for all 26 tables across 8 modules.
- Created `database/smart_learning.db` SQLite async database for zero-config native local development.
- Built Core Security module: Argon2id password hashing and JWT access/refresh token generation.
- Implemented Dual-Channel Authentication (Authorization Bearer Header + HttpOnly Secure Cookie).
- Implemented Granular RBAC (Roles: `STUDENT`, `TEACHER`, `ADMIN`, `SUPERADMIN`).
- Built Authentication API endpoints: `/api/v1/auth/register`, `/login`, `/me`, `/logout`.
- Built System Health Check endpoint: `/api/v1/health`.
- Built and ran database seeder `scripts/seed_database.py` with Vietnamese curriculum (Grades 10-12, Math 11, Physics 11, Chemistry 11, KaTeX Lesson, 3 KaTeX Questions, 45-min Exam, Class 11A1, and 3 test accounts).
- Implemented automated test suite with pytest & pytest-asyncio: 3/3 test suites passing (Auth, Health, RBAC).
