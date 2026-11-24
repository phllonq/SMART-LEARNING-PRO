# BÁO CÁO HOÀN THÀNH TRIỂN KHAI — PHASE 7.2.4.3
## WRONG ANSWER DIAGNOSTIC DRAWER & EXAM REVIEW INTEGRATION

**Dự án:** SMART-LEARNING-PRO  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Ngày báo cáo:** 24/11/2026  
**Trạng thái:** HOÀN THÀNH — TOÀN BỘ KIỂM THỬ PASS (31/31 Frontend Playwright E2E, 30/30 Backend Regression, TypeScript Type-check Clean)  
**Baseline Git HEAD:** `d6326e5415cb125b62fbe12aea077ecf921d3a88`  

---

## 1. TỔNG QUAN VÀ MỤC TIÊU (EXECUTIVE SUMMARY)

Phase 7.2.4.3 đã hoàn thành xuất sắc việc xây dựng và tích hợp giao diện Slide-Over Drawer (`WrongAnswerDiagnosticDrawer`) giải thích câu trả lời sai bằng AI vào trang xem lại bài thi của học sinh (`StudentExamAttemptPage`), kết nối với REST API backend đã được phê duyệt ở Phase 7.2.3:
`POST /api/v1/ai/diagnostics/wrong-answer`

### Các mục tiêu chính đạt được:
1. **Component Slide-Over Drawer chuyên dụng:** Xây dựng `frontend/src/components/student/exams/wrong-answer-diagnostic-drawer.tsx` với 5 trạng thái giao diện rõ ràng (`IDLE`, `LOADING`, `SUCCESS`, `INSUFFICIENT_INFORMATION`, `ERROR`), hỗ trợ KaTeX rendering cho công thức toán học và chuyển đổi các mã kỹ thuật `ErrorCategory` thành các nhãn tiếng Việt mang tính sư phạm cao.
2. **Tích hợp Exam Review Page chặt chẽ:** Tích hợp nút **"Phân tích lỗi sai bằng AI"** vào `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx` chỉ khi học sinh xem lại bài thi sau khi nộp (`attempt.status !== "IN_PROGRESS"`), chỉ xuất hiện tại các câu hỏi trả lời SAI (`!q.is_correct`), tuyệt đối không xuất hiện ở câu đúng hoặc trong quá trình đang làm bài.
3. **Cơ chế Cache và Ngăn chặn Duplicate Requests:** Tích hợp TanStack Query Client cache với query key `["ai-diagnostic", attemptId, questionId]` giúp tải dữ liệu tức thì khi mở lại câu hỏi mà không kích hoạt request mạng thứ 2; sử dụng ref guard `isInFlightRef` để chặn triệt để tình trạng spam click nút phân tích.
4. **Chuẩn Accessibility (A11y):** Tuân thủ WAI-ARIA Dialog Modal (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `aria-describedby`), quản lý bẫy tiêu điểm (Focus Trap Tab/Shift+Tab), lắng nghe phím `Escape`, đóng khi nhấn backdrop overlay, khóa cuộn trang (`document.body.style.overflow = "hidden"`), và tự động khôi phục focus về nút kích hoạt ban đầu khi đóng.
5. **Đảm bảo tính bất biến dữ liệu (Read-Only Invariants):** Không thay đổi bất kỳ logic tính điểm, autosave, submission barrier, canonical answers hay database schema nào.

---

## 2. KIỂM KÊ GIT BASELINE VÀ TẬP TIN

### Git Baseline:
- **Baseline Git HEAD:** `d6326e5415cb125b62fbe12aea077ecf921d3a88`
- **Zero Commits / Zero Pushes:** Không thực hiện bất kỳ lệnh `git commit` hay `git push` nào.
- **Bảo toàn nguyên vẹn:** Toàn bộ file modified từ các phase trước được bảo vệ tuyệt đối.

### Danh mục tập tin thực hiện trong Phase 7.2.4.3:
| Tác vụ | Đường dẫn tập tin | Mô tả kỹ thuật |
| :--- | :--- | :--- |
| **Tạo mới** | `frontend/src/components/student/exams/wrong-answer-diagnostic-drawer.tsx` | Slide-Over Drawer component hiển thị chẩn đoán AI sai sót |
| **Chỉnh sửa** | `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx` | Tích hợp nút kích hoạt và render drawer trong chế độ review |
| **Tạo mới** | `frontend/e2e/wrong-answer-diagnostic-drawer.spec.ts` | 15 kịch bản Playwright e2e kiểm thử UI states, cache, a11y |
| **Tạo mới** | `docs/PHASE_7_2_4_3_WRONG_ANSWER_DIAGNOSTIC_DRAWER_REPORT.md` | Báo cáo hoàn thành Phase 7.2.4.3 (tài liệu này) |

---

## 3. KIẾN TRÚC COMPONENT & PROPS DESIGN

Component `WrongAnswerDiagnosticDrawer` được thiết kế dưới dạng React 19 Client Component ("use client"), tuân thủ quy chuẩn TypeScript strict và thiết kế phân lớp:

```typescript
export interface WrongAnswerDiagnosticDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  attemptId: string;
  questionId?: string | null | undefined;
  questionContent?: string | null | undefined;
  questionIndex?: number;
  triggerElementRef?: React.RefObject<HTMLElement | null>;
}
```

### Bảng chuyển đổi Danh mục Lỗi kỹ thuật sang Nhãn sư phạm Tiếng Việt (`ERROR_CATEGORY_LABELS`):
| `ErrorCategory` (Backend Enum) | Nhãn hiển thị Tiếng Việt | Phân loại màu Badge |
| :--- | :--- | :--- |
| `CONCEPTUAL_MISCONCEPTION` | **Quan niệm sai lầm về khái niệm** | `purple` |
| `CALCULATION_ERROR` | **Lỗi tính toán sai số học / đại số** | `warning` |
| `QUESTION_MISREAD` | **Đọc nhầm hoặc hiểu sai đề bài** | `secondary` |
| `FORMULA_MISAPPLICATION` | **Áp dụng sai công thức / định lý** | `destructive` |
| `LOGICAL_GAP` | **Thiếu bước lập luận hoặc suy luận logic** | `purple` |
| `INSUFFICIENT_INFORMATION` | **Chưa đủ dữ liệu để kết luận** | `outline` |

---

## 4. QUẢN LÝ TRẠNG THÁI GIAO DIỆN (UI STATES)

Giao diện Drawer chuyển đổi nhịp nhàng qua 5 trạng thái dựa trên vòng đời dữ liệu:

1. **`IDLE`:** Drawer đóng hoặc chưa có yêu cầu phân tích (`isOpen === false`). Không tốn tài nguyên render hay chiếm dụng bộ nhớ.
2. **`LOADING`:** Khi đang gửi request và chờ phản hồi từ AI backend.
   - Hiển thị banner có icon não bộ xoay tròn kèm dòng thông báo: *"AI đang phân tích câu sai của bạn... Đối chiếu kiến thức và tìm ra quan niệm sai lệch"*.
   - Khung Skeleton loading placeholder với các kích thước tương thích với 4 khối nội dung.
   - Thuộc tính `aria-busy="true"` và `aria-live="polite"` thông báo cho trình đọc màn hình.
3. **`SUCCESS`:** Phân tích hoàn tất thành công (`is_sufficient: true`).
   - Badge danh mục lỗi và Banner tóm tắt nguyên nhân sai sót (`error_summary`).
   - Khối 1: Phân tích quan niệm sai & Lỗ hổng tư duy (`misconception_analysis`).
   - Khối 2: Hướng dẫn tư duy từng bước (`step_by_step_guidance`).
   - Khối 3: Kiến thức cốt lõi cần nhớ (`key_takeaway`).
   - Khối 4: Đề xuất ôn tập thêm (`suggested_review` - render có điều kiện nếu có nội dung).
4. **`INSUFFICIENT_INFORMATION`:** Trả về khi AI phát hiện không đủ dữ kiện học sinh (`is_sufficient: false` hoặc category `INSUFFICIENT_INFORMATION`).
   - Được xử lý như phản hồi HTTP 200 OK thành công, **không** xem là lỗi hệ thống.
   - Hiển thị Card màu vàng hổ phách thân thiện: *"Chưa đủ dữ liệu để kết luận chính xác"*, kèm lời khuyên học sinh đối chiếu với lời giải chi tiết của bài thi.
5. **`ERROR`:** Phản hồi mã lỗi HTTP từ backend.
   - Đối với **Lỗi nghiệp vụ không thể thử lại** (400, 401, 403, 404, 422): Hiển thị thông báo giải thích cụ thể bằng tiếng Việt (ví dụ: *"Câu hỏi này bạn đã trả lời đúng, không cần phân tích lỗi sai"*), không hiển thị nút "Thử lại".
   - Đối với **Lỗi hạ tầng AI tạm thời** (502, 503, 504): Hiển thị thông báo sự cố tạm thời kèm nút **"Thử lại phân tích"** (`fetchDiagnostic(true)`), cho phép gọi lại API mà không bị chặn bởi cache cũ.

---

## 5. RENDER CÔNG THỨC TOÁN HỌC KATEX & AN TOÀN NỘI DUNG (XSS)

- **MathKaTeX Rendering:** Sử dụng component chuẩn `@/components/shared/math-katex` để hiển thị các công thức toán học TeX/LaTeX (dạng `$inline$` và `$$display$$` hoặc `\(...\)`).
- **Phòng chống XSS Injection:** 
  - Toàn bộ nội dung chuỗi văn bản từ AI (`error_summary`, `misconception_analysis`, `step_by_step_guidance`, `key_takeaway`) được render thông qua React Text Nodes và trình phân tích KaTeX có sanitization nghiêm ngặt.
  - Các thẻ HTML độc hại (ví dụ: `<script>`, `<img src=x onerror=.../>`) được kiểm thử tự động xác nhận chỉ hiển thị dưới dạng văn bản thuần túy, tuyệt đối không bị trình duyệt thực thi DOM execution.

---

## 6. ĐIỀU PHỐI CACHE & BẢO VỆ IN-FLIGHT DUPLICATE REQUESTS

- **TanStack Query Cache Coordination:**
  - Query Key chuẩn: `["ai-diagnostic", attemptId, questionId]`.
  - Khi mở Drawer, component kiểm tra `queryClient.getQueryData(queryKey)`. Nếu dữ liệu đã tồn tại trong cache, Drawer hiển thị ngay lập tức trong 0ms mà không gửi bất kỳ HTTP request nào.
  - Khi người dùng nhấn nút "Thử lại", cờ `forceRefresh = true` được kích hoạt để bypass cache và cập nhật lại cache mới khi hoàn thành.
- **In-flight Duplicate Prevention:**
  - `isInFlightRef.current` theo dõi request đang diễn ra. Khi một request đang trong tiến trình mạng, mọi thao tác click lặp lại đều bị chặn ngay tại client, triệt tiêu race conditions và tiết kiệm token hạn mức AI của học sinh.

---

## 7. CHUẨN ACCESSIBILITY & ARIA (A11Y)

1. **WAI-ARIA Structure:**
   - Container chính: `role="dialog"`, `aria-modal="true"`.
   - Liên kết tiêu đề: `aria-labelledby={titleId}` trỏ tới tiêu đề "Phân tích lỗi sai bằng AI".
   - Liên kết mô tả: `aria-describedby={descId}` trỏ tới phần mô tả ngữ cảnh.
   - Trạng thái thông báo: `aria-live="polite"` cho kết quả thành công và `aria-live="assertive"` cho khối lỗi.
2. **Keyboard Navigation & Focus Trap:**
   - Phím `Escape`: Đóng Drawer ngay lập tức từ bất kỳ phần tử nào bên trong.
   - Phím `Tab` & `Shift + Tab`: Bẫy tiêu điểm luân chuyển an toàn giữa nút Đóng (`X`), nút Thử lại, và các phần tử tương tác khác bên trong Drawer, không thất thoát tiêu điểm ra nền trang web bên ngoài.
3. **Body Scroll Lock:**
   - Khi Drawer mở: Ghi đè `document.body.style.overflow = "hidden"` để khóa cuộn trang phía sau.
   - Khi Drawer đóng hoặc unmount: Tự động hoàn trả chính xác kiểu cuộn ban đầu (`originalOverflow`).
4. **Focus Restoration:**
   - Lưu trữ `document.activeElement` trước khi mở và khôi phục tiêu điểm chính xác về nút bấm kích hoạt ban đầu khi Drawer đóng.

---

## 8. TÍCH HỢP VÀO TRANG XEM LẠI BÀI THI (EXAM REVIEW PAGE)

Tại `frontend/src/app/student/exams/attempts/[attemptId]/page.tsx`:
- Nút kích hoạt:
  ```tsx
  {!q.is_correct && q.question_id && (
    <div className="pt-2 flex justify-end">
      <Button
        variant="outline"
        size="sm"
        data-testid={`ai-diagnostic-btn-${q.question_id}`}
        className="gap-2 border-indigo-200 bg-indigo-50/50 hover:bg-indigo-100/70 text-indigo-700 hover:text-indigo-800 font-medium text-xs shadow-2xs transition-colors"
        onClick={() => {
          setSelectedDiagnosticQuestion({
            questionId: q.question_id,
            questionContent: q.content,
            questionIndex: idx + 1,
          });
          setDiagnosticDrawerOpen(true);
        }}
      >
        <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
        <span>Phân tích lỗi sai bằng AI</span>
      </Button>
    </div>
  )}
  ```
- **Ràng buộc an toàn bất biến:**
  1. Chỉ hiển thị khi `attempt.status !== "IN_PROGRESS"` (sau khi bài nộp hoàn tất).
  2. Chỉ hiển thị tại câu hỏi có `q.is_correct === false`.
  3. Tuyệt đối **không** hiển thị tại câu làm đúng (`q.is_correct === true`).
  4. Tuyệt đối **không** hiển thị trong lúc học sinh đang làm bài thi.

---

## 9. KẾT QUẢ KIỂM THỬ PLAYWRIGHT E2E (FRONTEND)

Toàn bộ **31/31 kiểm thử E2E** trên Playwright đã chạy thành công 100%:

```
Running 31 tests using 1 worker

  ok  1 [chrome] › e2e\ai-diagnostics-api.spec.ts › Request targets exact endpoint without duplicate /api/v1 prefix
  ok  2 [chrome] › e2e\ai-diagnostics-api.spec.ts › Request body contains ONLY two UUIDs and strips disallowed client fields
  ok  3 [chrome] › e2e\ai-diagnostics-api.spec.ts › Authentication header is attached from sessionStorage
  ok  4 [chrome] › e2e\ai-diagnostics-api.spec.ts › Successful response is parsed accurately into WrongAnswerDiagnosticResponse
  ok  5 [chrome] › e2e\ai-diagnostics-api.spec.ts › INSUFFICIENT_INFORMATION is returned as 200 OK with is_sufficient=false
  ok  6 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 400: Throws ApiClientError with status 400
  ok  7 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 401: Throws ApiClientError with status 401
  ok  8 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 403: Throws ApiClientError with status 403
  ok  9 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 404: Throws ApiClientError with status 404
  ok 10 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 422: Throws ApiClientError with status 422
  ok 11 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 502: Throws ApiClientError with status 502
  ok 12 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 503: Throws ApiClientError with status 503
  ok 13 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error 504: Throws ApiClientError with status 504
  ok 14 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error classification: isBusinessRuleError distinguishes 4xx business vs 5xx server errors
  ok 15 [chrome] › e2e\ai-diagnostics-api.spec.ts › Error classification: isRetryableAIError identifies retryable infrastructure errors
  ok 16 [chrome] › e2e\ai-diagnostics-api.spec.ts › getDiagnosticErrorMessage provides sanitized Vietnamese messages without leaking secrets
  ok 17 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › All 6 technical ErrorCategory enum values map to explicit Vietnamese labels and badge variants
  ok 18 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › MathKaTeX renders mathematical expressions and safely escapes raw HTML injections
  ok 19 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Body scroll lock: overflow is set to 'hidden' when open and restored to previous style when closed
  ok 20 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Escape key press triggers drawer close callback
  ok 21 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Backdrop click triggers drawer close callback
  ok 22 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Dialog ARIA structure: role='dialog', aria-modal='true', aria-labelledby and aria-describedby
  ok 23 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › TanStack Query cache key ['ai-diagnostic', attemptId, questionId] returns cached data without second API fetch
  ok 24 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › In-flight guard blocks rapid duplicate clicks from making concurrent network requests
  ok 25 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Business Rule Errors (400, 401, 403, 404, 422) do NOT allow retry
  ok 26 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Transient Infrastructure Errors (502, 503, 504) trigger retry button policy
  ok 27 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Vietnamese error messages for 400 ANSWER_NOT_INCORRECT and other codes are descriptive and sanitized
  ok 28 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › INSUFFICIENT_INFORMATION response is handled cleanly as 200 OK status without throwing error
  ok 29 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Review mode: Button 'Phân tích lỗi sai bằng AI' appears ONLY for questions where is_correct === false
  ok 30 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Active examination mode: Button NEVER appears when attempt.status === 'IN_PROGRESS'
  ok 31 [chrome] › e2e\wrong-answer-diagnostic-drawer.spec.ts › Completed examination mode: Review mode is active when attempt.status !== 'IN_PROGRESS'

  31 passed (2.3s)
```

Kiểm tra kiểu dữ liệu TypeScript (`npm run type-check` / `tsc --noEmit`):
```
> frontend@0.1.0 type-check
> tsc --noEmit
(Hoàn tất không có bất kỳ lỗi biên dịch nào — Exit Code: 0)
```

---

## 10. KẾT QUẢ KIỂM THỬ HỒI QUY BACKEND

Bộ kiểm thử hồi quy Backend (`backend/tests/test_ai_diagnostics_api_723.py`) đã chạy và đạt 100% PASS:

```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.2.0, pluggy-1.7.0
rootdir: E:\SMART-LEARNING-PRO\backend
configfile: pytest.ini
collected 30 items

backend\tests\test_ai_diagnostics_api_723.py .............................. [100%]

============================= 30 passed in 36.70s =============================
```

---

## 11. ĐÁNH GIÁ TÍNH BẤT BIẾN VÀ AN TOÀN BẢO MẬT (READ-ONLY INVARIANTS)

1. **Bất biến Dữ liệu Thi Cử (Exam Data Immutability):**
   - Tuyệt đối không thay đổi trạng thái bài nộp (`ExamAttempt`), điểm số câu hỏi, câu trả lời của học sinh hay đáp án chuẩn trong database.
   - Drawer hoạt động hoàn toàn ở chế độ đọc (read-only) và hiển thị kết quả chẩn đoán độc lập.
2. **Bảo mật Multi-Tenancy & Phân quyền:**
   - Chỉ có học sinh sở hữu lượt thi mới được phép kích hoạt chẩn đoán thông qua backend verification ở Phase 7.2.3.
   - Nút chẩn đoán gửi duy nhất hai mã định danh UUID: `attempt_id` và `question_id`.
3. **An toàn Bí mật Hệ thống & Thông điệp Thân thiện:**
   - Mọi lỗi kỹ thuật và exception đều được chuyển dịch sang tiếng Việt sư phạm, ngăn chặn hoàn toàn việc rò rỉ token, headers, API keys hoặc stack trace ra giao diện trình duyệt của học sinh.

---

## 12. XÁC MINH RANH GIỚI PHẠM VI (SCOPE BOUNDARIES)

- Không triển khai các tính năng ngoài phạm vi như: Multi-turn Chat, Follow-up Questions, SSE streaming, RAG vector database, hoặc thay đổi database schema.
- Không sửa đổi mã nguồn Backend, Exam Engine, Grading Engine, Autosave hay Concurrency controls.
- Git repository được giữ nguyên trạng, không commit, không push, không thay đổi branch.

---

## 13. KẾT LUẬN & SẴN SÀNG CHO BƯỚC TIẾP THEO

Phase 7.2.4.3 đã hoàn tất trọn vẹn và đạt chất lượng kiểm thử tối đa:
- **Slide-Over Drawer Component hoàn chỉnh, chuẩn sư phạm và thẩm mỹ cao.**
- **Tích hợp an toàn, chính xác vào Student Exam Review Page.**
- **Bảo toàn 100% hệ thống và vượt qua toàn bộ kiểm thử Frontend lẫn Backend.**

Sẵn sàng bước vào các bước tiếp theo hoặc bàn giao cho Tech Lead nghiệm thu.
