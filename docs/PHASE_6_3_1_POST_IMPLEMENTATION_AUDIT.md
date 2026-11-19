# PHASE 6.3.1 — POST-IMPLEMENTATION TECHNICAL AUDIT REPORT
**SMART LEARNING PRO** — Nền tảng Học tập Thông minh Chuẩn GDPT 2018  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Inspected HEAD:** `ca43c16a22dba95436d1ef0237a67a64c04e032d` (`ca43c16`)  
**Audit Scope:** Phase 6.3 Student Exam Interface Implementation  
**Audit Mode:** READ-ONLY Technical Audit (No source code, database, tests, or Git history modified)  
**Execution Date:** 2026-11-19

---

## 1. EXECUTIVE SUMMARY

Giai đoạn Phase 6.3 đã thành công trong việc xây dựng giao diện phòng thi tương tác học sinh (`/student/exams/[id]` và `/student/exams/attempts/[attemptId]`) kết nối với FastAPI backend, vượt qua 36/36 kịch bản Playwright E2E và 31/31 bài kiểm thử Pytest backend.

Tuy nhiên, cuộc kiểm toán kỹ thuật chuyên sâu (Technical Audit) độc lập tại Phase 6.3.1 đã phát hiện **4 lỗi nghiêm trọng (Critical / High-Risk Defects)** và **4 tồn tại mức trung bình/thấp (Medium / Low-Risk Findings)** mà bộ kiểm thử E2E trước đó chưa bao phủ hết do phạm vi kiểm thử chỉ tập trung vào câu hỏi đơn lựa chọn (`SINGLE_CHOICE`).

### Bảng Tổng Hợp Đánh Giá Theo Danh Mục Audit
| Danh mục kiểm toán | Trạng thái kỹ thuật | Đánh giá rủi ro | Ghi chú cốt lõi |
| :--- | :---: | :---: | :--- |
| **A. Tương thích loại câu hỏi** | **FAIL** / **NOT IMPLEMENTED** | **HIGH** | `SINGLE_CHOICE` hoạt động tốt. `MULTIPLE_CHOICE` và `TRUE_FALSE` có code nhưng `NOT TESTED`. `SHORT_ANSWER` chưa hoàn thiện (`NOT IMPLEMENTED`), rò rỉ đáp án trong snapshot câu hỏi. |
| **B. Thời hạn quy định máy chủ** | **FAIL** (Một phần) | **MEDIUM** | Cơ chế đếm ngược phụ thuộc vào đồng hồ hệ thống của client (`Date.now()`); Backend thiếu kiểm tra deadline trong API nộp bài thủ công (`submit_exam_attempt`). |
| **C. Nhất quán tự động lưu (Autosave)** | **FAIL** | **HIGH** | Chưa có Debounce (mọi phím gõ gửi 1 request); Cơ chế chống ghi đè bằng `time_spent_seconds` không đủ tin cậy; Bảng `student_answers` thiếu Unique Constraint `(attempt_id, question_id)`. |
| **D. Nộp bài và Xử lý Timeout** | **PASS** | **LOW** | Chống nộp trùng lặp (Idempotency) tốt; Chặn sửa đáp án sau khi nộp; Xử lý race condition đồng thời qua rollback `IntegrityError` trên `exam_results`. |
| **E. Tích hợp Bài tập về nhà** | **FAIL** (Ranh giới quyền) | **HIGH** | Attempt liên kết đúng `assignment_id`, nhưng phòng thi nộp bài qua router `/exams/attempts/{id}/submit` dẫn tới bỏ qua thiết lập `allow_late_submission` và `allow_review` của bài tập. |
| **F. An ninh & Bảo mật dữ liệu** | **FAIL** (Một phần) | **HIGH** | Chống IDOR và xác thực tốt. Tuy nhiên câu hỏi `SHORT_ANSWER` bị lộ nội dung đáp án ngay trong payload snapshot câu hỏi khi bắt đầu thi. |

---

## 2. KẾT QUẢ KIỂM TOÁN CHI TIẾT THEO DANH MỤC

### A. TƯƠNG THÍCH CÁC LOẠI CÂU HỎI (QUESTION TYPE COMPATIBILITY)

#### 1. `SINGLE_CHOICE` (Đơn lựa chọn)
- **Backend Schema & DB:** [backend/app/modules/questions/schemas.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/questions/schemas.py#L60-L66) yêu cầu tối thiểu 2 options, đúng 1 option đúng. DB mapped `selected_option_id`.
- **Autosave & Grading:** Lưu `selected_option_id`. Đánh giá so khớp `selected_option_id == correct_opt.id` ([service.py#L716-L719](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L716-L719)).
- **Frontend Rendering:** Radio card selection, đánh dấu viền tím, hiển thị KaTeX ([page.tsx#L682-L718](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L682-L718)).
- **Phân loại:** **PASS** (Được kiểm chứng bằng thực thi tự động trong `backend/tests/test_exams.py` và `frontend/e2e/exam-lifecycle.spec.ts`).

#### 2. `MULTIPLE_CHOICE` (Đa lựa chọn)
- **Backend Schema & DB:** Schema yêu cầu tối thiểu 2 options, tối thiểu 1 option đúng. DB lưu `selected_option_ids_json` dạng Text JSON.
- **Autosave & Grading:** API nhận `selected_option_ids`. Grading so khớp tập hợp `set(student_ids) == set(correct_ids)` ([service.py#L720-L732](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L720-L732)).
- **Frontend Rendering:** Checkbox toggle, lưu mảng IDs ([page.tsx#L719-L760](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L719-L760)).
- **Phân loại:** **NOT TESTED** (Mã nguồn đã xây dựng nhưng chưa có bất kỳ bài kiểm thử đơn vị, tích hợp hay E2E nào kiểm chứng việc lưu và chấm điểm câu hỏi `MULTIPLE_CHOICE`).

#### 3. `TRUE_FALSE` (Đúng / Sai)
- **Backend Schema & DB:** Schema yêu cầu đúng 2 options, đúng 1 option đúng. Tái sử dụng logic lưu và chấm điểm của `SINGLE_CHOICE`.
- **Frontend Rendering:** Tái sử dụng giao diện Single Choice.
- **Phân loại:** **NOT TESTED** (Chưa có test nào trong test suite thực thi câu hỏi `TRUE_FALSE`).

#### 4. `SHORT_ANSWER` (Câu trả lời ngắn)
- **Backend Pydantic Schema:** Tại [backend/app/modules/questions/schemas.py#L51-L81](file:///E:/SMART-LEARNING-PRO/backend/app/modules/questions/schemas.py#L51-L81), validator `validate_options_by_type` hoàn toàn **thiếu nhánh kiểm tra cho `SHORT_ANSWER`**. Nếu giáo viên tạo câu hỏi `SHORT_ANSWER` với `options: []`, hệ thống vẫn chấp nhận `201 Created`, dẫn đến câu hỏi không thể chấm điểm được.
- **Rò rỉ đáp án chuẩn (Lỗ hổng bảo mật nghiêm trọng):**
  - Tại [backend/app/modules/exams/service.py#L416-L435](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L416-L435), khi tạo `sanitized_snapshot` cho học sinh:
  ```python
  sanitized_opts = [
      {"id": o.id, "option_key": o.option_key, "content": o.content, "order_index": i + 1}
      for i, o in enumerate(opts)
  ]
  ```
  - Logic chỉ loại bỏ trường `is_correct`, nhưng **vẫn giữ nguyên `content` của options**. Đối với `SHORT_ANSWER`, nội dung đáp án đúng được lưu trong `QuestionOption.content`. Do đó, toàn bộ danh sách đáp án được chấp nhận **bị gửi trực tiếp về cho học sinh** trong payload câu hỏi khi vừa bắt đầu làm bài!
- **Autosave & Trải nghiệm:** Frontend input gọi trực tiếp `handleSaveAnswer` trên từng sự kiện `onChange` mà không có debounce, gây nghẽn và xung đột gói tin.
- **Hiển thị Review:** Tại [page.tsx#L475](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L475), giao diện xem lại chỉ hiển thị `q.correct_option_keys` (ví dụ `["1"]` hoặc `["A"]`), không hiển thị chuỗi văn bản đáp án đúng và không hiển thị câu trả lời học sinh đã nhập.
- **Phân loại:** **NOT IMPLEMENTED** (Vòng đời câu hỏi bị đứt gãy và rò rỉ dữ liệu, chưa sẵn sàng sử dụng).

---

### B. THỜI HẠN QUY ĐỊNH MÁY CHỦ (SERVER-AUTHORITATIVE DEADLINE)

- **Mốc thời gian bắt đầu & Tính toán hạn chót:** Máy chủ ghi nhận `started_at = now` (UTC) và tính `deadline_at = started_at + timedelta(minutes=exam.duration_minutes)` ([service.py#L394-L400](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L394-L400)).
- **Chuẩn hóa Múi giờ:** Hàm `parseServerDate()` tại [page.tsx#L32-L38](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L32-L38) bổ sung hậu tố `Z` nếu thiếu, đảm bảo chuỗi ISO UTC từ SQLite được diễn giải đúng thành UTC.

#### Đánh giá 5 Trường Hợp Cụ Thể:
1. **Đồng hồ Client chạy trước 10 phút:**
   - *Hành vi thực tế:* Tại [page.tsx#L140](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L140), frontend tính `diffSec = Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000))`. Vì `Date.now()` lấy giờ của máy client, timer đếm lùi về 0:00 sớm hơn 10 phút so với hạn chót thực tế của máy chủ. Giao diện client kích hoạt tự động nộp bài khi học sinh thực tế vẫn còn 10 phút.
   - *Phân loại:* **FAIL** (Đồng hồ đếm ngược client chưa độc lập hoàn toàn với clock của máy trạm).

2. **Đồng hồ Client chạy chậm 10 phút:**
   - *Hành vi thực tế:* Khi máy chủ đã hết giờ làm bài, timer của client vẫn hiển thị còn 10 phút. Nếu học sinh tiếp tục thao tác chọn đáp án, request autosave gửi lên backend bị chặn lại tại [service.py#L547-L551](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L547-L551): Backend tự động nộp bài (`AUTO_SUBMITTED`) và trả về `403 Forbidden`. Học sinh thấy báo lỗi lưu và không thể lưu thêm.
   - *Phân loại:* **PASS** trên backend (Máy chủ chặn lưu sau hạn chót).

3. **Client tải lại trang (Reload/F5) sau khi đã quá hạn chót:**
   - *Hành vi thực tế:* Endpoint `GET /api/v1/exams/attempts/{attempt_id}` ([router.py#L62-L94](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/router.py#L62-L94)) chỉ đọc dữ liệu thô từ DB, **không kiểm tra deadline để chuyển trạng thái sang `AUTO_SUBMITTED`**. Nếu client có đồng hồ chính xác, client nhận `deadline_at`, tính `diffSec <= 0` và kích hoạt `handleFinalSubmit()`. Nhưng nếu client cố tình chỉnh lùi giờ máy trạm, giao diện vẫn hiển thị phòng thi dạng `IN_PROGRESS`.
   - *Phân loại:* **FAIL** (Backend thiếu cơ chế passive auto-submit khi truy vấn GET attempt).

4. **Client gửi lệnh nộp bài sau khi đã quá hạn chót:**
   - *Hành vi thực tế:* Tại [backend/app/modules/exams/service.py#L601-L651](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L601-L651), hàm `submit_exam_attempt` **hoàn toàn không kiểm tra `now > attempt.deadline_at`**. Một học sinh có thể gửi `POST /attempts/{id}/submit` muộn nhiều giờ/ngày sau khi hết giờ, máy chủ vẫn chấp nhận chấm điểm bình thường và gán `status = "SUBMITTED"` (thay vì phân loại là bài nộp quá hạn).
   - *Phân loại:* **FAIL** (Thiếu ràng buộc kiểm tra deadline trong API submit).

5. **Client thực hiện autosave sau hạn chót:**
   - *Hành vi thực tế:* Tại [service.py#L547-L551](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L547-L551), backend so sánh `now > deadline`. Máy chủ tự động kích hoạt `submit_exam_attempt(..., auto_submitted=True)`, chấm điểm các câu đã làm trước đó và raise `403 Forbidden`. Đáp án mới gửi kèm bị loại bỏ.
   - *Phân loại:* **PASS** (Được kiểm chứng qua mã nguồn và logic).

---

### C. NHẤT QUÁN TỰ ĐỘNG LƯU (AUTOSAVE CONSISTENCY)

1. **Thiếu Cơ Chế Debounce (Debounce Missing):**
   - Vị trí: [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L178-L245](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L178-L245).
   - Mặc dù dòng 177 ghi chú `// Debounced/Safe Autosave Handler`, hàm `handleSaveAnswer` là một hàm `async` thông thường, không chứa bất kỳ `setTimeout`, `clearTimeout` hay debounce wrapper nào.
   - Đối với câu hỏi nhập liệu `SHORT_ANSWER`, mỗi ký tự gõ phím đều lập tức kích hoạt một cuộc gọi mạng HTTP PUT.
   - *Phân loại:* **FAIL**.

2. **Cơ chế sắp xếp gói tin bằng `time_spent_seconds` không đảm bảo độ tin cậy:**
   - Vị trí: [backend/app/modules/exams/service.py#L581-L584](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L581-L584).
   ```python
   # Out-of-order protection: discard delayed packet if time_spent is strictly lower than existing recorded time
   if data.time_spent_seconds < answer.time_spent_seconds:
       return answer
   ```
   - Nhược điểm nghiêm trọng:
     a) `time_spent_seconds` được tính trên client bằng `Math.floor(...) / 1000` (độ phân giải 1 giây). Mọi thao tác click hoặc gõ phím diễn ra trong cùng 1 giây đều mang cùng một giá trị `time_spent_seconds`.
     b) Phép toán so sánh sử dụng toán tử `<` (nhỏ hơn nghiêm ngặt). Do đó, khi hai gói tin có cùng `time_spent_seconds` (`5 < 5` là False), backend **không hủy gói tin đến sau**. Nếu gói tin cũ bị trễ mạng và đến sau gói tin mới, đáp án cũ sẽ ghi đè lên đáp án mới!
     c) Tham số này do client tự gửi, không có chữ ký hay cơ chế sequence number / version id từ server.
   - *Phân loại:* **FAIL**.

3. **Thiếu Ràng Buộc Duy Nhất Trong Cơ Sở Dữ Liệu (Missing Unique Constraint):**
   - Vị trí: Bảng `student_answers` ([backend/app/modules/exams/models.py#L95-L113](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/models.py#L95-L113)).
   - Kiểm tra schema SQLite thực tế qua câu lệnh `SELECT sql FROM sqlite_master WHERE name = 'student_answers'`:
     Bảng `student_answers` **hoàn toàn không có Unique Constraint hay Unique Index trên cặp `(attempt_id, question_id)`**!
   - Hệ quả Race Condition: Nếu 2 request autosave cho cùng 1 câu hỏi được gửi tới máy chủ cùng một lúc khi câu hỏi chưa có bản ghi:
     Cả hai tiến trình đều thực hiện `select` và nhận diện `answer is None`. Cả hai đều `db.add(answer)`. Hai bản ghi trùng lặp được tạo ra.
     Ở các lần autosave tiếp theo, dòng lệnh `ans_res.scalar_one_or_none()` ([service.py#L564](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L564)) sẽ phát sinh ngoại lệ `MultipleResultsFound`, làm sập API autosave của học sinh đó với lỗi HTTP 500!
   - *Phân loại:* **FAIL** (Rủi ro lỗi dữ liệu nghiêm trọng).

4. **Xử lý lỗi mạng và Thử lại (Retry):**
   - Client bắt lỗi mạng, hiển thị nút "Lỗi lưu (Thử lại)". Bấm vào nút này sẽ gửi lại request với dữ liệu hiện tại.
   - *Phân loại:* **PASS** (Được kiểm chứng qua Playwright Scenario 15).

---

### D. NỘP BÀI VÀ XỬ LÝ TIMEOUT (SUBMISSION & TIMEOUT)

1. **Nộp bài thủ công (Manual Submission):**
   - Hộp thoại modal xác nhận mở ra, hiển thị thống kê câu hỏi. Bấm "Xác nhận nộp bài" gọi `POST /attempts/{id}/submit`. Chấm điểm tự động và trả kết quả chính xác.
   - *Phân loại:* **PASS** (Kiểm chứng qua Playwright Scenarios 1-10).

2. **Chống nộp bài trùng lặp (Idempotency):**
   - Nộp lại nhiều lần trên bài thi đã nộp trả về đúng kết quả cũ với mã `200 OK` ([service.py#L616-L641](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L616-L641)).
   - *Phân loại:* **PASS** (Kiểm chứng qua Playwright Scenario 11).

3. **Yêu cầu nộp bài đồng thời (Simultaneous Submits):**
   - Khóa duy nhất `unique=True` trên `exam_results.attempt_id` kích hoạt ngoại lệ `IntegrityError` khi có 2 luồng cùng ghi kết quả. Khối `try ... except IntegrityError` tại [service.py#L876-L882](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L876-L882) thực hiện `rollback()` và đệ quy trả về kết quả đã được ghi nhận trước đó mà không nhân đôi điểm XP.
   - *Phân loại:* **PASS** (Kiểm chứng qua mã nguồn và bài test `test_hardening_audit.py`).

4. **Trạng thái bài thi (Status Transitions):**
   - Trạng thái chuyển đổi một chiều: `IN_PROGRESS` -> `SUBMITTED` / `AUTO_SUBMITTED` -> `GRADED`.
   - Khi đã nộp, API autosave từ chối ghi nhận thêm đáp án với mã lỗi 403 Forbidden.
   - *Phân loại:* **PASS** (Kiểm chứng qua thực thi bài test `test_exams.py`).

---

### E. TÍCH HỢP BÀI TẬP VỀ NHÀ (ASSIGNMENT INTEGRATION)

1. **Vòng đời chuyển tiếp bài tập (Workflow Transition):**
   - Danh sách bài tập (`/student/assignments`) -> Bấm "Bắt đầu làm bài" -> Gọi `POST /api/v1/assignments/{id}/start` -> Nhận `attempt_id` -> Chuyển hướng sang `/student/exams/attempts/{attempt_id}`.
   - Trường `assignment_id` được ghi nhận chính xác vào bảng `exam_attempts` ([service.py#L452](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L452)) và được lập chỉ mục `index=True`.
   - Sổ điểm giáo viên (`GET /assignments/{id}/submissions`) truy vấn và hiển thị đúng điểm số của học sinh làm bài tập.
   - *Phân loại:* **PASS** (Kiểm chứng qua thực thi test và mã nguồn).

2. **Lỗ hổng Bỏ qua Chính sách Bài tập (Assignment Policy Bypass Defect):**
   - Vị trí: [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L104](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L104) và [backend/app/modules/exams/service.py#L898](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L898).
   - Mô tả lỗi:
     Khi học sinh làm bài tập về nhà trong phòng thi `/student/exams/attempts/[attemptId]`, việc nộp bài được thực hiện thông qua `examsApi.submitAttempt(attemptId)`, tương ứng với endpoint:
     `POST /api/v1/exams/attempts/{attempt_id}/submit` (thay vì endpoint `POST /api/v1/assignments/{assignment_id}/submit`).
   - Hai hệ quả vi phạm nghiệp vụ:
     a) **Bỏ qua chính sách xem lại bài tập (`allow_review`):**
        Nếu đề thi gốc có `exam.allow_review = True`, nhưng giáo viên tạo bài tập quy định `assignment.allow_review = False` (không cho học sinh xem đáp án bài tập về nhà):
        Do `submit_exam_attempt` và `get_attempt_review` chỉ kiểm tra `attempt.exam.allow_review` ([service.py#L898, L918](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L898)), học sinh vẫn được trả về toàn bộ đáp án chuẩn và lời giải chi tiết, **vô hiệu hóa hoàn toàn thiết lập bảo mật bài tập của giáo viên**!
     b) **Bỏ qua chính sách nộp muộn (`allow_late_submission`):**
        Endpoint `POST /exams/attempts/{id}/submit` không kiểm tra `assignment.allow_late_submission`, cho phép học sinh nộp bài tập quá hạn ngay cả khi giáo viên đã khóa nộp muộn.
   - *Phân loại:* **FAIL** (Lỗi ranh giới nghiệp vụ nghiêm trọng).

---

### F. AN NINH & BẢO MẬT (SECURITY AUDIT)

| Tiêu chí an ninh | Hiện trạng thực tế | Phân loại | Bằng chứng kiểm chứng |
| :--- | :--- | :---: | :--- |
| **Sở hữu Attempt & Chống IDOR** | Học sinh lạ truy cập attempt của người khác bị máy chủ từ chối mã `403 Forbidden`. Frontend hiển thị giao diện khiên đỏ "Không có quyền truy cập". | **PASS** | Kiểm chứng tự động qua Playwright Scenario 12 và Pytest `test_hardening_audit.py`. |
| **Bảo mật Lời giải (Explanation)** | Trường `explanation` bị triệt tiêu hoàn toàn trong snapshot khi đang thi. Gọi `GET /attempts/{in_progress_id}/review` bị chặn 403 Forbidden. | **PASS** | Kiểm chứng tự động qua Playwright Scenarios 13, 14. |
| **Bảo mật Đáp án Trắc nghiệm** | Các loại `SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `TRUE_FALSE` bị lọc sạch trường `is_correct` trong snapshot. | **PASS** | Kiểm chứng tự động qua Playwright Scenario 14. |
| **Bảo mật Đáp án Tự luận Ngắn** | Câu hỏi `SHORT_ANSWER` bị lộ nội dung đáp án đúng ngay trong mảng `options[].content` của snapshot câu hỏi gửi về trình duyệt. | **FAIL** | Phát hiện qua kiểm tra mã nguồn tại [service.py#L417-L420](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L417-L420). |
| **Sửa đổi Đáp án Trái phép** | Endpoint autosave xác thực quyền sở hữu `attempt.student_id == student.id` và trạng thái `attempt.status == IN_PROGRESS`. | **PASS** | Kiểm chứng qua `backend/tests/test_exams.py`. |
| **Lưu trữ Trình duyệt & Nhật ký** | Token xác thực lưu trong `sessionStorage`, không lưu dữ liệu nhạy cảm trong `localStorage`. Không có `console.log` trong code frontend; backend logger không ghi log đáp án hay mật khẩu. | **PASS** | Kiểm chứng qua `git grep` trên toàn bộ thư mục `frontend/src` và `backend/app`. |

---

## 3. DANH SÁCH LỖI NGHIÊM TRỌNG & RỦI RO CAO (CRITICAL & HIGH-RISK DEFECTS)

### DEFECT-01 (CRITICAL — Security Leak): Lộ đáp án câu hỏi `SHORT_ANSWER` trong snapshot câu hỏi
- **Vị trí:** [backend/app/modules/exams/service.py:416-435](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L416-L435).
- **Hành vi thực tế:** Khi tạo snapshot câu hỏi đã lọc (`sanitized_snapshot`), hệ thống chỉ loại bỏ cờ `is_correct`, nhưng giữ nguyên mảng `options` với thuộc tính `content`. Đối với câu hỏi trả lời ngắn, `content` chính là đáp án chấp nhận.
- **Hành vi kỳ vọng:** Câu hỏi dạng `SHORT_ANSWER` phải làm rỗng mảng `options: []` trong snapshot gửi cho học sinh, chỉ lưu trữ phương án so khớp trong `answer_key_snapshot_json` trên máy chủ.
- **Điều kiện tái hiện:** Tạo đề thi có câu hỏi `SHORT_ANSWER`. Học sinh bắt đầu thi, mở DevTools Network tab xem response của `POST /exams/{id}/start` -> Đọc được đáp án trong `questions[i].options[0].content`.

### DEFECT-02 (HIGH — Data Integrity / Concurrency): Thiếu Unique Constraint trên `student_answers` gây lỗi 500
- **Vị trí:** [backend/app/modules/exams/models.py:95-113](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/models.py#L95-L113) và schema bảng `student_answers`.
- **Hành vi thực tế:** Bảng `student_answers` không có ràng buộc duy nhất trên `(attempt_id, question_id)`. Hai request autosave đồng thời có thể tạo 2 bản ghi trùng lặp. Khi đó, câu lệnh `ans_res.scalar_one_or_none()` tại [service.py#L564](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L564) sẽ ném lỗi `MultipleResultsFound`, gây sập API với mã lỗi 500.
- **Hành vi kỳ vọng:** Bảng phải có `UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_answer")`.

### DEFECT-03 (HIGH — Logic Defect / Race Condition): Autosave thiếu debounce và cơ chế sắp xếp gói tin lỗi thời
- **Vị trí:** [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx:178-245](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L178-L245) và [backend/app/modules/exams/service.py:581-584](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L581-L584).
- **Hành vi thực tế:** Không có debounce khi gõ phím. `time_spent_seconds` chỉ có độ phân giải 1 giây. Các gói tin gửi trong cùng 1 giây có `time_spent_seconds` bằng nhau; điều kiện `data.time_spent_seconds < answer.time_spent_seconds` đánh giá `False`, dẫn đến việc gói tin cũ đến sau vẫn ghi đè lên gói tin mới.
- **Hành vi kỳ vọng:** Frontend phải debounce 400-500ms đối với ô nhập văn bản. Backend phải sử dụng version tăng đơn điệu (`version: int`) hoặc so khớp thời điểm chính xác tính bằng millisecond.

### DEFECT-04 (HIGH — Business Policy Bypass): Bỏ qua phân quyền xem lại và nộp muộn của bài tập về nhà
- **Vị trí:** [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx:104](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L104) và [backend/app/modules/exams/service.py:898, 918](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L898).
- **Hành vi thực tế:** Học sinh làm bài tập nộp bài qua router `/exams/attempts/{id}/submit`. Backend kiểm tra `attempt.exam.allow_review` thay vì `attempt.assignment.allow_review`. Giáo viên cấm xem lại bài tập vẫn bị học sinh xem hết đáp án sau khi nộp.
- **Hành vi kỳ vọng:** `submit_exam_attempt` và `get_attempt_review` phải kiểm tra nếu `attempt.assignment_id` tồn tại thì ưu tiên áp dụng chính sách của `assignment` thay vì `exam`.

---

## 4. CÁC TỒN TẠI MỨC TRUNG BÌNH & THẤP (MEDIUM & LOW-RISK FINDINGS)

### FINDING-01 (MEDIUM — Deadline Integrity): Client countdown phụ thuộc vào giờ máy trạm (`Date.now()`)
- **Vị trí:** [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx:140](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L140).
- **Mô tả:** Frontend lấy `nowMs = Date.now()`. Nếu máy học sinh lệch giờ (chạy nhanh hoặc chậm 10 phút), đồng hồ hiển thị sai lệch tương ứng và có thể tự động nộp bài sớm trước hạn.
- **Khắc phục:** Khi nhận response từ máy chủ, tính độ lệch thời gian giữa client và server (`serverTimeOffset = serverNow - clientNow`) và hiệu chỉnh `Date.now() + serverTimeOffset`.

### FINDING-02 (MEDIUM — Missing Validation): Thiếu kiểm tra deadline trong API submit thủ công
- **Vị trí:** [backend/app/modules/exams/service.py:601-651](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L601-L651).
- **Mô tả:** Hàm `submit_exam_attempt` không kiểm tra `if now > attempt.deadline_at`. Học sinh có thể gửi lệnh nộp bài sau hạn chót nhiều ngày mà bài thi vẫn được chấm và gắn nhãn `SUBMITTED` thay vì `AUTO_SUBMITTED` hoặc bị từ chối.
- **Khắc phục:** Thêm kiểm tra `if deadline and now > deadline: auto_submitted = True`.

### FINDING-03 (LOW — UI Review Gap): Giao diện xem lại không hiển thị câu trả lời tự luận của học sinh
- **Vị trí:** [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx:471-490](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L471-L490).
- **Mô tả:** Khi xem lại bài làm, giao diện chỉ hiển thị nội dung câu hỏi và đáp án đúng, không hiển thị lại văn bản học sinh đã nhập đối với câu hỏi trả lời ngắn.

### FINDING-04 (LOW — Test Coverage Gap): `MULTIPLE_CHOICE` và `TRUE_FALSE` chưa có kiểm thử tự động
- **Vị trí:** Toàn bộ thư mục `backend/tests` và `frontend/e2e`.
- **Mô tả:** Mặc dù code đã được viết trên cả backend và frontend, 100% các bài test hiện có chỉ chạy trên `SINGLE_CHOICE`.

---

## 5. KẾ HOẠCH KHẮC PHỤC YÊU CẦU (REQUIRED REMEDIATION)

Để đưa hệ thống đạt chuẩn hoàn thiện trước khi mở rộng tính năng mới, cần thực hiện gói vá lỗi kỹ thuật:

1. **Khắc phục Lỗ hổng Rò rỉ Đáp án `SHORT_ANSWER`:**
   - Trong `start_exam_attempt` ([service.py#L416](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L416)): Nếu `q.question_type == QuestionType.SHORT_ANSWER.value`, thiết lập `sanitized_opts = []`.
   - Trong `QuestionCreate.validate_options_by_type`: Bổ sung kiểm tra bắt buộc có ít nhất 1 đáp án đúng làm mẫu so khớp.

2. **Thêm Ràng buộc Duy nhất cho `student_answers`:**
   - Viết migration script thêm `UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_answer")` vào bảng `student_answers`.
   - Bổ sung `try ... except IntegrityError` trong `autosave_answer` để phòng ngừa race condition khi insert đồng thời.

3. **Bổ sung Debounce & Hoàn thiện Cơ chế Sắp xếp Autosave:**
   - Sử dụng hook `useDebounce` (400ms) trên input của `SHORT_ANSWER`.
   - Bổ sung trường `client_version: int` trong `AutosaveAnswerRequest` và lưu vào `student_answers.version` để đảm bảo gói tin đến muộn không bao giờ ghi đè gói tin có version cao hơn.

4. **Đồng bộ Chính sách Bài tập về nhà với Đề thi:**
   - Trong `submit_exam_attempt` và `get_attempt_review`: Nếu `attempt.assignment_id` tồn tại, truy vấn `assignment` và ghi đè quyền `allow_review = assignment.allow_review` cũng như kiểm tra `allow_late_submission`.

5. **Hiệu chỉnh Đồng hồ Client & Kiểm tra Deadline Backend:**
   - Hiệu chỉnh `serverTimeOffset` trong countdown timer.
   - Bổ sung kiểm tra quá hạn trong `submit_exam_attempt`.

---

## 6. KHUYẾN NGHỊ GIAI ĐOẠN TIẾP THEO

- **Khuyến nghị:** **TẠM DỪNG mở rộng tính năng mới (Phase 7 - AI Engine)** cho đến khi thực hiện xong phiên vá lỗi kỹ thuật **Phase 6.3.2 (Hardening & Remediation)** để giải quyết 4 lỗi nghiêm trọng trên.
- Việc tích hợp AI Socratic Tutor trên một nền tảng thi cử còn tồn tại lỗ hổng rò rỉ đáp án và xung đột autosave sẽ tích lũy nợ kỹ thuật (technical debt) và làm sai lệch dữ liệu đánh giá học sinh.

---

## 7. XÁC NHẬN CHẾ ĐỘ KIỂM TOÁN (AUDIT MODE CONFIRMATION)

- [x] Không có bất kỳ tệp mã nguồn nào (`.py`, `.tsx`, `.ts`, `.js`, `.json`) bị thay đổi trong quá trình kiểm toán.
- [x] Không có bài test nào bị tạo mới hoặc sửa đổi trong kho mã nguồn.
- [x] Không có migration nào được thực thi trên cơ sở dữ liệu dự án.
- [x] Không có commit Git nào được tạo ra. Lịch sử Git giữ nguyên tại commit `ca43c16`.
- [x] Cây thư mục làm việc (`working tree`) hoàn toàn sạch sẽ (`clean`).
