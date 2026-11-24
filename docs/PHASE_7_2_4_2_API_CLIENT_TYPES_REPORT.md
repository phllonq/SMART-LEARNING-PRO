# BÁO CÁO TRIỂN KHAI PHASE 7.2.4.2
## AI Diagnostics API Client & TypeScript Contracts

**Dự án:** SMART LEARNING PRO  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Giai đoạn:** Phase 7.2.4.2 — API Client & Type Contracts  
**Ngày thực hiện:** 24/11/2026  
**Baseline Git HEAD:** `d6326e5415cb125b62fbe12aea077ecf921d3a88` (Bảo toàn nguyên vẹn)  
**Trạng thái:** **HOÀN THÀNH (PASS)**  

---

## 1. Xác minh hợp đồng Backend (Backend Contract Verification)

Trước khi tiến hành xây dựng các định nghĩa TypeScript, toàn bộ các tệp backend thẩm quyền đã được kiểm tra trực tiếp:
- `backend/app/modules/ai_engine/diagnostics/schemas.py`
- `backend/app/modules/ai_engine/diagnostics/service.py`
- `backend/app/modules/ai_engine/diagnostics/router.py`
- `backend/tests/test_ai_diagnostics_api_723.py`

### Bảng đối chiếu Backend Pydantic ↔ Frontend TypeScript

| Thành phần Contract | Backend Pydantic v2 Schema | Frontend TypeScript Contract | Trạng thái đối chiếu |
|---|---|---|:---:|
| **Enum loại lỗi** | `class ErrorCategory(str, Enum)`<br>- `CONCEPTUAL_MISCONCEPTION`<br>- `CALCULATION_ERROR`<br>- `QUESTION_MISREAD`<br>- `FORMULA_MISAPPLICATION`<br>- `LOGICAL_GAP`<br>- `INSUFFICIENT_INFORMATION` | `export type ErrorCategory =`<br>`  \| "CONCEPTUAL_MISCONCEPTION"`<br>`  \| "CALCULATION_ERROR"`<br>`  \| "QUESTION_MISREAD"`<br>`  \| "FORMULA_MISAPPLICATION"`<br>`  \| "LOGICAL_GAP"`<br>`  \| "INSUFFICIENT_INFORMATION";` | **KHỚP 100%** |
| **Request Model** | `WrongAnswerDiagnosticRequest`<br>- `attempt_id: str` (UUID v4)<br>- `question_id: str` (UUID v4)<br>- `extra = "forbid"` | `export interface WrongAnswerDiagnosticRequest {`<br>`  attempt_id: string;`<br>`  question_id: string;`<br>`}` | **KHỚP 100%** |
| **Detail Model** | `DiagnosticDetail`<br>- `error_category: ErrorCategory`<br>- `error_summary: str`<br>- `misconception_analysis: str`<br>- `step_by_step_guidance: str`<br>- `key_takeaway: str`<br>- `suggested_review: Optional[str] = None` | `export interface DiagnosticDetail {`<br>`  error_category: ErrorCategory;`<br>`  error_summary: string;`<br>`  misconception_analysis: string;`<br>`  step_by_step_guidance: string;`<br>`  key_takeaway: string;`<br>`  suggested_review?: string \| null;`<br>`}` | **KHỚP 100%** |
| **Response Model** | `WrongAnswerDiagnosticResponse`<br>- `diagnostic: Optional[DiagnosticDetail] = None`<br>- `cached: bool = False`<br>- `latency_ms: float = 0.0`<br>- `prompt_version: str`<br>- `is_sufficient: bool = True` | `export interface WrongAnswerDiagnosticResponse {`<br>`  diagnostic?: DiagnosticDetail \| null;`<br>`  cached: boolean;`<br>`  latency_ms: number;`<br>`  prompt_version: string;`<br>`  is_sufficient: boolean;`<br>`}` | **KHỚP 100%** |

### Phát hiện quan trọng trong Bước 1
1. **Trường gợi ý ôn tập:** Trong schema gốc của Backend, trường này có tên là `suggested_review` (kiểu `Optional[str]`), không phải `suggested_review_topic`. TypeScript contract đã tuân thủ đúng định danh thẩm quyền `suggested_review`.
2. **Trường hợp không đủ dữ liệu (`INSUFFICIENT_INFORMATION`):** Backend trả về mã HTTP **200 OK** với `is_sufficient: false` và `diagnostic.error_category: "INSUFFICIENT_INFORMATION"`. Đây không phải là một lỗi HTTP (không phải HTTP 422). Do đó, frontend xem đây là một trạng thái phản hồi hợp lệ đặc biệt để hiển thị UI phù hợp, không kích hoạt luồng xử lý ngoại lệ hay retry.
3. **Các trường metadata:** `cached` (boolean), `latency_ms` (number), `prompt_version` (string) đều được định kiểu bắt buộc rõ ràng.

---

## 2. Hợp đồng TypeScript (TypeScript Contracts)

Đã khởi tạo tệp mới:
`frontend/src/types/ai-diagnostics.ts`
và re-export công khai qua `frontend/src/types/index.ts`.

**Đặc điểm thiết kế:**
- Tuyệt đối không sử dụng `any`.
- Giữ nguyên định dạng snake_case (`attempt_id`, `question_id`, `error_category`, `error_summary`, `misconception_analysis`, `step_by_step_guidance`, `key_takeaway`, `suggested_review`, `latency_ms`, `prompt_version`, `is_sufficient`).
- Phân biệt rõ ràng giữa các trường bắt buộc và trường có thể `null` hoặc `undefined` (`suggested_review?: string | null`, `diagnostic?: DiagnosticDetail | null`).
- Cung cấp hằng số mảng `ERROR_CATEGORIES` đóng vai trò là danh mục chuẩn không thể sửa đổi (`readonly ErrorCategory[]`).

---

## 3. Triển khai API Client (API Client Implementation)

Đã khởi tạo tệp mới:
`frontend/src/lib/api/ai-diagnostics.ts`

### 3.1 Xử lý ghép URL và chống trùng lặp tiền tố `/api/v1`
Trong `frontend/src/lib/api/client.ts`, biến `API_BASE_URL` được cấu hình:
```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
```
Hàm `request()` thực hiện nối chuỗi:
```typescript
let url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
```
Do `API_BASE_URL` mặc định đã kết thúc bằng `/api/v1`, hằng số đường dẫn trong `ai-diagnostics.ts` được xác định chính xác là:
```typescript
export const DIAGNOSTICS_ENDPOINT = "/ai/diagnostics/wrong-answer";
```
Khi gọi `apiClient.post(DIAGNOSTICS_ENDPOINT, ...)`, URL cuối cùng được sinh ra là:
`http://localhost:8000/api/v1/ai/diagnostics/wrong-answer`
Hoàn toàn loại bỏ nguy cơ trùng lặp tiền tố thành `/api/v1/api/v1/ai/diagnostics/wrong-answer`. Đã được kiểm chứng thực tế trong test case `1 & 13`.

### 3.2 Cơ chế Whitelist Payload (Chống rò rỉ và giả mạo)
Trong hàm `diagnoseWrongAnswer`, payload gửi đi được khởi tạo bằng whitelist tường minh:
```typescript
const sanitizedPayload: WrongAnswerDiagnosticRequest = {
  attempt_id: request.attempt_id,
  question_id: request.question_id,
};
```
Ngay cả khi phía UI hoặc caller vô tình truyền thêm các thuộc tính thừa như `is_correct`, `correct_answer`, `canonical_answer`, hay `system_prompt`, hàm API client sẽ chủ động loại bỏ các thuộc tính này, chỉ gửi đúng 2 trường UUID `attempt_id` và `question_id`. Điều này đảm bảo request luôn hợp lệ với cấu hình `extra: "forbid"` của Backend Pydantic.

---

## 4. Tích hợp Authentication (Authentication Integration)

- Tái sử dụng 100% cơ chế quản lý token hiện tại của dự án trong `frontend/src/lib/api/client.ts`.
- Token được lưu trữ trong `sessionStorage` (`smart_learning_session_token`) và đọc qua `getAuthToken()`.
- **Bảo mật:** Không sử dụng `localStorage`.
- Header `Authorization: Bearer ${token}` được tự động gắn vào mọi request gửi đi khi học sinh đã đăng nhập. Đã được kiểm chứng qua test case `3`.

---

## 5. Ánh xạ lỗi và Xử lý ngoại lệ (Error Mapping)

Hệ thống tái sử dụng lớp lỗi `ApiClientError(status, message, data)` từ `client.ts` và bổ sung 3 hàm tiện ích chuyên biệt trong `ai-diagnostics.ts`:

1. **`isBusinessRuleError(statusCode: number): boolean`**
   - Trả về `true` cho các mã lỗi: `400`, `401`, `403`, `404`, `422`.
   - Báo hiệu cho tầng UI/Query rằng đây là lỗi nghiệp vụ hoặc phân quyền (bài thi chưa nộp, câu đã đúng, bài của học sinh khác, v.v.), **tuyệt đối không được tự động retry**.

2. **`isRetryableAIError(statusCode: number): boolean`**
   - Trả về `true` cho các mã lỗi: `502`, `503`, `504`.
   - Báo hiệu đây là sự cố hạ tầng AI tạm thời (timeout, rate limit, JSON sai cú pháp), cho phép hiển thị nút "Thử lại" thủ công cho học sinh.

3. **`getDiagnosticErrorMessage(error: unknown): string`**
   - Ánh xạ mã HTTP status thành thông báo tiếng Việt sư phạm, rõ ràng, thân thiện.
   - Chặn đứng hoàn toàn việc để lộ `GEMINI_API_KEY`, chuỗi JWT token, URL cụm máy chủ nội bộ hoặc Python stack trace ra giao diện người dùng.

---

## 6. Tính tương thích với TanStack Query v5 (TanStack Query Compatibility)

API client được thiết kế tương thích trực tiếp với hook `useMutation` của `@tanstack/react-query: ^5.108.0`:
- **Chữ ký hàm:** Nhận vào object duy nhất `{ attempt_id, question_id }`, trả về `Promise<WrongAnswerDiagnosticResponse>`.
- **Cơ chế không retry tự động:**
  ```typescript
  // Cấu hình chuẩn khi tích hợp vào UI (Phase 7.2.4.3):
  const mutation = useMutation({
    mutationFn: aiDiagnosticsApi.diagnoseWrongAnswer,
    retry: (failureCount, error) => {
      if (error instanceof ApiClientError && isBusinessRuleError(error.status)) {
        return false; // Không tự động retry lỗi 400, 401, 403, 404, 422
      }
      return failureCount < 2; // Tối đa 2 lần nếu là lỗi kết nối mạng
    },
  });
  ```
- **Cơ chế Cache Client-side:** Kết quả chẩn đoán có thể được lưu trữ trong TanStack `queryClient` theo query key `["ai-diagnostic", attemptId, questionId]`, ngăn ngừa việc gọi lại AI khi học sinh đóng và mở lại Drawer cho cùng một câu hỏi.

---

## 7. Bằng chứng kiểm thử tự động (Test Evidence)

Đã xây dựng bộ test Playwright chuyên biệt:
`frontend/e2e/ai-diagnostics-api.spec.ts` (gồm 16 test cases độc lập).

### Kết quả chạy kiểm thử API Client:
- **Lệnh thực thi:**
  ```powershell
  cd frontend; npx playwright test e2e/ai-diagnostics-api.spec.ts
  ```
- **Exit code:** `0`
- **Kết quả:** **16 passed in 816ms** (16/16 PASS, 0 fail, 0 skip).

```text
Running 16 tests using 1 worker

  ok  1 [chrome] › 1 & 13: Request targets exact endpoint without duplicate /api/v1 prefix (9ms)
  ok  2 [chrome] › 2, 3 & 14: Request body contains ONLY two UUIDs and strips disallowed client fields (6ms)
  ok  3 [chrome] › 3: Authentication header is attached from sessionStorage (2ms)
  ok  4 [chrome] › 4: Successful response is parsed accurately into WrongAnswerDiagnosticResponse (3ms)
  ok  5 [chrome] › 6: INSUFFICIENT_INFORMATION is returned as 200 OK with is_sufficient=false (1ms)
  ok  6 [chrome] › Error 400: Throws ApiClientError with status 400 and preserves message (1ms)
  ok  7 [chrome] › Error 401: Throws ApiClientError with status 401 and preserves message (1ms)
  ok  8 [chrome] › Error 403: Throws ApiClientError with status 403 and preserves message (1ms)
  ok  9 [chrome] › Error 404: Throws ApiClientError with status 404 and preserves message (2ms)
  ok 10 [chrome] › Error 422: Throws ApiClientError with status 422 and preserves message (1ms)
  ok 11 [chrome] › Error 502: Throws ApiClientError with status 502 and preserves message (1ms)
  ok 12 [chrome] › Error 503: Throws ApiClientError with status 503 and preserves message (1ms)
  ok 13 [chrome] › Error 504: Throws ApiClientError with status 504 and preserves message (1ms)
  ok 14 [chrome] › Error classification: isBusinessRuleError distinguishes 4xx business vs 5xx server errors (2ms)
  ok 15 [chrome] › Error classification: isRetryableAIError identifies retryable infrastructure errors (1ms)
  ok 16 [chrome] › 15: getDiagnosticErrorMessage provides sanitized Vietnamese messages without leaking secrets or tokens (2ms)

  16 passed (816ms)
```

### Kết quả kiểm tra kiểu dữ liệu TypeScript (Type-check):
- **Lệnh thực thi:**
  ```powershell
  cd frontend; npm run type-check
  ```
- **Exit code:** `0`
- **Kết quả:** `tsc --noEmit` hoàn thành với **0 lỗi**.

### Kết quả kiểm thử hồi quy Backend:
- **Lệnh thực thi:**
  ```powershell
  $env:PYTHONPATH = ".;backend"; .venv/Scripts/pytest.exe backend/tests/test_ai_diagnostics_api_723.py -q
  ```
- **Exit code:** `0`
- **Kết quả:** **30 passed in 37.65s**.

---

## 8. Danh sách tệp tạo mới và chỉnh sửa

| Đường dẫn tệp | Loại thay đổi | Mô tả chi tiết |
|---|---|---|
| `frontend/src/types/ai-diagnostics.ts` | **TẠO MỚI** | Định nghĩa các kiểu `ErrorCategory`, `WrongAnswerDiagnosticRequest`, `DiagnosticDetail`, `WrongAnswerDiagnosticResponse`. |
| `frontend/src/lib/api/ai-diagnostics.ts` | **TẠO MỚI** | Xây dựng API client `aiDiagnosticsApi.diagnoseWrongAnswer` và các hàm phân loại lỗi `isBusinessRuleError`, `isRetryableAIError`, `getDiagnosticErrorMessage`. |
| `frontend/e2e/ai-diagnostics-api.spec.ts` | **TẠO MỚI** | Bộ 16 test cases kiểm thử tự động API client, hợp đồng dữ liệu, mã lỗi HTTP và tính năng bảo mật token. |
| `frontend/src/types/index.ts` | **CHỈNH SỬA** | Bổ sung dòng `export * from "./ai-diagnostics";` ở cuối tệp để xuất bản thuận tiện ra toàn dự án. |
| `docs/PHASE_7_2_4_2_API_CLIENT_TYPES_REPORT.md` | **TẠO MỚI** | Báo cáo hoàn thành Phase 7.2.4.2 bằng tiếng Việt. |

---

## 9. Trạng thái Git & Xác nhận bảo toàn hệ thống

- **Git HEAD SHA:** `d6326e5415cb125b62fbe12aea077ecf921d3a88` (Khớp 100% với baseline).
- **Cam kết an toàn:**
  - Không tạo commit mới, không push.
  - Không chạy `git reset` hoặc `git clean`.
  - Không thay đổi database schema hoặc tạo Alembic migration.
  - Toàn bộ các file modified và untracked từ các phase trước được bảo toàn nguyên vẹn.

---

## 10. Hạn chế đã biết (Known Limitations)

- Giai đoạn này chỉ tập trung vào tầng API client và TypeScript types. Giao diện Drawer, các trạng thái UI, và nút bấm trên trang xem lại bài thi sẽ được xây dựng tuần tự ở các subphase tiếp theo (`7.2.4.3`, `7.2.4.4`).

---

## 11. Kết luận và Dừng đúng phạm vi (Final Verdict & Stop Condition)

### Kết luận
**FINAL VERDICT: PASS**  
Tầng API Client và TypeScript Contracts của Phase 7.2.4.2 đã hoàn thành xuất sắc, khớp chính xác 100% với hợp đồng backend, bảo đảm an toàn dữ liệu, chống lặp prefix URL, và vượt qua toàn bộ 16 bài kiểm thử tự động cùng kiểm tra kiểu TypeScript với 0 lỗi.

### Dừng đúng phạm vi
Theo đúng chỉ thị tại mục 11:
- **KHÔNG** tạo Drawer.
- **KHÔNG** sửa Exam Review Page.
- **KHÔNG** tích hợp KaTeX vào UI.
- **KHÔNG** bắt đầu Phase 7.2.4.3 hay Phase 7.3.
- **DỪNG LẠI TẠI ĐÂY** và chờ ChatGPT / Tech Lead xem xét, phê duyệt trước khi tiếp tục.
