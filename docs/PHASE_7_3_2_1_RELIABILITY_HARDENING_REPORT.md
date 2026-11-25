# BÁO CÁO TRIỂN KHAI PHASE 7.3.2.1 — CONVERSATION RELIABILITY HARDENING

**Dự án:** SMART-LEARNING-PRO  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Vai trò thực hiện:** Senior Backend Engineer & Reliability Architect  
**Tài liệu tham chiếu audit:** `docs/PHASE_7_3_2_POST_IMPLEMENTATION_AUDIT.md`  
**Ngày hoàn thành:** 25/11/2026  

---

## 1. GIT PREFLIGHT

Kiểm tra trước khi triển khai Phase 7.3.2.1:

```powershell
git rev-parse HEAD
# 72280c9047461948a1b039af7497287105b72ba0

git log -5 --oneline
# 72280c9 Update
# d6326e5 fix(exam): serialize autosave and submission concurrency
# 4819937 feat(exam): implement submission barrier and answer persistence guarantee
# 9406a45 feat(exam): remediate autosave versioning and reload consistency
# 7b490e3 feat(exam): harden exam engine and remediate audit defects

git status --short
#  M backend/app/modules/ai_tutor/__init__.py
#  M backend/app/modules/ai_tutor/schemas.py
# ?? backend/app/modules/ai_tutor/exceptions.py
# ?? backend/app/modules/ai_tutor/services/
# ?? backend/tests/test_ai_tutor_conversation_service_732.py
# ?? docs/PHASE_7_3_2_CONVERSATION_STATE_SERVICE_REPORT.md
# ?? docs/PHASE_7_3_2_POST_IMPLEMENTATION_AUDIT.md
```

- HEAD khớp chính xác `72280c9047461948a1b039af7497287105b72ba0`.
- Không sử dụng `git reset`, `git clean`, `git checkout`, `git restore`, `git commit`, `git push`.
- Không sửa ORM models, database schema hoặc tạo migration Alembic.

---

## 2. FINDINGS ADDRESSED (TỔNG HỢP KHẮC PHỤC CÁC PHÁT HIỆN AUDIT)

| Mã Finding | Mức độ | Trạng thái khắc phục | Tóm tắt giải pháp |
| :--- | :---: | :---: | :--- |
| **SEC-732-M1** | **MEDIUM** | **FIXED** | Ép buộc kiểm tra state machine tại tất cả các đường ghi trạng thái (`build_message_metadata_json`, `apply_message_state_transition`, `_atomic_transition_message`), kết hợp Compare-And-Swap (CAS) trên `metadata_json` và đọc lại trạng thái DB mới nhất (`populate_existing=True`). |
| **SEC-732-L1** | **LOW** | **FIXED** | Thiết kế lại `recover_stale_streaming_messages_batch` kiểm tra trạng thái khóa (`is_locked`), lấy khóa thu hồi độc quyền ngắn hạn trên `conversation_id`, đọc lại hàng DB mới nhất và thực thi CAS `UPDATE` chống race condition tuyệt đối. |
| **SEC-732-L2** | **LOW** | **FIXED** | Áp dụng batching giới hạn tối đa 100 bản ghi ứng viên mỗi lượt (`MAX_RECOVERY_BATCH_SIZE = 100`), sắp xếp ổn định `(created_at ASC, id ASC)`, lọc SQL chuẩn xác theo key-value JSON `"status": "STREAMING"/"PENDING"`, và hỗ trợ keyset pagination qua `(after_created_at, after_id)` và `drain_backlog`. |
| **Bổ sung (Section 5)** | **HARDENING** | **FIXED** | Chặn stale worker ghi đè ở mọi đường (`COMPLETED`, `FAILED`, `INTERRUPTED`, partial content, `conversation.updated_at`), đồng thời phân tách telemetry API phát sinh thực tế vào phiên giao dịch độc lập (`_record_usage_telemetry_isolated`). |

---

## 3. FILES MODIFIED (DANH SÁCH FILE THAY ĐỔI)

1. `backend/app/modules/ai_tutor/services/message_state.py` (Modified):
   - Bổ sung `enforce_transition: bool = True` trong `build_message_metadata_json(...)` để tự động kiểm tra `validate_message_state_transition` mỗi khi truyền `existing_metadata_json`.
   - Thêm hàm `apply_message_state_transition(...)` bảo vệ `version`, `status`, `updated_at` và bảo toàn nguyên vẹn metadata mở rộng không liên quan.
2. `backend/app/modules/ai_tutor/services/conversation_lock.py` (Modified):
   - Bổ sung phương thức `is_locked(conversation_id)` kiểm tra khóa đang hoạt động trên Redis (`exists`) hoặc in-memory fallback.
   - Bổ sung xử lý decode `bytes` an toàn trong `is_lock_owned(...)`.
3. `backend/app/modules/ai_tutor/services/tutor_service.py` (Modified):
   - Khởi tạo assistant placeholder ở trạng thái `PENDING`, xác minh lock ownership và chuyển đổi nguyên tử `PENDING -> STREAMING` trước khi gọi provider.
   - Bổ sung `_atomic_transition_message(...)` đọc dữ liệu DB mới nhất (`populate_existing=True`, `with_for_update()` trên PostgreSQL), xác thực chuyển đổi trạng thái và cập nhật theo cơ chế Compare-And-Swap (`WHERE id = :id AND metadata_json = :expected_old_meta`).
   - Bổ sung kiểm tra `is_lock_owned` trong `_update_message_on_failure` để chặn stale worker ghi trạng thái `FAILED`/`INTERRUPTED` hoặc nội dung dở dang (`partial_content`).
   - Phân tách `_record_usage_telemetry_isolated` cho trường hợp provider đã trả usage thực tế trước khi worker mất lock.
   - Triển khai `RecoveryBatchResult`, `recover_stale_streaming_messages_batch(...)` và nâng cấp `recover_stale_streaming_messages(...)`.
4. `backend/app/modules/ai_tutor/services/__init__.py` & `backend/app/modules/ai_tutor/__init__.py` (Modified):
   - Export `apply_message_state_transition`.
5. `backend/tests/test_ai_tutor_conversation_service_732.py` (Modified):
   - Bổ sung Group G (3 tests), Group H (6 tests — đầy đủ Scenarios A–E + Batching/Keyset pagination), Group I (4 tests — Stale worker write-protection & mocked Redis commands). Tổng cộng 31 test cases.

---

## 4. STATE TRANSITION ENFORCEMENT (SEC-732-M1)

Mọi vị trí cập nhật `AIMessage.metadata_json` trong `ai_tutor` đều đã được rà soát và khóa chặt qua một đường kiểm soát duy nhất:

1. **Khởi tạo ban đầu:**
   - User message: tạo mới với `build_message_metadata_json(status=MessageStatus.COMPLETED)` (`existing_metadata_json=None`).
   - Assistant message placeholder: tạo mới với `build_message_metadata_json(status=MessageStatus.PENDING, model_name=...)`.
2. **Mọi chuyển đổi trạng thái sau khi bản ghi đã tồn tại (`PENDING -> STREAMING`, `STREAMING -> COMPLETED/FAILED/INTERRUPTED`):**
   - Đều đi qua `_atomic_transition_message(...)`.
   - `_atomic_transition_message` luôn truy vấn lại `metadata_json` mới nhất từ DB (`populate_existing=True`), gọi `apply_message_state_transition(...)` -> gọi `validate_message_state_transition(current_status, target_status)`.
   - Mọi chuyển đổi bị cấm (`COMPLETED -> INTERRUPTED`, `COMPLETED -> FAILED`, `FAILED -> COMPLETED`, `INTERRUPTED -> COMPLETED`, `FAILED -> STREAMING`, v.v.) đều bị chặn ngay lập tức bằng `InvalidMessageStateTransitionError`.
   - `build_message_metadata_json` cũng tự động kích hoạt `validate_message_state_transition` nếu có bất kỳ caller nào gọi trực tiếp kèm `existing_metadata_json`.
3. **Backward Compatibility & Preservation:**
   - Các trường mở rộng không liên quan trong `existing_metadata_json` được sao chép bảo toàn khi merge.
   - Dữ liệu cũ không có field `status` được `parse_message_metadata` đọc an toàn là `COMPLETED` và được bảo vệ không bị ghi đè ngược về trạng thái dở dang.

---

## 5. RECOVERY RACE PREVENTION (SEC-732-L1)

Hàm `recover_stale_streaming_messages_batch` loại bỏ hoàn toàn race condition giữa bước kiểm tra Redis lock, đọc DB và commit `INTERRUPTED` bằng cơ chế bảo vệ 3 lớp:

1. **Lớp 1 — Lock Inspection (`is_locked`):** Nếu cuộc hội thoại đang có bất kỳ khóa hợp lệ nào (Worker A vẫn đang stream > 300s nhờ heartbeat, hoặc Worker B mới vừa tiếp quản), recovery bỏ qua ngay lập tức.
2. **Lớp 2 — Exclusive Recovery Lock (`acquire_lock` + `is_lock_owned`):** Trước khi động chạm tới DB, recovery worker phải chiếm được khóa ngắn hạn (`ttl_seconds=15`, `recovery_token = f"recovery-{uuid4()}"`) trên chính `conversation_id` đó và xác minh lại quyền sở hữu khóa. Điều này chặn mọi worker mới hoặc recovery worker thứ hai xen ngang vào cùng conversation trong lúc thu hồi.
3. **Lớp 3 — Authoritative Re-read + SQL Atomic Compare-And-Swap (CAS):** Trong `_atomic_transition_message`, recovery đọc lại trực tiếp hàng dữ liệu từ DB (`populate_existing=True`, có `FOR UPDATE` trên PostgreSQL), xác nhận trạng thái vẫn là `STREAMING` hoặc `PENDING`, rồi thực hiện `UPDATE ai_messages SET metadata_json = :new_meta WHERE id = :id AND metadata_json = :expected_old_meta`. Chỉ khi `rowcount == 1` và `commit()` thành công mới tính `recovered_count += 1`. Nếu bất kỳ worker nào vừa cập nhật trước đó một micro-giây, CAS tự động trả `rowcount == 0` và hủy bỏ an toàn.

*(Lưu ý kỹ thuật thực tế phát hiện trong quá trình test)*:
- Ban đầu khi sử dụng SQL `AIMessage.metadata_json.contains("STREAMING")` trong SQLite, vì `LIKE` của SQLite không phân biệt hoa thường nên đã khớp nhầm vào chuỗi `"Streaming cancelled by client or consumer."` bên trong `error_message` của các bản ghi đã `INTERRUPTED`. Đã khắc phục bằng cách lọc chính xác cặp key-value JSON `'"status": "STREAMING"'` / `'"status":"STREAMING"'` và `'"status": "PENDING"'` / `'"status":"PENDING"'`.
- Ban đầu khi dùng ORM object trong vòng lặp recovery rồi gọi `db.expire(row)`, truy cập `msg.conversation_id` trong `finally:` gây ra `sqlalchemy.exc.MissingGreenlet`. Đã khắc phục bằng cách truy vấn projection các cột scalar `(AIMessage.id, AIMessage.conversation_id, AIMessage.metadata_json, AIMessage.created_at)`.

---

## 6. BATCHING STRATEGY (SEC-732-L2)

- **Giới hạn bộ nhớ & kích thước lô:** `MAX_RECOVERY_BATCH_SIZE = 100` (`safe_batch_size = max(1, min(100, batch_size))`). Không bao giờ tải toàn bộ bảng hay toàn bộ cột `content` vào RAM.
- **Thứ tự ổn định (Deterministic Ordering):** `.order_by(AIMessage.created_at.asc(), AIMessage.id.asc())`.
- **Keyset Pagination:** Hỗ trợ con trỏ `(after_created_at, after_id)` theo điều kiện `(created_at > after_created_at) OR (created_at == after_created_at AND id > after_id)` để không bị bỏ sót hoặc lặp lại bản ghi ngay cả khi đầu danh sách có các active stream đang bị giữ lock.
- **Tùy chọn xử lý tồn đọng:** `recover_stale_streaming_messages(..., drain_backlog=True)` tự động lặp từng batch tối đa 100 bản ghi qua keyset cursor cho đến khi hết tồn đọng (`has_more == False`).

---

## 7. STALE WORKER WRITE-PROTECTION

Mọi thao tác ghi của `SocraticTutorService` đều kiểm tra quyền sở hữu khóa (`is_lock_owned(conversation_id, lock_token)`):

- **`PENDING -> STREAMING`:** Kiểm tra `is_lock_owned` + CAS trước khi gọi LLM.
- **`STREAMING -> COMPLETED`:** Kiểm tra `is_lock_owned` + CAS trước khi ghi nội dung hoàn chỉnh và trước khi cập nhật `AIConversation.updated_at`. Nếu mất khóa hoặc CAS fail (`rowcount != 1`), raise `StaleWorkerException` và không cập nhật trạng thái hội thoại/tin nhắn.
- **`STREAMING -> FAILED / INTERRUPTED` (`_update_message_on_failure`):** Kiểm tra `is_lock_owned` trước khi cập nhật DB (kể cả khi retry qua `_safe_update_message_status`). Worker đã mất khóa tuyệt đối không được đánh dấu `FAILED`/`INTERRUPTED` hoặc ghi `partial_content`.
- **Phân biệt Usage Telemetry thực tế:**
  - Nếu stream thất bại hoặc chưa nhận được usage từ provider -> không tạo `AIUsageLog`.
  - Nếu provider thực sự đã hoàn tất trả token metrics (`last_usage` có `input_tokens` và `output_tokens` hợp lệ) nhưng worker mất lock trước lúc finalize conversation state -> lưu riêng chi phí API đã phát sinh vào phiên giao dịch độc lập (`_record_usage_telemetry_isolated`), tách rời hoàn toàn khỏi trạng thái conversation/message và tuyệt đối không xóa telemetry hợp lệ.

---

## 8. NEW TEST SCENARIOS & EXPLORATORY FAILURES

Các test mới bổ sung vào `backend/tests/test_ai_tutor_conversation_service_732.py` (Groups G, H, I — 13 tests mới):
- **Group G:**
  - `test_forbidden_transitions_enforced_in_metadata_builders`
  - `test_atomic_transition_preserves_unrelated_metadata_and_blocks_terminal_overwrite`
  - `test_backward_compatibility_legacy_metadata_without_status`
- **Group H (Scenarios A–E & Batching):**
  - `test_recovery_scenario_a_active_stream_with_heartbeat_not_recovered` (Real async SQLite DB + In-memory lock manager)
  - `test_recovery_scenario_b_dead_worker_expired_lock_recovered` (Real async SQLite DB + In-memory lock manager)
  - `test_recovery_scenario_c_new_worker_protected` (Real async SQLite DB + In-memory lock manager)
  - `test_recovery_scenario_d_concurrent_recovery_workers_no_conflict` (Real async SQLite DB + concurrent `asyncio.gather`)
  - `test_recovery_scenario_e_terminal_messages_untouched` (Real async SQLite DB)
  - `test_recovery_batching_and_keyset_pagination_backlog` (105 stale + 5 completed trong SQLite DB)
- **Group I (Stale Worker Write-Protection & Mocked Redis):**
  - `test_stale_worker_cannot_mark_failed_or_write_partial_content_on_error`
  - `test_stale_worker_cannot_mark_interrupted_or_write_partial_content_on_cancel`
  - `test_stale_worker_blocks_conversation_update_but_preserves_incurred_usage`
  - `test_mocked_redis_commands_for_lock_operations` (**Mocked Redis unit test** kiểm tra `SET NX EX`, `EXISTS`, `GET` với bytes decoding, Lua `EVAL` — không thay thế cho test Redis cluster thật).

### Các exploratory test fail đã gặp và sửa trong quá trình phát triển:
1. **`MissingGreenlet` trong `test_stale_streaming_recovery`:** Gặp phải khi `recover_stale_streaming_messages_batch` duyệt ORM object sau khi `_atomic_transition_message` gọi `db.expire(row)`. Đã sửa bằng scalar column projection trong query recovery.
2. **SQLite case-insensitive `LIKE '%STREAMING%'` khớp nhầm `error_message`:** Làm batch đầu tiên trong `test_recovery_batching_and_keyset_pagination_backlog` đếm `scanned=100, recovered=95` thay vì `100`. Đã sửa SQL filter thành khớp chính xác cặp key-value JSON `"status": "STREAMING"` / `"status": "PENDING"` và làm sạch dữ liệu cũ trước khi test batching.
3. **`TypeError` keyword arguments trong `spy_acquire` test helper:** `send_message_stream` gọi `acquire_lock(conversation_id=..., lock_token=...)` bằng keyword args trong khi hàm spy trong test nhận positional `(cid, tok)`. Đã cập nhật chữ ký hàm spy khớp tên tham số.

---

## 9. TEST RESULTS (KẾT QUẢ KIỂM THỬ THỰC TẾ SAU SỬA LỖI CUỐI CÙNG)

```powershell
# 1. Phase 7.3.2 + 7.3.2.1 dedicated test suite:
$env:PYTHONPATH='backend'; .venv/Scripts/python.exe -m pytest backend/tests/test_ai_tutor_conversation_service_732.py -v
# Output: 31 passed in 5.40s (Exit code 0)

# 2. AI Engine & AI Tutor combined suites (7.1 + 7.3.1 + 7.3.2 + 7.3.2.1):
$env:PYTHONPATH='backend'; .venv/Scripts/python.exe -m pytest backend/tests/test_ai_tutor_streaming_provider_731.py backend/tests/test_ai_tutor_conversation_service_732.py backend/tests/test_ai_foundation.py -q
# Output: 118 passed in 8.59s (Exit code 0)

# 3. Full backend regression suite:
$env:PYTHONPATH='backend'; .venv/Scripts/python.exe -m pytest backend/tests/ -q
# Output: 265 passed, 1 skipped in 118.25s (0:01:58) (Exit code 0)

# 4. Frontend TypeScript check:
npm --prefix frontend run type-check
# Output: tsc --noEmit (0 errors, Exit code 0)
```

---

## 10. REMAINING LIMITATIONS (GIỚI HẠN CÒN LẠI)

1. **Redis Integration Verification:** Môi trường test cục bộ không chạy Redis daemon thật, do đó các bài test concurrency thực thi trên `InMemoryCache` / in-memory lock guard kết hợp với mocked Redis unit test (`test_mocked_redis_commands_for_lock_operations`). Khả năng distributed lock đa worker qua Redis thật (`SET NX EX` & Lua scripts) đã được xác minh về mặt thiết kế mã nguồn nhưng **chưa chạy integration test trên Redis cluster thực tế**.
2. **Hiệu năng SQLite vs PostgreSQL:** Cơ chế Compare-And-Swap (`WHERE id = :id AND metadata_json = :expected_old_meta`) hoạt động nguyên tử trên cả SQLite và PostgreSQL; khi triển khai PostgreSQL production, `_atomic_transition_message` kích hoạt thêm `.with_for_update()` để khóa hàng cấp database.

---

## 11. GIT STATUS AFTER IMPLEMENTATION

```powershell
git rev-parse HEAD
# 72280c9047461948a1b039af7497287105b72ba0

git status --short
#  M backend/app/modules/ai_tutor/__init__.py
#  M backend/app/modules/ai_tutor/schemas.py
# ?? backend/app/modules/ai_tutor/exceptions.py
# ?? backend/app/modules/ai_tutor/services/
# ?? backend/tests/test_ai_tutor_conversation_service_732.py
# ?? docs/PHASE_7_3_2_CONVERSATION_STATE_SERVICE_REPORT.md
# ?? docs/PHASE_7_3_2_POST_IMPLEMENTATION_AUDIT.md
# ?? docs/PHASE_7_3_2_1_RELIABILITY_HARDENING_REPORT.md
```

---

## 12. FINAL VERDICT

# **FINAL VERDICT: PASS**

- **SEC-732-M1:** **FIXED**
- **SEC-732-L1:** **FIXED**
- **SEC-732-L2:** **FIXED**

Tất cả các phát hiện từ audit đã được khắc phục triệt để, 31/31 test chuyên biệt và 265/265 test hồi quy backend đều PASS (0 lỗi), Frontend type-check sạch sẽ, zero schema mutation, Git HEAD giữ nguyên vẹn. Hệ thống dừng tại đây chờ review trước khi chuyển sang Phase 7.3.3.
