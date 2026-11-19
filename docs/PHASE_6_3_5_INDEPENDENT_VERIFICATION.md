# BÁO CÁO KIỂM ĐỊNH ĐỘC LẬP GIAI ĐOẠN 6.3.5
## READ-ONLY AUDIT: AUTOSAVE CONCURRENCY, TRANSACTION SAFETY & SUBMISSION INTEGRITY
### DỰ ÁN SMART LEARNING PRO

- **Thời gian thực hiện**: 19/11/2026 18:50:00 (UTC+7)
- **Kiểu kiểm định**: READ-ONLY TECHNICAL AUDIT (Không chỉnh sửa source, không sửa test, không commit)
- **Baseline Git Commit**: `9406a45` (`feat(exam): remediate autosave versioning and reload consistency`)
- **Branch**: `master`

---

## 1. TỔNG QUAN & PHẠM VI KIỂM ĐỊNH (SCOPE OF AUDIT)

Đợt kiểm định này đánh giá độc lập tính chính xác, an toàn giao dịch và tính nhất quán dữ liệu của Phase 6.3.4, đặc biệt tập trung vào:
1. Tính toàn vẹn Git và baseline commit (`9406a45`).
2. Cơ chế Atomic Optimistic Concurrency Control (OCC) và Conditional Update cấp Database.
3. Độ an toàn giao dịch khi xảy ra xung đột bản ghi đầu tiên (`IntegrityError` & Rollback).
4. Khôi phục phiên bản trên Frontend sau khi F5 và phòng ngừa race conditions giữa các response lệch pha.
5. **Tính toàn vẹn khi Nộp bài (`handleFinalSubmit`)** — Tiêu chí ưu tiên cao nhất: Kiểm tra việc xả debounce, xử lý `Promise.allSettled`, trạng thái `SAVING` / `CONFLICT` / `ERROR` khi gửi lệnh `submit`.
6. Đối chiếu bằng chứng kiểm thử thực tế và chạy kiểm tra toàn bộ Quality Gates.

---

## 2. KẾT QUẢ ĐÁNH GIÁ TỪNG CỔNG (GATES A — G)

### GATE A — GIT INTEGRITY

- **Lệnh thực thi**:
  - `git rev-parse HEAD`: `9406a45560cab85382d7a57171d08dca0cca4009`
  - `git status --short`: `(empty - working tree clean)`
  - `git log -1 --oneline`: `9406a45 feat(exam): remediate autosave versioning and reload consistency`
  - `git diff HEAD`: `(empty)`
  - `git diff --cached`: `(empty)`
- **Kết luận Cổng A**: **PASS** (HEAD khớp hoàn toàn `9406a45`, không có thay đổi rò rỉ hay uncommitted).

---

### GATE B — ATOMIC AUTOSAVE

Kiểm tra mã nguồn tại:
- `backend/app/modules/exams/service.py:613-647`
- `backend/app/modules/exams/router.py:122-151`
- `backend/app/modules/exams/schemas.py:109-128`
- `backend/app/modules/exams/models.py:95-117` (`StudentAnswer`)

#### Phân tích chi tiết 9 câu hỏi kỹ thuật:
1. **UPDATE có điều kiện `version == expected_version` có thực thi tại database không?**
   - **CÓ**. Tại `service.py:617-633`, câu lệnh SQLAlchemy `update(StudentAnswer).where(StudentAnswer.id == answer.id, StudentAnswer.version == expected_version)` biên dịch thành `UPDATE student_answers SET ... WHERE id = ? AND version = ?`.
2. **Version có được tăng trong cùng câu lệnh UPDATE không?**
   - **CÓ**. Giá trị `version=target_version` (`target_version = max(answer.version + 1, req_version)`) nằm trực tiếp trong mệnh đề `.values(...)` của câu lệnh UPDATE (line 629).
3. **Hai request đồng thời với cùng `expected_version` có thể cùng ghi thành công không?**
   - **KHÔNG THỂ**. Khi Request 1 cập nhật thành công, row version trong DB đã tăng. Request 2 thực thi với cùng `expected_version` sẽ nhận `rowcount == 0` do điều kiện `WHERE version = expected_version` không còn khớp bất kỳ dòng nào.
4. **`rowcount == 0` được phân loại thế nào?**
   - Tại `service.py:635-640`, `if update_res.rowcount == 0:` kích hoạt `await db.rollback()`, truy vấn lại bản ghi hiện hành qua `existing_query` và trả về `("VERSION_CONFLICT", conflicted_answer)`.
5. **Response có trả về persisted version và persisted answer từ database không?**
   - **CÓ**. Sau `await db.flush()`, `service.py:644` thực hiện `select(StudentAnswer)` đọc lại bản ghi vừa flush và trả về cho router. Router đưa vào `AutosaveAnswerResponse(version=answer.version, selected_option_id=..., selected_option_ids=..., answer_text=...)`.
6. **Có trường hợp trả `SAVED` trước khi transaction commit thành công không?**
   - **VỀ MẶT THỰC THI (Transaction Lifespan)**: Transaction commit diễn ra tại generator dependency `get_db()` (`backend/app/core/database.py:68`) sau khi route handler trả về response model. Bản ghi đã được `flush()` bảo đảm tính toàn vẹn cú pháp và constraint, nhưng commit vật lý của connection chỉ hoàn tất ngay khi kết thúc request. Nếu commit tại `get_db()` gặp lỗi hạ tầng (ví dụ I/O error), FastAPI sẽ rollback và trả về HTTP 500 chứ không gửi HTTP 200 `SAVED` cho client.
7. **Nếu transaction commit thất bại, API trả kết quả gì?**
   - Khối `try...except Exception` tại `get_db()` kích hoạt `await session.rollback(); raise`, dẫn đến HTTP 500 Internal Server Error.
8. **`STALE_IGNORED` có thể làm mất một thay đổi hợp lệ của người dùng không?**
   - Tại `service.py:606`, điều kiện `if data.client_version is not None and data.client_version <= answer.version:` loại bỏ gói tin cũ. Khi học sinh thao tác bình thường, client gửi `client_version = baseVersion + 1` (luôn `> answer.version`), nên không bị nhận nhầm. Trừ trường hợp đặc biệt: nếu phía client gửi liên tiếp hai request với cùng `client_version` mà không tăng số đếm (lỗi logic client), request thứ hai sẽ bị coi là stale.
9. **Phân biệt request trùng lặp, đến trễ và xung đột phiên bản:**
   - **Xung đột phiên bản (VERSION_CONFLICT)**: Client gửi `expected_version` cụ thể nhưng DB đã có `answer.version` khác, hoặc `rowcount == 0` khi update đồng thời.
   - **Đến trễ / Lạc hậu (STALE_IGNORED)**: Client gửi `client_version <= answer.version` mà không có `expected_version` lệch, phản ánh một gói tin cũ trên mạng đến sau một gói tin mới hơn.
   - **Trùng lặp (Duplicate)**: Đến cùng một `client_version` đã được lưu trước đó, bị chặn an toàn qua nhánh `STALE_IGNORED` hoặc `VERSION_CONFLICT`.

- **Kết luận Cổng B**: **PASS**.

---

### GATE C — CONCURRENT FIRST INSERT & TRANSACTION SAFETY

Kiểm tra tại `backend/app/modules/exams/service.py:576-599`:
```python
    if not answer:
        answer = StudentAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            ...
            version=max(req_version, 1),
            answered_at=now
        )
        db.add(answer)
        try:
            await db.flush()
            await db.refresh(answer)
            return "SAVED", answer
        except IntegrityError:
            # Race condition: concurrent autosave inserted the initial record between select and flush
            await db.rollback()
            # Re-fetch the winning record from DB
            ans_res2 = await db.execute(existing_query)
            answer = ans_res2.scalar_one()
```

#### Đánh giá chi tiết:
1. **Unique constraint có ngăn duplicate không?**
   - **CÓ**. Bảng `student_answers` có `UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_answer")` và `UNIQUE INDEX uq_attempt_question_answer`. Khi 2 request cùng tạo ban đầu, request thứ hai bắt buộc văng `IntegrityError`.
2. **`db.rollback()` có làm mất dữ liệu khác trong transaction không?**
   - Trong luồng `autosave_answer`, từ đầu hàm đến trước `db.add(answer)`, chỉ có các câu lệnh `SELECT` (`get_attempt_detail`, `existing_query`). Không có câu lệnh `INSERT`/`UPDATE` nào khác bị ảnh hưởng bởi lệnh `rollback()`.
3. **Trạng thái Session sau rollback**:
   - `AsyncSession.rollback()` đưa session về trạng thái sạch (clean state). Khi câu lệnh `ans_res2 = await db.execute(existing_query)` chạy tiếp theo, SQLAlchemy tự động mở transaction mới hợp lệ trên connection.
4. **Xử lý sau khi lấy lại bản ghi chiến thắng**:
   - Sau khi gán `answer = ans_res2.scalar_one()`, mã nguồn tiếp tục rơi xuống dòng 600 để thực hiện kiểm tra OCC `VERSION_CONFLICT` / `STALE_IGNORED` hoặc UPDATE.
   - Request thua cuộc (với `client_version = 1 <= 1`) được phân loại chính xác là `STALE_IGNORED`, không ghi đè dữ liệu của request chiến thắng.
5. **Điểm quan sát (Observation)**:
   - Chưa có bài test đơn vị nào thực hiện gọi đồng thời 2 coroutine `autosave_answer` bằng `asyncio.gather` để kích hoạt nhánh `except IntegrityError` trong `test_autosave_remediation_634.py` (các test hiện tại thực hiện tuần tự).

- **Kết luận Cổng C**: **PASS** (Logic an toàn về mặt ACID và ORM, ghi nhận thiếu sót test concurrent insert).

---

### GATE D — FRONTEND RELOAD & CONFLICT HANDLING

Kiểm tra `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`:
- Dòng 90–99: `useEffect` khôi phục `versionCounters.current[qid] = serverVer` từ `attempt.saved_answers[qid].version` khi F5 hoặc mở trang.
- Dòng 131–137: `baseVersion = Math.max(versionCounters.current[qid] || 0, attempt.saved_answers?.[qid]?.version || 0)` bảo đảm không bao giờ autosave với version 1 nếu DB đã có version cao hơn.
- Dòng 156–165: Khi người dùng thao tác, `setLocalAnswers` và `setLocalSaveStatuses("SAVING")` phản hồi tức thì trên UI.
- Dòng 178–186:
  ```typescript
  if (response.version && response.version > (versionCounters.current[questionId] || 0)) {
    versionCounters.current[questionId] = response.version;
  }
  if (
    versionCounters.current[questionId] === response.version ||
    versionCounters.current[questionId] === clientVersion
  ) {
    // update status
  }
  ```
  - Nếu Response A (cũ) về sau Response B (mới), `versionCounters` không bị hạ cấp.
  - Trạng thái UI của Response A bị bỏ qua do không khớp `versionCounters.current[questionId]`.
- Dòng 192–196: `VERSION_CONFLICT` và `STALE_IGNORED` kích hoạt trạng thái `CONFLICT`. Dữ liệu `localAnswers` của học sinh **không bị xóa hay ghi đè**.
- Dòng 682–700: Nút bấm *"Xung đột lưu (Thử lại)"* cho phép học sinh gửi lại đáp án hiện tại trên màn hình với version mới nhất của server.

- **Kết luận Cổng D**: **PASS**.

---

### GATE E — SUBMIT INTEGRITY (ƯU TIÊN CAO NHẤT — CRITICAL GATE)

Đọc toàn bộ `handleFinalSubmit` tại [page.tsx](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L266-L308):
```typescript
  // Submit Attempt
  const handleFinalSubmit = useCallback(async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);

    // Drain/flush any pending debounced autosaves before final submission
    const flushPromises: Promise<unknown>[] = [];
    for (const [qid, pending] of Object.entries(pendingTextSaves.current)) {
      if (textDebounceTimers.current[qid]) {
        clearTimeout(textDebounceTimers.current[qid]);
        delete textDebounceTimers.current[qid];
      }
      delete pendingTextSaves.current[qid];
      flushPromises.push(
        handleSaveAnswer(qid, undefined, undefined, pending.text, pending.flagged)
      );
    }
    if (flushPromises.length > 0) {
      await Promise.allSettled(flushPromises);
    }

    try {
      const result = await examsApi.submitAttempt(attemptId);
      setSubmitResult(result);
      setIsSubmitModalOpen(false);
      ...
```

#### Phân tích chi tiết 9 câu hỏi kiểm định:
1. **Sau `Promise.allSettled`, frontend có kiểm tra tất cả Promise thành công không?**
   - **KHÔNG (NO)**. Tại dòng 284, `await Promise.allSettled(flushPromises)` được gọi nhưng kết quả trả về (`PromiseSettledResult[]`) bị bỏ qua hoàn toàn. Không có bước kiểm tra `status === "fulfilled"`.
2. **Có xác nhận từng câu trả lời nhận được trạng thái `SAVED` không?**
   - **KHÔNG (NO)**. Không kiểm tra xem các câu hỏi vừa flush có chuyển thành `SAVED` hay không trước khi gọi `submitAttempt`.
3. **Nếu một request rejected, submit có bị chặn không?**
   - **KHÔNG (NO)**. `Promise.allSettled` không bao giờ reject. Dù autosave thất bại do lỗi mạng hoặc HTTP 500, tiến trình submit vẫn lập tức được gọi ở dòng 288.
4. **Nếu một request trả `VERSION_CONFLICT`, submit có bị chặn không?**
   - **KHÔNG (NO)**. Trong `handleSaveAnswer`, khi server trả `VERSION_CONFLICT`, hàm bắt trạng thái và kết thúc mà không `throw Error`. Promise được coi là fulfilled, và submit vẫn được thực hiện.
5. **Nếu một request trả `STALE_IGNORED`, submit có bị chặn không?**
   - **KHÔNG (NO)**. Tương tự `VERSION_CONFLICT`, `submitAttempt` vẫn chạy bình thường.
6. **Nếu request timeout hoặc mất mạng, local answer có được giữ lại không?**
   - **CÓ (YES)**. `localAnswers` vẫn còn trong state React.
7. **Có thể submit khi vẫn còn câu hỏi ở trạng thái `SAVING`, `CONFLICT` hoặc `ERROR` không?**
   - **CÓ (YES - LỖI NGHIÊM TRỌNG)**. 
     - Mảng `flushPromises` chỉ gom các câu hỏi tự luận ngắn đang nằm trong bộ đệm debounce (`pendingTextSaves.current`).
     - Bất kỳ câu hỏi trắc nghiệm nào (`SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `TRUE_FALSE`) vừa được click chọn ngay trước khi bấm nộp bài đang ở trạng thái `SAVING` (request đang bay trên đường truyền) **HOÀN TOÀN KHÔNG ĐƯỢC THEO DÕI HOẶC CHỜ ĐỢI**.
     - Nếu có câu hỏi đang bị `CONFLICT` hoặc `ERROR`, nút "Xác nhận nộp bài" trong Dialog vẫn kích hoạt `handleFinalSubmit()`, không hề có barrier chặn submit khi `Object.values(localSaveStatuses).some(s => s === "SAVING" || s === "ERROR" || s === "CONFLICT")`.
8. **Có race condition giữa flush debounce / autosave và submit request không?**
   - **CÓ (YES - LỖI MẤT DỮ LIỆU THỰC TẾ)**.
     - Khi một câu hỏi trắc nghiệm đang bay trên mạng (`SAVING`), nếu học sinh bấm "Xác nhận nộp bài", request `POST /submit` được gửi song song.
     - Nếu request `POST /submit` đến server trước, trạng thái attempt chuyển thành `COMPLETED` / `GRADED`.
     - Khi request autosave của câu hỏi trắc nghiệm đến sau, server kiểm tra tại `service.py:550`:
       `if attempt.status != AttemptStatus.IN_PROGRESS.value: raise PermissionDeniedException(...)`
       Và văng HTTP 403.
     - **Hệ quả**: Câu trả lời trắc nghiệm vừa chọn của học sinh bị server từ chối ghi nhận, bài thi bị chấm điểm thiếu câu đó.
9. **Có bảo đảm submit chỉ diễn ra sau khi tất cả answer hợp lệ đã được persist không?**
   - **KHÔNG (NO)**.

#### Đối chiếu Tiêu chí Chấp thuận (Acceptance Condition):
> *"Acceptance condition: Không được gửi submit request nếu còn bất kỳ answer nào chưa được xác nhận lưu thành công hoặc đang có conflict chưa được giải quyết. Nếu không thể bảo đảm điều kiện này, đánh dấu FAIL."*

- **Kết luận Cổng E**: **FAIL**.
- **Mức độ nghiêm trọng**: **P0 — Critical Data Loss & Inconsistent State Vulnerability**.

---

### GATE F — BẢNG ĐỐI CHIẾU KỊCH BẢN KIỂM THỬ

| Scenario | Test exists? | Actually executed? | Result | Location & Notes |
|:---|:---:|:---:|:---:|:---|
| **F5 reload, edit, save** | **YES** | **YES** | **PASS** | `test_autosave_remediation_634.py::test_autosave_page_reload_consistency` & `e2e/exam-lifecycle.spec.ts` (Scenarios 7-8). |
| **Two tabs same answer (OCC)** | **YES** | **YES** | **PASS** | `test_autosave_remediation_634.py::test_autosave_atomic_occ_and_version_conflict`. |
| **Out-of-order requests** | **YES** | **YES** | **PASS** | `test_autosave_remediation_634.py::test_autosave_stale_request_rejection` & `test_hardening_audit.py:156`. |
| **Concurrent first insert** | **NO** | **NO** | **NOT TESTED** | Chưa có test mô phỏng race condition của initial insert qua `asyncio.gather` để kích hoạt `IntegrityError` tại dòng 593. |
| **Stale version conflict** | **YES** | **YES** | **PASS** | `test_autosave_remediation_634.py::test_autosave_atomic_occ_and_version_conflict`. |
| **Network failure** | **YES** | **YES** | **PASS** | `frontend/e2e/exam-lifecycle.spec.ts:312` (Scenario 15: Network route abort). |
| **Retry after conflict** | **YES** | **YES** | **PASS** | `test_autosave_remediation_634.py:219-229`. |
| **Submit while autosave pending** | **NO** | **NO** | **NOT TESTED** | Chưa có test E2E hay backend mô phỏng việc bấm submit trong khi request autosave đang in-flight. |
| **Submit when autosave fails** | **NO** | **NO** | **NOT TESTED** | Chưa có test chặn nộp bài khi câu hỏi đang ở trạng thái `ERROR` hoặc `CONFLICT`. |
| **Duplicate autosave** | **YES** | **YES** | **PASS** | `test_hardening_632.py::test_student_answers_unique_constraint_and_autosave_versions`. |

- **Kết luận Cổng F**: **CONDITIONAL PASS** (6/10 kịch bản có test thực thi PASS; 4/10 kịch bản chưa có test tự động, đặc biệt là các kịch bản submit integrity).

---

### GATE G — THỰC THI KIỂM THỬ THỰC TẾ

Tất cả các lệnh kiểm thử được chạy trực tiếp trên baseline `9406a45` mà không chỉnh sửa bất kỳ tệp tin nào:

1. **Backend Full Pytest Suite**:
   - **Command**: `$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests`
   - **Exit Code**: `0`
   - **Summary**: `39 passed in 13.29s`
2. **Frontend TypeScript Check**:
   - **Command**: `cd frontend; npx tsc --noEmit`
   - **Exit Code**: `0`
   - **Summary**: 0 errors
3. **Frontend ESLint**:
   - **Command**: `cd frontend; npm run lint`
   - **Exit Code**: `0`
   - **Summary**: 0 warnings, 0 errors
4. **Playwright E2E Test Suite**:
   - **Command**: `powershell -ExecutionPolicy Bypass -File scripts/test_e2e.ps1`
   - **Exit Code**: `0`
   - **Summary**: `36 passed in 18.4s` (100% test cases pass trên Google Chrome thật).

- **Kết luận Cổng G**: **PASS**.

---

## 3. DANH SÁCH PHÁT HIỆN KỸ THUẬT (DEFECT FINDINGS)

### FINDING 1 [P0 — CRITICAL]: Thiếu Submission Guard — Có thể Nộp bài khi Đang lưu (SAVING) hoặc Xung đột (CONFLICT / ERROR)
- **Vị trí**: [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L266-L308](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L266-L308) và dòng 1107–1126.
- **Mô tả**:
  1. `handleFinalSubmit` không kiểm tra trạng thái lưu toàn cục. Nếu có bất kỳ câu hỏi nào đang ở trạng thái `"SAVING"`, `"CONFLICT"`, hoặc `"ERROR"`, hệ thống vẫn cho phép người dùng bấm "Xác nhận nộp bài".
  2. Mảng `flushPromises` chỉ chứa các câu trả lời ngắn đang debounce trong `pendingTextSaves`. Nó không theo dõi các request autosave trắc nghiệm đang bay trên mạng.
  3. `await Promise.allSettled(flushPromises)` không kiểm tra kết quả settled. Nếu request debounce bị từ chối hoặc lỗi mạng, lệnh `submitAttempt` vẫn được gửi đi ngay sau đó.
- **Rủi ro thực tế**: Mất bài làm của học sinh nếu nộp bài ngay sau khi chọn đáp án trắc nghiệm hoặc khi mạng chập chờn.
- **Khuyến nghị khắc phục (cho Phase tiếp theo)**:
  - Bổ sung kiểm tra barrier trong `handleFinalSubmit`:
    ```typescript
    // 1. Flush pending debounces and verify fulfillment
    const flushResults = await Promise.allSettled(flushPromises);
    const hasFlushError = flushResults.some(r => r.status === "rejected");
    
    // 2. Check all active question save statuses
    const isAnySaving = Object.values(localSaveStatuses).some(s => s === "SAVING");
    const isAnyConflict = Object.values(localSaveStatuses).some(s => s === "CONFLICT" || s === "ERROR");
    if (hasFlushError || isAnySaving || isAnyConflict) {
      setSubmitError("Một số câu trả lời chưa được lưu thành công hoặc đang gặp xung đột. Vui lòng kiểm tra lại trước khi nộp bài.");
      setIsSubmitting(false);
      return;
    }
    ```
  - Trong Dialog xác nhận nộp bài, vô hiệu hóa nút submit (hoặc cảnh báo đỏ) nếu `isAnySaving || isAnyConflict`.

---

### FINDING 2 [P1 — MEDIUM]: Chưa có Test Tự động cho Race Condition Khởi tạo Ban đầu (Concurrent Initial Insert)
- **Vị trí**: [backend/app/modules/exams/service.py#L589-L598](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L589-L598)
- **Mô tả**: Đoạn code xử lý `IntegrityError` và rollback session khi có 2 request đồng thời khởi tạo câu trả lời lần đầu tiên đã được viết, nhưng chưa có test case nào kích hoạt nhánh này bằng `asyncio.gather` trong bộ test Pytest.
- **Khuyến nghị khắc phục**: Bổ sung test case `test_concurrent_first_insert_race_condition` vào `test_autosave_remediation_634.py`.

---

### FINDING 3 [P2 — MINOR]: Transaction Commit diễn ra ở Generator Teardown
- **Vị trí**: [backend/app/core/database.py#L68](file:///E:/SMART-LEARNING-PRO/backend/app/core/database.py#L68) & [service.py#L642](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L642)
- **Mô tả**: `service.py` gọi `await db.flush()` thay vì `commit()`, để `get_db` thực hiện `commit()`. Đây là chuẩn kiến trúc dependency injection của FastAPI. Tuy nhiên, `status: "SAVED"` được gán ở tầng service trước khi connection thực hiện commit vật lý. Nếu commit gặp lỗi tầng OS/Disk, client sẽ nhận HTTP 500 thay vì HTTP 200, điều này là an toàn (fail-closed), nhưng cần được ghi nhận về mặt kiến trúc.

---

## 4. KẾT LUẬN & VERDICT

Căn cứ theo quy định nghiêm ngặt của Mission:
- Cổng A, B, D, G đạt **PASS**.
- Cổng C đạt **PASS** (có lưu ý P1).
- **Cổng E (Submit Integrity) không đạt điều kiện chấp thuận (Acceptance Condition)**: Hệ thống cho phép thực hiện lệnh submit ngay cả khi có câu hỏi chưa lưu xong (`SAVING`) hoặc đang gặp lỗi/xung đột (`CONFLICT` / `ERROR`), đồng thời không kiểm tra kết quả của `Promise.allSettled`.

Do đó, theo đúng quy tắc đánh giá:
> *"Acceptance condition: Không được gửi submit request nếu còn bất kỳ answer nào chưa được xác nhận lưu thành công hoặc đang có conflict chưa được giải quyết. Nếu không thể bảo đảm điều kiện này, đánh dấu FAIL."*

### **FINAL VERDICT: FAIL**

*(Lưu ý: Không thực hiện commit, không sửa source code hay database. Kết quả này được chuyển cho Phase triển khai khắc phục tiếp theo giải quyết dứt điểm Finding P0 tại Gate E).*
