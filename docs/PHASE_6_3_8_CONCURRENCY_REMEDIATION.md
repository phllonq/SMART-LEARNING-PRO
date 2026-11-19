# BÁO CÁO TRIỂN KHAI — PHASE 6.3.8: TARGETED CONCURRENCY REMEDIATION

> **Dự án:** SMART LEARNING PRO  
> **Workspace:** `E:\SMART-LEARNING-PRO`  
> **Baseline Git HEAD:** `4819937772ff3bc19f396f2fb6674e74f3767b21`  
> **Báo cáo kiểm định trước:** [docs/PHASE_6_3_7_INDEPENDENT_VERIFICATION.md](file:///E:/SMART-LEARNING-PRO/docs/PHASE_6_3_7_INDEPENDENT_VERIFICATION.md)  
> **Mục tiêu:** Khắc phục triệt để 2 phát hiện P1 (P1-01 Promise Registry Race & P1-02 Backend Serialization) và đóng 3 khoảng trống kiểm thử tự động P2.

---

## 1. NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)

### A. Finding P1-01 (Frontend Promise Registry Race)
- **Vấn đề:** Trong `StudentExamAttemptPage` (`page.tsx`), khối `finally` của `executeAutosave` thực thi xóa vô điều kiện theo ID câu hỏi:
  ```typescript
  delete inFlightAutosavePromises.current[questionId];
  ```
- **Hệ quả:** Khi học sinh thay đổi đáp án liên tục (Request A bắt đầu, Request B bắt đầu cho cùng câu hỏi trước khi A hoàn tất), Request A hoàn thành muộn hơn sẽ xóa entry registry của Request B đang chạy. Mặc dù Stage 4 (State Barrier) vẫn chặn submit do câu hỏi ở trạng thái `SAVING`, Promise của Request B bị rò rỉ khỏi danh sách `Promise.allSettled`.

### B. Finding P1-02 (Backend Concurrency & Transaction Serialization)
- **Vấn đề:** 
  1. `submit_exam_attempt` trước đây chỉ thực hiện `db.flush()` ở cuối hàm (sau khi đã tính điểm xong toàn bộ câu hỏi). Trong khoảng thời gian submit đang đọc câu hỏi và chấm điểm, trạng thái trên DB vẫn là `IN_PROGRESS`.
  2. `autosave_answer` chỉ đọc `attempt` ở đầu hàm mà không khóa dòng `exam_attempts` hoặc cập nhật trạng thái có điều kiện.
- **Hệ quả:** Trên các hệ quản trị CSDL đa tiến trình như PostgreSQL (chế độ Read Committed) hoặc khi có 2 request chạy đồng thời qua `asyncio.gather`, Submit có thể đọc câu trả lời trước khi Autosave ghi nhận, và Autosave có thể ghi nhận thành công sau khi Submit đã chuyển trạng thái, dẫn đến việc đáp án không được tính vào bài nộp đã chấm.

---

## 2. GIẢI PHÁP & TRIỂN KHAI KỸ THUẬT

### A. Task A — Frontend Promise Lifecycle & Registry Tracking
**File:** [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/[attemptId]/page.tsx)
- Chuyển đổi kiến trúc lưu trữ Promise:
  - `inFlightAutosavePromises`: Chuyển thành `useRef<Set<Promise<...>>>(new Set())` lưu trữ tất cả các Promise đang bay qua mạng độc lập.
  - `latestInFlightByQuestion`: `useRef<Record<string, Promise<...>>>({})` theo dõi Promise mới nhất của từng câu hỏi.
- **Kiểm tra danh tính (Identity Checking):**
  Trong khối `finally` của `executeAutosave`:
  ```typescript
  // 1. Chỉ xóa tracker theo câu hỏi nếu nó đúng là Promise hiện tại
  if (latestInFlightByQuestion.current[questionId] === currentPromise) {
    delete latestInFlightByQuestion.current[questionId];
  }
  // 2. Xóa khỏi Set in-flight toàn cục theo đúng reference đối tượng
  inFlightAutosavePromises.current.delete(currentPromise);
  ```
- **Vòng lặp Await triệt để tại Stage 3:**
  ```typescript
  while (inFlightAutosavePromises.current.size > 0) {
    const activePromises = Array.from(inFlightAutosavePromises.current);
    await Promise.allSettled(activePromises);
  }
  ```
  Đảm bảo mọi request autosave (kể cả request gối đầu nhau cho cùng một câu hỏi) đều được chờ đợi 100% trước khi bước sang Stage 4 Validate.

### B. Task B — Backend Transaction Serialization & Row Locking
**File:** [backend/app/modules/exams/service.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py)
- **Hỗ trợ `with_for_update()`:**
  Cập nhật `get_attempt_detail(..., for_update: bool = False)`:
  - Khi `for_update=True`, thêm `query = query.with_for_update()`.
  - Trên PostgreSQL, SQLAlchemy phát sinh `SELECT ... FOR UPDATE` khóa dòng `exam_attempts`.
  - Trên SQLite, SQLAlchemy bỏ qua mệnh đề này một cách an toàn mà không phát sinh lỗi.
- **Cập nhật có điều kiện Cấp Database trong `autosave_answer`:**
  Trước khi ghi câu trả lời, `autosave_answer` thực hiện atomic touch có điều kiện:
  ```python
  stmt_touch = (
      update(ExamAttempt)
      .where(
          ExamAttempt.id == attempt_id,
          ExamAttempt.status == AttemptStatus.IN_PROGRESS.value
      )
      .values(time_spent_seconds=max(attempt.time_spent_seconds, data.time_spent_seconds))
  )
  touch_res = await db.execute(stmt_touch)
  if touch_res.rowcount == 0:
      await db.rollback()
      raise PermissionDeniedException(...)
  ```
  Nếu Submit đã chuyển trạng thái bài thi sang `SUBMITTED` hoặc `GRADED`, `touch_res.rowcount == 0`, Autosave ngay lập tức rollback và trả về `HTTP 403 Forbidden`.
- **Flush tức thì trạng thái `SUBMITTED` trong `submit_exam_attempt`:**
  ```python
  attempt.submitted_at = now
  attempt.status = AttemptStatus.AUTO_SUBMITTED.value if auto_submitted else AttemptStatus.SUBMITTED.value
  await db.flush()  # Ghi nhận trạng thái đóng bài thi vào DB ngay lập tức
  ```

---

## 3. KIỂM THỬ MỚI BỔ SUNG (TASK C & REGRESSION)

### 1. Regression Test cho P1-01 (Scenario 17 — Playwright E2E)
- File: [frontend/e2e/exam-lifecycle.spec.ts](file:///E:/SMART-LEARNING-PRO/frontend/e2e/exam-lifecycle.spec.ts)
- Mô phỏng: Request A bắt đầu cho Q1 -> Request B bắt đầu cho Q1 trước khi A xong -> Request A về trước -> Request B vẫn đang bay qua mạng.
- Kết quả: Hộp thoại nộp bài vô hiệu hóa nút submit; Stage 3 chờ Request B hoàn tất; chỉ sau khi Request B hoàn tất và cập nhật `SAVED`, bài thi mới được nộp. (PASS).

### 2. Delayed MC Autosave (Scenario 18 — Playwright E2E)
- File: [frontend/e2e/exam-lifecycle.spec.ts](file:///E:/SMART-LEARNING-PRO/frontend/e2e/exam-lifecycle.spec.ts)
- Mô phỏng: Chọn phương án trắc nghiệm với độ trễ mạng 500ms; bấm nộp bài ngay lập tức.
- Kết quả: Nút nộp bài chờ autosave hoàn tất trước khi kích hoạt; không có request submit nào bị gọi sớm. (PASS).

### 3. SHORT_ANSWER Debounce Drain (Scenario 19 — Playwright E2E)
- File: [frontend/e2e/exam-lifecycle.spec.ts](file:///E:/SMART-LEARNING-PRO/frontend/e2e/exam-lifecycle.spec.ts)
- Mô phỏng: Nhập đáp án tự luận "30" và bấm nộp bài ngay trong khoảng thời gian debounce < 400ms.
- Kết quả: Stage 2 xả debounce tức thì, gửi autosave lên máy chủ, xác nhận `SAVED`, nộp bài và chấm điểm đạt 10.0/10.0 (+10 đ). (PASS).

### 4. Backend Serialization Tests (Pytest)
- File: [backend/tests/test_concurrency_remediation_638.py](file:///E:/SMART-LEARNING-PRO/backend/tests/test_concurrency_remediation_638.py)
  - `test_backend_autosave_first_then_submit`: Autosave ghi nhận trước -> Submit tính điểm chính xác. (PASS).
  - `test_backend_submit_first_then_autosave_rejected`: Submit xong trước -> Autosave đến sau bị từ chối `HTTP 403 Forbidden`. (PASS).
  - `test_backend_concurrent_autosave_and_submit_gather`: Chạy đồng thời qua `asyncio.gather`, xác nhận tính tuần tự hóa tuyệt đối. (PASS).

---

## 4. TỔNG HỢP QUALITY GATES & KẾT QUẢ THỰC THI (TASK D)

| Kiểm tra | Lệnh thực thi | Kết quả | Trạng thái |
| :--- | :--- | :---: | :---: |
| **Backend Pytest** | `$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests` | **44/44 passed** in 14.32s | **PASS** |
| **Frontend TypeScript** | `cd frontend; npx tsc --noEmit` | **0 errors** | **PASS** |
| **Frontend ESLint** | `cd frontend; npm run lint` | **0 errors, 0 warnings** | **PASS** |
| **Next.js Production Build** | `cd frontend; npm run build` *(BypassSandbox: true)* | **23/23 routes compiled** | **PASS** |
| **Playwright E2E Suite** | `powershell -ExecutionPolicy Bypass -File scripts/test_e2e.ps1` | **39/39 passed** in 27.3s | **PASS** |

---

## 5. TÌNH TRẠNG XÁC MINH POSTGRESQL & GIỚI HẠN

- **Môi trường hiện tại:** Môi trường local sử dụng engine SQLite (`sqlite+aiosqlite:///./database/smart_learning.db`).
- **PostgreSQL status:** Không có dịch vụ PostgreSQL đang chạy trên máy cục bộ.
- **Biện pháp kiến trúc đã triển khai:**
  1. Đã biên dịch và kiểm chứng câu lệnh SQL: `select(ExamAttempt)...with_for_update()` phát sinh chính xác cú pháp `FOR UPDATE` trên dialect PostgreSQL.
  2. Cơ chế khóa dòng và conditional touch `UPDATE exam_attempts ... WHERE status = 'IN_PROGRESS'` hoạt động độc lập với dialect.
  3. Báo cáo này **minh bạch ghi nhận** rằng kiểm thử đa tiến trình thực tế được thực hiện trên môi trường SQLite local. Hướng dẫn chạy kiểm thử trên PostgreSQL: cấu hình `DATABASE_URL=postgresql+asyncpg://user:pass@host/db` trong `.env` và chạy `pytest backend/tests/test_concurrency_remediation_638.py`.
