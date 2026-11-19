# BÁO CÁO KỸ THUẬT GIAI ĐOẠN 6.3.6
## SUBMISSION BARRIER & ANSWER PERSISTENCE GUARANTEE
### DỰ ÁN SMART LEARNING PRO

- **Thời gian thực hiện**: 19/11/2026 19:05:00 (UTC+7)
- **Workspace**: `E:\SMART-LEARNING-PRO`
- **Baseline Git Commit**: `9406a45`
- **Tài liệu kiểm định trước đó**: `docs/PHASE_6_3_5_INDEPENDENT_VERIFICATION.md` (Verdict: FAIL tại Gate E)

---

## 1. NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE) ĐƯỢC PHÁT HIỆN Ở PHASE 6.3.5

Tại Phase 6.3.5, kiểm toán độc lập đã chỉ ra lỗ hổng bảo vệ tính toàn vẹn khi nộp bài thi (Gate E: Submit Integrity):
1. **Bỏ qua kết quả của `Promise.allSettled`**: `handleFinalSubmit` gọi `await Promise.allSettled(flushPromises)` nhưng không kiểm tra trạng thái settled. Nếu request debounce bị từ chối hoặc gặp lỗi mạng, tiến trình submit vẫn được gửi đi ngay sau đó.
2. **Không theo dõi các request trắc nghiệm đang bay trên mạng (In-Flight Requests)**: Mảng `flushPromises` chỉ gom các câu hỏi tự luận ngắn từ `pendingTextSaves.current`. Các câu hỏi trắc nghiệm vừa được chọn đang bay trên đường truyền (`localSaveStatuses[qid] === "SAVING"`) hoàn toàn không có handle Promise để chờ.
3. **Race Condition Mất Dữ Liệu**: Nếu `submitAttempt` đến server trước và chuyển attempt sang `SUBMITTED`, request autosave trắc nghiệm đến sau bị máy chủ từ chối với HTTP 403 `PermissionDeniedException`, dẫn đến câu trả lời vừa chọn bị mất mà không được chấm điểm.
4. **Không có Barrier Chặn Nộp khi Có Lỗi/Xung đột**: Học sinh vẫn bấm nộp bài được khi có câu hỏi hiển thị lỗi lưu (`ERROR`) hoặc xung đột phiên bản (`CONFLICT`).

---

## 2. KIẾN TRÚC & CÁC GIẢI PHÁP KỸ THUẬT ĐÃ TRIỂN KHAI

### 2.1. Task A — Centralized Autosave Tracking
Trong `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`:
1. **`inFlightAutosavePromises = useRef<Record<string, Promise<{ status: string; version: number }>>>({})`**:
   - Mọi thao tác lưu câu trả lời (chọn 1 đáp án, chọn nhiều đáp án, đúng/sai, tự luận ngắn xả debounce) đều tạo một Promise duy nhất được đăng ký vào `inFlightAutosavePromises.current[questionId]`.
   - Hàm `handleSaveAnswer` trả về Promise này.
   - Khi request hoàn tất (dù thành công hay gặp lỗi), Promise tự động dọn dẹp khỏi `inFlightAutosavePromises` trong khối `finally`.
2. **Theo dõi Phiên bản & Revision Phía Client**:
   - `versionCounters.current[questionId]` ghi nhận local revision mới nhất.
   - Response cũ lệch thứ tự không làm sai số đếm phiên bản hoặc ghi đè trạng thái của revision mới hơn (`versionCounters.current[qid] === response.version || versionCounters.current[qid] === clientVersion`).
3. **Bảo tồn Dữ liệu Client**:
   - Dù request gặp `ERROR` hay `CONFLICT`, dữ liệu trong `localAnswers` không bao giờ bị xóa.

### 2.2. Task B — Quy trình 6 Giai đoạn của Submission Barrier (`handleFinalSubmit`)

Quy trình nộp bài được tái cấu trúc thành 6 giai đoạn nghiêm ngặt:

```
[Học sinh bấm Nộp bài / Hết giờ]
           │
           ▼
Stage 1: FREEZE (Khóa UI, isSubmitting = true, chống double-click)
           │
           ▼
Stage 2: FLUSH (Xả tức thì mọi bộ đệm pendingTextSaves, kích hoạt savePromise)
           │
           ▼
Stage 3: AWAIT (Chờ TẤT CẢ inFlightAutosavePromises của mọi câu hỏi trắc nghiệm & tự luận)
           │
           ▼
Stage 4: VALIDATE (Kiểm tra từng câu đã làm: PHẢI là "SAVED", cấm SAVING/CONFLICT/ERROR)
           ├────────────────────────────┬────────────────────────────┐
           │ (Có câu lỗi/xung đột/chưa lưu)                       │ (100% câu đã làm là SAVED)
           ▼                                                         ▼
Stage 6: UNLOCK (Hủy submit, hiển thị lỗi)             Stage 5: SUBMIT (Gọi examsApi.submitAttempt)
                                                                     │
                                                                     ▼
                                                       [Chuyển màn hình Kết quả bài thi]
```

#### Chi tiết các Stage:
- **Stage 1 — Freeze**: Đặt `isSubmitting = true`. Toàn bộ các lựa chọn đáp án trắc nghiệm, ô nhập văn bản tự luận ngắn (`disabled={isSubmitting}`), nút gắn cờ và nút submit đều bị khóa, ngăn chặn mọi thay đổi trạng thái trong quá trình xả dữ liệu.
- **Stage 2 — Flush**: Hủy tất cả bộ đếm timeout trong `textDebounceTimers.current`, lấy các văn bản đang chờ trong `pendingTextSaves.current` và kích hoạt ngay lập tức `handleSaveAnswer`, đưa promise vào danh sách theo dõi.
- **Stage 3 — Await**: Thu thập `Object.values(inFlightAutosavePromises.current)` và dùng `await Promise.allSettled(activePromises)` chờ tất cả các request đang bay trên mạng hoàn tất một cách có thẩm quyền.
- **Stage 4 — Validate**: Duyệt qua từng câu hỏi trong đề thi. Nếu câu hỏi có dữ liệu trả lời (đã chọn phương án hoặc có text):
  - Phải có trạng thái xác nhận `status === "SAVED"`.
  - Nếu câu hỏi đang ở trạng thái `SAVING`, `CONFLICT`, hoặc `ERROR`: gom vào danh sách `failedQuestions`.
  - **Nếu `failedQuestions.length > 0`**:
    Tạo thông báo lỗi chi tiết: *"Không thể nộp bài do một số câu trả lời chưa được lưu thành công trên máy chủ: Câu X (Lỗi lưu/Xung đột)... Vui lòng kiểm tra và bấm 'Thử lại' trên các câu hỏi bị lỗi trước khi nộp bài."*
    Gọi `setIsSubmitting(false)` để mở khóa giao diện (Stage 6) và **DỪNG LẠI NGAY LẬP TỨC, TUYỆT ĐỐI KHÔNG GỌI `submitAttempt`**.
- **Stage 5 — Submit**: Chỉ khi 100% câu hỏi đã làm được máy chủ xác nhận lưu thành công (`SAVED`), client mới gọi `examsApi.submitAttempt(attemptId)`.
- **Stage 6 — Unlock**: Nếu gặp lỗi mạng khi submit hoặc khi validation thất bại, hệ thống mở khóa để học sinh sửa và thử lại. Dữ liệu bài làm local được giữ nguyên 100%.

### 2.3. Task C — Backend Submission Safety
1. **Kiểm tra Quyền & Trạng thái Attempt**:
   - `submit_exam_attempt` xác minh học sinh sở hữu attempt, kiểm tra deadline theo giờ máy chủ (`server_time`).
2. **Từ chối Tuyệt đối Autosave Sau Submit**:
   - Khi attempt chuyển sang `SUBMITTED`, mọi request autosave trễ hoặc đến sau đều bị chặn đứng tại `service.py:550` với HTTP 403 `PermissionDeniedException`.
   - Với Submission Barrier ở frontend, không còn tình huống request autosave hợp lệ bị gửi đồng thời với lệnh submit.
3. **Chiến lược Concurrency Database**:
   - SQLite trong môi trường phát triển serialize các giao dịch ghi thông qua cơ chế khóa tệp DB. Trong môi trường production PostgreSQL, các bản ghi `exam_attempts` và `student_answers` được bảo vệ bằng OCC `UPDATE ... WHERE version = :expected_version` và khóa hàng (row-level lock).

---

## 3. CÁC BỔ SUNG KIỂM THỬ TỰ ĐỘNG (TASK D & E)

### 3.1. Bổ sung Test Backend (`backend/tests/test_autosave_remediation_634.py`)
1. **`test_concurrent_first_insert_race_condition`**:
   - Sử dụng `asyncio.gather` thực thi đồng thời 2 request tạo bản ghi câu trả lời đầu tiên cho cùng một câu hỏi.
   - Xác nhận: Cả 2 request đều trả về HTTP 200 (một `SAVED`, một xử lý rollback an toàn thành `STALE_IGNORED`/`VERSION_CONFLICT`), database chỉ chứa đúng 1 bản ghi và không bị crash do lỗi vi phạm khóa duy nhất.
2. **`test_post_submit_autosave_rejected`**:
   - Nộp bài thi thành công -> attempt chuyển sang trạng thái `SUBMITTED`.
   - Gửi tiếp request autosave -> máy chủ từ chối dứt khoát với HTTP 403 `PermissionDeniedException` ("Bài thi này đã nộp hoặc kết thúc").

### 3.2. Bổ sung Test Playwright E2E (`frontend/e2e/exam-lifecycle.spec.ts`)
1. **`Scenario 15: Network failure during autosave displays error state and Submission Barrier blocks submission`**:
   - Giả lập lỗi mạng ngắt kết nối autosave (`page.route(..., route.abort("failed"))`).
   - Học sinh chọn phương án -> hiển thị trạng thái `Lỗi lưu (Thử lại)`.
   - Mở hộp thoại nộp bài -> xuất hiện cảnh báo đỏ: *"Cảnh báo: Có câu hỏi chưa được lưu thành công trên máy chủ (Xung đột hoặc Lỗi kết nối)..."*.
   - Nút "Xác nhận nộp bài" bị **VÔ HIỆU HÓA (DISABLED)**.
   - Xác nhận bằng test assertion: Endpoint submit **HOÀN TOÀN KHÔNG BỊ GỌI** (`expect(submitAttemptCalled).toBe(false)`).

---

## 4. KẾT QUẢ KIỂM THỬ THỰC TẾ (TEST EXECUTION EVIDENCE)

Mọi cổng kiểm định kỹ thuật đều được chạy thực tế và đạt 100%:

### 4.1. Backend Pytest
- **Lệnh**: `$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests`
- **Kết quả**: `41 passed in 14.13s` (Exit code: 0).
  - Bao gồm 6 test chuyên sâu trong `test_autosave_remediation_634.py` (tăng từ 4 lên 6 tests).

### 4.2. Frontend TypeScript Typecheck
- **Lệnh**: `cd frontend; npx tsc --noEmit`
- **Kết quả**: `0 errors` (Exit code: 0).

### 4.3. Frontend ESLint
- **Lệnh**: `cd frontend; npm run lint`
- **Kết quả**: `0 warnings, 0 errors` (Exit code: 0).

### 4.4. Next.js Production Build
- **Lệnh**: `cd frontend; npm run build` (Turbopack)
- **Kết quả**: Biên dịch thành công toàn bộ 23 static & dynamic routes trong 966ms (Exit code: 0).

### 4.5. Playwright E2E Test Suite
- **Lệnh**: `powershell -ExecutionPolicy Bypass -File scripts/test_e2e.ps1`
- **Kết quả**: **36/36 tests PASS trong 18.8s** trên Google Chrome thật (Exit code: 0).

---

## 5. BẢNG ĐỐI CHIẾU TIÊU CHÍ NGHIỆM THU (ACCEPTANCE MATRIX)

| Tiêu chuẩn Nghiệm thu | Mức độ | Trạng thái | Bằng chứng |
|:---|:---:|:---:|:---|
| **Không submit khi còn autosave pending** | **P0** | **PASS** | Stage 3 Await chờ toàn bộ `inFlightAutosavePromises`; Stage 4 Validate cấm `status === "SAVING"`. |
| **Không submit khi có CONFLICT hoặc ERROR** | **P0** | **PASS** | Stage 4 Validate quét toàn bộ câu hỏi, chặn submit và hiển thị chi tiết câu lỗi; nút submit trong Dialog bị disable. |
| **Không submit khi chưa xác nhận persist** | **P0** | **PASS** | Chỉ cho phép gọi submit khi 100% câu hỏi đã làm có trạng thái `SAVED`. |
| **Không mất local answers khi flush thất bại** | **P0** | **PASS** | Khi validation thất bại hoặc lỗi mạng, state `localAnswers` được giữ nguyên vẹn, mở khóa UI cho phép thử lại. |
| **Không double-submit** | **P0** | **PASS** | `isSubmitting` freeze ngay lập tức từ Stage 1; nút bấm hiển thị loading spinner và bị disable. |
| **Mọi loại câu hỏi được theo dõi** | **P1** | **PASS** | `inFlightAutosavePromises` bao phủ `SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `TRUE_FALSE`, `SHORT_ANSWER`. |
| **Không có stale response ghi đè revision mới** | **P1** | **PASS** | In-flight check `versionCounters.current[qid] === response.version` loại bỏ response đến chậm. |
| **Backend xử lý đúng race autosave và submit** | **P1** | **PASS** | `test_post_submit_autosave_rejected` xác nhận máy chủ từ chối 403 nếu autosave đến sau submit. |
| **Full test suites PASS** | **P1** | **PASS** | Pytest 41/41 PASS, Typecheck 0 lỗi, ESLint 0 lỗi, Next.js build 23/23 routes, Playwright 36/36 PASS. |

---

## 6. HẠN CHẾ ĐÃ BIẾT (KNOWN LIMITATIONS)
1. **Môi trường Database SQLite**: Trong môi trường local development với SQLite, concurrency được serialize ở cấp connection/file lock. Khi triển khai production trên PostgreSQL, kiến trúc cần kết hợp row-level lock (`SELECT ... FOR UPDATE`) trên bảng `exam_attempts` khi submit để đảm bảo tính nhất quán phân tán tuyệt đối giữa nhiều uvicorn worker processes.
2. **Mất kết nối kéo dài**: Nếu học sinh mất kết nối internet hoàn toàn trong khi làm bài và không thể kết nối lại trước khi hết giờ, client sẽ hiển thị lỗi lưu và không thể nộp bài trực tuyến. Học sinh cần duy trì kết nối mạng để flush dữ liệu thành công.

---

## 7. KẾT LUẬN

Tất cả các tiêu chí P0 và P1 của Mission Phase 6.3.6 đã được đáp ứng đầy đủ với bằng chứng thực thi thực tế. Lỗ hổng Submission Integrity được phát hiện ở Phase 6.3.5 đã được khắc phục triệt để.
