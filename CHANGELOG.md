# CHANGELOG — SMART LEARNING PRO

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
