# CHANGELOG — SMART LEARNING PRO

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
