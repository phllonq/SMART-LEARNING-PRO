# PHASE 7.1.3 — FINAL USAGE COST INTEGRITY AUDIT REPORT
**SMART LEARNING PRO — AI Engine Foundation**  
**Date:** 2026-11-20  
**Git Baseline:** `d6326e5415cb125b62fbe12aea077ecf921d3a88`  
**Verdict:** COMPLETE (PASS)

---

## 1. MỤC TIÊU VÀ PHẠM VI AUDIT

Phase 7.1.3 thực hiện targeted remediation giải quyết dứt điểm 2 lỗ hổng toàn vẹn dữ liệu chi phí và token accounting còn sót lại sau Phase 7.1.2:
1. **Loại bỏ hoàn toàn hành vi ép `None` thành `0.0`**: Trước Phase 7.1.3, khi chi phí `estimated_cost_usd` chưa xác định (`None`), hàm `record_usage_to_db` chuyển thành `0.0` để né ràng buộc `NOT NULL` của schema `ai_usage_logs`. Điều này làm sai lệch dữ liệu tài chính (không phân biệt được giữa chi phí thực bằng 0 và chi phí chưa xác định).
2. **Kiểm soát chặt chẽ công thức Context Caching và bảo vệ chống tính phí hai lần**: Xác minh từ `google-genai==1.75.0` rằng `prompt_token_count` đã bao gồm `cached_content_token_count`. Bảo đảm không clamp sai lệch khi `cached_tokens > prompt_tokens` (phải trả về `cost = None`), không cộng trùng token suy luận (`thoughts_token_count`), và không áp dụng giá context caching cho Batch tier.

---

## 2. VẤN ĐỀ TRƯỚC REMEDIATION VÀ GIẢI PHÁP THỰC TẾ

### 2.1 Vấn đề 1: Ép `estimated_cost_usd is None` thành `0.0`

#### Trước sửa đổi:
```python
cost = usage_record.estimated_cost_usd if usage_record.estimated_cost_usd is not None else 0.0
log_entry = AIUsageLog(..., estimated_cost_usd=cost)
db.add(log_entry)
```
- **Hậu quả**: Khi một model chưa được định giá (ví dụ unpriced model, date nằm ngoài schedule, hoặc metadata cached token bị lỗi), hệ thống vẫn lưu vào `ai_usage_logs` với `estimated_cost_usd = 0.0`. Khi phòng kế toán hoặc admin kiểm toán chi phí API, các bản ghi này bị hiểu nhầm là Google không tính tiền (free call), gây thất thoát kiểm soát chi phí.

#### Sau sửa đổi:
```python
if usage_record.estimated_cost_usd is None:
    logger.warning(
        "Skipping AIUsageLog persistence: estimated cost is unverified/unknown for model '%s' (input=%s, output=%s)",
        usage_record.model_name,
        usage_record.input_tokens,
        usage_record.output_tokens,
    )
    return None
```
- **Bảo toàn**:
  - Không chuyển `None` thành `0.0`.
  - Không lưu bản ghi giả mạo chi phí `0.0`.
  - Nếu chi phí là `0.0` thực sự (ví dụ `mock-model-v1` có giá $0.0/1M trong bảng giá xác minh), `usage_record.estimated_cost_usd is None` là `False`, bản ghi được lưu với `estimated_cost_usd = 0.0`.
  - Nếu chi phí dương (`cost > 0.0`), bản ghi được lưu với giá trị thực tế.
  - Logging an toàn tuyệt đối: không log prompt text, response text, PII người dùng hoặc API key.
  - Không gây crash business request của học sinh/giáo viên khi telemetry skip.

---

### 2.2 Vấn đề 2: Tính phí Cached Token và Ngăn chặn Clamping Sai lệch

#### Trước sửa đổi:
```python
regular_input = max(0, input_tokens - cached_tokens) # Tự clamp về 0 nếu cached > input!
```
- **Hậu quả**: Nếu metadata từ upstream bị lỗi dẫn đến `cached_tokens > input_tokens`, việc `max(0, ...)` sẽ ép `regular_input` về 0 và tiếp tục tính tiền trên số token cache bất thường đó, giả vờ như chi phí tính ra là chính xác.

#### Sau sửa đổi:
```python
if cached_tokens is not None:
    if cached_tokens < 0:
        logger.warning("Invalid usage metadata: negative cached_tokens (%d)...", cached_tokens)
        return None

    if cached_tokens > input_tokens:
        logger.warning(
            "Invalid usage metadata: cached_tokens (%d) > input_tokens (%d) for model '%s'. Cost set to None.",
            cached_tokens,
            input_tokens,
            model_name,
        )
        return None

    if cached_tokens > 0:
        if schedule.cached_input_per_million is None:
            # Batch tier không hỗ trợ context caching discount -> Cost set to None
            return None
        regular_input_tokens = input_tokens - cached_tokens
        cost_in_regular = (regular_input_tokens * schedule.input_per_million) / 1_000_000.0
        cost_in_cache = (cached_tokens * schedule.cached_input_per_million) / 1_000_000.0
        cost_in_total = cost_in_regular + cost_in_cache
    else:
        cost_in_total = (input_tokens * schedule.input_per_million) / 1_000_000.0
```

---

## 3. CÔNG THỨC ĐỊNH GIÁ THỰC TẾ & MINH CHỨNG SỐ HỌC

### 3.1 Bảng giá chính thức áp dụng cho Gemini 3.8 Flash (2026 - 2027)

| Tier | Thời điểm áp dụng | Input / 1M | Output / 1M | Cached Input / 1M | Batch Discount |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Standard** | 2026-01-01 $\rightarrow$ 2026-12-31 | \$0.75 | \$3.75 | \$0.075 | Không |
| **Standard** | 2027-01-01 $\rightarrow$ 2099-12-31 | \$1.50 | \$7.50 | \$0.150 | Không |
| **Batch** | 2026-01-01 $\rightarrow$ 2026-12-31 | \$0.375 | \$1.875 | *None (không hỗ trợ)* | Giảm 50% |
| **Batch** | 2027-01-01 $\rightarrow$ 2099-12-31 | \$0.750 | \$3.750 | *None (không hỗ trợ)* | Giảm 50% |

### 3.2 Công thức tính toán
$$\text{regular\_input\_tokens} = \text{prompt\_tokens} - \text{cached\_tokens}$$
$$\text{cost\_input} = \frac{\text{regular\_input\_tokens} \times P_{\text{in}} + \text{cached\_tokens} \times P_{\text{cache}}}{1\,000\,000}$$
$$\text{cost\_output} = \frac{\text{candidates\_tokens} \times P_{\text{out}}}{1\,000\,000}$$
$$\text{total\_cost} = \text{round}(\text{cost\_input} + \text{cost\_output}, 6)$$

### 3.3 Trường hợp kiểm thử số học cụ thể (Yêu cầu Mục C)
- $\text{prompt} = 1\,000\,000$ tokens; $\text{cached} = 200\,000$ tokens.
- $\text{regular\_input} = 1\,000\,000 - 200\,000 = 800\,000$ tokens.
- $P_{\text{in}} = \$0.75$ / 1M; $P_{\text{cache}} = \$0.075$ / 1M.
- $\text{regular cost} = \frac{800\,000 \times 0.75}{1\,000\,000} = \$0.600$.
- $\text{cached cost} = \frac{200\,000 \times 0.075}{1\,000\,000} = \$0.015$.
- $\text{total input cost} = \$0.600 + \$0.015 = \mathbf{\$0.615}$ (Khớp 100% với kỳ vọng kiểm toán).

---

## 4. MA TRẬN TEST CASES & KẾT QUẢ KIỂM THỬ

Toàn bộ các test cases mới và hồi quy đã được bổ sung vào `backend/tests/test_ai_foundation.py`:

| STT | Tên Test Case | Điều kiện kiểm thử | Kết quả kỳ vọng | Kết quả thực tế |
| :---: | :--- | :--- | :--- | :---: |
| 1 | `test_calculate_cost_cached_pricing_formula_verification` | prompt=1M, cached=200k, out=0 | Cost = 0.615 | **PASSED** |
| 2 | `test_calculate_cost_cached_tokens_zero` | prompt=1M, cached=0, out=0 | Cost = 0.75 | **PASSED** |
| 3 | `test_calculate_cost_cached_tokens_none_unavailable` | prompt=1M, cached=None, out=0 | Cost = 0.75 | **PASSED** |
| 4 | `test_calculate_cost_cached_equals_prompt_tokens` | prompt=1M, cached=1M, out=0 | Cost = 0.075 | **PASSED** |
| 5 | `test_calculate_cost_cached_exceeds_prompt_tokens_returns_none` | prompt=1M, cached=1.2M (lỗi dữ liệu) | Cost = None (không clamp) | **PASSED** |
| 6 | `test_calculate_cost_negative_cached_tokens_returns_none` | prompt=1M, cached=-50 (lỗi dữ liệu) | Cost = None | **PASSED** |
| 7 | `test_calculate_cost_batch_tier_with_cached_tokens_returns_none` | tier="batch", cached=200k | Cost = None (batch không hỗ trợ cache) | **PASSED** |
| 8 | `test_record_usage_skips_persistence_when_cost_none` | estimated_cost_usd = None | Return None, 0 rows trong DB | **PASSED** |
| 9 | `test_record_usage_persists_exact_positive_cost` | estimated_cost_usd = 0.615 | Return log_entry, DB cost = 0.615 | **PASSED** |
| 10 | `test_record_usage_persists_when_actual_zero_tokens` | input=0, output=0, cost=0.0 | Return log_entry, DB cost = 0.0 | **PASSED** |
| 11 | `test_record_usage_db_failure_isolated` | DB ném lỗi kết nối khi lưu usage | Return None, không crash exception | **PASSED** |
| 12 | `test_retry_does_not_duplicate_usage_records` | Retry 2 lần transient lỗi | Duy nhất 1 telemetry record tạo và lưu | **PASSED** |
| 13 | `test_google_provider_normalizes_usage_metadata_without_double_counting_thoughts` | candidates=50, thoughts=20 | output_tokens=50 (không bị thành 70) | **PASSED** |

### Tổng hợp thực thi kiểm thử:
1. **AI Foundation Suite**:
   ```powershell
   $env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests/test_ai_foundation.py -v
   ```
   $\rightarrow$ **62 passed in 3.28s (Exit code 0)**.
2. **Full Backend Regression Suite**:
   ```powershell
   $env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests -v
   ```
   $\rightarrow$ **106 passed in 19.48s (Exit code 0)**.
3. **Frontend TypeScript Check**:
   ```powershell
   cd frontend; npx tsc --noEmit; cd ..
   ```
   $\rightarrow$ **0 errors (Exit code 0)**.

---

## 5. GIT VÀ DATABASE INTEGRITY STATUS

### 5.1 Git Baseline Verification
- **HEAD Commit**: `d6326e5415cb125b62fbe12aea077ecf921d3a88` (Không thay đổi).
- **Trạng thái Commit**: 0 commit mới được tạo.
- **Phân loại tệp tin theo `git status --short`**:
  - **Modified Tracked Files (3 tệp)**:
    1. `.env.example`: Thêm cấu hình biến môi trường AI (`AI_PROVIDER`, `GEMINI_MODEL`, timeouts, retries).
    2. `backend/app/config.py`: Khai báo Pydantic Settings cho các biến AI trên.
    3. `backend/requirements.txt`: Ghim `google-genai==1.75.0`.
  - **Untracked Directories & Files**:
    1. `backend/app/modules/ai_engine/` (Mô-đun nền tảng AI).
    2. `backend/tests/test_ai_foundation.py` (62 unit/integration tests).
    3. Các tài liệu báo cáo: `docs/PHASE_6_3_9_POSTGRESQL_TRANSACTION_AUDIT.md`, `docs/PHASE_7_0_AI_ARCHITECTURE_ASSESSMENT.md`, `docs/PHASE_7_1_1_INDEPENDENT_AUDIT_REPORT.md`, `docs/PHASE_7_1_2_USAGE_DATA_INTEGRITY_REPORT.md`, `docs/PHASE_7_1_3_FINAL_USAGE_COST_AUDIT.md`.
  - **Deleted Files**: 0 tệp.
  - **Staged Files**: 0 tệp.

### 5.2 Database & Migration Status
- **Alembic Migrations**: 0 file migration được tạo hoặc chạy.
- **Database Schema**: Giữ nguyên 100% (không thêm/sửa/xóa cột hay bảng).
- **SQLite Database Files**: Giữ nguyên toàn bộ dữ liệu hiện có.

---

## 6. HẠN CHẾ CÒN LẠI (LIMITATIONS)

1. **Schema Column Nullability**:
   Bảng `ai_usage_logs` hiện tại vẫn giữ nguyên thiết kế từ Phase trước (`prompt_tokens`, `completion_tokens`, `estimated_cost_usd` là `NOT NULL DEFAULT 0`). Vì Phase 7.1.x cấm migration, khi token hoặc chi phí chưa xác định, hệ thống **bỏ qua việc lưu dòng vào database** để bảo đảm không lưu dữ liệu giả mạo.
2. **Khuyến nghị cho Phase Migration tương lai (Phase 8+)**:
   Khi hệ thống bước vào giai đoạn schema migration được cấp phép, nên cập nhật:
   - Cho phép `prompt_tokens`, `completion_tokens`, `estimated_cost_usd` mang giá trị `NULL`.
   - Thêm cột `telemetry_status` (`VERIFIED`, `TOKEN_MISSING`, `COST_UNPRICED`, `INVALID_METADATA`) để lưu vết mọi cuộc gọi kể cả khi không tính được chi phí.
   - Thêm các cột lưu chi tiết: `cached_tokens`, `thoughts_tokens`, `pricing_tier`.

---

## 7. KẾT LUẬN & DỪNG THEO QUY ĐỊNH (STOP CONDITION)

- Đã loại bỏ hoàn toàn việc ép `None` thành `0.0`.
- Đã kiểm định chặt chẽ toàn bộ logic tính phí cached token và token suy luận.
- Toàn bộ 106 tests backend và TypeScript frontend đều PASS 100%.
- Không tạo commit, không chạy migration, dừng hoàn toàn trước Phase 7.2.
