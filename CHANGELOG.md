# CHANGELOG — SMART LEARNING PRO

## [0.7.3] - 2026-11-19
### Added & Verified - Phase 6.3: Student Exam Interface Implementation
- **Giao diện Phòng Thi Học Sinh & Làm Bài Trực Tuyến**:
  - Xây dựng tuyến đường Quy định & Khởi tạo Đề thi: `frontend/src/app/student/exams/[id]/page.tsx` hiển thị chi tiết đề thi (thời lượng, số câu, điểm đạt, quy định) và khởi tạo attempt.
  - Cập nhật sảnh luyện thi `frontend/src/app/student/exams/page.tsx`: Nút "Bắt đầu làm bài" điều hướng mượt mà sang trang chi tiết đề thi.
  - Xây dựng Phòng thi trực tuyến và Màn hình kết quả: `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`.
    - Thanh điều hướng đỉnh cố định (Sticky Topbar) với tiến độ câu hỏi, lượt thi, trạng thái lưu và nút nộp bài.
    - Ma trận câu hỏi (Question Matrix) hỗ trợ điều hướng nhanh với 4 trạng thái (đã làm, chưa làm, đang xem, gắn cờ).
    - Hỗ trợ đầy đủ các dạng câu hỏi: Chọn 1 đáp án (Single-choice), Chọn nhiều đáp án (Multiple-choice), Đúng/Sai (True/False), và Câu trả lời ngắn (Short-answer).
    - Kết xuất ký hiệu và công thức toán học GDPT 2018 bằng `MathKaTeX`.
    - Cơ chế tự động lưu phía máy chủ (Debounced Autosave) với hiển thị trạng thái trung thực (`SAVING`, `SAVED`, `ERROR` kèm nút thử lại).
    - Đồng hồ đếm ngược có thẩm quyền phía máy chủ (Authoritative Server Timer) chuẩn hóa múi giờ (`parseServerDate`), tự động kích hoạt nộp bài khi hết giờ.
    - Hộp thoại xác nhận nộp bài hiển thị thống kê câu hỏi đã trả lời/chưa trả lời và cảnh báo nổi bật.
    - Màn hình kết quả hiển thị điểm số máy chủ, tỷ lệ chính xác, số câu đúng/sai/bỏ qua, và xem lại đáp án chi tiết khi được phép.
    - Giao diện bảo mật chống IDOR với thẻ cảnh báo HTTP 403 khi học sinh truy cập attempt của học sinh khác.
  - Tích hợp giao diện làm bài tập về nhà `frontend/src/app/student/assignments/page.tsx` kết nối trực tiếp với attempt làm bài thi.
- **Mở rộng API Service & Types**:
  - Bổ sung các kiểu dữ liệu thi cử trong `frontend/src/types/index.ts`.
  - Mở rộng `frontend/src/lib/api/exams.ts` với các phương thức `startExam`, `getAttempt`, `autosaveAnswer`, `submitAttempt`, `getAttemptReview`.
- **Kiểm thử Tự động E2E & Tiêu chuẩn Chất lượng**:
  - Mở rộng `frontend/e2e/exam-lifecycle.spec.ts` với đầy đủ 16 kịch bản kiểm thử tự động trên Google Chrome thực tế và live FastAPI backend.
  - Bộ kiểm thử Playwright E2E: **36/36 tests PASS trong 15.3s (Exit Code 0)**.
  - Bộ kiểm thử Pytest Backend: **31/31 tests PASS trong 6.52s (Exit Code 0)**.
  - TypeScript Check: **0 errors**.
  - ESLint Linting: **0 errors, 0 warnings**.
  - Next.js Production Build: **23/23 routes compiled thành công**.
- **Báo cáo Kỹ thuật**: Tạo [docs/PHASE_6_3_STUDENT_EXAM_INTERFACE.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_STUDENT_EXAM_INTERFACE.md).

## [0.7.2] - 2026-11-19
### Verified & Tested - Phase 6.2: Critical Workflow & Security Verification
- **Kiểm thử Tự động hóa E2E Nghiệp vụ Thi & Chấm điểm (Stage A)**:
  - Tạo `frontend/e2e/exam-lifecycle.spec.ts` kiểm chứng toàn diện 11 yêu cầu kỹ thuật:
    - Mở sảnh đề thi trên giao diện UI (`PASS`).
    - Ghi nhận trạng thái UI: Giao diện tương tác làm bài thi trực tiếp (`/student/exams/[id]`) là `NOT IMPLEMENTED` trong frontend Phase 6 (nút làm bài thi hiện hiển thị thông báo alert cho học sinh).
    - Kiểm chứng qua API: Khởi tạo attempt, cơ chế chống lộ đáp án (anti-leak) bảo đảm 100% không có `is_correct` và `explanation` trong snapshot đề thi, lưu câu trả lời thời gian thực (`PUT /answers`), chấm điểm tự động (`POST /submit`), cơ chế lũy thừa khi nộp lại (trả về kết quả đã chấm kèm HTTP 200), và phân quyền xem lại bài thi (`GET /review` trả về 200 cho học sinh sở hữu, 403 Forbidden cho học sinh khác và 403 Forbidden khi attempt chưa nộp).
- **Kiểm thử Tự động hóa E2E Thao tác Giáo viên & Ranh giới Sở hữu (Stage B)**:
  - Tạo `frontend/e2e/teacher-mutations.spec.ts` kiểm chứng 10 yêu cầu đột biến dữ liệu:
    - Tạo lớp học mới, xem danh sách và mở chi tiết lớp trên giao diện UI (`PASS`).
    - Tạo đề thi mới và xuất bản mở phòng luyện trên giao diện UI (`PASS`).
    - Thêm câu hỏi vào đề thi qua backend API (`PASS`); ghi nhận giao diện chọn ma trận câu hỏi trên UI là `NOT IMPLEMENTED`.
    - Tạo bài tập từ đề thi, hủy bài tập có xác nhận modal, và xuất bản bài tập nháp trên giao diện UI (`PASS`).
    - Kiểm tra sổ điểm bài tập qua API (`PASS`); ghi nhận giao diện bảng điểm chi tiết trên UI là `NOT IMPLEMENTED`.
    - Ranh giới sở hữu giáo viên: Giáo viên B bị chặn nghiêm ngặt bằng mã `403 Forbidden` khi cố truy cập chi tiết lớp, tạo lại mã mời, sửa đề thi hoặc lưu trữ lớp của Giáo viên A (`PASS`).
- **Kiểm thử Ma trận Phân quyền Backend (Stage C)**:
  - Tạo `frontend/e2e/backend-authorization.spec.ts` kiểm thử 21 API endpoints trên 4 vai trò (Student, Teacher B, Admin, Unauthenticated). Toàn bộ 7 suite đạt chuẩn phân quyền.
- **Kiểm toán Kiến trúc Xác thực & Nguy cơ XSS (Stage D)**:
  - Trả lời chi tiết 10 câu hỏi an ninh dựa trên bằng chứng mã nguồn (`client.ts`, `auth-context.tsx`, `auth/router.py`, `dependencies.py`, `math-katex.tsx`).
  - Phân tích rõ: `sessionStorage` giảm thiểu rò rỉ token kéo dài giữa các phiên trình duyệt, nhưng KHÔNG ngăn chặn được việc đánh cắp token nếu xảy ra XSS trong phiên hiện tại.
  - Phân loại rủi ro: SEC-01 (Medium: Thiếu cơ chế thu hồi refresh token trên máy chủ), SEC-02 (Medium: Token gửi qua header từ storage và thiếu header anti-CSRF tường minh), SEC-03 (Low: Cơ chế hết hạn thụ động), SEC-04 (Low: Bề mặt render KaTeX).
- **Cổng Tiêu chuẩn Chất lượng Toàn diện (Stage E)**:
  - TypeScript Strict: **0 errors**.
  - ESLint: **0 errors, 0 warnings**.
  - Next.js Production Build: **21/21 routes compiled thành công**.
  - Backend Pytest Suite: **31/31 tests PASS trong 5.92s**.
  - Playwright Chrome E2E Suite: **34/34 tests PASS trong 13.4s**.
- **Báo cáo Chuyên sâu**: Tạo [docs/PHASE_6_2_CRITICAL_VERIFICATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_2_CRITICAL_VERIFICATION.md).

## [0.7.1] - 2026-11-19
### Verified & Hardened - Phase 6.1: Frontend Functional Integration & RBAC Audit
- **Kiểm thử Tự động hóa E2E Playwright trên Google Chrome thực tế**:
  - Cài đặt `@playwright/test` và thiết lập cấu hình `frontend/playwright.config.ts` chạy trên Google Chrome hệ thống (`channel: 'chrome'`).
  - Viết 18 kịch bản kiểm thử E2E tích hợp thực tế kết nối trực tiếp FastAPI backend và Next.js frontend:
    - `frontend/e2e/auth-rbac.spec.ts`: Xác thực, đăng nhập học sinh/giáo viên/quản trị, chặn truy cập trái phép, phân quyền RBAC và đăng xuất dọn session.
    - `frontend/e2e/student-workflow.spec.ts`: Dữ liệu bảng điều khiển thời gian thực, danh sách lớp học, bắt lỗi mã mời không hợp lệ, cây môn học GDPT 2018, phòng luyện thi và bài tập về nhà.
    - `frontend/e2e/teacher-workflow.spec.ts`: Thống kê giảng dạy, quản lý lớp học, hộp mã mời khổ lớn, danh sách học sinh, ngân hàng câu hỏi KaTeX kèm đáp án chuẩn, ngân hàng đề thi và quản lý bài tập xuyên lớp.
  - Xây dựng kịch bản PowerShell `scripts/test_e2e.ps1` tự động khởi chạy và dọn dẹp tiến trình backend/frontend sạch sẽ.
  - Kết quả kiểm thử E2E: **18/18 tests PASS (100%) trong 9.0s (Exit Code 0)**.
- **Thắt chặt An ninh & Bảo mật Dữ liệu**:
  - Chuyển đổi cơ chế lưu trữ JWT access token từ `localStorage` sang `sessionStorage` trong `frontend/src/lib/api/client.ts` để ngăn ngừa rò rỉ token qua persistent XSS.
  - Viết lại bộ bóc tách công thức toán `MathKaTeX` bằng regex an toàn: văn bản thông thường được escape qua React bindings, công thức LaTeX được parse qua KaTeX an toàn.
  - Đồng bộ hóa tài khoản đăng nhập nhanh trên giao diện (`/login`) với tài khoản thực tế được khởi tạo từ database seeder.
  - Nâng cấp trải nghiệm xử lý mã mời lớp học: hiển thị thông báo lỗi thân thiện thay vì thông báo lỗi thô của backend.
- **Tiêu chuẩn Chất lượng (Quality Gates)**:
  - TypeScript Strict: **0 errors**.
  - ESLint: **0 errors, 0 warnings**.
  - Next.js Production Build: **21/21 routes compiled thành công**.
  - Backend Pytest Suite: **31/31 tests PASS trong 6.70s**.
  - Báo cáo chi tiết: Tạo [docs/PHASE_6_1_FUNCTIONAL_AUDIT.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_1_FUNCTIONAL_AUDIT.md).

## [0.7.0] - 2026-11-19
### Added - Phase 6: Frontend Foundation (Student, Teacher & Admin Portals)
- **Kiến trúc Frontend Next.js 16 App Router & React 19**:
  - Khởi tạo nền tảng frontend chuẩn production bằng Next.js 16.4.6, React 19.3.0, TypeScript Strict Mode và Tailwind CSS v4 trong thư mục `frontend/`.
  - Cấu hình TanStack React Query v5 để quản lý server state, caching, và refetch tự động.
  - Tích hợp thư viện KaTeX chuẩn quốc tế với component `MathKaTeX`, hỗ trợ hiển thị mượt mà các công thức Toán, Lý, Hóa phức tạp (cả inline `$formula$` và block `$$formula$$`).
- **Hệ thống Design System & UI Primitives**:
  - Tạo bộ UI primitives có khả năng tái sử dụng cao: `Button`, `Card`, `Badge`, `Input`, `Dialog` (Modal), `Skeleton`.
  - Xây dựng các widget domain dùng chung: `MathKaTeX`, `StatCard`, `EmptyState`.
- **Cơ chế Xác thực & Phiên làm việc (Dual-Mode Security)**:
  - Xây dựng `apiClient` linh hoạt (`frontend/src/lib/api/client.ts`) hỗ trợ cả `Authorization: Bearer <token>` và HttpOnly Cookies (`credentials: "include"`).
  - Triển khai `AuthProvider` và hook `useAuth()` an toàn cho React 19, tự động phục hồi phiên khi tải trang và hỗ trợ chuyển đổi vai trò.
- **Cổng Học Sinh (Student Portal - `/student/*`)**:
  - Giao diện Tổng quan (Dashboard): Thống kê chuỗi ngày học liên tục (Streak), điểm kinh nghiệm (XP), cấp độ (Level), lớp học đang tham gia và đề thi tự do.
  - Quản lý Lớp học: Xem danh sách lớp, modal nhập mã mời tham gia (`SL-XXXXXX`), chức năng tự rời lớp.
  - Quản lý Bài tập về nhà: Danh sách bài tập kèm huy hiệu trạng thái (Chưa làm, Đang làm, Đã nộp, Đã chấm kèm điểm số) và cảnh báo hạn chót.
  - Khám phá Môn học GDPT 2018: Lọc môn học theo Khối lớp 6 đến 12 từ API Curriculum.
  - Phòng Luyện thi: Danh sách đề thi mở tự do kèm thời lượng, số câu hỏi và nút bắt đầu làm bài.
  - Hồ sơ Học sinh: Thông tin tài khoản, danh hiệu và thống kê thành tích.
- **Cổng Giáo Viên (Teacher Portal - `/teacher/*`)**:
  - Bảng điều khiển Giảng dạy: Tổng số lớp, sĩ số học sinh, số lượng đề thi và câu hỏi trong kho.
  - Quản lý Lớp học & Mã mời: Danh sách lớp, modal tạo lớp học mới (`POST /classrooms`).
  - Chi tiết Lớp học (`/teacher/classrooms/[id]`): Hộp hiển thị mã mời kích thước lớn, nút sao chép và tạo lại mã mời, bảng danh sách học sinh (xóa học sinh khỏi lớp), tab bài tập kèm modal "Giao bài tập mới".
  - Quản lý Bài tập: Điều phối toàn bộ bài tập qua các lớp, xuất bản (Publish), hủy bài (Cancel), xem sổ điểm.
  - Ngân hàng Đề thi: Quản lý ma trận đề, thời lượng, điểm đạt, xuất bản đề thi.
  - Ngân hàng Câu hỏi: Duyệt câu hỏi theo mức độ nhận thức (Nhận biết, Thông hiểu, Vận dụng, Vận dụng cao), tìm kiếm từ khóa, hiển thị công thức KaTeX, làm nổi bật đáp án đúng và lời giải chi tiết.
  - Danh sách Học sinh: Tổng hợp toàn bộ học sinh theo học trên tất cả các lớp của giáo viên.
  - Hồ sơ Giáo viên: Thông tin chứng thực và quyền hạn giảng dạy.
- **Cổng Quản Trị Hệ Thống (Admin Portal - `/admin/*`)**:
  - Bảng điều khiển giám sát hạ tầng và trạng thái backend qua endpoint `/api/v1/health`.
  - Lối tắt chuyển đổi quyền nhanh giữa cổng Học sinh và cổng Giáo viên.
- **Chất lượng & Kiểm thử**:
  - TypeScript Strict Mode: **0 lỗi**.
  - ESLint: **0 lỗi, 0 cảnh báo**.
  - Next.js Production Build: **21/21 routes compiled & prerendered thành công**.
  - Bộ kiểm thử Backend: **31/31 tests PASS (100%)** trong 9.06s.

## [0.6.1] - 2026-11-19
### Security & Reliability Hardening (Phase 5.1 Production Readiness Audit)
- **Toàn vẹn khóa ngoại (Referential Integrity)**:
  - Kích hoạt `PRAGMA foreign_keys=ON` trên mọi kết nối SQLite Async thông qua SQLAlchemy sync engine connect event listener trong `backend/app/core/database.py`.
  - Ngăn chặn triệt để dữ liệu mồ côi và bản ghi không hợp lệ.
- **Đóng băng đề thi & Tách biệt chấm điểm (Immutable Snapshot Grading)**:
  - Bổ sung cột `answer_key_snapshot_json` vào `exam_attempts`.
  - Khi bắt đầu làm bài (`start_exam_attempt`), toàn bộ đáp án đúng, thang điểm và lời giải chi tiết được chụp cố định tại thời điểm bắt đầu thi.
  - Công cụ chấm bài (`submit_exam_attempt`) đánh giá hoàn toàn dựa trên snapshot này, tách biệt 100% với các thao tác chỉnh sửa hoặc xóa câu hỏi trong Question Bank sau đó của giáo viên.
- **Kiểm soát đồng thời (Concurrency & Race Safety)**:
  - Thiết lập partial unique indexes `uq_active_exam_attempt` và `uq_active_assignment_attempt` trên `exam_attempts` với điều kiện `WHERE status = 'IN_PROGRESS'`.
  - Xử lý race condition khi bắt đầu lượt thi đồng thời: tự động xử lý và trả về lượt thi active hợp lệ duy nhất mà không sinh bản ghi thừa.
  - Cơ chế kiểm tra sĩ số lớp học 2 lớp (pre-check bộ nhớ + atomic post-flush count verification), ngăn chặn 2 học sinh cùng vào lớp có 1 chỗ trống còn lại.
  - Cơ chế chống ghi đè gói tin autosave trễ mạng (out-of-order packet protection): gói tin có `time_spent_seconds` nhỏ hơn sẽ bị tự động bỏ qua.
- **Bảo mật & Xem lại bài làm (Review Endpoint & Anti-IDOR)**:
  - Bổ sung endpoint `GET /api/v1/exams/attempts/{attempt_id}/review`.
  - Kiểm tra 3 tầng: (1) Chỉ cho phép xem khi attempt đã nộp/đã chấm, (2) Chặn tấn công IDOR giữa các học sinh (403 Forbidden), (3) Tôn trọng cờ `allow_review` của đề thi/bài tập.
- **Bảo vệ hủy bài tập (Cancelled Assignment Safety)**:
  - Thêm cờ `allow_cancelled=True` cho phép học sinh nộp bài an toàn ngay cả khi giáo viên vừa hủy bài tập trong lúc học sinh đang hoàn thành.
- **Bộ kiểm thử tự động kiểm toán chuyên sâu**:
  - Tạo `backend/tests/test_hardening_audit.py` bao quát 8 tình huống kiểm toán: tính lũy thừa migration, đồng thời join lớp, vượt sĩ số, đồng thời start đề thi, trễ autosave, tách biệt Question Bank, bảo mật IDOR review, nộp bài tập đã hủy.
  - Nâng tổng số kiểm thử toàn hệ thống lên **31/31 tests PASS (100%)** trong 8.22 giây.
- **Báo cáo kiểm toán**: Tạo `docs/PHASE_5_1_HARDENING_AUDIT.md`.

## [0.6.0] - 2026-11-19
### Added
- **Classroom Management Module (`/api/v1/classrooms/*`)**:
  - `GET /classrooms`: Danh sách lớp học theo phân quyền (Giáo viên xem các lớp do mình sở hữu, Học sinh xem các lớp đã tham gia, Admin xem toàn bộ hệ thống).
  - `POST /classrooms`: Tạo lớp học mới, tự động sinh mã mời ngẫu nhiên (`SL-XXXXXX`), thiết lập sĩ số tối đa (`max_students`).
  - `GET /classrooms/{classroom_id}`: Xem chi tiết lớp học và danh sách thành viên (kiểm tra phân quyền nghiêm ngặt).
  - `PATCH /classrooms/{classroom_id}`: Cập nhật thông tin lớp học (tên, mô tả, khối lớp, sĩ số tối đa).
  - `POST /classrooms/{classroom_id}/archive`: Lưu trữ lớp học, chặn toàn bộ yêu cầu tham gia mới.
  - `POST /classrooms/{classroom_id}/regenerate-invite-code`: Cấp lại mã mời mới an toàn.
  - `GET /classrooms/{classroom_id}/members`: Danh sách thành viên trong lớp kèm thông tin học sinh.
  - `POST /classrooms/join`: Học sinh tham gia lớp học qua mã mời với kiểm tra trùng lặp (`409 Conflict`), kiểm tra trạng thái lưu trữ (`403 Forbidden`) và kiểm tra sĩ số tối đa (`403 Forbidden`).
  - `DELETE /classrooms/{classroom_id}/members/{student_id}`: Giáo viên gỡ học sinh khỏi lớp học.
  - `POST /classrooms/{classroom_id}/leave`: Học sinh tự rời khỏi lớp học.
  - `GET /classrooms/{classroom_id}/statistics`: Báo cáo thống kê hiệu suất lớp học (tổng sĩ số, số bài tập, số bài nộp, điểm trung bình toàn lớp, tỷ lệ hoàn thành).
- **Homework Assignment Engine (`/api/v1/assignments/*` & `/classrooms/{id}/assignments`)**:
  - `GET /classrooms/{classroom_id}/assignments`: Danh sách bài tập (Học sinh chỉ thấy các bài tập đã xuất bản; Giáo viên thấy toàn bộ các trạng thái DRAFT/PUBLISHED/CANCELLED).
  - `POST /classrooms/{classroom_id}/assignments`: Giao bài tập về nhà từ đề thi có sẵn trong Ngân hàng đề thi, cấu hình hạn nộp (`due_date`), thời điểm mở (`open_date`), số lần làm bài (`max_attempts`), chính sách nộp muộn (`allow_late_submission`) và chính sách xem đáp án (`allow_review`).
  - `GET /assignments/{assignment_id}`: Chi tiết bài tập (chặn 403 nếu học sinh không thuộc lớp học).
  - `PATCH /assignments/{assignment_id}`: Chỉnh sửa thông số bài tập.
  - `POST /assignments/{assignment_id}/publish`: Xuất bản bài tập để học sinh bắt đầu làm bài.
  - `POST /assignments/{assignment_id}/cancel`: Hủy bài tập.
  - `GET /assignments/{assignment_id}/submissions`: Bảng điểm lớp học (Gradebook) chi tiết từng học sinh kèm trạng thái làm bài, điểm số, thời gian nộp và tỷ lệ đạt.
- **Quy trình học sinh làm bài tập**:
  - `POST /assignments/{assignment_id}/start`: Bắt đầu hoặc tiếp tục bài tập dở dang, trả về snapshot câu hỏi không chứa đáp án đúng.
  - Tái sử dụng engine autosave và auto-grading của Examination Engine không trùng lặp code.
  - `GET /assignments/{assignment_id}/my-attempt`: Xem lại các đáp án đã lưu trước đó khi tải lại trang.
  - `POST /assignments/{assignment_id}/submit`: Nộp bài tập, tự động chấm điểm, tính điểm số, tỷ lệ chính xác, và xử lý nộp bài trùng lặp an toàn (idempotent).
- **Bộ kiểm thử tự động chuyên sâu**:
  - Tạo `backend/tests/test_classrooms.py` và `backend/tests/test_assignments.py` với 4 test suites bao quát 100% yêu cầu.
  - Toàn bộ backend test suite đạt **23/23 tests PASS (100%)** trong 5.46 giây.

## [0.5.0] - 2026-11-19
### Added
- **Online Examination Engine & Auto-Grading (`/api/v1/exams/*`)**:
  - `GET /exams/available`: Danh sách đề thi đang mở cho học sinh, kiểm tra khung thời gian và giới hạn lượt thi (`max_attempts`).
  - `POST /exams/{exam_id}/start`: Bắt đầu làm bài thi với bản chụp bất biến (`questions_snapshot_json`) **đã loại bỏ hoàn toàn đáp án đúng và lời giải** để chống gian lận.
  - `GET /exams/attempts/{attempt_id}`: Khôi phục trạng thái làm bài và từ điển các câu trả lời học sinh đã lưu trước đó (`saved_answers`).
  - `POST /exams/attempts/{attempt_id}/questions/{question_id}/autosave`: Tự động lưu đáp án nền (debounce real-time) hỗ trợ đơn lựa chọn, đa lựa chọn, đánh dấu câu hỏi cần xem lại (`is_flagged`) và thời gian làm bài.
  - `POST /exams/attempts/{attempt_id}/submit`: Nộp bài thi và kích hoạt **Server-side Auto Grading Engine**:
    - Chấm điểm tự động các dạng câu hỏi Single Choice, Multiple Choice, True/False, Short Answer.
    - Tính điểm chi tiết từng câu (`points_awarded`), tổng điểm (`total_score`), tỷ lệ chính xác (`accuracy_percentage`), phân loại Đạt / Không đạt (`is_passed`).
    - Lưu kết quả phân tích thống kê vào bảng `exam_results`.
  - `GET /exams/attempts/{attempt_id}/review`: Xem lại chi tiết từng câu hỏi, đáp án học sinh đã chọn, đáp án chuẩn và lời giải KaTeX sau khi nộp bài (nếu đề thi bật `allow_review`).
- **Quản lý đề thi dành cho Giáo viên & Quản trị viên**:
  - `GET /exams`: Phân trang, lọc theo môn học, khối lớp, trạng thái và giáo viên.
  - `POST /exams`: Tạo đề thi mới ở trạng thái `DRAFT` hoặc `PUBLISHED`.
  - `GET /exams/{exam_id}`: Chi tiết cấu hình và danh sách câu hỏi kèm điểm số.
  - `PATCH /exams/{exam_id}`: Cập nhật thông số đề thi (kiểm soát quyền sở hữu giáo viên).
  - `POST /exams/{exam_id}/questions`: Thêm câu hỏi từ ngân hàng câu hỏi vào đề thi với trọng số điểm riêng.
  - `DELETE /exams/{exam_id}/questions/{question_id}`: Gỡ câu hỏi khỏi đề thi.
  - `POST /exams/{exam_id}/publish`: Xuất bản đề thi (chặn xuất bản nếu đề chưa có câu hỏi).
  - `POST /exams/{exam_id}/archive`: Lưu trữ đề thi (đóng phòng thi).
  - `GET /exams/{exam_id}/submissions`: Thống kê kết quả nộp bài của toàn bộ học sinh.
- **Ranh giới sở hữu và kiểm soát gian lận**:
  - Ranh giới quyền sở hữu giáo viên (Teacher Ownership Boundary) chặn 403 khi sửa/xóa/lưu trữ đề thi của giáo viên khác; Quản trị viên có quyền Admin Override.
  - Tách biệt hoàn toàn câu hỏi đề thi snapshot với thay đổi sau này trong Ngân hàng câu hỏi.
- **Bộ kiểm thử tự động chuyên sâu**:
  - Tạo `backend/tests/test_exams.py` với 2 test suites bao quát toàn bộ quy trình giáo viên và học sinh.
  - Toàn bộ backend test suite đạt **19/19 tests PASS (100%)** trong 2.91 giây.

## [0.4.0] - 2026-11-18
### Added
- **Question Bank Module (`/api/v1/questions/*`)**:
  - `GET /questions`: Danh sách câu hỏi có phân trang và bộ lọc chuyên sâu theo khối lớp, môn học, chương, chủ đề, bài học, độ khó, dạng câu hỏi, tác giả, và tìm kiếm từ khóa trong nội dung / thẻ tags.
  - `GET /questions/{question_id}`: Xem chi tiết câu hỏi và các phương án lựa chọn.
  - `POST /questions`: Tạo câu hỏi mới (chỉ dành cho Giáo viên và Quản trị viên) với xác thực nghiệp vụ chặt chẽ theo dạng câu hỏi (Single Choice, Multiple Choice, True/False, Short Answer).
  - `PATCH /questions/{question_id}`: Cập nhật nội dung câu hỏi, độ khó, thẻ tags hoặc thay thế danh sách phương án.
  - `DELETE /questions/{question_id}`: Xóa câu hỏi khỏi ngân hàng câu hỏi.
  - `POST /questions/{question_id}/toggle-publish`: Chuyển đổi trạng thái câu hỏi giữa Bản nháp và Công khai.
- **Bảo mật & Chống gian lận (Answer Confidentiality)**:
  - Tách bạch schema phản hồi: Học sinh và khách vãng lai nhận `QuestionStudentResponse` hoàn toàn **không chứa trường `is_correct`** của các phương án.
  - Giáo viên và Quản trị viên nhận `QuestionAdminResponse` đầy đủ đáp án phục vụ quản lý và ra đề.
- **Ranh giới sở hữu câu hỏi (Teacher Ownership Boundary)**:
  - Giáo viên chỉ có quyền sửa hoặc xóa câu hỏi do chính mình tạo ra (`creator_id`).
  - Hệ thống chặn `403 Forbidden` nếu giáo viên cố gắng can thiệp vào câu hỏi của giáo viên khác.
  - Quản trị viên (`ADMIN`, `SUPERADMIN`) được cấp quyền ghi đè (Admin Override) để kiểm duyệt chất lượng nội dung toàn trường.
- **Bộ kiểm thử tự động chuyên sâu**:
  - Tạo `backend/tests/test_questions.py` với 6 test suites bao quát toàn bộ yêu cầu bảo mật, quyền sở hữu, lọc đa cấp và xác thực dữ liệu.
  - Toàn bộ backend test suite đạt **17/17 tests PASS (100%)** trong 2.01 giây.

## [0.3.0] - 2026-11-18
### Added
- Curriculum Module API (`/api/v1/curriculum/*`) với 11 endpoints hoàn chỉnh.
- Kiểm soát xuất bản: Bản nháp được ẩn an toàn với học sinh.
- Hỗ trợ công thức toán học KaTeX trong bài giảng.
- Bộ kiểm thử tự động Curriculum: 8 test suites.

## [0.2.0] - 2026-11-18
### Added
- Hoàn thành kiến trúc hệ thống và đặc tả kỹ thuật Phase 1.
- Xây dựng 26 models SQLAlchemy 2.0 ORM và khởi tạo SQLite async database.
- Xây dựng module bảo mật Argon2id và JWT token kép (Header Bearer + HttpOnly Secure Cookie).
- Xây dựng bộ lọc phân quyền RBAC và API xác thực (`/register`, `/login`, `/me`, `/logout`).
- Xây dựng seeder dữ liệu GDPT 2018 và test suites ban đầu.

## [0.1.0] - 2026-11-18
### Added
- Khởi tạo project độc lập tại `E:\SMART-LEARNING-PRO` và thiết lập Git.
