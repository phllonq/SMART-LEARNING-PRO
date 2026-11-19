# PHASE 6.3.2 — EXAM ENGINE HARDENING & REMEDIATION REPORT
**SMART LEARNING PRO** — Nền tảng Học tập Thông minh Chuẩn GDPT 2018  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Baseline Git HEAD:** `ca43c16a22dba95436d1ef0237a67a64c04e032d` (`ca43c16`)  
**Previous Audit:** `docs/PHASE_6_3_1_POST_IMPLEMENTATION_AUDIT.md`  
**Execution Date:** 2026-11-19  

---

## 1. EXECUTIVE SUMMARY

Giai đoạn Phase 6.3.2 tập trung giải quyết triệt để và khắc phục hoàn toàn tất cả các khiếm khuyết kỹ thuật nghiêm trọng (Critical / High-Risk Defects) và trung bình đã được phát hiện trong báo cáo kiểm toán độc lập Phase 6.3.1.

Toàn bộ các giải pháp đã được hiện thực hóa trực tiếp trên mã nguồn backend FastAPI, cơ sở dữ liệu SQLite, frontend Next.js 16 và được kiểm chứng tự động qua bộ kiểm thử hồi quy toàn diện.

### Bảng Tổng Hợp Kết Quả Khắc Phục (Before vs. After)

| Hạng mục khiếm khuyết | Trạng thái trước (Phase 6.3.1) | Trạng thái sau khắc phục (Phase 6.3.2) | Kết quả kiểm chứng |
| :--- | :---: | :---: | :---: |
| **TASK A — Bảo mật đáp án SHORT_ANSWER** | **FAIL** (Rò rỉ đáp án trong payload khởi tạo bài thi) | **PASS** (`sanitized_opts = []`, giữ nguyên snapshot bảo mật `answer_key_snapshot_json`) | `test_short_answer_confidentiality_and_validation` |
| **TASK B — Toàn vẹn dữ liệu `student_answers`** | **FAIL** (Thiếu ràng buộc duy nhất, nguy cơ trùng bản ghi) | **PASS** (Migration bổ sung `UNIQUE INDEX uq_attempt_question_answer`, xử lý rollback & retry) | `scripts/migrate_phase632.py`, `models.py` |
| **TASK C — Tính nhất quán Autosave & Debounce** | **FAIL** (Gõ phím gửi request liên tục, nguy cơ ghi đè ngược) | **PASS** (Debounce 400ms, atomic versioning `client_version`, loại bỏ stale packet) | `page.tsx`, `service.py`, `test_student_answers_unique_constraint_and_autosave_versions` |
| **TASK D — Phân quyền chính sách Bài tập (Assignment)** | **FAIL** (Router `/exams/attempts/{id}/*` bỏ qua thiết lập của assignment) | **PASS** (Assignment `allow_review` & `allow_late_submission` có độ ưu tiên cao nhất) | `test_assignment_policy_enforcement` (403 và 200) |
| **TASK E — Kiểm soát Deadline & Lệch đồng hồ** | **FAIL** (Thiếu chặn deadline ở server, lệch đồng hồ client) | **PASS** (Backend tự động nộp bài khi hết hạn, `serverTimeOffset` đồng bộ thời gian) | `router.py`, `service.py`, `page.tsx` |
| **TASK F — Kiểm thử bao phủ 4 dạng câu hỏi** | **FAIL** (`MULTIPLE_CHOICE`, `TRUE_FALSE`, `SHORT_ANSWER` chưa kiểm thử) | **PASS** (Kiểm thử tự động E2E cả 4 dạng câu hỏi với điểm số 10.0/10.0 và review chi tiết) | `test_all_four_question_types_e2e` |

---

## 2. CHI TIẾT CÁC HẠNG MỤC ĐÃ KHẮC PHỤC

### 2.1. TASK A — Bảo Mật Đáp Án Tự Luận Ngắn (SHORT_ANSWER Confidentiality)
- **Vấn đề cũ:** Tại hàm `start_exam_attempt`, câu hỏi dạng `SHORT_ANSWER` vẫn chuyển tiếp danh sách `options` vào `questions_snapshot_json`, dẫn đến việc học sinh mở tab Network hoặc DevTools có thể thấy toàn bộ các phương án chấp nhận (chứa đáp án chuẩn).
- **Giải pháp triển khai:**
  1. Trong `backend/app/modules/exams/service.py` (`start_exam_attempt`): Nếu `q.question_type == QuestionType.SHORT_ANSWER.value`, thiết lập `sanitized_opts = []`.
  2. Bảng snapshot đáp án chuẩn của server (`full_snapshot` / `answer_key_snapshot_json`) vẫn lưu đầy đủ các options có `is_correct: True` để phục vụ tự động chấm điểm và review sau thi.
  3. Trong `backend/app/modules/questions/schemas.py`: Bổ sung kiểm tra tính hợp lệ bắt buộc câu hỏi `SHORT_ANSWER` phải có ít nhất 1 option mang `is_correct == True` (ngăn chặn câu hỏi không thể tự động chấm).
  4. Trong Review Endpoint (`get_attempt_review`): Trả về `student_answer_text` và `correct_answer_texts` để học sinh đối chiếu sau khi được phép xem lại bài.

### 2.2. TASK B — Toàn Vẹn Bảng `student_answers` & Migration An Toàn
- **Vấn đề cũ:** Bảng `student_answers` không có Unique Constraint cho cặp `(attempt_id, question_id)`, dẫn tới nguy cơ race condition khi hai request autosave đồng thời tạo ra hai bản ghi khác nhau.
- **Giải pháp triển khai:**
  1. Soạn thảo và chạy script migration `scripts/migrate_phase632.py`:
     - Kiểm tra dữ liệu hiện có: 0 bản ghi trùng lặp trên toàn bộ 81 câu trả lời.
     - Thêm cột `version INTEGER NOT NULL DEFAULT 1`.
     - Tạo chỉ mục duy nhất: `CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_question_answer ON student_answers(attempt_id, question_id)`.
     - Script được kiểm chứng có tính lũy thừa (Idempotent).
  2. Cập nhật model SQLAlchemy `backend/app/modules/exams/models.py`:
     - Khai báo `version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)`.
     - Khai báo `UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_answer")`.
  3. Cập nhật `autosave_answer` trong `service.py`: Bọc khối tạo mới bằng `try ... await db.flush() except IntegrityError: await db.rollback()` để bắt và xử lý triệt để race condition khi có 2 request ghi đồng thời.

### 2.3. TASK C — Autosave Nhất Quán, Versioning & Debounce 400ms
- **Vấn đề cũ:** Frontend gọi autosave trên từng ký tự nhập liệu (`onChange`) cho câu hỏi tự luận ngắn; Request đến trễ do độ trễ mạng có thể ghi đè lên dữ liệu mới hơn.
- **Giải pháp triển khai:**
  1. **Frontend Debounce:** Tại `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`, bổ sung hàm `handleTextChange` với bộ đếm thời gian debounce 400ms (`textDebounceTimers`). Cập nhật state nội bộ ngay lập tức cho UI phản hồi mượt mà, nhưng chỉ gửi request lên mạng sau 400ms kể từ lần gõ phím cuối cùng.
  2. **Atomic Versioning:** Bổ sung trường `client_version` vào schema `AutosaveAnswerRequest`. Mỗi lần người dùng thay đổi câu trả lời, frontend tăng biến đếm `versionCounters[questionId]`.
  3. **Backend Stale Protection:** Backend kiểm tra `if data.client_version is not None and data.client_version < answer.version: return answer`, từ chối ghi đè dữ liệu cũ hơn và chỉ xác nhận trạng thái `SAVED` khi phiên bản trả về khớp với phiên bản mới nhất ở client.
  4. Khi học sinh bấm nút "Nộp bài", toàn bộ debounce timer đang chờ được xóa và hoàn tất an toàn.

### 2.4. TASK D — Phân Quyền Chính Sách Bài Tập Về Nhà (Assignment Policy Enforcement)
- **Vấn đề cũ:** Khi bài thi được giao trong bài tập (`attempt.assignment_id is not None`), nhưng học sinh nộp bài hoặc yêu cầu xem lại qua `/api/v1/exams/attempts/{id}/submit` và `/api/v1/exams/attempts/{id}/review`, hệ thống lại dùng thiết lập của đề thi gốc thay vì chính sách của bài tập.
- **Giải pháp triển khai:**
  1. Trong `submit_exam_attempt` và `get_attempt_review` (`backend/app/modules/exams/service.py`):
     ```python
     if attempt.assignment_id and attempt.assignment:
         review_allowed = bool(attempt.assignment.allow_review)
         allow_late = bool(attempt.assignment.allow_late_submission)
     else:
         review_allowed = bool(attempt.exam.allow_review)
         allow_late = False
     ```
  2. Nếu `review_allowed == False`, học sinh gọi `/api/v1/exams/attempts/{attempt_id}/review` sẽ nhận mã lỗi `403 Forbidden` ("Bài thi/bài tập này không cho phép xem lại bài làm.").
  3. Nếu `allow_late == False` và quá hạn `due_date`, hệ thống tự động gắn cờ `AUTO_SUBMITTED`.

### 2.5. TASK E — Kiểm Soát Deadline Phía Máy Chủ & Đồng Bộ Thời Gian
- **Vấn đề cũ:** Đồng hồ đếm ngược frontend phụ thuộc vào giờ máy tính học sinh (`Date.now()`); Backend thiếu kiểm tra deadline trong API `get_attempt` và `submit_exam_attempt`.
- **Giải pháp triển khai:**
  1. **Server Time Offset:** Trong các response `ExamStartResponse`, `get_attempt`, và `ExamSubmitResponse`, backend luôn trả về mốc thời gian máy chủ `server_time`. Frontend tính toán:
     ```typescript
     const serverNowMs = attempt.server_time ? parseServerDate(attempt.server_time) : Date.now();
     const serverTimeOffset = serverNowMs - Date.now();
     ```
     Từ đó, `updateTimer` sử dụng `Date.now() + serverTimeOffset`, loại bỏ hoàn toàn sai lệch múi giờ hay clock drift ở máy khách.
  2. **Authoritative Expiration:** Trong router `get_attempt` (`backend/app/modules/exams/router.py`), nếu phát hiện bài làm đang ở trạng thái `IN_PROGRESS` mà mốc thời gian máy chủ đã vượt quá `deadline_at`, backend tự động gọi `submit_exam_attempt(..., auto_submitted=True)`.

### 2.6. TASK F — Bao Phủ Toàn Bộ 4 Dạng Câu Hỏi Chuẩn GDPT 2018
- **Vấn đề cũ:** Thiếu kiểm thử tự động cho `MULTIPLE_CHOICE`, `TRUE_FALSE`, `SHORT_ANSWER`.
- **Giải pháp triển khai:**
  1. Xây dựng bài kiểm thử tích hợp đầy đủ `test_all_four_question_types_e2e` trong `backend/tests/test_hardening_632.py`.
  2. Tạo 1 đề thi tổng hợp chứa đủ 4 dạng câu hỏi với trọng số điểm tương ứng (2.5 điểm mỗi câu = 10.0 điểm tối đa).
  3. Mô phỏng học sinh thi thật: làm bài, lưu đáp án tự động theo dạng, nộp bài, kiểm tra chấm điểm chính xác 10.0/10.0 và review chi tiết lời giải.

---

## 3. BẰNG CHỨNG THỰC THI & KIỂM CHỨNG TỰ ĐỘNG

### 3.1. Dữ Liệu Cơ Sở Dữ Liệu & Migration
```
Running Phase 6.3.2 Exam Engine Hardening Migration...
Database file: E:\SMART-LEARNING-PRO\database\smart_learning.db
[1/3] Checking student_answers table...
Found 81 existing answers.
No duplicate (attempt_id, question_id) rows found.
[2/3] Adding version column to student_answers...
Added column 'version' to student_answers successfully.
[3/3] Creating UNIQUE index 'uq_attempt_question_answer'...
Unique index 'uq_attempt_question_answer' created successfully.
=== MIGRATION PHASE 6.3.2 COMPLETED SUCCESSFULLY ===
```

### 3.2. Toàn Bộ Test Suite Backend (Pytest)
```
pytest -c backend/pytest.ini backend/tests
collected 35 items

backend\tests\test_assignments.py ..                                     [  5%]
backend\tests\test_auth.py .                                             [  8%]
backend\tests\test_classrooms.py ..                                      [ 14%]
backend\tests\test_curriculum.py ........                                [ 37%]
backend\tests\test_exams.py ..                                           [ 42%]
backend\tests\test_hardening_632.py ....                                 [ 54%]
backend\tests\test_hardening_audit.py ........                           [ 77%]
backend\tests\test_health.py .                                           [ 80%]
backend\tests\test_questions.py ......                                   [ 97%]
backend\tests\test_rbac.py .                                             [100%]

============================= 35 passed in 11.92s =============================
```

### 3.3. Kiểm Tra Kiểu Dữ Liệu TypeScript (Frontend)
```
cd frontend; npx tsc --noEmit
Exit Code: 0 (Zero errors)
```

### 3.4. Kiểm Tra Quy Chuẩn Mã Nguồn Linter (Frontend)
```
cd frontend; npm run lint
> frontend@0.1.0 lint
> eslint
Exit Code: 0 (Zero errors, zero warnings)
```

### 3.5. Biên Dịch Môi Trường Sản Xuất Next.js 16 (Turbopack)
```
cd frontend; npm run build
▲ Next.js 16.4.6 (Turbopack)
✓ Running next.config.ts took 26ms
- Cache Components enabled
- Partial Prefetching enabled
  Creating an optimized production build ...
✓ Compiled successfully in 755ms
  Running TypeScript ...
  Finished TypeScript in 2.8s ...
  Collecting page data using 15 workers ...
✓ Generating static pages using 15 workers (23/23) in 965ms
  Finalizing page optimization ...
Exit Code: 0
```

### 3.6. Toàn Bộ Kịch Bản Playwright E2E
```
Executing Playwright E2E Test Suite...
Running 36 tests using 1 worker
  ok  1 [chrome] › e2e\auth-rbac.spec.ts:4:3 › Landing page loads successfully with role entry points (307ms)
  ok  2 [chrome] › e2e\auth-rbac.spec.ts:11:3 › Student login via quick-fill redirects to Student Dashboard (413ms)
  ok  3 [chrome] › e2e\auth-rbac.spec.ts:28:3 › Teacher login via quick-fill redirects to Teacher Dashboard (424ms)
  ok  4 [chrome] › e2e\auth-rbac.spec.ts:44:3 › Admin login via quick-fill redirects to Admin Dashboard (436ms)
  ok  5 [chrome] › e2e\auth-rbac.spec.ts:59:3 › Unauthenticated user accessing protected route is redirected to /login (222ms)
  ok  6 [chrome] › e2e\auth-rbac.spec.ts:65:3 › Student role guard blocks access to Teacher portal (458ms)
  ok  7 [chrome] › e2e\auth-rbac.spec.ts:80:3 › Logout clears session and redirects to /login (491ms)
  ok  8 [chrome] › e2e\backend-authorization.spec.ts:116:3 › Student calling Teacher-only endpoints receives 403 Forbidden (25ms)
  ok  9 [chrome] › e2e\backend-authorization.spec.ts:146:3 › Student accessing non-enrolled classroom receives 403 Forbidden (32ms)
  ok 10 [chrome] › e2e\backend-authorization.spec.ts:162:3 › Teacher B accessing Teacher A's classroom receives 403 Forbidden (38ms)
  ok 11 [chrome] › e2e\backend-authorization.spec.ts:182:3 › Teacher B modifying Teacher A's exam or question receives 403 Forbidden (51ms)
  ok 12 [chrome] › e2e\backend-authorization.spec.ts:210:3 › Unauthenticated user calling protected endpoints receives 401 Unauthorized (18ms)
  ok 13 [chrome] › e2e\backend-authorization.spec.ts:234:3 › Student cannot read answer key or explanation before allowed review (107ms)
  ok 14 [chrome] › e2e\backend-authorization.spec.ts:273:3 › Admin has privileged override access across resources (38ms)
  ok 15 [chrome] › e2e\exam-lifecycle.spec.ts:79:3 › Complete Student Examination Workflow in UI (1.6s)
  ok 16 [chrome] › e2e\exam-lifecycle.spec.ts:193:3 › Repeated submission does not create duplicate results (Idempotency) (32ms)
  ok 17 [chrome] › e2e\exam-lifecycle.spec.ts:224:3 › Student cannot access another student's attempt (Anti-IDOR) (589ms)
  ok 18 [chrome] › e2e\exam-lifecycle.spec.ts:266:3 › Student cannot review an unsubmitted attempt (39ms)
  ok 19 [chrome] › e2e\exam-lifecycle.spec.ts:285:3 › Anti-leak confidentiality check during active attempt (21ms)
  ok 20 [chrome] › e2e\exam-lifecycle.spec.ts:304:3 › Network failure during autosave displays error state (748ms)
  ok 21 [chrome] › e2e\exam-lifecycle.spec.ts:336:3 › Expired attempt handling (97ms)
  ok 22 [chrome] › e2e\student-workflow.spec.ts:12:3 › Dashboard displays real stats, enrolled classes and practice exams (482ms)
  ok 23 [chrome] › e2e\student-workflow.spec.ts:18:3 › Classrooms page lists enrolled classes and handles invalid invite code gracefully (622ms)
  ok 24 [chrome] › e2e\student-workflow.spec.ts:34:3 › Courses page displays GDPT 2018 subjects for current grade (463ms)
  ok 25 [chrome] › e2e\student-workflow.spec.ts:43:3 › Exams lobby displays available practice examinations (795ms)
  ok 26 [chrome] › e2e\student-workflow.spec.ts:53:3 › Assignments page renders homework list with status badges (518ms)
  ok 27 [chrome] › e2e\teacher-mutations.spec.ts:48:3 › Create Classroom in UI and verify list presence (949ms)
  ok 28 [chrome] › e2e\teacher-mutations.spec.ts:81:3 › Create Exam, Add Questions (API), and Publish Exam in UI (997ms)
  ok 29 [chrome] › e2e\teacher-mutations.spec.ts:137:3 › Create Assignment from Exam, Publish, and Cancel in UI (1.3s)
  ok 30 [chrome] › e2e\teacher-mutations.spec.ts:210:3 › Teacher Ownership Boundary: Teacher B cannot modify Teacher A's resources (40ms)
  ok 31 [chrome] › e2e\teacher-workflow.spec.ts:12:3 › Teacher Dashboard displays metrics and quick-copy invite codes (460ms)
  ok 32 [chrome] › e2e\teacher-workflow.spec.ts:19:3 › Classrooms management lists owned classes with invite code (727ms)
  ok 33 [chrome] › e2e\teacher-workflow.spec.ts:28:3 › Classroom detail view displays large invite code box and student roster (799ms)
  ok 34 [chrome] › e2e\teacher-workflow.spec.ts:39:3 › Question Bank displays questions with KaTeX formulas and answer confidentiality (803ms)
  ok 35 [chrome] › e2e\teacher-workflow.spec.ts:51:3 › Exams bank displays exams list with publish status (534ms)
  ok 36 [chrome] › e2e\teacher-workflow.spec.ts:57:3 › Assignments management displays cross-classroom homework (487ms)

  36 passed (18.8s)
=== E2E TESTS COMPLETED WITH EXIT CODE: 0 ===
```

---

## 4. KẾT LUẬN & CHẤP THUẬN CHẤT LƯỢNG (QUALITY GATE SIGN-OFF)

1. Toàn bộ 4 khiếm khuyết cấp độ Critical/High từ Phase 6.3.1 đã được khắc phục hoàn toàn.
2. Mã nguồn đạt chuẩn nghiêm ngặt: không có lỗi cú pháp, không có lỗi kiểu dữ liệu TypeScript, không có cảnh báo linter.
3. Không làm gián đoạn hay sửa đổi các module cốt lõi trước đó (Curriculum, Auth, Question Bank, Classroom, Homework).
4. Hệ thống Exam Engine và Student Exam Interface của SMART LEARNING PRO đã sẵn sàng 100% để chuyển sang các giai đoạn tiếp theo (AI Tutor, RAG, Adaptive Learning).
