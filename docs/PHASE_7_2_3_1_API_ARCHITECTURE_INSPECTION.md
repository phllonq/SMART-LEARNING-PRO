# BÁO CÁO KIỂM TRA KIẾN TRÚC API — SUBPHASE 7.2.3.1
## API ARCHITECTURE, ROUTING & DEPENDENCY INJECTION INSPECTION

**Dự án:** SMART LEARNING PRO  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Vai trò:** Senior Backend Engineer & API Architect  
**Thời gian kiểm tra:** 23/11/2026  
**Git Baseline:** `d6326e5415cb125b62fbe12aea077ecf921d3a88`  
**Trạng thái kiểm tra:** **HOÀN TẤT (INSPECTION COMPLETE)**

---

## 1. MỤC TIÊU VÀ PHẠM VI

Trước khi bắt đầu triển khai code cho Phase 7.2.3, đợt kiểm tra này rà soát toàn bộ cấu trúc kiến trúc FastAPI, cơ chế Dependency Injection, Authentication/Authorization, Exception Handling, và hệ thống test integration hiện có trong mã nguồn nhằm bảo đảm router mới tuân thủ 100% các quy chuẩn của hệ thống mà không tạo ra các mẫu thiết kế dị biệt.

---

## 2. KẾT QUẢ KIỂM TRA KIẾN TRÚC (ARCHITECTURAL INVENTORY)

### 2.1. Cấu trúc Router & Đăng ký Router trong Application Entrypoint
- **Application Entrypoint:** [backend/app/main.py](file:///e:/SMART-LEARNING-PRO/backend/app/main.py).
- **Quy ước Versioning & Prefix:**
  - Prefix gốc API v1: `settings.API_V1_PREFIX = "/api/v1"` (định nghĩa trong [config.py](file:///e:/SMART-LEARNING-PRO/backend/app/config.py)).
  - Các router được include trong `main.py` qua:
    ```python
    app.include_router(module_router, prefix=settings.API_V1_PREFIX)
    ```
- **Kế hoạch đăng ký Router AI Diagnostics:**
  - Định nghĩa router tại: `backend/app/modules/ai_engine/diagnostics/router.py`.
  - Prefix nội bộ của router: `prefix="/ai/diagnostics"`, tags=`["AI Diagnostics"]`.
  - Route endpoint: `@router.post("/wrong-answer", response_model=WrongAnswerDiagnosticResponse, ...)`
  - Khi mount vào `main.py` với `prefix=settings.API_V1_PREFIX`, đường dẫn đầy đủ chính xác là:
    `POST /api/v1/ai/diagnostics/wrong-answer` (khớp hoàn toàn với quyết định kiến trúc đã phê duyệt).

### 2.2. Dependency Injection Conventions
- **Database Session:** `db: AsyncSession = Depends(get_db)` (từ [app/core/database.py](file:///e:/SMART-LEARNING-PRO/backend/app/core/database.py)). Quản lý commit/rollback qua context session tự động đóng sau request.
- **Service Dependency:**
  - Các module hiện tại khởi tạo service hoặc inject dependency qua FastAPI `Depends()`.
  - Để hỗ trợ override trong pytest (`app.dependency_overrides`), service `WrongAnswerDiagnosticService` sẽ được cung cấp qua factory dependency:
    ```python
    def get_wrong_answer_diagnostic_service() -> WrongAnswerDiagnosticService:
        return WrongAnswerDiagnosticService()
    ```
  - `WrongAnswerDiagnosticService` nội bộ sử dụng cache singleton `cache_service` và nạp provider qua `get_llm_provider()` (hỗ trợ client reuse, không khởi tạo client mới vô ích cho mỗi request).

### 2.3. Authentication & Current User Dependencies
- **Tập tin định nghĩa:** [backend/app/core/dependencies.py](file:///e:/SMART-LEARNING-PRO/backend/app/core/dependencies.py).
- **Cơ chế trích xuất Token:** `get_token_from_request` ưu tiên Bearer Token trong header `Authorization: Bearer <token>`, sau đó fallback về HttpOnly Cookie `access_token`.
- **Dependency xác thực người dùng:**
  - `get_current_user`: Giải mã JWT access token, truy vấn database để nạp thực thể `User`, kiểm tra `user.is_active`. Ném `InvalidCredentialsException` (HTTP 401) nếu chưa đăng nhập hoặc token không hợp lệ; ném HTTP 403 nếu tài khoản bị khóa.
- **Ràng buộc vai trò (Role Gate):**
  - Scope hiện tại của tính năng chẩn đoán lỗi sai chỉ dành riêng cho **STUDENT**.
  - Xây dựng dependency chuyên biệt `get_current_student`:
    ```python
    async def get_current_student(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != UserRole.STUDENT.value:
            raise PermissionDeniedException("Tính năng chẩn đoán chỉ dành riêng cho học sinh (STUDENT).")
        return current_user
    ```
  - Đảm bảo TEACHER hoặc ADMIN khi gọi vào endpoint sẽ bị từ chối với HTTP 403 Forbidden. Đồng thời, quyền sở hữu bài thi (`attempt.student_id == student.id`) tiếp tục được service kiểm tra một cách chặt chẽ.

### 2.4. Exception Hierarchy & Error Response Format
- **Định dạng lỗi chuẩn của hệ thống:**
  Trong `main.py`, FastAPI trả về định dạng chuẩn:
  ```json
  {
    "detail": "<Nội dung thông báo lỗi bằng tiếng Việt hoặc tiếng Anh chuẩn>"
  }
  ```
- **Hệ thống Exception của AI Diagnostics:**
  Định nghĩa tại [backend/app/modules/ai_engine/diagnostics/exceptions.py](file:///e:/SMART-LEARNING-PRO/backend/app/modules/ai_engine/diagnostics/exceptions.py), tất cả kế thừa từ `DiagnosticError(Exception)` với thuộc tính `status_code` và `message`:
  - `AttemptNotFoundException` -> HTTP 404
  - `DiagnosticUnauthorizedException` -> HTTP 403
  - `AttemptNotSubmittedException` -> HTTP 400
  - `QuestionNotInAttemptException` -> HTTP 404
  - `QuestionAlreadyCorrectException` -> HTTP 400
  - `GradingUnavailableException` -> HTTP 422
  - `InsufficientEvidenceException` -> HTTP 422
  - `AIMalformedOutputException` -> HTTP 502
  - `AIProviderUnavailableException` -> HTTP 503
  - `CacheCoordinationException` -> HTTP 503
  - `AITimeoutException` -> HTTP 504
- **Đăng ký Exception Handler:**
  Đăng ký `@app.exception_handler(DiagnosticError)` trong `main.py` để tự động trả về `JSONResponse(status_code=exc.status_code, content={"detail": exc.message})`.
  Điều này bảo đảm:
  - 100% không để lộ stack trace nội bộ ra client.
  - 100% không để lộ API key, secrets hay raw external exception.
  - Phân loại HTTP status code chuẩn mực (400, 403, 404, 422, 502, 503, 504), không chuyển tất cả thành 500.

### 2.5. Request & Response Schemas
- **Request:** `WrongAnswerDiagnosticRequest` (tại [schemas.py](file:///e:/SMART-LEARNING-PRO/backend/app/modules/ai_engine/diagnostics/schemas.py)).
  - Bổ sung cấu hình `model_config = {"str_strip_whitespace": True, "extra": "forbid"}` để cấm tuyệt đối client truyền thêm các trường lạ (như `is_correct`, `correct_answer`, `system_prompt`).
  - Chỉ nhận 2 trường định danh UUID v4: `attempt_id` và `question_id`.
- **Response:** `WrongAnswerDiagnosticResponse` chứa `DiagnosticDetail`, `cached: bool`, `latency_ms: float`, `prompt_version: str`, `is_sufficient: bool`.
- **Read-Only Invariant:** Endpoint chỉ gọi hàm query đọc DB và gửi prompt tới service, tuyệt đối không có lệnh INSERT/UPDATE nào đối với các bảng `exam_attempts`, `student_answers`, `questions`, `exams`, `exam_results`.

### 2.6. Quy ước Test Integration hiện hữu
- Sử dụng `client: httpx.AsyncClient` từ [conftest.py](file:///e:/SMART-LEARNING-PRO/backend/tests/conftest.py).
- Khởi tạo session database test qua `AsyncSessionLocal()`.
- Tạo token đăng nhập bằng `create_access_token({"sub": user.id, "type": "access"})` từ [app/core/security.py](file:///e:/SMART-LEARNING-PRO/backend/app/core/security.py) để truyền vào header `Authorization: Bearer <token>`.

---

## 3. KẾT LUẬN VÀ BƯỚC TIẾP THEO

Kiến trúc hiện tại của dự án hoàn toàn trong sạch, nhất quán và sẵn sàng cho việc tích hợp.
Sau khi báo cáo kiểm tra này được hoàn tất, tiến hành ngay:
1. Cấu hình `extra="forbid"` trong `WrongAnswerDiagnosticRequest`.
2. Tạo file `dependencies.py` và `router.py` trong `backend/app/modules/ai_engine/diagnostics/`.
3. Đăng ký router và `DiagnosticError` exception handler trong `main.py`.
4. Viết toàn diện 30+ test integration trong `backend/tests/test_ai_diagnostics_api_723.py`.
