# BÁO CÁO KIỂM TOÁN AN NINH & ĐỒNG THỜI — PHASE 7.2.2.1
## Kiểm toán Chuyên sâu: Lock TTL, Fallback khi Không có Redis & Giới hạn Tenant Isolation

**Dự án:** SMART LEARNING PRO  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Giai đoạn:** Phase 7.2.2.1 — Final Security & Concurrency Audit  
**Ngày thực hiện:** 2026-11-23  
**Trạng thái kiểm toán:** HOÀN THÀNH (10/10 Test Kiểm toán đạt; 173/173 Test Toàn hệ thống Backend đạt 100%)  
**Baseline Git HEAD:** `d6326e5415cb125b62fbe12aea077ecf921d3a88` (Bảo toàn nguyên vẹn)

---

## 1. Mục tiêu Kiểm toán

Thực hiện kiểm toán kỹ thuật độc lập và chuyên sâu đối với `WrongAnswerDiagnosticService` đã xây dựng trong Phase 7.2.2 nhằm trả lời dứt điểm 3 vấn đề an ninh và đồng thời (concurrency):
1. **Lock TTL và Nguy cơ Trùng lặp Yêu cầu AI (Duplicate Requests):** Tính toán thời gian tối đa của một tác vụ AI, so sánh với Lock TTL và thiết lập cơ chế gia hạn khóa (lock renewal) an toàn.
2. **Hành vi Khi Thiếu Redis (Redis-Unavailable Fallback):** Phân định ranh giới giữa điều phối đơn tiến trình (single-process) và đa tiến trình (multi-worker), ghi nhận rõ các giới hạn suy giảm hiệu năng (degraded mode).
3. **Hiện trạng Cô lập Đa người thuê (Tenant Isolation) trên Thực thể Dữ liệu:** Khảo sát toàn bộ model SQLAlchemy thực tế, lập bảng quan hệ và công bố rõ ràng giới hạn kiến trúc về việc schema hiện tại chưa có cột `tenant_id`.

---

## 2. Kiểm toán Lock TTL và Thời lượng Tác vụ AI

### 2.1. Tính toán Thời lượng Tối đa của Tác vụ AI (Maximum Operation Duration)

Dựa trên mã nguồn thực tế:
- **Cấu hình Timeout:** Tại `backend/app/modules/ai_engine/config.py` (dòng 28-39):
  - `AIConfig.timeout_seconds`: Mặc định là `15.0s` (cho phép cấu hình trong khoảng `0.0s < t <= 120.0s`).
  - `AIConfig.max_retries`: Mặc định là `2` (tối đa 3 lần thử: 1 lần gốc + 2 lần retry).
  - `AIConfig.retry_backoff_base`: Mặc định là `0.5s` (lũy thừa cơ số 2 kèm jitter).
- **Cơ chế Retry và Deadline:** Tại `backend/app/modules/ai_engine/retry.py` (`execute_with_retry`, dòng 50-98):
  - Tham số `total_timeout` (mặc định `15.0s`) là **ngân sách thời gian tuyệt đối (overall hard deadline)** bao trùm toàn bộ các lần thử và thời gian chờ backoff.
  - Về mặt lý thuyết, nếu hệ số `AI_TIMEOUT_SECONDS` trong file `.env` được người quản trị nâng lên (ví dụ: `45s` hoặc `60s`), thì thời lượng tác vụ AI có thể kéo dài tương ứng tới con số đó.

### 2.2. Đối chiếu với Lock TTL và Polling Timeout

Trước khi hiệu chỉnh:
- **Lock TTL:** Đặt cố định là `30 giây`.
- **Cache Polling Timeout:** Đặt cố định là `15 giây`.

### 2.3. Trả lời Trực tiếp 6 Câu hỏi Kiểm toán

1. **Tác vụ AI có thể tồn tại lâu hơn Lock TTL không?**
   - **CÓ (trong trường hợp cấu hình mở rộng).** Nếu `AI_TIMEOUT_SECONDS` được cấu hình lớn hơn 30s (ví dụ 45s hoặc 60s), hoặc khi một tác vụ gặp độ trễ mạng tích lũy cộng với xử lý dữ liệu vượt quá 30s, tác vụ AI sẽ vượt quá Lock TTL ban đầu.
   - Thêm vào đó, `DEFAULT_CONCURRENT_WAIT_TIMEOUT = 15.0s` là quá ngắn: nếu Worker 1 chạy mất 18 giây (vẫn trong hạn 30s của lock), Worker 2 sẽ dừng chờ quá sớm trước khi Worker 1 kịp ghi kết quả vào cache.
2. **Yêu cầu khác có thể chiếm khóa khi yêu cầu đầu vẫn đang sinh dữ liệu không?**
   - **CÓ.** Nếu khóa hết hạn trên Redis mà tác vụ AI chưa hoàn tất, Redis tự động giải phóng key `lock:{cache_key}`. Một Worker khác đến sau sẽ thực thi `_acquire_lock()` thành công và kích hoạt thêm một tiến trình gọi AI độc lập thứ hai cho cùng một câu hỏi.
3. **Điều này có gây trùng lặp lượt gọi AI và phát sinh chi phí kép không?**
   - **CÓ.** Cả hai Worker đều gọi đến Google Gemini API (hoặc provider bên ngoài), tiêu tốn token đầu vào/đầu ra và bị tính phí hai lần cho cùng một lỗi sai của học sinh.
4. **Cơ chế gia hạn khóa (Lock Renewal) đã được triển khai chưa?**
   - Tại Phase 7.2.2 ban đầu: **CHƯA.** Khóa chỉ được gán TTL tĩnh một lần lúc acquire.
5. **Cơ chế giải phóng khóa (Lock Release) có xác minh quyền sở hữu token không?**
   - **CÓ.** Tại `service.py` (dòng 573-616), việc giải phóng khóa trên Redis sử dụng Lua Script nguyên tử (`if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end`), và trên bộ nhớ kiểm tra `existing_token == lock_token`. Do đó, một worker chạy trễ không thể xóa nhầm khóa của worker mới.
6. **Điều gì xảy ra khi worker ban đầu bị sự cố (Crash / SIGKILL)?**
   - Khóa có TTL hữu hạn trên Redis nên sau khi worker chết, key tự động hết hạn, giải phóng tài nguyên và tránh hoàn toàn tình trạng deadlock vĩnh viễn.

### 2.4. Hiệu chỉnh Tối thiểu & An toàn Đã Triển khai

Để loại bỏ triệt để rủi ro trên mà không làm xáo trộn kiến trúc:
1. **Tính toán Lock TTL Động (`_calculate_lock_ttl`):**
   - Công thức: `effective_lock_ttl = max(DEFAULT_LOCK_TTL_SECONDS, int(total_timeout + 15.0))`
   - Trong đó `DEFAULT_LOCK_TTL_SECONDS` được nâng lên `45 giây` (với timeout 15s chuẩn, lock kéo dài 45s, vượt xa thời gian thực thi).
   - `_calculate_poll_timeout()` được đồng bộ thành `max(DEFAULT_CONCURRENT_WAIT_TIMEOUT, float(total_timeout + 5.0))` (tối thiểu `20.0s`).
2. **Cơ chế Heartbeat Gia hạn Khóa Tự động (`_heartbeat_worker` & `_renew_lock`):**
   - Khi Worker chiếm khóa thành công, một background task asyncio định kỳ (mỗi `effective_lock_ttl / 3` giây) sẽ gửi lệnh gia hạn khóa (`EXPIRE`) tới Redis qua Lua script có kiểm tra quyền sở hữu token:
     ```lua
     if redis.call("get", KEYS[1]) == ARGV[1] then
         return redis.call("expire", KEYS[1], ARGV[2])
     else
         return 0
     end
     ```
   - Trong khối `finally:`, task heartbeat được hủy lập tức (`heartbeat_task.cancel()`) và khóa được giải phóng bằng `_release_lock()`.
   - Nếu worker bị tắt đột ngột (crash), task heartbeat dừng lại và khóa tự động hết hạn trên Redis.

---

## 3. Kiểm toán Fallback khi Redis Không khả dụng

Hệ thống cung cấp cơ chế dự phòng `InMemoryCache` và `_in_memory_locks` khi kết nối Redis thất bại.

### 3.1. Phân định Ranh giới Phục vụ (Service Boundaries)

| Môi trường triển khai | Khả năng điều phối đồng thời | Cam kết Idempotency | Ghi chú kiến trúc |
|---|---|---|---|
| **Đơn tiến trình (Single-process / 1 Worker Uvicorn)** | **Hoàn toàn đảm bảo** qua `_in_memory_locks` (`asyncio.Lock`) | **Đạt chuẩn Idempotency** trong phạm vi tiến trình | Phù hợp môi trường Local dev, CI/CD, Unit tests |
| **Đa tiến trình (Multi-worker Uvicorn / Cluster)** | **KHÔNG đảm bảo qua các Worker khác nhau** | **Không có Distributed Idempotency** | Mỗi worker có vùng nhớ RAM riêng biệt, không chia sẻ lock hay cache |
| **Có Redis (Distributed Cache & Lock)** | **Hoàn toàn đảm bảo** trên toàn cụm worker | **Đạt chuẩn Global Distributed Idempotency** | Chuẩn vận hành production khuyến nghị |

### 3.2. Quy tắc Vận hành Chế độ Suy giảm (Degraded Mode)

Khi Redis không khả dụng:
- **Không chặn luồng chính:** Học sinh vẫn nhận được phản hồi chẩn đoán lỗi sai bình thường; hệ thống không ném lỗi 500 chỉ vì thiếu cache.
- **Cảnh báo minh bạch trong log:** Hệ thống ghi nhận cảnh báo:
  `WARNING: Redis is unavailable. Running in degraded mode: distributed idempotency across multiple workers is not guaranteed.`
- **Không công bố sai sự thật:** Không xác nhận hệ thống có Distributed Lock toàn cục khi đang chạy fallback trên RAM.

---

## 4. Kiểm toán Thực tế: Tenant Isolation trên Database Schema

Tiến hành kiểm tra phản chiếu (introspection) thông qua SQLAlchemy Inspector trên toàn bộ các model liên quan đến kỳ thi.

### 4.1. Bảng Đối chiếu Thực tế các Model

| Model | Bảng DB | Cột Tenant (`tenant_id`/`school_id`) | Quan hệ thực tế trong Schema | Cơ chế Ủy quyền & Kiểm soát Truy cập |
|---|---|---|---|---|
| `ExamAttempt` | `exam_attempts` | **KHÔNG CÓ** | `student` (`users.id`), `exam` (`exams.id`), `assignment` (`assignments.id`) | **Ủy quyền sở hữu cá nhân:** Bắt buộc `attempt.student_id == student.id` và trạng thái `status in ('SUBMITTED', 'AUTO_SUBMITTED', 'GRADED')`. |
| `Exam` | `exams` | **KHÔNG CÓ** | `creator` (`users.id`), `subject` (`subjects.id`), `grade` (`grades.id`) | Giáo viên sở hữu đề (`creator_id == teacher.id`) hoặc Admin override. |
| `StudentAnswer` | `student_answers` | **KHÔNG CÓ** | `attempt` (`exam_attempts.id`), `question` (`questions.id`) | Gắn liền với `attempt_id`. Kết quả chấm điểm tác vụ đọc từ `is_correct`. |
| `Question` | `questions` | **KHÔNG CÓ** | `options` (`question_options`), `topic`, `lesson`, `creator` | Xác thực câu hỏi nằm trong snapshot của đề thi (`attempt.questions_snapshot_json`). |
| `ExamResult` | `exam_results` | **KHÔNG CÓ** | `attempt` (`exam_attempts.id`) | Khóa ngoại duy nhất gắn với `attempt_id`. |
| `User` | `users` | **KHÔNG CÓ** | `sessions` (`user_sessions`) | Định danh người dùng qua `user.id` và vai trò `user.role` (STUDENT/TEACHER/ADMIN). |
| `Classroom` | `classrooms` | **KHÔNG CÓ** | `teacher` (`users.id`), `members` (`classroom_members`) | Lớp học thuộc quyền giáo viên (`teacher_id`), học sinh tham gia qua `ClassroomMember`. |
| `Assignment` | `assignments` | **KHÔNG CÓ** | `classroom` (`classrooms.id`), `exam` (`exams.id`) | Giao bài tập theo phạm vi lớp học. |

### 4.2. Kết luận Ranh giới Kiến trúc (Architectural Limitation)

> [!WARNING]
> **Hiện trạng Database Schema:**
> - Cơ sở dữ liệu hiện tại của SMART-LEARNING-PRO **chưa hỗ trợ đa trường học/đa đơn vị (multi-tenancy) ở mức bảng dữ liệu vật lý**. Không có bất kỳ cột `tenant_id` hay `school_id` nào trong cơ sở dữ liệu.
> - **Cơ chế an ninh cốt lõi hiện hành là Ủy quyền Sở hữu Học sinh (Student Ownership Authorization):** Học sinh A tuyệt đối không thể truy cập, xem lại hoặc chẩn đoán bài thi của Học sinh B vì hệ thống kiểm tra chặt chẽ `attempt.student_id == authenticated_student.id`.
> - **Về mặt Cache Key:** Tiền tố `tenant_id` trong cache key (mặc định là `"default"` hoặc lấy từ attribute tùy chọn) đóng vai trò chuẩn bị sẵn sàng (ready-for-tenancy) để tránh đụng độ khóa khi dự án bổ sung cột tenant trong tương lai, nhưng **bản thân cache key không thể thay thế cho việc thiếu vắng ranh giới tenant trong database**.
> - Không tạo migration hay tự ý thêm cột vào database trong giai đoạn này (tuân thủ nghiêm ngặt quy tắc Phase Scope).

---

## 5. Bằng chứng Thực thi Kiểm thử (Test Evidence)

### 5.1. File Kiểm toán Mới: `backend/tests/test_ai_diagnostics_audit_7221.py`

Bao gồm 10 test case chuyên sâu cho Phase 7.2.2.1:
1. `test_lock_ttl_calculation_outlives_provider_timeout`: Tính toán TTL tự động vượt quá deadline của provider. (PASS)
2. `test_lock_release_correct_token_succeeds`: Giải phóng khóa bằng token chính chủ. (PASS)
3. `test_lock_release_incorrect_token_fails`: Ngăn chặn token giả mạo giải phóng khóa. (PASS)
4. `test_lock_renewal_token_ownership`: Xác thực quyền sở hữu khi gia hạn khóa. (PASS)
5. `test_lock_heartbeat_renewal_prevents_expiration`: Heartbeat duy trì khóa trong suốt thời gian tác vụ AI chạy. (PASS)
6. `test_worker_crash_abandoned_lock_expires`: Khóa tự động giải phóng khi worker bị crash bỏ rơi khóa. (PASS)
7. `test_redis_unavailable_single_process_coordination`: Điều phối đơn tiến trình trên RAM khi không có Redis. (PASS)
8. `test_redis_unavailable_multi_worker_limitation`: Minh chứng giới hạn đa tiến trình khi không có Redis. (PASS)
9. `test_actual_database_models_have_no_tenant_column`: Kiểm tra thực tế xác nhận schema không có cột tenant. (PASS)
10. `test_student_ownership_real_database_records`: Kiểm tra an ninh quyền sở hữu học sinh trên bản ghi DB thực tế. (PASS)

**Kết quả chạy riêng suite kiểm toán:**
```
pytest backend/tests/test_ai_diagnostics_audit_7221.py -v
============================= 10 passed in 12.67s =============================
Exit Code: 0
```

### 5.2. Kiểm tra Toàn diện Regression Test Suite

Lệnh thực thi:
```powershell
$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests -v
```

Kết quả thực tế:
```
============================ 173 passed in 52.81s =============================
Exit Code: 0
```

Chi tiết phân bổ 173 test case:
- `test_ai_diagnostics_audit_7221.py`: **10 PASSED** (Mới)
- `test_ai_diagnostics_service_722.py`: **31 PASSED**
- `test_ai_diagnostics_721.py`: **26 PASSED**
- `test_ai_foundation.py`: **62 PASSED**
- Các module kiểm thử backend hiện hữu (auth, exams, autosave, concurrency, curriculum, etc.): **44 PASSED**

**Tỷ lệ đạt:** 173/173 (100%), 0 FAILED, 0 SKIPPED. Không có bất kỳ lỗi hồi quy nào.

---

## 6. Trạng thái Repository & Database

- **Git HEAD:** `d6326e5415cb125b62fbe12aea077ecf921d3a88` (Khớp tuyệt đối baseline).
- **Files Modified:**
  - `backend/app/modules/ai_engine/diagnostics/service.py` (Bổ sung tính toán TTL động, gia hạn khóa heartbeat, và ghi log degraded mode).
- **Files Created:**
  - `backend/tests/test_ai_diagnostics_audit_7221.py` (Suite kiểm toán an ninh và concurrency).
  - `docs/PHASE_7_2_2_1_FINAL_SECURITY_CONCURRENCY_AUDIT.md` (Báo cáo này).
- **Database Migrations:** 0 (Không tạo migration mới).
- **Database Schema:** Giữ nguyên 100%.
- **Git Commits:** 0 (Chưa commit, chờ người dùng phê duyệt).

---

## 7. Điều kiện Dừng & Khuyến nghị Tiếp theo

Phase 7.2.2.1 đã hoàn thành đầy đủ các yêu cầu kiểm toán:
- Rủi ro Lock TTL đã được giải quyết triệt để bằng TTL động và cơ chế Heartbeat Renewal.
- Giới hạn khi thiếu Redis đã được định nghĩa minh bạch trong mã nguồn và tài liệu.
- Hiện trạng Tenant trên Database Model đã được kiểm chứng và ghi nhận chính xác.
- Tuyệt đối chưa triển khai REST API router (Phase 7.2.3) hoặc Frontend UI (Phase 7.2.4).

Hệ thống sẵn sàng chuyển sang **Phase 7.2.3 (REST API Endpoint)** khi có sự chấp thuận từ người dùng.
