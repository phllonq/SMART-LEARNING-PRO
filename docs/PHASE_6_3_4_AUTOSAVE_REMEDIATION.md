# BÁO CÁO KỸ THUẬT GIAI ĐOẠN 6.3.4
## KHẮC PHỤC TRIỆT ĐỂ LỖI ĐỒNG BỘ PHIÊN BẢN AUTOSAVE & TÍNH NHẤT QUÁN DỮ LIỆU KHI TẢI LẠI TRANG
### DỰ ÁN SMART LEARNING PRO

- **Thời gian thực hiện**: 19/11/2026
- **Workspace**: `E:\SMART-LEARNING-PRO`
- **Baseline Git Commit**: `7b490e3`
- **Tài liệu kiểm tra độc lập trước đó**: `docs/PHASE_6_3_3_INDEPENDENT_VERIFICATION.md`

---

## 1. TỔNG QUAN VÀ PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)

### 1.1. Hiện tượng khuyết tật được phát hiện tại Phase 6.3.3
Tại Phase 6.3.3 (`docs/PHASE_6_3_3_INDEPENDENT_VERIFICATION.md`), kiểm toán độc lập đã phát hiện một khiếm khuyết nghiêm trọng liên quan đến cơ chế tự động lưu (autosave) bài thi của học sinh:
- Sau khi học sinh tải lại trang (nhấn F5 hoặc mở lại bài thi đang làm dở), `useRef` lưu trữ số thứ tự phiên bản phía frontend (`versionCounters = useRef<Record<string, number>>({})`) bị khởi tạo lại về `{}` (rỗng).
- Khi học sinh thay đổi đáp án hoặc nhập câu trả lời mới, client tính toán `currentVersion = (versionCounters.current[qid] || 0) + 1 = 1`.
- Request gửi lên máy chủ với `client_version = 1`. Tuy nhiên, trong cơ sở dữ liệu, bản ghi câu trả lời này đã có `answer.version >= 2` (do đã từng lưu trước đó).
- Tại backend `service.py:609`, phép kiểm tra `if client_version < answer.version` đánh giá request này là "gói tin trễ/lạc hậu" (stale) nên âm thầm bỏ qua không ghi đè vào DB.
- Đồng thời, backend router vẫn trả về `status: "SAVED"`.
- **Hệ quả thực tế**: Giao diện học sinh hiển thị huy hiệu xanh lá "Đã lưu máy chủ", nhưng dữ liệu mới hoàn toàn không được lưu trữ vào DB. Nếu nộp bài thi, đáp án mới bị mất trắng.

### 1.2. Hạn chế của kiến trúc cũ
1. **Frontend không khôi phục trạng thái phiên bản**: `AttemptDetailResponse` trả về trường `version` trong `saved_answers[qid].version`, nhưng frontend chưa đồng bộ vào `versionCounters.current`.
2. **Thiếu cơ chế Conditional Update cấp Database (OCC)**: Kiểm tra phiên bản diễn ra ở bộ nhớ Python trước khi gọi `UPDATE`, dẫn đến nguy cơ xung đột đua (race condition) khi nhiều tab cùng lưu.
3. **Thông điệp trạng thái không trung thực**: Bất kỳ request nào (kể cả bị bỏ qua do phiên bản cũ) đều nhận phản hồi `status: "SAVED"`.
4. **Mất dữ liệu câu trả lời ngắn (SHORT_ANSWER) khi nộp bài gấp**: Nếu học sinh vừa gõ xong câu trả lời ngắn mà bấm "Nộp bài" ngay trong khoảng thời gian debounce (400ms), bộ đếm thời gian bị hủy mà không được xả (drain/flush) vào DB trước khi nộp.

---

## 2. KIẾN TRÚC & GIAO THỨC ĐỒNG BỘ PHIÊN BẢN (OCC PROTOCOL)

### 2.1. Cấu trúc dữ liệu và Hợp đồng API

#### Request Payload (`AutosaveAnswerRequest`):
```json
{
  "selected_option_id": "opt-uuid-string",
  "selected_option_ids": ["opt-1", "opt-2"],
  "answer_text": "Đáp án câu hỏi ngắn",
  "is_flagged": false,
  "time_spent_seconds": 120,
  "client_version": 3,
  "expected_version": 2
}
```

#### Response Payload (`AutosaveAnswerResponse`):
```json
{
  "status": "SAVED | VERSION_CONFLICT | STALE_IGNORED",
  "attempt_id": "attempt-uuid",
  "question_id": "q-uuid",
  "version": 3,
  "saved_at": "2026-11-19T11:30:00Z",
  "selected_option_id": "opt-uuid-string",
  "selected_option_ids": ["opt-1", "opt-2"],
  "answer_text": "Đáp án câu hỏi ngắn"
}
```

### 2.2. Ma trận Trạng thái Phản hồi

| Tình huống | Điều kiện kỹ thuật | HTTP Code | Status trả về | Hành động Frontend |
|:---|:---|:---:|:---:|:---|
| **Lưu thành công** | `expected_version == answer.version` hoặc tạo mới v1 | 200 | `SAVED` | Cập nhật `versionCounters = response.version`, hiển thị "Đã lưu máy chủ" |
| **Xung đột phiên bản đa tab** | `expected_version != answer.version` hoặc DB OCC `rowcount == 0` | 200 | `VERSION_CONFLICT` | Cập nhật `versionCounters = response.version`, hiển thị huy hiệu vàng "Xung đột lưu (Thử lại)", giữ nguyên dữ liệu vừa nhập |
| **Gói tin đến trễ / Lạc hậu** | `client_version <= answer.version` (không có expected_version) | 200 | `STALE_IGNORED` | Bỏ qua ghi đè, đồng bộ `versionCounters = response.version` |
| **Hết hạn làm bài** | `now > deadline_at` | 400 | Exception | Tự động chuyển sang trạng thái nộp bài |

---

## 3. CÁC THAY ĐỔI ĐÃ TRIỂN KHAI

### 3.1. Backend (`backend/app/modules/exams/`)

1. **`schemas.py`**:
   - Bổ sung trường `expected_version: Optional[int] = None` vào `AutosaveAnswerRequest`.
   - Bổ sung `selected_option_id`, `selected_option_ids`, `answer_text` vào `AutosaveAnswerResponse` để client luôn có thể đối chiếu dữ liệu được máy chủ chấp nhận.

2. **`service.py` (`autosave_answer`)**:
   - Chuyển đổi toàn bộ quy trình cập nhật câu trả lời sang **Atomic Conditional Update** cấp cơ sở dữ liệu:
     ```python
     stmt = (
         update(StudentAnswer)
         .where(
             StudentAnswer.id == answer.id,
             StudentAnswer.version == expected_version
         )
         .values(...)
     )
     ```
   - Xử lý race condition khi tạo câu trả lời lần đầu: Sử dụng khối `try...except IntegrityError` để bắt xung đột khóa duy nhất `uq_student_answers_attempt_question` và tự động rollback, truy xuất bản ghi chiến thắng để tiếp tục xử lý.
   - Trả về tuple phân loại rõ ràng: `("SAVED", answer)`, `("VERSION_CONFLICT", answer)`, `("STALE_IGNORED", answer)`.

3. **`router.py` (`PUT /attempts/{attempt_id}/answers/{question_id}`)**:
   - Trả về trạng thái lưu thực tế do `service` xác nhận (`save_status`). Tuyệt đối không giả mạo `SAVED` khi câu trả lời không được ghi xuống database.

### 3.2. Frontend (`frontend/src/`)

1. **`types/index.ts`**:
   - Cập nhật định nghĩa TypeScript cho `AutosaveAnswerRequest` (`expected_version?: number`) và `AutosaveAnswerResponse` (`selected_option_id`, `selected_option_ids`, `answer_text`).

2. **`StudentExamAttemptPage` (`page.tsx`)**:
   - **Khôi phục phiên bản sau Reload**:
     ```typescript
     useEffect(() => {
       if (attempt?.saved_answers) {
         for (const [qid, ans] of Object.entries(attempt.saved_answers)) {
           const serverVer = typeof ans.version === "number" ? ans.version : 1;
           if (serverVer > (versionCounters.current[qid] || 0)) {
             versionCounters.current[qid] = serverVer;
           }
         }
       }
     }, [attempt?.saved_answers]);
     ```
   - **Đồng bộ hóa gửi và nhận phiên bản**:
     Tính toán `baseVersion` từ giá trị lớn nhất giữa `versionCounters.current[qid]` và `attempt.saved_answers[qid].version`. Gửi cả `expected_version: baseVersion` và `client_version: baseVersion + 1`.
   - **Xử lý xung đột (Conflict Handling)**:
     Hỗ trợ trạng thái `"CONFLICT"`. Nếu gặp xung đột phiên bản giữa 2 tab, hiển thị nút màu hổ phách: `Xung đột lưu (Thử lại)`. Khi học sinh bấm thử lại, hàm gửi lại đáp án hiện tại với `expected_version` mới nhất từ máy chủ, tránh làm mất thao tác của học sinh.
   - **Drain/Flush Debounce khi nộp bài**:
     Bổ sung `pendingTextSaves.current`. Trong `handleFinalSubmit`, toàn bộ bộ đếm debounce của các câu hỏi ngắn đang gõ dở được hủy và xả ngay lập tức qua `Promise.allSettled` trước khi gọi `examsApi.submitAttempt`.

---

## 4. KẾT QUẢ KIỂM THỬ VÀ BẰNG CHỨNG XÁC THỰC

### 4.1. Kiểm thử đơn vị & Tích hợp Backend (Pytest)
Đã tạo tệp kiểm thử chuyên sâu mới `backend/tests/test_autosave_remediation_634.py`:
- `test_autosave_page_reload_consistency`: Kiểm tra tải lại trang (F5), khôi phục phiên bản, gửi tiếp đáp án v3 và xác nhận ghi nhận thành công trên DB.
- `test_autosave_atomic_occ_and_version_conflict`: Kiểm tra 2 tab đồng thời cùng sửa trên một phiên bản; tab 1 thành công (v2 `SAVED`), tab 2 nhận `VERSION_CONFLICT`, sau đó tab 2 thử lại với v2 -> thành công lên v3.
- `test_autosave_stale_request_rejection`: Kiểm tra gói tin đến trễ `client_version <= current_version` bị trả về `STALE_IGNORED` và không ghi đè đáp án mới hơn.
- `test_autosave_short_answer_lifecycle`: Kiểm tra gõ đáp án câu hỏi ngắn qua các phiên bản.

**Kết quả thực thi Pytest toàn bộ dự án**:
```text
collected 39 items

backend\tests\test_assignments.py ..                                     [  5%]
backend\tests\test_auth.py .                                             [  7%]
backend\tests\test_autosave_remediation_634.py ....                      [ 17%]
backend\tests\test_classrooms.py ..                                      [ 23%]
backend\tests\test_curriculum.py ........                                [ 43%]
backend\tests\test_exams.py ..                                           [ 48%]
backend\tests\test_hardening_632.py ....                                 [ 58%]
backend\tests\test_hardening_audit.py ........                           [ 79%]
backend\tests\test_health.py .                                           [ 82%]
backend\tests\test_questions.py ......                                   [ 97%]
backend\tests\test_rbac.py .                                             [100%]

============================= 39 passed in 8.93s ==============================
```
**Exit Code**: `0`

### 4.2. Kiểm tra chất lượng mã nguồn Frontend (Type Check & Linter)
1. **TypeScript Type Check**:
   ```bash
   cd frontend; npx tsc --noEmit
   ```
   **Kết quả**: Không có lỗi (`Exit Code: 0`).
2. **ESLint**:
   ```bash
   cd frontend; npm run lint
   ```
   **Kết quả**: 0 warnings, 0 errors (`Exit Code: 0`).

### 4.3. Kiểm thử đóng gói Production (Next.js Build)
```bash
cd frontend; npm run build
```
```text
▲ Next.js 16.4.6 (Turbopack)
✓ Compiled successfully in 950ms
  Running TypeScript ...
  Finished TypeScript in 2.7s ...
✓ Generating static pages using 15 workers (23/23) in 1009ms
  Finalizing page optimization ...

Route (app)
┌ ○ /
├ ○ /admin/dashboard
├ ○ /login
├ ○ /register
├ ○ /student/assignments
├ ○ /student/classrooms
├ ○ /student/courses
├ ○ /student/dashboard
├ ○ /student/exams
├   /student/exams/[id]
├   /student/exams/attempts/[attemptId]
...
```
**Kết quả**: Đóng gói 23/23 routes thành công (`Exit Code: 0`).

### 4.4. Kiểm thử End-to-End (Playwright E2E Test Suite)
Kịch bản E2E kiểm thử chu trình bài thi học sinh (`e2e/exam-lifecycle.spec.ts`) đã được mở rộng để bao gồm bước kiểm tra tải lại trang (reload) và đổi đáp án sau reload:
```bash
powershell -ExecutionPolicy Bypass -File scripts/test_e2e.ps1
```
```text
Running 36 tests using 1 worker

  ok  1 [chrome] › e2e\auth-rbac.spec.ts:4:3 › Landing page loads successfully with role entry points (269ms)
  ...
  ok 15 [chrome] › e2e\exam-lifecycle.spec.ts:79:3 › Scenarios 1-10: Complete Student Examination Workflow in UI (1.4s)
  ok 16 [chrome] › e2e\exam-lifecycle.spec.ts:201:3 › Scenario 11: Repeated submission does not create duplicate results (Idempotency) (25ms)
  ok 17 [chrome] › e2e\exam-lifecycle.spec.ts:232:3 › Scenario 12: Student cannot access another student's attempt (Anti-IDOR) (503ms)
  ok 18 [chrome] › e2e\exam-lifecycle.spec.ts:274:3 › Scenario 13: Student cannot review an unsubmitted attempt (47ms)
  ok 19 [chrome] › e2e\exam-lifecycle.spec.ts:293:3 › Scenario 14: Anti-leak confidentiality check during active attempt (15ms)
  ok 20 [chrome] › e2e\exam-lifecycle.spec.ts:312:3 › Scenario 15: Network failure during autosave displays error state (648ms)
  ok 21 [chrome] › e2e\exam-lifecycle.spec.ts:344:3 › Scenario 16: Expired attempt handling (98ms)
  ...
  ok 36 [chrome] › e2e\teacher-workflow.spec.ts:57:3 › Assignments management displays cross-classroom homework (418ms)

  36 passed (16.0s)
Cleaning up server processes...
=== E2E TESTS COMPLETED WITH EXIT CODE: 0 ===
```
**Kết quả**: 36/36 test cases E2E đạt 100% (`Exit Code: 0`).

---

## 5. KẾT LUẬN & KIẾN NGHỊ

Khuyết tật mất dữ liệu autosave sau khi reload trang đã được khắc phục triệt để và toàn diện ở cả 3 tầng:
1. **Database / ORM**: Conditional SQL Update bảo đảm tính nguyên tử và loại trừ triệt để race conditions.
2. **Backend API**: Giao thức OCC trả về trạng thái trung thực (`SAVED`, `VERSION_CONFLICT`, `STALE_IGNORED`).
3. **Frontend UI**: Tự động khôi phục phiên bản khi mở/tải lại bài thi, xử lý xung đột đa tab và xả dữ liệu debounce an toàn trước khi nộp bài.

Mọi cổng kiểm định kỹ thuật (Pytest 39/39, Type Check, ESLint, Next.js Production Build, Playwright E2E 36/36) đều đạt 100%. Hệ thống sẵn sàng cho các giai đoạn tiếp theo.
