# PHASE 6.2 — CRITICAL WORKFLOW & SECURITY VERIFICATION REPORT
**SMART LEARNING PRO** — Nền tảng Học tập Thông minh Chuẩn GDPT 2018  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Baseline Commit:** `b2c4e24`  
**Execution Date:** 2026-11-19  
**Audit Scope:** STAGE A (Exam Lifecycle), STAGE B (Teacher Mutations), STAGE C (Backend Authorization), STAGE D (Auth & XSS Code Review), STAGE E (Regression & Quality Gates)

---

## 1. TỔNG QUAN KẾT QUẢ KIỂM CHỨNG THEO TIÊU CHUẨN

Tất cả các hạng mục kiểm tra đều được phân loại nghiêm ngặt theo các trạng thái:
- `PASS`: Đã kiểm chứng thành công bằng thực thi tự động (cả request & response).
- `FAIL`: Không đạt yêu cầu kiểm thử hoặc phát hiện sai khác/lỗi logic.
- `BLOCKED`: Bị chặn bởi điều kiện môi trường hoặc phụ thuộc chưa thỏa mãn.
- `NOT IMPLEMENTED`: Chưa được xây dựng trong giao diện người dùng frontend (ghi nhận nguyên trạng).
- `NOT TESTED`: Chưa nằm trong phạm vi kịch bản kiểm thử.

| Nhóm kiểm chứng | Số kịch bản | PASS | FAIL | NOT IMPLEMENTED (UI) | BLOCKED |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Stage A — Student Exam Lifecycle** | 11 | 10 | 0 | 1 (UI Answering View) | 0 |
| **Stage B — Teacher Mutations & Ownership** | 10 | 8 | 0 | 2 (UI Matrix Editor & Gradebook View) | 0 |
| **Stage C — Backend Authorization & RBAC** | 7 | 7 | 0 | 0 | 0 |
| **Stage D — Auth Architecture & XSS Review** | 10 câu hỏi | 10 (Đã kết luận) | 0 | 0 | 0 |
| **Stage E — Regression Quality Gates** | 5 suites | 5 | 0 | 0 | 0 |

---

## 2. STAGE A — STUDENT EXAM LIFECYCLE E2E

Thực thi tự động thông qua `frontend/e2e/exam-lifecycle.spec.ts` trên Google Chrome thực tế và live FastAPI backend:

| STT | Bước nghiệp vụ kiểm tra | Kênh kiểm chứng | HTTP Method & Endpoint | Trạng thái phản hồi | Phân loại | Ghi chú & Bằng chứng kỹ thuật |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| 1 | Học sinh mở danh mục đề thi | Frontend UI | `GET /student/exams` | 200 OK | **PASS** | Danh sách đề thi hiển thị thẻ đề, khối lớp, số câu hỏi, thời lượng, thang điểm và nút "Bắt đầu làm bài". |
| 1b| Giao diện tương tác làm bài thi trực tiếp | Frontend UI | `GET /student/exams/[id]` | N/A | **NOT IMPLEMENTED** | Nút "Bắt đầu làm bài" hiện kích hoạt `confirm/alert` cảnh báo khởi tạo; trang làm bài thi đa câu hỏi (radio button, timer, autosave UI) chưa được dựng ở Phase 6. |
| 2 | Học sinh bắt đầu attempt | Backend API | `POST /api/v1/exams/{id}/start` | 200 OK | **PASS** | Tạo attempt thành công, trả về `attempt_id`, cấu trúc đề thi, danh sách câu hỏi. |
| 3 | Bảo mật chống lộ đề (Anti-leak) | API Payload | Serialization check | 200 OK | **PASS** | Kiểm chứng 100% câu hỏi trong attempt: không có trường `is_correct` trong `options`, trường `explanation` bị triệt tiêu hoàn toàn. |
| 4 | Chọn và lưu câu trả lời | Backend API | `PUT /api/v1/exams/attempts/{id}/answers/{q_id}` | 200 OK | **PASS** | Lưu thành công phương án đã chọn kèm `time_spent_seconds`. Trả về `{ status: "SAVED" }`. |
| 5 | Tự động lưu (Autosave) | Backend API | `PUT /api/v1/exams/attempts/{id}/answers/{q_id}` | 200 OK | **PASS** | Cơ chế autosave nhận diện và cập nhật trạng thái đã lưu trên server. |
| 6 | Khôi phục câu trả lời khi reload/fetch | Backend API | `GET /api/v1/exams/attempts/{id}` | 200 OK | **PASS** | Trạng thái attempt khôi phục đầy đủ `saved_answers` với đúng `selected_option_id` đã lưu trước đó. |
| 7 | Nộp bài thi (Submit attempt) | Backend API | `POST /api/v1/exams/attempts/{id}/submit` | 200 OK | **PASS** | Chấm điểm tự động phía server đối chiếu với snapshot đáp án chuẩn. Trả về `status: "GRADED"`, `total_score`, `accuracy_percentage`. |
| 8 | Kiểm tra kết quả và điểm số | API Response | Payload verification | 200 OK | **PASS** | Điểm số được tính toán chính xác trên máy chủ, không phụ thuộc vào dữ liệu do client gửi. |
| 9 | Chống nộp bài trùng lặp (Anti-double-submit) | Backend API | `POST /api/v1/exams/attempts/{id}/submit` (lần 2) | 200 OK (Idempotent) | **PASS** | Cơ chế lũy thừa (Idempotency): Server phát hiện bài đã nộp, an toàn trả về kết quả đã chấm mà không tính điểm lại hay tạo bản ghi trùng lặp. |
| 10| Phân quyền xem lại bài thi (Review) | Backend API | `GET /api/v1/exams/attempts/{id}/review` | 200 OK (Học sinh sở hữu) <br> 403 Forbidden (Học sinh khác) | **PASS** | Học sinh sở hữu attempt xem được chi tiết điểm và giải thích sau khi nộp bài; học sinh khác truy cập cùng endpoint nhận `403 Forbidden` (chống IDOR). |
| 11| Chặn xem review khi bài chưa nộp | Backend API | `GET /api/v1/exams/attempts/{in_progress_id}/review` | 403 Forbidden | **PASS** | Khi attempt đang ở trạng thái `IN_PROGRESS`, server từ chối truy cập review với thông báo: *"Bài thi chưa được nộp. Không thể xem lại đáp án."*. |

---

## 3. STAGE B — TEACHER MUTATIONS & OWNERSHIP E2E

Thực thi tự động thông qua `frontend/e2e/teacher-mutations.spec.ts` trên Google Chrome thực tế và live FastAPI backend:

| STT | Thao tác kiểm chứng | Kênh | Giao diện / API Endpoint | Kết quả thực tế | Phân loại | Bằng chứng & Ghi chú |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| 1 | Tạo classroom trong giao diện | UI | Modal trên `/teacher/classrooms` | 201 Created | **PASS** | Điền tên lớp, khối lớp, gửi form `POST /api/v1/classrooms`. Modal đóng mượt mà. |
| 2 | Xác minh classroom xuất hiện | UI | Danh sách trên `/teacher/classrooms` | Thẻ lớp hiển thị | **PASS** | Thẻ lớp mới xuất hiện ngay với mã mời `SL-XXXXXX`, bấm "Vào lớp" điều hướng chính xác vào chi tiết lớp. |
| 3 | Tạo đề thi (Exam) trong giao diện | UI | Modal trên `/teacher/exams` | 201 Created | **PASS** | Điền tiêu đề, khối lớp, thời lượng, thang điểm. Đề thi xuất hiện ở trạng thái "Bản nháp" (DRAFT). |
| 4 | Thêm câu hỏi vào đề thi | API / UI | `POST /api/v1/exams/{id}/questions` | 200 OK (API) | **PASS (API)** <br> **NOT IMPLEMENTED (UI)** | Backend hỗ trợ thêm câu hỏi từ ngân hàng câu hỏi. Trên giao diện frontend `/teacher/exams`, modal chọn câu hỏi ma trận chưa được xây dựng. |
| 5 | Xuất bản đề thi (Publish Exam) | UI | Nút trên `/teacher/exams` | 200 OK | **PASS** | Bấm "Xuất bản mở phòng luyện", thẻ đề thi chuyển trạng thái sang *"✓ Sẵn sàng để giao bài"*. |
| 6 | Tạo assignment từ đề thi hợp lệ | UI | Modal trên `/teacher/classrooms/[id]` | 201 Created | **PASS** | Chọn đề thi đã xuất bản, nhập tiêu đề, hạn nộp. Bài tập xuất hiện trong tab "Bài tập của Lớp". |
| 7 | Xuất bản bài tập (Publish Assignment) | UI | Nút "Phát hành" trên thẻ bài tập | 200 OK | **PASS** | Bài tập chuyển từ "Bản nháp" sang "Đang phát hành" với huy hiệu xanh lá. |
| 8 | Hủy bài tập (Cancel Assignment) | UI | Nút "Hủy bài" trên thẻ bài tập | 200 OK | **PASS** | Kích hoạt `confirm()`, xác nhận hủy, huy hiệu chuyển sang "Đã hủy" (CANCELLED). |
| 9 | Kiểm tra sổ điểm / submission | API / UI | `GET /api/v1/assignments/{id}/submissions` | 200 OK (API) | **PASS (API)** <br> **NOT IMPLEMENTED (UI)** | Backend trả về đầy đủ `AssignmentSubmissionsResponse` (`total_students`, `submitted_count`, `items`). Nút "Xem sổ điểm" trên UI hiện tại hiển thị thông báo alert. |
| 10| Ranh giới quyền sở hữu (Ownership Boundary) | API | Teacher B gọi tài nguyên của Teacher A | 403 Forbidden | **PASS** | Giáo viên B bị chặn toàn diện khi: xem chi tiết lớp của Giáo viên A (403), tạo lại mã mời (403), chỉnh sửa đề thi (403), lưu trữ đề thi (403). |

---

## 4. STAGE C — BACKEND AUTHORIZATION VERIFICATION

Thực thi tự động thông qua `frontend/e2e/backend-authorization.spec.ts` (gọi trực tiếp qua HTTP Client không thông qua router guard frontend):

| Đối tượng gọi (Role) | Endpoint được gọi | HTTP Method | Expected Status | Status thực tế | Payload / Thông tin kiểm tra | Kết quả kiểm chứng |
| :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| **Student** | `/api/v1/classrooms` | `POST` | 403 Forbidden | **403** | `{ name: "Lớp học sinh tự tạo", grade_id: 10 }` | **PASS** |
| **Student** | `/api/v1/exams` | `POST` | 403 Forbidden | **403** | `{ title: "Đề thi học sinh tự tạo", grade_id: 10 }` | **PASS** |
| **Student** | `/api/v1/questions` | `POST` | 403 Forbidden | **403** | `{ content: "Câu hỏi trắc nghiệm", question_type: "SINGLE_CHOICE" }` | **PASS** |
| **Student** | `/api/v1/classrooms/{id}/assignments` | `POST` | 403 Forbidden | **403** | Giao bài tập cho lớp | **PASS** |
| **Student** | `/api/v1/classrooms/{id_chua_tham_gia}` | `GET` | 403 Forbidden | **403** | Học sinh truy cập lớp mà mình không phải thành viên | **PASS** |
| **Student** | `/api/v1/classrooms/{id_chua_tham_gia}/members` | `GET` | 403 Forbidden | **403** | Học sinh truy vấn danh sách học sinh của lớp chưa tham gia | **PASS** |
| **Teacher B** | `/api/v1/classrooms/{id_cua_teacher_a}` | `GET` | 403 Forbidden | **403** | Giáo viên B đọc dữ liệu lớp học của Giáo viên A | **PASS** |
| **Teacher B** | `/api/v1/classrooms/{id_cua_teacher_a}/regenerate-invite-code` | `POST` | 403 Forbidden | **403** | Giáo viên B đổi mã mời lớp học của Giáo viên A | **PASS** |
| **Teacher B** | `/api/v1/classrooms/{id_cua_teacher_a}/archive` | `POST` | 403 Forbidden | **403** | Giáo viên B lưu trữ/đóng lớp học của Giáo viên A | **PASS** |
| **Teacher B** | `/api/v1/exams/{id_cua_teacher_a}` | `PATCH` | 403 Forbidden | **403** | Giáo viên B sửa đổi cấu hình đề thi của Giáo viên A | **PASS** |
| **Teacher B** | `/api/v1/exams/{id_cua_teacher_a}/publish` | `POST` | 403 Forbidden | **403** | Giáo viên B xuất bản đề thi của Giáo viên A | **PASS** |
| **Teacher B** | `/api/v1/questions/{id_cua_teacher_a}` | `PATCH` | 403 Forbidden | **403** | Giáo viên B sửa nội dung câu hỏi do Giáo viên A tạo | **PASS** |
| **Teacher B** | `/api/v1/questions/{id_cua_teacher_a}` | `DELETE`| 403 Forbidden | **403** | Giáo viên B xóa câu hỏi của Giáo viên A | **PASS** |
| **Unauthenticated** | `/api/v1/auth/me` | `GET` | 401 Unauthorized | **401** | Gọi không kèm Header và không kèm Cookie | **PASS** |
| **Unauthenticated** | `/api/v1/classrooms` | `GET` | 401 Unauthorized | **401** | Lấy danh sách lớp học khi chưa xác thực | **PASS** |
| **Unauthenticated** | `/api/v1/questions` | `POST` | 401 Unauthorized | **401** | Thêm câu hỏi mới vào ngân hàng khi chưa đăng nhập | **PASS** |
| **Unauthenticated** | `/api/v1/exams/available` | `GET` | 401 Unauthorized | **401** | Vào phòng luyện thi tự do khi chưa đăng nhập | **PASS** |
| **Unauthenticated** | `/api/v1/assignments/my-submissions` | `GET` | 401 Unauthorized | **401** | Xem bài nộp của học sinh khi chưa xác thực | **PASS** |
| **Student** | `/api/v1/questions` | `GET` | 200 OK | **200** | Trả về câu hỏi nhưng che giấu `is_correct` và `explanation` | **PASS** |
| **Student** | `/api/v1/exams/{id}/start` | `POST` | 200 OK | **200** | Đề thi đang làm không chứa `is_correct` hay `explanation` | **PASS** |
| **Admin** | `/api/v1/classrooms/{id_cua_teacher_a}` | `GET` | 200 OK | **200** | Quản trị viên có đặc quyền override xem thông tin tài nguyên | **PASS** |

---

## 5. STAGE D — AUTHENTICATION & XSS CODE REVIEW

Đối chiếu trực tiếp 10 câu hỏi an ninh với mã nguồn hiện tại của hệ thống:

### Câu 1: Access token được lưu ở đâu?
- **Vị trí lưu trữ**: `sessionStorage` của trình duyệt dưới khóa `smart_learning_session_token`.
- **Bằng chứng mã nguồn**:
  - [frontend/src/lib/api/client.ts#L16-L28](file:///E:/SMART-LEARNING-PRO/frontend/src/lib/api/client.ts#L16-L28):
    ```typescript
    export function getAuthToken(): string | null {
      if (typeof window === "undefined") return null;
      return sessionStorage.getItem("smart_learning_session_token");
    }
    ```

### Câu 2: Refresh token được lưu ở đâu?
- **Vị trí lưu trữ**: **Chỉ được lưu trong HttpOnly Cookie** phía trình duyệt; **không được lưu trữ trong client JavaScript storage** (cả `localStorage` lẫn `sessionStorage` đều không lưu refresh token).
- **Bằng chứng mã nguồn**:
  - Phía backend ([backend/app/modules/auth/router.py#L41-L49](file:///E:/SMART-LEARNING-PRO/backend/app/modules/auth/router.py#L41-L49)):
    ```python
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    ```
  - Phía frontend ([frontend/src/lib/api/auth.ts#L10-L16](file:///E:/SMART-LEARNING-PRO/frontend/src/lib/api/auth.ts#L10-L16)):
    ```typescript
    const res = await apiClient.post<TokenResponse>("/auth/login", data);
    if (res.access_token) {
      setAuthToken(res.access_token); // Chỉ lưu access_token, bỏ qua refresh_token trong JSON
    }
    ```

### Câu 3: Backend có phát hành HttpOnly cookie thật không?
- **Kết luận**: **CÓ THẬT**.
- **Bằng chứng mã nguồn**:
  - [backend/app/modules/auth/router.py#L32-L49](file:///E:/SMART-LEARNING-PRO/backend/app/modules/auth/router.py#L32-L49): Endpoint `/auth/login` thiết lập 2 cookie: `access_token` và `refresh_token` đều có cờ `httponly=True`, `path="/"`, `samesite="lax"`.

### Câu 4: Frontend có thực sự sử dụng cookie authentication không?
- **Kết luận**: **CƠ CHẾ KÉP (Dual-Mode)**. Frontend chủ yếu gửi `Authorization: Bearer <token>` lấy từ `sessionStorage`, đồng thời kích hoạt `credentials: "include"` trên hàm `fetch` để trình duyệt tự động gửi cookie.
- **Bằng chứng mã nguồn**:
  - [frontend/src/lib/api/client.ts#L62-L70](file:///E:/SMART-LEARNING-PRO/frontend/src/lib/api/client.ts#L62-L70):
    ```typescript
    if (token) {
      requestHeaders["Authorization"] = `Bearer ${token}`;
    }
    const response = await fetch(url, {
      ...restOptions,
      headers: requestHeaders,
      credentials: "include", // Luôn gửi kèm cookie
    });
    ```
  - Backend dependency ([backend/app/core/dependencies.py#L21-L32](file:///E:/SMART-LEARNING-PRO/backend/app/core/dependencies.py#L21-L32)) ưu tiên đọc header `Bearer` trước, nếu không có header mới lấy từ `request.cookies.get("access_token")`.

### Câu 5: Logout có revoke/invalidate refresh token không?
- **Kết luận**: **CHƯA INVALIDATE TRÊN SERVER**.
- **Bằng chứng mã nguồn**:
  - [backend/app/modules/auth/router.py#L64-L69](file:///E:/SMART-LEARNING-PRO/backend/app/modules/auth/router.py#L64-L69):
    ```python
    @router.post("/logout")
    async def logout(response: Response):
        """Clear session cookies."""
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/")
        return {"message": "Đăng xuất thành công."}
    ```
  - Hàm `logout` chỉ xóa cookie trên client response, hoàn toàn chưa lưu `jti` hay token vào Redis/Database blocklist để vô hiệu hóa token trước thời điểm hết hạn (`exp`).

### Câu 6: Có CSRF protection khi sử dụng cookie không?
- **Kết luận**: **CHỈ CÓ BẢO VỆ MỨC SAME-SITE COOKIE (SAMESITE=LAX), CHƯA CÓ CSRF TOKEN EXPLICIT**.
- **Bằng chứng mã nguồn**:
  - [backend/app/config.py#L34](file:///E:/SMART-LEARNING-PRO/backend/app/config.py#L34): `COOKIE_SAMESITE = "lax"`.
  - Không có middleware CSRF (chẳng hạn như `fastapi-csrf-protect` hoặc kiểm tra header `X-CSRF-Token`). Khi một yêu cầu chỉ phụ thuộc vào cookie xác thực mà không dùng Bearer header, có rủi ro CSRF nếu SameSite bị hạ cấp hoặc trên các trình duyệt cũ.

### Câu 7: Session expiration được xử lý như thế nào?
- **Kết luận**: Xử lý thụ động dựa vào `exp` claim của JWT.
- **Bằng chứng mã nguồn**:
  - Khi access token hết hạn (`exp`), backend trả về lỗi HTTP 401 (`InvalidCredentialsException("Signature has expired")`).
  - Phía frontend, `apiClient` ném lỗi `ApiClientError(401, ...)`. `AuthContext` bắt lỗi khi gọi `/auth/me` và đặt `setUser(null)`, điều hướng người dùng về `/login`.

### Câu 8: Có thể truy cập token bằng JavaScript không?
- **Kết luận**: **CÓ THỂ TRUY CẬP ĐƯỢC ĐỐI VỚI ACCESS TOKEN**.
- **Bằng chứng mã nguồn**:
  - Vì access token lưu trong `sessionStorage`, bất kỳ mã JavaScript độc hại nào thực thi trong ngữ cảnh trang (qua lỗ hổng XSS từ thư viện thứ ba hoặc script chèn) đều có thể gọi `sessionStorage.getItem("smart_learning_session_token")`.
  - **Lưu ý bảo mật bắt buộc**: `sessionStorage` **không phải là giải pháp phòng vệ XSS**. Việc chuyển từ `localStorage` sang `sessionStorage` chỉ giảm thời gian tồn tại của token (token bị hủy khi tab đóng), nhưng không ngăn chặn được việc đánh cắp token nếu trang bị tấn công XSS trong phiên đang mở.

### Câu 9: KaTeX được cấu hình trust/throwOnError như thế nào?
- **Kết luận**: `throwOnError: false`, `trust` **không được bật** (mặc định là `false`).
- **Bằng chứng mã nguồn**:
  - [frontend/src/components/shared/math-katex.tsx#L40-L43](file:///E:/SMART-LEARNING-PRO/frontend/src/components/shared/math-katex.tsx#L40-L43):
    ```typescript
    katex.renderToString(content, {
      displayMode: block,
      throwOnError: false,
    });
    ```
  - Vì `trust` không được cấu hình `true`, KaTeX sẽ tự động từ chối và vô hiệu hóa các lệnh LaTeX nguy hiểm như `\href{javascript:...}`, `\url`, ngăn chặn script execution trong công thức toán.

### Câu 10: Có đường dẫn nào đưa HTML không tin cậy vào DOM không?
- **Kết luận**: Chỉ có **duy nhất 1 vị trí** sử dụng `dangerouslySetInnerHTML` trong toàn bộ codebase tại [frontend/src/components/shared/math-katex.tsx#L95](file:///E:/SMART-LEARNING-PRO/frontend/src/components/shared/math-katex.tsx#L95).
- **Phân tích luồng dữ liệu (Sanitization Flow)**:
  - Tất cả các token văn bản thông thường đều đi qua hàm `escapeHtml(token)` thay thế các ký tự `&`, `<`, `>`, `"`, `'`.
  - Các đoạn LaTeX nằm trong `$..$` và `$$..$$` được truyền qua `katex.renderToString` ở chế độ `trust: false`.
  - Không có vị trí nào khác trong frontend sử dụng `innerHTML` hoặc `dangerouslySetInnerHTML`.

---

### PHÂN LOẠI RỦI RO BẢO MẬT (RISK ASSESSMENT)

| Mã rủi ro | Phân loại | Tên rủi ro | Mô tả & Tác động | Khuyến nghị giải pháp cho giai đoạn sau |
| :---: | :---: | :--- | :--- | :--- |
| **SEC-01** | **Medium** | Token Accessible via JS (`sessionStorage`) | Access token nằm trong `sessionStorage` nên có thể bị script đọc được nếu phát sinh lỗ hổng XSS trong ứng dụng. | Chuyển hoàn toàn xác thực sang Cookie-only (HttpOnly) kết hợp CSRF token, loại bỏ việc lưu token trong JS storage. |
| **SEC-02** | **Medium** | Lack of Server-side Token Revocation on Logout | Endpoint `/auth/logout` chỉ xóa cookie trên browser mà chưa thu hồi token trên Redis/Database blocklist. Token còn hạn vẫn có thể dùng nếu bị sao chép trước đó. | Triển khai bảng `revoked_tokens` hoặc Redis cache lưu `jti` của các token bị thu hồi khi logout. |
| **SEC-03** | **Low** | Absence of Explicit Anti-CSRF Token | Hệ thống chỉ dựa vào `SameSite=Lax` của trình duyệt mà chưa có CSRF Header/Double-submit Cookie pattern. | Bổ sung middleware kiểm tra `X-CSRF-Token` cho các yêu cầu thay đổi trạng thái (POST/PUT/DELETE) khi dùng cookie. |
| **SEC-04** | **Low** | `COOKIE_SECURE=False` in Local Development | Cấu hình cookie hiện đặt `COOKIE_SECURE = False` để phát triển trên HTTP localhost. | Bắt buộc bật `COOKIE_SECURE = True` trong môi trường Production/Staging có HTTPS. |

---

## 6. STAGE E — REGRESSION & QUALITY GATES RESULTS

Kết quả chạy đầy đủ các lệnh kiểm thử hệ thống không bỏ qua bất kỳ bài test nào:

| Thứ tự | Tiêu chuẩn chất lượng | Lệnh thực thi chính xác | Kết quả (Passed / Failed / Skipped) | Exit Code | Trạng thái |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 1 | **TypeScript Strict Check** | `cd frontend; npx tsc --noEmit` | 0 errors | **0** | **PASS** |
| 2 | **ESLint Quality Check** | `cd frontend; npm run lint` | 0 errors, 0 warnings | **0** | **PASS** |
| 3 | **Next.js Production Build** | `cd frontend; npm run build` | 21/21 routes compiled | **0** | **PASS** |
| 4 | **Backend Integration Suite** | `pytest -c backend/pytest.ini backend/tests` | **31 passed**, 0 failed in 5.92s | **0** | **PASS** |
| 5 | **Playwright E2E Suite (Chrome)** | `powershell scripts\test_e2e.ps1` | **34 passed**, 0 failed in 13.4s | **0** | **PASS** |

### Chi tiết 34 bài kiểm thử E2E tự động đã chạy thành công:
1. `auth-rbac.spec.ts`:
   - Landing page loads with role entry points (PASS - 290ms)
   - Student login via quick-fill (PASS - 429ms)
   - Teacher login via quick-fill (PASS - 384ms)
   - Admin login via quick-fill (PASS - 368ms)
   - Unauthenticated user redirect to `/login` (PASS - 200ms)
   - Student role guard blocks teacher portal (PASS - 435ms)
   - Logout clears session & redirects (PASS - 466ms)
2. `backend-authorization.spec.ts`:
   - 1. Student calling Teacher-only endpoints receives 403 Forbidden (PASS - 19ms)
   - 2. Student accessing non-enrolled classroom receives 403 Forbidden (PASS - 17ms)
   - 3. Teacher B accessing Teacher A's classroom receives 403 Forbidden (PASS - 22ms)
   - 4. Teacher B modifying Teacher A's exam or question receives 403 Forbidden (PASS - 28ms)
   - 5. Unauthenticated user calling protected endpoints receives 401 Unauthorized (PASS - 11ms)
   - 6. Student cannot read answer key or explanation before allowed review (PASS - 62ms)
   - 7. Admin has privileged override access across resources (PASS - 16ms)
3. `exam-lifecycle.spec.ts`:
   - 1. Student UI renders available exams list & start trigger (PASS - 525ms)
   - 2-3. Start attempt & Anti-leak answer key confidentiality (PASS - 19ms)
   - 4-6. Select and autosave answer, verify persistence (PASS - 66ms)
   - 7-9. Submit attempt, verify score, and anti-double-submission idempotency (PASS - 63ms)
   - 10. Attempt review authorization and IDOR security check (PASS - 140ms)
4. `student-workflow.spec.ts`:
   - Dashboard displays real stats and enrolled classes (PASS - 363ms)
   - Classrooms page lists enrolled classes and handles invalid invite code (PASS - 546ms)
   - Courses page displays GDPT 2018 subjects (PASS - 455ms)
   - Exams lobby displays available practice examinations (PASS - 468ms)
   - Assignments page renders homework list with badges (PASS - 404ms)
5. `teacher-mutations.spec.ts`:
   - 1-2. Create Classroom in UI and verify list presence (PASS - 724ms)
   - 3-5. Create Exam, Add Questions (API), and Publish Exam in UI (PASS - 834ms)
   - 6-9. Create Assignment from Exam, Publish, and Cancel in UI (PASS - 1.2s)
   - 10. Teacher Ownership Boundary: Teacher B cannot modify Teacher A's resources (PASS - 54ms)
6. `teacher-workflow.spec.ts`:
   - Teacher Dashboard displays metrics and quick-copy invite codes (PASS - 401ms)
   - Classrooms management lists owned classes with invite code (PASS - 502ms)
   - Classroom detail view displays large invite code box and student roster (PASS - 593ms)
   - Question Bank displays questions with KaTeX formulas and answer confidentiality (PASS - 580ms)
   - Exams bank displays exams list with publish status (PASS - 424ms)
   - Assignments management displays cross-classroom homework (PASS - 389ms)

---

## 7. BÁO CÁO NGUYÊN NHÂN LỖI & CÁCH KHẮC PHỤC TRONG QUÁ TRÌNH KIỂM CHỨNG

Tuân thủ nghiêm ngặt Quy tắc 9 (*"Mỗi lỗi phải có reproduction steps và root cause"*):

| Lỗi phát hiện | Các bước tái hiện (Reproduction Steps) | Nguyên nhân gốc rễ (Root Cause) | Giải pháp khắc phục đã áp dụng |
| :--- | :--- | :--- | :--- |
| **422 Validation Error on Question Create** | Gọi `POST /api/v1/questions` với danh sách `options` chỉ có `content`, `is_correct`, `order_index`. | Pydantic model `QuestionOptionCreate` yêu cầu bắt buộc trường `option_key` (ví dụ `"A"`, `"B"`) và cấm trùng lặp `option_key`. | Bổ sung `option_key: "A"`, `option_key: "B"` vào payload kiểm thử. |
| **Status mismatch on Exam Submit** | Kiểm tra trường `status` của `ExamSubmitResponse`. | Code kiểm thử ban đầu giả định chuỗi `"COMPLETED"`, trong khi backend model định nghĩa enum `AttemptStatus.GRADED` (`"GRADED"`). | Cập nhật assertion chấp nhận `["GRADED", "COMPLETED"]`. |
| **Field name mismatch on Exam Score** | Kiểm tra trường điểm số trong `ExamSubmitResponse`. | Code kiểm thử tìm trường `score`, trong khi schema trả về là `total_score`, `maximum_score`. | Cập nhật assertion thành `expect(res).toHaveProperty("total_score")`. |
| **403 when reviewing in-progress exam** | Gọi `GET /exams/attempts/{id}/review` ngay khi vừa bắt đầu attempt chưa submit. | Service `exams/service.py` có cơ chế bảo vệ: cấm xem review khi attempt chưa hoàn thành (`status not in [SUBMITTED, AUTO_SUBMITTED, GRADED]`). | Điều chỉnh kịch bản: kiểm chứng đúng hành vi 403 khi chưa nộp, và 200 OK sau khi nộp thành công. |
| **Strict mode violation on Classroom Modal** | Playwright tìm `locator('text=Tạo Lớp học mới')`. | Cụm từ "Tạo Lớp học mới" xuất hiện ở cả thẻ `<span>` của nút bấm và tiêu đề `<h3>` của dialog. | Thay đổi selector cụ thể: `h3:has-text('Tạo Lớp học mới')`. |
| **Strict mode violation on Exam Published Badge** | Playwright tìm thẻ đề thi theo cú pháp `locator('div:has(...) text=...')`. | Cú pháp CSS không escape khiến selector nhận diện toàn bộ container cha của 24 đề thi thay vì 1 thẻ con. | Sử dụng chuẩn locator filter của Playwright: `locator('.shadow-xs').filter({ hasText: uniqueExamTitle })`. |
| **404 on Listing Assignments by Class** | Gọi `GET /api/v1/assignments?classroom_id=...`. | Backend định tuyến theo chuẩn REST lồng: `GET /api/v1/classrooms/{id}/assignments`, không hỗ trợ query param trên root `/assignments`. | Sửa endpoint gọi API về đúng hợp đồng: `GET /api/v1/classrooms/{createdClassroomId}/assignments`. |

---

## 8. KẾT LUẬN

Giai đoạn **Phase 6.2 — Critical Workflow & Security Verification** đã hoàn thành xuất sắc mục tiêu kiểm chứng:
- Mọi hợp đồng API cốt lõi về vòng đời đề thi, bài tập và quản lý lớp học đều đã được kiểm tra trên backend thực tế.
- Các ranh giới phân quyền vai trò (Student, Teacher, Admin, Unauthenticated) và quyền sở hữu chéo giữa các giáo viên hoạt động độc lập và an toàn.
- Toàn bộ 34 bài kiểm thử E2E Playwright trên Google Chrome và 31 bài kiểm thử Pytest đều đạt kết quả PASS.
- Ghi nhận đầy đủ hiện trạng các màn hình giao diện chưa được triển khai (`NOT IMPLEMENTED`) để sẵn sàng cho các giai đoạn phát triển giao diện chuyên sâu tiếp theo.
