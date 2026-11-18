# CHANGELOG — SMART LEARNING PRO

## [0.3.0] - 2026-11-18
### Added
- **Curriculum Module API (`/api/v1/curriculum/*`)**:
  - `GET /grades`: Lấy danh sách khối lớp (Lớp 6 đến 12).
  - `GET /grades/{grade_id}/subjects`: Lấy danh sách môn học theo khối lớp có hỗ trợ phân trang.
  - `GET /subjects`: Danh sách môn học toàn hệ thống với bộ lọc khối lớp.
  - `GET /subjects/{subject_id}`: Chi tiết thông tin môn học.
  - `POST /subjects`: Tạo môn học mới (Admin only).
  - `GET /subjects/{subject_id}/chapters`: Lấy toàn bộ cây đề cương (Chương -> Chủ đề -> Tóm tắt Bài học) với quan hệ nạp sẵn `selectinload`.
  - `POST /chapters`: Tạo chương mới thuộc môn học (Giáo viên / Admin).
  - `POST /topics`: Tạo chủ đề mới thuộc chương (Giáo viên / Admin).
  - `GET /topics/{topic_id}/lessons` & `GET /chapters/{chapter_id}/lessons`: Danh sách bài học có phân trang.
  - `GET /lessons/{lesson_id}`: Chi tiết nội dung bài giảng phong phú hỗ trợ công thức toán học KaTeX (`$\sin x = m$`) và tài liệu đính kèm.
  - `POST /lessons` & `PATCH /lessons/{lesson_id}`: Tạo và cập nhật nội dung bài giảng (Giáo viên / Admin).
  - `DELETE /lessons/{lesson_id}`: Xóa bài giảng (Admin only).
- **Kiểm soát xuất bản (Publication Filtering)**:
  - Học sinh và khách chỉ xem được các môn học và bài giảng đã công khai (`is_published: true`).
  - Bản nháp chưa xuất bản được ẩn an toàn (trả về 404 cho học sinh, chỉ giáo viên và quản trị viên được phép truy cập).
- **Bộ kiểm thử tự động toàn diện**:
  - Thêm 8 test suite cho Curriculum trong `backend/tests/test_curriculum.py`.
  - Toàn bộ backend test suite đạt **11/11 tests PASS (100%)** trong 1.06 giây.

## [0.2.0] - 2026-11-18
### Added
- Hoàn thành tài liệu kiến trúc hệ thống và đặc tả kỹ thuật Phase 1 trong `docs/`.
- Xác lập Git baseline commit `3cac958`.
- Khởi tạo môi trường ảo Python 3.11 (`.venv`) và cài đặt toàn bộ dependencies.
- Xây dựng 26 models SQLAlchemy 2.0 ORM và khởi tạo database SQLite async `database/smart_learning.db`.
- Xây dựng module bảo mật Argon2id và JWT token kép (Header Bearer + HttpOnly Secure Cookie).
- Xây dựng bộ lọc phân quyền RBAC (`STUDENT`, `TEACHER`, `ADMIN`, `SUPERADMIN`).
- Xây dựng các API xác thực `/api/v1/auth/register`, `/login`, `/me`, `/logout`.
- Xây dựng endpoint kiểm tra sức khỏe hệ thống `/api/v1/health`.
- Xây dựng và thực thi seeder dữ liệu `scripts/seed_database.py`.
- Thiết lập bộ kiểm thử tự động với pytest & pytest-asyncio (Commit `a329d5c`).

## [0.1.0] - 2026-11-18
### Added
- Khởi tạo cấu trúc thư mục độc lập tại `E:\SMART-LEARNING-PRO`.
- Khởi tạo Git repository.
- Kiểm tra môi trường hệ thống.
