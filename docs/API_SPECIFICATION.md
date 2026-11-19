# REST API SPECIFICATION — SMART LEARNING PRO

Tất cả các API tuân thủ tiêu chuẩn RESTful, trả về dữ liệu chuẩn JSON, hỗ trợ tiền tố chung `/api/v1`.

---

## 1. XÁC THỰC & NGƯỜI DÙNG (AUTHENTICATION & USERS)

### `POST /api/v1/auth/register`
- **Mục đích**: Đăng ký tài khoản mới (Học sinh hoặc Giáo viên).
- **Body**:
  ```json
  {
    "email": "student1@smartlearning.vn",
    "password": "Password123!",
    "full_name": "Nguyễn Văn An",
    "role": "STUDENT",
    "grade_level": 11
  }
  ```
- **Response 201**:
  ```json
  {
    "message": "Đăng ký thành công",
    "user": {
      "id": "uuid-...",
      "email": "student1@smartlearning.vn",
      "full_name": "Nguyễn Văn An",
      "role": "STUDENT",
      "grade_level": 11
    }
  }
  ```

### `POST /api/v1/auth/login`
- **Mục đích**: Đăng nhập, cấp Access Token và Refresh Token (qua HttpOnly Cookie và JSON response).
- **Body**:
  ```json
  {
    "email": "student1@smartlearning.vn",
    "password": "Password123!"
  }
  ```
- **Response 200**:
  - Sets Cookie `access_token` và `refresh_token` (HttpOnly, SameSite=Lax).
  - Trả về JSON chứa user profile và token.

### `GET /api/v1/auth/me`
- **Mục đích**: Lấy thông tin người dùng hiện tại đang đăng nhập.
- **Headers**: Cookie hoặc `Authorization: Bearer <token>`
- **Response 200**: Chi tiết user profile, XP, streak, vai trò.

### `POST /api/v1/auth/logout`
- **Mục đích**: Đăng xuất, hủy cookie và session.

---

## 2. CHƯƠNG TRÌNH HỌC (CURRICULUM)

Tất cả các endpoint chương trình học đều hỗ trợ kiểm soát phân quyền RBAC:
- **Học sinh (STUDENT) & Khách vãng lai**: Chỉ xem được các môn học, bài giảng đã công khai (`is_published: true`).
- **Giáo viên (TEACHER) & Admin (ADMIN / SUPERADMIN)**: Có thể xem được cả bản nháp chưa công khai và có quyền tạo/sửa chương, chủ đề, bài học.
- **Admin**: Có quyền tạo/sửa môn học và xóa bài học.

### 2.1. Danh Sách Khối Lớp (Grades)
- **`GET /api/v1/curriculum/grades`**
  - **Mô tả**: Lấy danh sách toàn bộ các khối lớp (Lớp 6 đến Lớp 12).
  - **Quyền hạn**: Công khai.
  - **Response 200**:
    ```json
    [
      { "id": 10, "name": "Khối 10", "description": "Chương trình GDPT 2018 Lớp 10", "order_index": 1 },
      { "id": 11, "name": "Khối 11", "description": "Chương trình GDPT 2018 Lớp 11", "order_index": 2 },
      { "id": 12, "name": "Khối 12", "description": "Chương trình GDPT 2018 Lớp 12", "order_index": 3 }
    ]
    ```

### 2.2. Môn Học (Subjects)
- **`GET /api/v1/curriculum/grades/{grade_id}/subjects`**
  - **Mô tả**: Lấy danh sách môn học theo khối lớp (hỗ trợ phân trang: `page`, `page_size`).
  - **Quyền hạn**: Công khai (chỉ trả về môn đã công khai). Giáo viên/Admin thấy toàn bộ.
  - **Response 200**:
    ```json
    {
      "items": [
        {
          "id": "toan-11",
          "grade_id": 11,
          "name": "Toán học 11",
          "code": "MATH11",
          "icon": "Calculator",
          "color": "#635BFF",
          "is_published": true,
          "order_index": 1
        }
      ],
      "total": 3,
      "page": 1,
      "page_size": 20,
      "total_pages": 1
    }
    ```

- **`GET /api/v1/curriculum/subjects`**
  - **Mô tả**: Lấy toàn bộ môn học, hỗ trợ lọc theo query `grade_id`, phân trang `page`, `page_size`.

- **`GET /api/v1/curriculum/subjects/{subject_id}`**
  - **Mô tả**: Xem thông tin chi tiết của môn học.

- **`POST /api/v1/curriculum/subjects`**
  - **Quyền hạn**: `ADMIN`, `SUPERADMIN`.
  - **Body**: `{ "id": "tin-11", "grade_id": 11, "name": "Tin học 11", "code": "CS11", "is_published": true, "order_index": 4 }`
  - **Response 201**: Thông tin môn học vừa tạo.

### 2.3. Cây Đề Cương & Bài Học (Chapters, Topics, Lessons)
- **`GET /api/v1/curriculum/subjects/{subject_id}/chapters`**
  - **Mô tả**: Lấy toàn bộ cây cấu trúc Chương -> Chủ đề -> Tóm tắt Bài học của môn học.
  - **Response 200**:
    ```json
    [
      {
        "id": "chap-toan11-01",
        "subject_id": "toan-11",
        "title": "Chương 1: Hàm số lượng giác và phương trình lượng giác",
        "order_index": 1,
        "topics": [
          {
            "id": "topic-toan11-ptlg",
            "chapter_id": "chap-toan11-01",
            "title": "Phương trình lượng giác cơ bản",
            "description": "Nắm vững cách giải các phương trình sin x = m, cos x = m",
            "order_index": 1,
            "lessons": [
              {
                "id": "lesson-toan11-01",
                "topic_id": "topic-toan11-ptlg",
                "title": "Bài 1: Phương trình bậc nhất đối với một hàm số lượng giác",
                "duration_minutes": 45,
                "order_index": 1,
                "has_video": true
              }
            ]
          }
        ]
      }
    ]
    ```

- **`POST /api/v1/curriculum/chapters`**
  - **Quyền hạn**: `TEACHER`, `ADMIN`, `SUPERADMIN`.
  - **Body**: `{ "subject_id": "toan-11", "title": "Chương 2: Dãy số", "order_index": 2 }`

- **`POST /api/v1/curriculum/topics`**
  - **Quyền hạn**: `TEACHER`, `ADMIN`, `SUPERADMIN`.
  - **Body**: `{ "chapter_id": "uuid-...", "title": "Cấp số cộng", "order_index": 1 }`

- **`GET /api/v1/curriculum/topics/{topic_id}/lessons`** & **`GET /api/v1/curriculum/chapters/{chapter_id}/lessons`**
  - **Mô tả**: Lấy danh sách bài học theo topic hoặc theo cả chapter (hỗ trợ phân trang).

- **`GET /api/v1/curriculum/lessons/{lesson_id}`**
  - **Mô tả**: Chi tiết nội dung bài học, chứa công thức toán học KaTeX chuẩn (ví dụ: `$\sin x = m$`, `$\cos x = m$`) và danh sách tài liệu đính kèm (`materials`).
  - **Response 200**:
    ```json
    {
      "id": "lesson-toan11-01",
      "topic_id": "topic-toan11-ptlg",
      "title": "Bài 1: Phương trình bậc nhất đối với một hàm số lượng giác",
      "content_markdown": "# Phương trình lượng giác cơ bản\n\n## 1. Phương trình $\\sin x = m$\n...",
      "video_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
      "duration_minutes": 45,
      "order_index": 1,
      "materials": []
    }
    ```

- **`POST /api/v1/curriculum/lessons`** (Tạo bài học)
  - **Quyền hạn**: `TEACHER`, `ADMIN`, `SUPERADMIN`.

- **`PATCH /api/v1/curriculum/lessons/{lesson_id}`** (Cập nhật bài học)
  - **Quyền hạn**: `TEACHER`, `ADMIN`, `SUPERADMIN`.

- **`DELETE /api/v1/curriculum/lessons/{lesson_id}`** (Xóa bài học)
  - **Quyền hạn**: `ADMIN`, `SUPERADMIN`.
  - **Response 204**: No Content.

---

## 3. NGÂN HÀNG CÂU HỎI (QUESTION BANK)

### 3.1. Nguyên Tắc Bảo Mật & Phân Quyền (RBAC & Confidentiality)
- **Bảo mật đáp án tuyệt đối**: Học sinh (STUDENT) hoặc người dùng chưa đăng nhập khi gọi API danh sách hoặc chi tiết câu hỏi sẽ nhận schema `QuestionStudentResponse`. Trong schema này, trường `is_correct` trong từng phương án trắc nghiệm **hoàn toàn bị loại bỏ** để chống gian lận thi cử.
- **Quyền hạn tạo & sửa**: Chỉ `TEACHER`, `ADMIN`, `SUPERADMIN` mới có quyền tạo câu hỏi.
- **Ranh giới sở hữu (Teacher Ownership Boundary)**: Giáo viên chỉ có quyền sửa hoặc xóa câu hỏi do chính mình tạo ra (`creator_id == user.id`). Nếu cố tình sửa câu hỏi của giáo viên khác, hệ thống lập tức trả về `403 Forbidden`. Quản trị viên (`ADMIN`/`SUPERADMIN`) có quyền duyệt và can thiệp toàn bộ.
- **Bản nháp (Drafts)**: Câu hỏi ở trạng thái `is_public: false` chỉ hiển thị với giáo viên và admin; học sinh truy cập sẽ nhận `404 Not Found`.

### 3.2. Chi Tiết Endpoints
- **`GET /api/v1/questions`**
  - **Mô tả**: Danh sách câu hỏi có phân trang và bộ lọc chuyên sâu.
  - **Query Parameters**:
    - `grade_id`: Khối lớp (1 đến 12).
    - `subject_id`: Mã môn học (ví dụ: `toan-11`).
    - `chapter_id`: Mã chương.
    - `topic_id`: Mã chủ đề.
    - `lesson_id`: Mã bài học.
    - `difficulty_level`: `RECOGNITION`, `COMPREHENSION`, `APPLICATION`, `HIGH_APPLICATION`.
    - `question_type`: `SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `TRUE_FALSE`, `SHORT_ANSWER`, `NUMERIC`, `ESSAY`.
    - `creator_id`: Lọc theo giáo viên tạo.
    - `is_public`: `true` hoặc `false` (chỉ áp dụng cho giáo viên/admin).
    - `search`: Từ khóa tìm kiếm trong nội dung câu hỏi hoặc thẻ tags.
    - `page` (default: 1), `page_size` (default: 20, max: 100).
  - **Response 200 (Dành cho Giáo viên/Admin)**:
    ```json
    {
      "items": [
        {
          "id": "q-toan11-01",
          "topic_id": "topic-toan11-ptlg",
          "lesson_id": "lesson-toan11-01",
          "creator_id": "user-teacher-01",
          "question_type": "SINGLE_CHOICE",
          "content": "Tìm tất cả các nghiệm của phương trình $\\sin x = \\frac{1}{2}$.",
          "difficulty_level": "RECOGNITION",
          "explanation": "Ta có $\\sin x = \\frac{1}{2} = \\sin \\frac{\\pi}{6}$...",
          "hint": "Nhớ lại góc đặc biệt có $\\sin$ bằng $\\frac{1}{2}$...",
          "tags": "lượng giác, 11",
          "is_public": true,
          "created_at": "2026-11-18T19:54:00Z",
          "updated_at": "2026-11-18T19:54:00Z",
          "options": [
            { "id": "opt-1", "option_key": "A", "content": "...", "is_correct": false, "order_index": 1 },
            { "id": "opt-2", "option_key": "B", "content": "...", "is_correct": true, "order_index": 2 }
          ],
          "creator_name": "Thầy Nguyễn Hoàng Nam",
          "topic_title": "Phương trình lượng giác cơ bản"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 20,
      "total_pages": 1
    }
    ```
  - **Response 200 (Dành cho Học sinh - Bảo mật)**:
    ```json
    {
      "items": [
        {
          "id": "q-toan11-01",
          "topic_id": "topic-toan11-ptlg",
          "lesson_id": "lesson-toan11-01",
          "question_type": "SINGLE_CHOICE",
          "content": "Tìm tất cả các nghiệm của phương trình $\\sin x = \\frac{1}{2}$.",
          "difficulty_level": "RECOGNITION",
          "tags": "lượng giác, 11",
          "hint": "Nhớ lại góc đặc biệt...",
          "options": [
            { "id": "opt-1", "option_key": "A", "content": "...", "order_index": 1 },
            { "id": "opt-2", "option_key": "B", "content": "...", "order_index": 2 }
          ]
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 20,
      "total_pages": 1
    }
    ```

- **`GET /api/v1/questions/{question_id}`**
  - **Mô tả**: Xem chi tiết câu hỏi (tự động lọc đáp án nếu là học sinh).

- **`POST /api/v1/questions`**
  - **Quyền hạn**: `TEACHER`, `ADMIN`, `SUPERADMIN`.
  - **Validation Rules**:
    - `SINGLE_CHOICE`: Phải có đúng 1 đáp án đúng (`is_correct: true`), tối thiểu 2 phương án.
    - `MULTIPLE_CHOICE`: Tối thiểu 1 đáp án đúng, tối thiểu 2 phương án.
    - `TRUE_FALSE`: Phải có đúng 2 phương án, đúng 1 đáp án đúng.
    - Không được trùng mã `option_key` (A, B, C...).
  - **Response 201**: Thông tin câu hỏi vừa tạo.

- **`PATCH /api/v1/questions/{question_id}`**
  - **Quyền hạn**: Giáo viên sở hữu hoặc Admin. Cho phép cập nhật từng phần (câu hỏi, lời giải, độ khó, hoặc thay đổi toàn bộ danh sách phương án).

- **`DELETE /api/v1/questions/{question_id}`**
  - **Quyền hạn**: Giáo viên sở hữu hoặc Admin.
  - **Response 204**: No Content.

- **`POST /api/v1/questions/{question_id}/toggle-publish`**
  - **Quyền hạn**: Giáo viên sở hữu hoặc Admin. Chuyển đổi trạng thái giữa Bản nháp (`false`) và Công khai (`true`).

---

## 4. ĐỀ THI & PHÒNG THI TRỰC TUYẾN (EXAMINATION ENGINE & AUTO-GRADING)

### 4.1. Dành Cho Học Sinh (Student Examination Flow)
- **`GET /api/v1/exams/available`**
  - **Mô tả**: Lấy danh sách các đề thi đã xuất bản (`PUBLISHED`), đang trong khung thời gian hợp lệ (`start_time` / `end_time`), và học sinh chưa vượt quá giới hạn lượt thi (`max_attempts`).
  - **Response 200**: Danh sách `ExamSummaryResponse`.

- **`POST /api/v1/exams/{exam_id}/start`**
  - **Mô tả**: Bắt đầu làm bài thi hoặc khôi phục lượt thi đang diễn ra (`IN_PROGRESS`).
  - **Bảo mật tuyệt đối**: Tạo bản chụp đề thi bất biến (`questions_snapshot_json`) đã **loại bỏ hoàn toàn** trường `is_correct`, `explanation`, `solution_key`.
  - **Response 200**:
    ```json
    {
      "attempt_id": "attempt-uuid-1",
      "exam_id": "exam-uuid-1",
      "attempt_number": 1,
      "started_at": "2026-11-19T00:00:00Z",
      "deadline_at": "2026-11-19T00:45:00Z",
      "duration_minutes": 45,
      "total_questions": 2,
      "questions": [
        {
          "question_id": "q-toan11-01",
          "points": 5.0,
          "order_index": 1,
          "content": "Tính đạo hàm của hàm số $y = \\sin(2x)$.",
          "question_type": "SINGLE_CHOICE",
          "options": [
            { "id": "opt-1", "option_key": "A", "content": "$2\\cos(2x)$" },
            { "id": "opt-2", "option_key": "B", "content": "$\\cos(2x)$" }
          ]
        }
      ]
    }
    ```

- **`GET /api/v1/exams/attempts/{attempt_id}`**
  - **Mô tả**: Lấy lại snapshot câu hỏi và từ điển các câu trả lời học sinh đã lưu trước đó (`saved_answers`) để khôi phục giao diện làm bài khi tải lại trang hoặc rớt mạng.

- **`POST /api/v1/exams/attempts/{attempt_id}/questions/{question_id}/autosave`**
  - **Mô tả**: Autosave câu trả lời nền (debounce theo thời gian thực).
  - **Body**:
    ```json
    {
      "selected_option_id": "opt-1",
      "selected_option_ids": ["opt-1"],
      "answer_text": null,
      "is_flagged": false,
      "time_spent_seconds": 15
    }
    ```
  - **Response 200**: `{ "status": "SAVED", "attempt_id": "...", "question_id": "...", "saved_at": "..." }`

- **`POST /api/v1/exams/attempts/{attempt_id}/submit`**
  - **Mô tả**: Học sinh nộp bài thi (hoặc hệ thống tự động nộp bài khi hết giờ). Kích hoạt **Server-side Auto Grading Engine**:
    - So khớp đáp án đã lưu với cơ sở dữ liệu gốc.
    - Hỗ trợ câu hỏi đơn lựa chọn (`SINGLE_CHOICE`), đa lựa chọn (`MULTIPLE_CHOICE`), Đúng/Sai (`TRUE_FALSE`), câu trả lời ngắn (`SHORT_ANSWER`).
    - Tính điểm chi tiết từng câu (`points_awarded`), tổng điểm (`total_score`), tỷ lệ chính xác (`accuracy_percentage`).
    - Tự động tạo bản ghi thống kê `exam_results`.
  - **Response 200**:
    ```json
    {
      "attempt_id": "attempt-uuid-1",
      "exam_id": "exam-uuid-1",
      "status": "GRADED",
      "total_score": 10.0,
      "maximum_score": 10.0,
      "passing_score": 5.0,
      "is_passed": true,
      "correct_answers_count": 2,
      "wrong_answers_count": 0,
      "skipped_answers_count": 0,
      "accuracy_percentage": 100.0,
      "feedback_summary": "Xuất sắc! Bạn đã vượt qua bài thi với kết quả tuyệt đối.",
      "submitted_at": "2026-11-19T00:15:00Z",
      "review_allowed": true
    }
    ```

- **`GET /api/v1/exams/attempts/{attempt_id}/review`**
  - **Mô tả**: Xem lại chi tiết từng câu hỏi, đáp án học sinh đã chọn, đáp án đúng và lời giải chi tiết (chỉ khả dụng sau khi nộp bài và nếu đề thi cho phép `allow_review: true`).

---

### 4.2. Dành Cho Giáo Viên & Quản Trị Viên (Teacher Exam Management & RBAC)
- **`GET /api/v1/exams`**: Danh sách đề thi có phân trang, lọc theo môn học (`subject_id`), khối lớp (`grade_id`), trạng thái (`status_filter`), giáo viên (`creator_id`).
- **`POST /api/v1/exams`**: Tạo đề thi mới (trạng thái ban đầu `DRAFT` hoặc `PUBLISHED`).
- **`GET /api/v1/exams/{exam_id}`**: Chi tiết cấu hình đề thi và danh sách câu hỏi kèm điểm số.
- **`PATCH /api/v1/exams/{exam_id}`**: Cập nhật thông số đề thi (Giáo viên sở hữu hoặc Admin).
- **`POST /api/v1/exams/{exam_id}/questions`**: Thêm câu hỏi từ Ngân hàng câu hỏi vào đề thi với điểm số và thứ tự tùy chỉnh.
- **`DELETE /api/v1/exams/{exam_id}/questions/{question_id}`**: Gỡ câu hỏi ra khỏi đề thi.
- **`POST /api/v1/exams/{exam_id}/publish`**: Xuất bản đề thi (Bắt buộc đề thi phải có ít nhất 1 câu hỏi).
- **`POST /api/v1/exams/{exam_id}/archive`**: Lưu trữ đề thi (Đóng phòng thi).
- **`GET /api/v1/exams/{exam_id}/submissions`**: Bảng tổng hợp kết quả làm bài của tất cả học sinh trong đề thi (điểm số, thời gian nộp, trạng thái đạt/không đạt).

---

## 5. QUẢN LÝ LỚP HỌC & BÀI TẬP VỀ NHÀ (CLASSROOMS & HOMEWORK ASSIGNMENTS)

### 5.1. Quản Lý Lớp Học (`/api/v1/classrooms/*`)
- **`GET /api/v1/classrooms`**: Danh sách lớp học liên quan đến người dùng hiện tại (Giáo viên: các lớp do mình phụ trách; Học sinh: các lớp đã tham gia; Admin: toàn bộ lớp học trên hệ thống).
- **`POST /api/v1/classrooms`**: Tạo lớp học mới (Giáo viên / Admin). Hệ thống tự sinh mã mời ngẫu nhiên (`SL-XXXXXX`), thiết lập sĩ số tối đa `max_students`.
- **`GET /api/v1/classrooms/{classroom_id}`**: Chi tiết lớp học và danh sách thành viên (chỉ dành cho Giáo viên chủ nhiệm, Admin hoặc Học sinh đã tham gia lớp).
- **`PATCH /api/v1/classrooms/{classroom_id}`**: Cập nhật thông tin lớp học (tên, mô tả, khối lớp, sĩ số tối đa).
- **`POST /api/v1/classrooms/{classroom_id}/archive`**: Lưu trữ lớp học (Đóng lớp, không cho phép học sinh mới tham gia).
- **`POST /api/v1/classrooms/{classroom_id}/regenerate-invite-code`**: Cấp lại mã mời mới cho lớp học.
- **`GET /api/v1/classrooms/{classroom_id}/members`**: Danh sách học sinh trong lớp (họ tên, email, ảnh đại diện, ngày tham gia).
- **`POST /api/v1/classrooms/join`**: Học sinh tham gia lớp học qua mã mời. Kiểm tra tự động lớp có bị lưu trữ không, chống trùng lặp thành viên (`409 Conflict`), kiểm tra giới hạn sĩ số tối đa (`403 Forbidden`).
- **`DELETE /api/v1/classrooms/{classroom_id}/members/{student_id}`**: Xóa học sinh ra khỏi lớp học (Giáo viên chủ nhiệm hoặc Admin).
- **`POST /api/v1/classrooms/{classroom_id}/leave`**: Học sinh tự rời khỏi lớp học.
- **`GET /api/v1/classrooms/{classroom_id}/statistics`**: Thống kê hiệu suất lớp học (tổng số học sinh, số bài tập đã giao, số lượt nộp bài, điểm trung bình toàn lớp, tỷ lệ hoàn thành bài tập).

---

### 5.2. Quản Lý Bài Tập Về Nhà (`/api/v1/assignments/*` & `/classrooms/{id}/assignments`)
- **`GET /api/v1/classrooms/{classroom_id}/assignments`**: Danh sách bài tập trong lớp (Giáo viên xem được tất cả các bài DRAFT/PUBLISHED/CANCELLED; Học sinh chỉ thấy các bài đã PUBLISHED).
- **`POST /api/v1/classrooms/{classroom_id}/assignments`**: Giao bài tập về nhà từ một đề thi đã xuất bản trong Ngân hàng đề thi (`exam_id`). Cấu hình hạn chót (`due_date`), thời điểm mở (`open_date`), số lần làm bài tối đa (`max_attempts`), chính sách nộp muộn (`allow_late_submission`) và chính sách xem lời giải sau khi nộp (`allow_review`).
- **`GET /api/v1/assignments/{assignment_id}`**: Xem chi tiết bài tập (Học sinh ngoài lớp bị chặn `403 Forbidden`).
- **`PATCH /api/v1/assignments/{assignment_id}`**: Cập nhật thông số bài tập (Giáo viên chủ nhiệm hoặc Admin).
- **`POST /api/v1/assignments/{assignment_id}/publish`**: Xuất bản bài tập để học sinh trong lớp bắt đầu làm bài.
- **`POST /api/v1/assignments/{assignment_id}/cancel`**: Hủy bài tập.
- **`GET /api/v1/assignments/{assignment_id}/submissions`**: Bảng tổng hợp điểm số (Gradebook) của toàn bộ học sinh trong lớp (trạng thái: NOT_STARTED, IN_PROGRESS, SUBMITTED, điểm số, thời gian nộp bài, tỷ lệ đạt).

### 5.3. Quy Trình Học Sinh Làm Bài Tập
- **`POST /api/v1/assignments/{assignment_id}/start`**: Bắt đầu hoặc tiếp tục bài tập đang làm dở.
  - Kiểm tra điều kiện: Phải là thành viên lớp học, bài tập đang mở, chưa quá hạn (nếu không cho nộp muộn), chưa vượt quá số lượt làm bài cho phép (`max_attempts`).
  - Bảo mật: Trả về snapshot câu hỏi **không chứa đáp án đúng**.
- **`PUT /api/v1/exams/attempts/{attempt_id}/answers/{question_id}`**: Tự động lưu đáp án câu hỏi (Autosave real-time).
- **`GET /api/v1/assignments/{assignment_id}/my-attempt`**: Xem trạng thái và các câu trả lời đã lưu của học sinh.
- **`POST /api/v1/assignments/{assignment_id}/submit`**: Nộp bài tập.
  - Tự động kích hoạt Server-side Auto-Grading Engine để tính điểm.
  - Xử lý nộp bài trùng lặp (Idempotent): Trả về kết quả đã chấm mà không nhân đôi bản ghi.
  - Tôn trọng chính sách `allow_review` của bài tập.

---

## 6. GIA SƯ AI & PHÂN TÍCH LỖI SAI (AI TUTOR ENGINE)

### `POST /api/v1/ai/analyze-wrong-answer`
- **Mục đích**: Phân tích chuyên sâu một câu hỏi học sinh làm sai bằng Gemini AI.
- **Body**:
  ```json
  {
    "question_id": "uuid-...",
    "student_selected_option_id": "uuid-option-b",
    "attempt_id": "uuid-attempt-..."
  }
  ```
- **Response 200**:
  ```json
  {
    "error_category": "MISAPPLIED_FORMULA",
    "diagnosis_title": "Nhầm lẫn công thức đạo hàm hàm hợp",
    "explanation": "Em đã tính đạo hàm của hàm số hợp theo biến số ban đầu mà quên nhân với đạo hàm của hàm u(x)...",
    "step_by_step_guidance": [
      "Bước 1: Nhận diện đây là dạng u(x) = x^2 + 1",
      "Bước 2: Áp dụng công thức (u^n)' = n * u^(n-1) * u'",
      "Bước 3: Tính u'(x) = 2x rồi nhân vào kết quả..."
    ],
    "remedial_question": {
      "content": "Tính đạo hàm của hàm số $y = (2x^3 - 1)^4$",
      "options": [
        { "key": "A", "content": "$y' = 24x^2(2x^3 - 1)^3$", "is_correct": true },
        { "key": "B", "content": "$y' = 4(2x^3 - 1)^3$", "is_correct": false },
        { "key": "C", "content": "$y' = 12x^2(2x^3 - 1)^3$", "is_correct": false },
        { "key": "D", "content": "$y' = 24x(2x^3 - 1)^3$", "is_correct": false }
      ],
      "explanation": "Áp dụng đúng công thức hàm hợp: $y' = 4(2x^3 - 1)^3 \\cdot (2x^3 - 1)' = 4(2x^3 - 1)^3 \\cdot 6x^2 = 24x^2(2x^3 - 1)^3$."
    }
  }
  ```

### `POST /api/v1/ai/tutor-chat`
- **Mục đích**: Đối thoại Socratic 1-on-1 với AI Tutor giải đáp thắc mắc bài giảng.
- **Body**:
  ```json
  {
    "conversation_id": "uuid-optional",
    "lesson_id": "uuid-optional",
    "message": "Thầy ơi giải thích giúp em tại sao sin^2(x) + cos^2(x) luôn bằng 1 với ạ?"
  }
  ```
- **Response 200**:
  ```json
  {
    "conversation_id": "uuid-...",
    "reply": "Chào em! Để hiểu tại sao $\\sin^2(x) + \\cos^2(x) = 1$, chúng ta hãy quay lại tam giác vuông và định lý Pytago nhé...",
    "suggested_followups": [
      "Định lý Pytago liên quan thế nào đến đường tròn lượng giác?",
      "Công thức này có áp dụng cho góc âm được không?"
    ]
  }
  ```

---

## 5. NĂNG LỰC & LỘ TRÌNH HỌC TẬP (MASTERY & ANALYTICS)

- `GET /api/v1/analytics/student/overview` — Tổng hợp điểm số, thời gian học, radar năng lực theo môn.
- `GET /api/v1/analytics/student/mastery` — Độ thành thạo (%) của tất cả các chủ đề.
- `GET /api/v1/analytics/student/knowledge-gaps` — Danh sách các lỗ hổng kiến thức cần khắc phục khẩn cấp.
- `GET /api/v1/analytics/student/recommended-practice` — Lộ trình luyện tập thích ứng đề xuất riêng cho học sinh.

---

## 6. LỚP HỌC & GIÁO VIÊN (CLASSROOMS & ASSIGNMENTS)

- `GET /api/v1/classrooms` — Danh sách lớp học (Giáo viên xem lớp tạo ra, Học sinh xem lớp đã tham gia).
- `POST /api/v1/classrooms` — Tạo lớp học mới và sinh mã code tham gia. [Giáo viên]
- `POST /api/v1/classrooms/join` — Học sinh nhập mã code để tham gia lớp học.
- `GET /api/v1/classrooms/{class_id}/members` — Danh sách học sinh trong lớp.
- `POST /api/v1/classrooms/{class_id}/assignments` — Giao bài tập cho lớp. [Giáo viên]
- `GET /api/v1/classrooms/{class_id}/gradebook` — Bảng điểm và phân tích năng lực cả lớp. [Giáo viên]

---

## 7. QUẢN TRỊ HỆ THỐNG & AI MONITORING (ADMIN)

- `GET /api/v1/admin/users` — Quản trị danh sách người dùng, thay đổi vai trò hoặc trạng thái.
- `GET /api/v1/admin/ai/metrics` — Thống kê số lượng request, token tiêu thụ, chi phí Gemini theo thời gian thực.
- `GET /api/v1/admin/audit-logs` — Truy vết nhật ký các hành động nhạy cảm trong hệ thống.
