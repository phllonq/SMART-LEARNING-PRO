# KẾ HOẠCH TRIỂN KHAI FRONTEND FOUNDATION (PHASE 6)
## SMART LEARNING PRO — AUTONOMOUS FULL-STACK EDTECH PLATFORM

**Mã phiên:** Phase 6 — Frontend Foundation  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Backend Baseline:** Commit `6f38285` (31/31 pytest passed)  
**Ngày lập:** 19/11/2026

---

## 1. MỤC TIÊU VÀ PHẠM VI TRIỂN KHAI

Xây dựng nền tảng Frontend chuẩn SaaS EdTech hiện đại, hiệu năng cao, tích hợp trực tiếp với hệ thống backend FastAPI hiện có tại `http://localhost:8000/api/v1`. Tuyệt đối không sử dụng mock data giả lập để thay thế backend.

### Phạm vi chức năng Phase 6:
1. **Frontend Architecture & Scaffold:** Next.js 15 (hoặc 14 LTS ổn định) App Router, React 19/18, TypeScript strict mode, Tailwind CSS v3/v4.
2. **Centralized Typed API Client & State Management:**
   - Client HTTP kiểu mẫu (typed) với TanStack Query v5.
   - Cơ chế dual-auth: Tự động gửi HttpOnly Cookies (`credentials: "include"`) và hỗ trợ `Authorization: Bearer <token>`.
   - Xử lý lỗi tập trung: Trích xuất lỗi có cấu trúc từ backend FastAPI (`{"detail": "..."}`).
3. **Authentication & Role-Based Access Control (RBAC):**
   - Đăng nhập (`/login`) cho Học sinh, Giáo viên, Quản trị viên.
   - Đăng ký tài khoản (`/register`) hỗ trợ chọn vai trò (`STUDENT`, `TEACHER`) và khối lớp (6-12).
   - Đăng xuất (`/api/v1/auth/logout`) và dọn dẹp phiên làm việc.
   - Context xác thực và Route Guards bảo vệ các layout:
     - `/student/*` chỉ dành cho role `STUDENT`.
     - `/teacher/*` chỉ dành cho role `TEACHER`, `ADMIN`, `SUPERADMIN`.
     - `/admin/*` chỉ dành cho role `ADMIN`, `SUPERADMIN`.
4. **Design System & Reusable Components:**
   - Hệ thống UI theo tiêu chuẩn shadcn/ui kết hợp Lucide icons.
   - Hỗ trợ công thức toán học KaTeX (inline `$f(x)$` và block `$$...$$`).
   - Các UI primitives: Button, Input, Select, Dialog/Modal, Card, Table, Badge, Tabs, Skeleton loading, Toast notifications.
5. **Cổng Học Sinh (Student Portal):**
   - `/student/dashboard`: Thống kê tổng quan, tiến độ học, lớp học tham gia, bài tập cần làm.
   - `/student/classrooms`: Danh sách lớp học, modal tham gia lớp bằng mã mời (`SL-XXXXXX`), rời lớp học.
   - `/student/assignments`: Danh sách bài tập từ các lớp học đã tham gia, chi tiết hạn nộp, trạng thái làm bài.
   - `/student/courses`: Khám phá chương trình học theo khối lớp và môn học từ backend.
   - `/student/exams`: Danh sách đề thi trực tuyến mở cho học sinh.
   - `/student/profile`: Thông tin cá nhân, khối lớp, streak, điểm kinh nghiệm (XP/Level).
6. **Cổng Giáo Viên (Teacher Portal):**
   - `/teacher/dashboard`: Thống kê số lớp, sĩ số học sinh, số bài tập đang giao.
   - `/teacher/classrooms`: Danh sách lớp học do giáo viên phụ trách, modal tạo lớp học mới, chức năng lưu trữ lớp.
   - `/teacher/classrooms/[id]`: Chi tiết lớp học, hiển thị mã mời, cấp lại mã mời, danh sách thành viên.
   - `/teacher/assignments`: Danh sách bài tập đã giao, modal tạo bài tập mới từ đề thi có sẵn.
   - `/teacher/exams`: Danh sách đề thi giáo viên sở hữu.
   - `/teacher/questions`: Ngân hàng câu hỏi, bộ lọc theo môn học và mức độ nhận thức.
   - `/teacher/students`: Danh sách học sinh theo lớp học.
   - `/teacher/profile`: Hồ sơ giáo viên.
7. **Cổng Quản Trị Viên (Admin Portal):**
   - Layout placeholder với navigation chuẩn phân quyền.

---

## 2. KIẾN TRÚC THƯ MỤC FRONTEND

```
frontend/
├── .env.example                       # Cấu hình biến môi trường mẫu
├── .env.local                         # Cấu hình môi trường dev cục bộ
├── package.json                       # Package dependencies & scripts
├── tsconfig.json                      # TypeScript strict configuration
├── tailwind.config.ts                 # Tailwind configuration
├── postcss.config.js                  # PostCSS plugins
├── src/
│   ├── app/                           # Next.js App Router
│   │   ├── layout.tsx                 # Root layout (QueryClientProvider, AuthProvider, Toaster)
│   │   ├── page.tsx                   # Public Landing / Gateway page
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx         # Trang đăng nhập
│   │   │   └── register/page.tsx      # Trang đăng ký
│   │   ├── student/                   # Student Portal Layout & Pages
│   │   │   ├── layout.tsx             # Student sidebar, header & route guard
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── classrooms/page.tsx
│   │   │   ├── assignments/page.tsx
│   │   │   ├── courses/page.tsx
│   │   │   ├── exams/page.tsx
│   │   │   └── profile/page.tsx
│   │   ├── teacher/                   # Teacher Portal Layout & Pages
│   │   │   ├── layout.tsx             # Teacher sidebar, header & route guard
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── classrooms/page.tsx
│   │   │   ├── classrooms/[id]/page.tsx
│   │   │   ├── assignments/page.tsx
│   │   │   ├── exams/page.tsx
│   │   │   ├── questions/page.tsx
│   │   │   ├── students/page.tsx
│   │   │   └── profile/page.tsx
│   │   └── admin/                     # Admin Portal Layout & Pages
│   │       ├── layout.tsx             # Admin sidebar & route guard
│   │       └── dashboard/page.tsx
│   ├── components/
│   │   ├── ui/                        # Reusable primitives (button, input, card, badge, dialog, table...)
│   │   ├── layout/                    # Sidebar, Header, Navbar, UserMenu
│   │   ├── shared/                    # MathKaTeX, EmptyState, LoadingSkeleton, StatCard
│   │   └── providers/                 # TanStack Query Provider, Auth Provider
│   ├── features/
│   │   ├── auth/                      # Login/Register forms, auth hooks
│   │   ├── student/                   # Student dashboard widgets, classroom join modal
│   │   ├── teacher/                   # Teacher classroom creation, assignment modal
│   │   ├── curriculum/                # Subject cards, grade selector
│   │   ├── classrooms/                # Classroom cards, member tables
│   │   └── assignments/               # Assignment list, submission badges
│   ├── lib/
│   │   ├── api/                       # API client, endpoints map, error handling
│   │   ├── auth/                      # Token storage, auth cookies, role checker
│   │   └── utils.ts                   # cn, date formatters, number formatters
│   ├── hooks/                         # useAuth, useClassrooms, useAssignments...
│   └── types/                         # TypeScript interfaces (User, Classroom, Exam, Assignment...)
```

---

## 3. CÁC GIAI ĐOẠN THỰC THI (STAGED EXECUTION ROADMAP)

### Giai đoạn A: Khởi tạo và thiết lập Scaffold (Setup & Scaffolding)
- Khởi tạo dự án Next.js tại `frontend/` với TypeScript, Tailwind CSS, App Router.
- Cài đặt dependencies chuẩn:
  - `@tanstack/react-query`
  - `lucide-react`
  - `clsx`, `tailwind-merge`
  - `react-hook-form`, `@hookform/resolvers`, `zod`
  - `katex`
- Thiết lập `tsconfig.json` đường dẫn alias `@/* -> ./src/*`.
- Tạo `.env.example` và `.env.local` với `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`.

### Giai đoạn B: Design System, API Client & Authentication
- Xây dựng hệ thống UI Components: Button, Input, Select, Card, Badge, Table, Modal/Dialog, Skeleton, Toast.
- Xây dựng component `MathKaTeX` kết xuất công thức toán học KaTeX an toàn.
- Xây dựng HTTP API Client (`src/lib/api/client.ts`):
  - Tự động gắn Bearer Token và gửi credentials (cookies).
  - Chuẩn hóa lỗi API trả về thông báo Tiếng Việt thân thiện.
- Xây dựng `AuthProvider` và `useAuth` hook:
  - Gọi `/auth/login`, `/auth/register`, `/auth/me`, `/auth/logout`.
  - Lưu trữ session an toàn trong React State và localStorage / cookie dự phòng.
- Xây dựng trang Đăng nhập (`/login`) và Đăng ký (`/register`).

### Giai đoạn C: Xây dựng Cổng Học Sinh (Student Portal)
- `student/layout.tsx`: Sidebar thông minh cho học sinh, hiển thị XP, Level, Avatar, điều hướng phù hợp.
- `student/dashboard/page.tsx`: Tích hợp API thật lấy thông tin học sinh, lớp học đã tham gia, bài tập cần làm.
- `student/classrooms/page.tsx`: Danh sách lớp học, modal tham gia lớp học bằng mã mời, xác nhận rời lớp.
- `student/assignments/page.tsx`: Danh sách bài tập với hạn nộp, trạng thái làm bài, liên kết chi tiết.
- `student/courses/page.tsx`: Trình duyệt môn học từ `/api/v1/curriculum/subjects`.
- `student/exams/page.tsx`: Danh sách đề thi mở từ `/api/v1/exams/available`.
- `student/profile/page.tsx`: Hồ sơ cá nhân học sinh.

### Giai đoạn D: Xây dựng Cổng Giáo Viên (Teacher Portal)
- `teacher/layout.tsx`: Sidebar giáo viên với các mục: Lớp học, Bài tập, Đề thi, Ngân hàng câu hỏi, Học sinh.
- `teacher/dashboard/page.tsx`: Tích hợp API thống kê các lớp do giáo viên quản lý.
- `teacher/classrooms/page.tsx`: Danh sách lớp học của giáo viên, modal tạo lớp học mới (`POST /api/v1/classrooms`), thao tác lưu trữ lớp.
- `teacher/classrooms/[id]/page.tsx`: Chi tiết lớp, hiển thị mã mời lớn để trình chiếu trên lớp, chức năng cấp lại mã mời, danh sách thành viên.
- `teacher/assignments/page.tsx`: Danh sách bài tập đã giao kèm sĩ số nộp bài và hạn chót.
- `teacher/exams/page.tsx`: Quản lý các đề thi do giáo viên biên soạn.
- `teacher/questions/page.tsx`: Ngân hàng câu hỏi phân loại theo môn học và mức độ.
- `teacher/students/page.tsx`: Tổng quan học sinh theo lớp học.
- `teacher/profile/page.tsx`: Hồ sơ giáo viên.

### Giai đoạn E: Kiểm thử tích hợp, tối ưu giao diện & Hoàn tất
- Kiểm tra toàn bộ luồng đăng nhập của Học sinh và Giáo viên.
- Kiểm tra TypeScript compile (`tsc --noEmit`).
- Kiểm tra Next.js Production Build (`npm run build`).
- Đảm bảo thiết kế tương thích (Responsive) trên Desktop, Tablet, Mobile.
- Cập nhật tài liệu kỹ thuật: `PHASE_6_FRONTEND_PLAN.md`, `FRONTEND_ARCHITECTURE.md`, `FRONTEND_API_INTEGRATION.md`, `PROJECT_STATUS.md`, `TASK_TRACKER.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`.
- Thực hiện Git commit: `feat(frontend): establish student and teacher portal foundation`.
