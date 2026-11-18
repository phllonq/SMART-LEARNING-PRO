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

## 3. NGÂN HÀNG CÂU HỎI & ĐỀ THI (QUESTIONS & EXAMS)

- `GET /api/v1/questions` — Danh sách câu hỏi (Lọc theo môn, lớp, chủ đề, độ khó). [Giáo viên / Admin]
- `POST /api/v1/questions` — Tạo câu hỏi mới kèm phương án và KaTeX. [Giáo viên / Admin]
- `GET /api/v1/exams` — Danh sách đề kiểm tra và đề thi thử công khai.
- `POST /api/v1/exams` — Tạo đề thi mới (Tự động từ ngân hàng hoặc chọn lọc thủ công). [Giáo viên]
- `GET /api/v1/exams/{exam_id}` — Chi tiết đề thi (thông tin tổng quan trước khi vào phòng thi).
- `POST /api/v1/exams/{exam_id}/start` — Bắt đầu một lượt thi mới (Khởi tạo `exam_attempt` và trả về danh sách câu hỏi).
- `POST /api/v1/exams/attempts/{attempt_id}/save-answer` — Lưu câu trả lời tức thì (Autosave background).
  - **Body**: `{ "question_id": "...", "selected_option_id": "...", "answer_text": "...", "is_flagged": false }`
- `POST /api/v1/exams/attempts/{attempt_id}/submit` — Nộp bài thi, kích hoạt engine tự động chấm điểm.
- `GET /api/v1/exams/attempts/{attempt_id}/result` — Xem bảng điểm kết quả, số câu đúng/sai, độ chính xác.

---

## 4. GIA SƯ AI & PHÂN TÍCH LỖI SAI (AI TUTOR ENGINE)

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
