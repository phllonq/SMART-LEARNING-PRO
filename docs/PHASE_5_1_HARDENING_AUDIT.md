# BÁO CÁO KIỂM TOÁN VÀ TỐI ƯU TOÀN DIỆN HỆ THỐNG BACKEND (PHASE 5.1)
## SMART LEARNING PRO — PRODUCTION READINESS & CONCURRENCY HARDENING AUDIT

**Ngày thực hiện:** 19/11/2026  
**Môi trường:** Python 3.11, FastAPI, SQLAlchemy 2.0 Async (SQLite Local Mode / PostgreSQL Dual-Mode Ready)  
**Phạm vi:** Kiểm toán tính toàn vẹn dữ liệu, kiểm soát đồng thời (concurrency), ranh giới bảo mật (IDOR, Data Leakage), tính bất biến của lịch sử thi và snapshot đề thi.  
**Kết quả kiểm thử:** **31/31 PASSED (100%)** — `pytest -c backend/pytest.ini backend/tests -v` (8.22s)

---

## 1. MỤC TIÊU & NGUYÊN TẮC KIỂM TOÁN

Trước khi tiến hành phát triển tầng Frontend và tích hợp AI Tutor, toàn bộ nền tảng Backend Core (Authentication, Curriculum, Question Bank, Examination Engine, Classroom & Homework Management) bắt buộc phải đạt tiêu chuẩn Production-Ready:
1. **Toàn vẹn khóa ngoại (Foreign Key Referential Integrity):** SQLite async mặc định không tự động kích hoạt `PRAGMA foreign_keys=ON`, dẫn đến nguy cơ lưu trữ dữ liệu mồ côi (orphaned rows) nếu không được quản lý chặt chẽ.
2. **Kiểm soát đồng thời (Concurrency & Race Conditions):** Học sinh gửi nhiều request đồng thời khi bắt đầu làm bài, tham gia lớp học vào phút chót, hoặc gửi autosave theo thứ tự trễ mạng (out-of-order packets) không được làm sai lệch trạng thái hoặc vượt quá sĩ số tối đa.
3. **Tính bất biến của dữ liệu lịch sử thi (Decoupled Snapshot Grading):** Giáo viên sửa đổi hoặc xóa câu hỏi trong Question Bank sau khi đề thi đã phát hành tuyệt đối không được làm thay đổi kết quả, thang điểm hoặc giải thích của các bài thi đã và đang làm.
4. **Bảo mật và chống rò rỉ đáp án (Confidentiality & Anti-IDOR):** Không rò rỉ `is_correct` qua API học sinh; bảo vệ endpoint xem lại bài làm (`/attempts/{id}/review`) trước các cuộc tấn công IDOR giữa các học sinh.

---

## 2. DANH MỤC VẤN ĐỀ ĐÃ PHÁT HIỆN & BIỆN PHÁP XỬ LÝ (DETAILED DEFECTS & FIXES)

| ID | Module / Lĩnh vực | Mức độ nghiêm trọng | Hiện tượng phát hiện | Giải pháp kỹ thuật đã áp dụng | Trạng thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Database Engine | **CRITICAL** | SQLite mặc định tắt ràng buộc khóa ngoại (`PRAGMA foreign_keys: 0`), cho phép tạo bản ghi tham chiếu đến `id` không tồn tại. | Đăng ký connection event listener `@event.listens_for(engine.sync_engine, "connect")` thực thi `PRAGMA foreign_keys=ON` trên mỗi kết nối SQLite. | **RESOLVED** |
| **INT-01** | Examination Engine | **CRITICAL** | Chấm bài (`submit_exam_attempt`) phụ thuộc vào truy vấn bảng `Question` và `QuestionOption` trực tiếp lúc nộp. Nếu giáo viên chỉnh sửa câu hỏi trong Question Bank, điểm thi của học sinh bị biến động. | Thêm cột `answer_key_snapshot_json` vào `exam_attempts`. Khi bắt đầu làm bài (`start_exam_attempt`), toàn bộ đáp án đúng, điểm số, và lời giải được đóng băng vĩnh viễn ở phía máy chủ. Công cụ chấm bài tự động đối chiếu hoàn toàn dựa trên snapshot này. | **RESOLVED** |
| **CONC-01**| Examination Engine | **HIGH** | Học sinh gửi 2 request song song đến `/api/v1/exams/{id}/start` tạo ra 2 lượt thi `IN_PROGRESS` đồng thời, vi phạm giới hạn số lượt thi (`max_attempts`). | Tạo partial unique index `uq_active_exam_attempt` và `uq_active_assignment_attempt` trên `exam_attempts` với điều kiện `WHERE status = 'IN_PROGRESS'`. Xử lý `IntegrityError` tại service để rollback và trả về lượt thi active hợp lệ duy nhất. | **RESOLVED** |
| **CONC-02**| Classroom Module | **HIGH** | Race condition khi 2 học sinh cùng ấn tham gia lớp học có 1 chỗ trống còn lại (`max_students=1`), khiến sĩ số lớp vượt quá giới hạn. | Kiểm tra sĩ số 2 lớp: (1) Kiểm tra bộ nhớ trước khi insert, (2) Kiểm tra tổng số thành viên thực tế trong DB sau khi `flush()`. Nếu vượt quá `max_students`, tự động xóa thành viên mới và trả về HTTP 403 Forbidden. | **RESOLVED** |
| **CONC-03**| Classroom Module | **HIGH** | Học sinh click đúp nút "Tham gia lớp" gửi 2 request join cùng lúc gây lỗi 500 Unhandled Exception. | Unique index `uq_classroom_member(classroom_id, student_id)`. Bắt `IntegrityError` và chuyển đổi thành `DuplicateEntityException` (HTTP 409 Conflict) với thông báo rõ ràng. | **RESOLVED** |
| **NET-01** | Autosave Engine | **MEDIUM** | Độ trễ mạng khiến gói tin autosave cũ (`time_spent=20s`) đến sau gói tin mới (`time_spent=45s`), ghi đè đáp án mới bằng đáp án cũ. | Thêm kiểm tra thời gian: nếu `data.time_spent_seconds < answer.time_spent_seconds`, hệ thống bỏ qua gói tin trễ và bảo toàn đáp án mới nhất. | **RESOLVED** |
| **SEC-02** | Examination Review | **HIGH** | Endpoint `/attempts/{id}/review` có thể bị học sinh khác truy cập (IDOR) hoặc bài thi đang làm có thể bị xem trộm đáp án đúng. | Xử lý kiểm tra 3 tầng: (1) Chỉ cho phép xem khi attempt ở trạng thái `SUBMITTED`, `AUTO_SUBMITTED`, `GRADED`, (2) Kiểm tra quyền sở hữu bài thi (`student_id == user.id`), (3) Tôn trọng cấu hình `allow_review` của đề thi/bài tập. | **RESOLVED** |
| **CONC-04**| Assignment Engine | **MEDIUM** | Giáo viên hủy bài tập (`CANCELLED`) trong khi học sinh đang làm bài dẫn đến lỗi 403 khi học sinh nộp bài. | Bổ sung cờ `allow_cancelled=True` trong `get_assignment_by_id` khi thực hiện `submit_assignment`, cho phép học sinh nộp bài an toàn mà không làm mất bài làm. | **RESOLVED** |
| **MIGR-01**| Migration Scripts | **LOW** | Chạy lại các file migration lần thứ hai có thể phát sinh lỗi trùng cột hoặc trùng index. | Xây dựng cơ chế kiểm tra `PRAGMA table_info` và `CREATE UNIQUE INDEX IF NOT EXISTS` đảm bảo tính lũy thừa (idempotency 100%). | **RESOLVED** |

---

## 3. CHI TIẾT CÁC CƠ CHẾ BẢO VỆ & HARDENING ARCHITECTURE

### 3.1. Kích hoạt toàn vẹn khóa ngoại (Referential Integrity)
Tệp `backend/app/core/database.py`:
```python
if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```
- Khi thực thi lệnh chèn dữ liệu không hợp lệ (ví dụ mã môn học không tồn tại `sub-toan-11`), SQLite lập tức kích hoạt lỗi `FOREIGN KEY constraint failed`, bảo vệ cơ sở dữ liệu khỏi rác và sai lệch tham chiếu.

### 3.2. Đóng băng đề thi & Tách biệt chấm điểm (Immutable Snapshot Grading)
- Bảng `exam_attempts` lưu trữ 2 bản snapshot JSON:
  1. `questions_snapshot_json`: Dành cho client học sinh (đã loại bỏ toàn bộ `is_correct`, `explanation`, đáp án chuẩn).
  2. `answer_key_snapshot_json`: Dành cho máy chủ chấm điểm (lưu trữ đầy đủ các phương án đúng, điểm số câu hỏi, thang điểm và lời giải chi tiết tại thời điểm bắt đầu làm bài).
- Khi giáo viên cập nhật câu hỏi trong Question Bank, câu hỏi trong ngân hàng thay đổi nội dung hoặc đáp án, nhưng `answer_key_snapshot_json` của học sinh không bị ảnh hưởng, đảm bảo sự công bằng và tính nhất quán lịch sử.

### 3.3. Partial Unique Indexes chống Race Condition
Tệp `scripts/migrate_hardening.py`:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_exam_attempt 
ON exam_attempts(student_id, exam_id) 
WHERE status = 'IN_PROGRESS' AND assignment_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_assignment_attempt 
ON exam_attempts(student_id, assignment_id) 
WHERE status = 'IN_PROGRESS' AND assignment_id IS NOT NULL;
```
- Cho phép học sinh hoàn thành nhiều lượt thi (các bản ghi `SUBMITTED`, `GRADED`), nhưng **chỉ duy nhất 1 bản ghi** ở trạng thái `IN_PROGRESS` tại một thời điểm.

---

## 4. BẰNG CHỨNG KIỂM THỬ (TEST EXECUTION EVIDENCE)

Toàn bộ 31 bài kiểm thử tự động (Unit & Integration Tests) được thực thi và xác nhận:

```powershell
PS E:\SMART-LEARNING-PRO> $env:PYTHONPATH="E:\SMART-LEARNING-PRO\backend"; .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests -v
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.2.0, pluggy-1.7.0 -- E:\SMART-LEARNING-PRO\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: E:\SMART-LEARNING-PRO\backend
configfile: pytest.ini
plugins: anyio-4.16.0, asyncio-1.5.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 31 items

backend\tests\test_assignments.py::test_assignment_lifecycle_and_security PASSED [  3%]
backend\tests\test_assignments.py::test_assignment_student_workflow_and_deadline_limits PASSED [  6%]
backend\tests\test_auth.py::test_register_and_login_flow PASSED          [  9%]
backend\tests\test_classrooms.py::test_classroom_creation_and_ownership PASSED [ 12%]
backend\tests\test_classrooms.py::test_student_join_and_membership_rules PASSED [ 16%]
backend\tests\test_curriculum.py::test_list_grades PASSED                [ 19%]
backend\tests\test_curriculum.py::test_list_subjects_and_detail PASSED   [ 22%]
backend\tests\test_curriculum.py::test_subject_chapters_and_hierarchy PASSED [ 25%]
backend\tests\test_curriculum.py::test_get_lesson_detail_with_katex PASSED [ 29%]
backend\tests\test_curriculum.py::test_missing_resources_return_404 PASSED [ 32%]
backend\tests\test_curriculum.py::test_input_validation_errors PASSED    [ 35%]
backend\tests\test_curriculum.py::test_unpublished_content_access_control PASSED [ 38%]
backend\tests\test_curriculum.py::test_teacher_and_admin_curriculum_management PASSED [ 41%]
backend\tests\test_exams.py::test_teacher_exam_management_and_ownership PASSED [ 45%]
backend\tests\test_exams.py::test_student_examination_flow_and_confidentiality PASSED [ 48%]
backend\tests\test_hardening_audit.py::test_migration_idempotency PASSED [ 51%]
backend\tests\test_hardening_audit.py::test_concurrent_classroom_join_same_student PASSED [ 54%]
backend\tests\test_hardening_audit.py::test_concurrent_classroom_join_capacity_limit PASSED [ 58%]
backend\tests\test_hardening_audit.py::test_concurrent_exam_attempt_start PASSED [ 61%]
backend\tests\test_hardening_audit.py::test_out_of_order_autosave_protection PASSED [ 64%]
backend\tests\test_hardening_audit.py::test_question_bank_edit_decoupling_and_snapshot_grading PASSED [ 67%]
backend\tests\test_hardening_audit.py::test_submission_review_security_and_idor PASSED [ 70%]
backend\tests\test_hardening_audit.py::test_cancelled_assignment_submission_safety PASSED [ 74%]
backend\tests\test_health.py::test_health_check PASSED                   [ 77%]
backend\tests\test_questions.py::test_list_questions_and_filters PASSED  [ 80%]
backend\tests\test_questions.py::test_answer_confidentiality_for_students PASSED [ 83%]
backend\tests\test_questions.py::test_create_question_validation_rules PASSED [ 87%]
backend\tests\test_create_and_retrieve_katex_question PASSED              [ 90%]
backend\tests\test_questions.py::test_teacher_ownership_boundaries_and_admin_override PASSED [ 93%]
backend\tests\test_questions.py::test_unpublished_question_visibility_and_toggle PASSED [ 96%]
backend\tests\test_rbac.py::test_rbac_permissions PASSED                 [100%]

============================= 31 passed in 8.22s ==============================
```

---

## 5. KẾT LUẬN & SẴN SÀNG CHO GIAI ĐOẠN TIẾP THEO

- Nền tảng Backend đã vượt qua toàn bộ các bài kiểm tra áp lực đồng thời, tính toàn vẹn cơ sở dữ liệu và bảo mật.
- Mã nguồn và cơ sở dữ liệu hoàn toàn sẵn sàng cho **Phase 6: Frontend Development** và **Phase 7: AI Engineering**.
