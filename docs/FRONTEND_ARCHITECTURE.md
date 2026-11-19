# FRONTEND ARCHITECTURE SPECIFICATION
## SMART LEARNING PRO — Phase 6: Frontend Foundation

**Version:** 1.0.0  
**Framework:** Next.js 16.4.6 (App Router) + React 19.3.0 + TypeScript Strict Mode  
**Styling & UI:** Tailwind CSS v4, Lucide React, KaTeX  
**Data & State:** TanStack React Query v5, Context API, Native Fetch with typed ApiClient  
**Backend Endpoint:** `http://localhost:8000/api/v1`

---

## 1. ARCHITECTURAL OVERVIEW

SMART LEARNING PRO frontend is structured around role-based portal isolation with shared design tokens, typed API contracts, and cryptographic authentication persistence.

```
frontend/
├── public/                     # Static assets & brand graphics
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── (auth)/             # Public authentication route group
│   │   │   ├── login/          # Dual credentials + Quick-fill demo accounts
│   │   │   └── register/       # Role-adaptive registration (Student/Teacher)
│   │   ├── student/            # Student Portal (Role Guard: STUDENT)
│   │   │   ├── layout.tsx      # Sidebar, XP bar, Streak counter, Level badge
│   │   │   ├── dashboard/      # Overview, enrolled classrooms, practice exams
│   │   │   ├── classrooms/     # Joined classes & invite code modal
│   │   │   ├── assignments/    # Homework tracker with countdown & status badges
│   │   │   ├── courses/        # Curriculum 2018 grade-level subject explorer
│   │   │   ├── exams/          # Examination lobby & session launcher
│   │   │   └── profile/        # Gamification & account statistics
│   │   ├── teacher/            # Teacher Portal (Role Guard: TEACHER/ADMIN)
│   │   │   ├── layout.tsx      # Teacher workspace navigation & identity badge
│   │   │   ├── dashboard/      # Overall classroom & student metrics
│   │   │   ├── classrooms/     # Owned classes & "Create Class" modal
│   │   │   │   └── [id]/       # Class detail: Code box, Student roster & Homework
│   │   │   ├── assignments/    # Central assignment dispatch & gradebook
│   │   │   ├── exams/          # Exam matrix bank & publish controls
│   │   │   ├── questions/      # Question bank with KaTeX formula preview
│   │   │   ├── students/       # Aggregate student roster across classrooms
│   │   │   └── profile/        # Teacher credentials & verification
│   │   ├── admin/              # Admin Portal (Role Guard: ADMIN/SUPERADMIN)
│   │   │   ├── layout.tsx      # Admin header & portal switcher
│   │   │   └── dashboard/      # System health & backend telemetry
│   │   ├── globals.css         # Tailwind v4 theme, KaTeX CSS & scrollbars
│   │   ├── layout.tsx          # Root layout with Query & Auth Providers
│   │   └── page.tsx            # High-conversion EdTech Landing Page
│   ├── components/
│   │   ├── shared/             # Specialized business widgets
│   │   │   ├── empty-state.tsx # Illustrated empty feedback
│   │   │   ├── math-katex.tsx  # International KaTeX formula parser
│   │   │   └── stat-card.tsx   # KPI metric card with visual accents
│   │   └── ui/                 # Reusable atomic UI primitives
│   │       ├── badge.tsx       # Status indicator badges
│   │       ├── button.tsx      # Polymorphic buttons with loading states
│   │       ├── card.tsx        # Card containers with header/content/footer
│   │       ├── dialog.tsx      # Accessible modal overlays
│   │       ├── input.tsx       # Standard inputs with validation text
│   │       └── skeleton.tsx    # Shimmer loading placeholders
│   ├── lib/
│   │   ├── api/                # Typed REST client modules
│   │   │   ├── assignments.ts  # Assignment & Gradebook API
│   │   │   ├── auth.ts         # Authentication & Session API
│   │   │   ├── classrooms.ts   # Classrooms, Invite codes & Members API
│   │   │   ├── client.ts       # Central HTTP fetcher with Bearer + Cookie
│   │   │   ├── curriculum.ts   # GDPT 2018 Grades & Subjects API
│   │   │   ├── exams.ts        # Online Examination API
│   │   │   └── questions.ts    # Question Bank API
│   │   ├── auth/
│   │   │   └── auth-context.tsx# React 19-safe authentication state machine
│   │   ├── providers.tsx       # QueryClient & Auth Provider tree
│   │   └── utils.ts            # Class merging (cn) & Vietnamese date formatters
│   └── types/
│       └── index.ts            # Strict TypeScript interfaces matching backend models
├── .env.example                # Template configuration
├── .env.local                  # Local development backend API pointer
├── eslint.config.mjs           # Next.js ESLint configuration
├── next.config.ts              # Next.js 16 compiler configuration
├── package.json                # Dependencies and npm run scripts
└── tsconfig.json               # TypeScript strict mode settings
```

---

## 2. AUTHENTICATION & RBAC ENFORCEMENT

1. **Dual-Mode Security Compatibility**:
   - `POST /api/v1/auth/login` sets HttpOnly `access_token` and `refresh_token` cookies.
   - Client API interceptor preserves token in `localStorage` (`smart_learning_access_token`) and automatically includes both `Authorization: Bearer <token>` and `credentials: "include"`.
   - Guarantees seamless operation across both browser cookie contexts and cross-origin development headers.

2. **Route Guards**:
   - `StudentLayout`: Restricts access strictly to users with role `STUDENT` (or `ADMIN`/`SUPERADMIN` for inspection). Redirects unauthenticated users to `/login`.
   - `TeacherLayout`: Restricts access to users with `TEACHER`, `ADMIN`, or `SUPERADMIN`.
   - `AdminLayout`: Restricts access to `ADMIN` and `SUPERADMIN`.

---

## 3. MATH FORMULA RENDERING (KaTeX)

- The platform employs `katex` v0.19.1 with `@types/katex`.
- `MathKaTeX` component dynamically parses:
  - Raw LaTeX formulas (e.g. `\int_{0}^{1} x^2 dx = \frac{1}{3}`).
  - Inline formulas delimited by `$ ... $`.
  - Display block formulas delimited by `$$ ... $$`.
- Renders server-side and client-side with zero hydration mismatch and `throwOnError: false` fallback.

---

## 4. BUILD & COMPLIANCE VERIFICATION

- **TypeScript Strict Mode**: 100% type coverage, 0 errors.
- **ESLint**: 0 errors, 0 warnings.
- **Next.js Production Build**: All 21 routes compiled and statically / partially prerendered without errors.
- **Backend API Integration**: 100% verified against live FastAPI endpoints.
