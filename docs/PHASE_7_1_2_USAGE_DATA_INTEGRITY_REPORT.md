# PHASE 7.1.2 — USAGE DATA INTEGRITY FINAL REPORT
**SMART LEARNING PRO — AI Engine Foundation**  
**Date:** 2026-11-20  
**Git Baseline:** `d6326e5415cb125b62fbe12aea077ecf921d3a88`  
**Status:** COMPLETE (PASS)

---

## 1. EXECUTIVE SUMMARY

Phase 7.1.2 resolves the critical data integrity vulnerability in token usage telemetry:
1. **Root Cause**: The existing `AIUsageLog` database model (`backend/app/modules/ai_tutor/models.py`) defines `prompt_tokens` and `completion_tokens` as `INTEGER NOT NULL DEFAULT 0`. In Phase 7.1.1, missing usage metadata (`None`) was coerced into `0`, polluting the telemetry database with fake zero-token records and making unmetered/unavailable calls indistinguishable from genuine zero-token executions.
2. **Remediation**: Replaced fallback-to-zero persistence with a strict **3-state distinction policy**:
   - **State 1 (Actual zero tokens)**: Both input and output tokens are reported as `0` by the provider (e.g., mock provider or free tier). Persisted to `ai_usage_logs` with verified `0` metrics.
   - **State 2 (Usage metadata unavailable)**: Either `input_tokens is None` or `output_tokens is None` (e.g., streaming chunks, unmetered calls, network drops). **Database persistence is completely skipped**; a sanitized warning is emitted, and `record_usage_to_db` returns `None`.
   - **State 3 (Provider call failed)**: Network timeout, HTTP error, or rate limit. No response or usage record is generated; exceptions are classified and handled by the resilience layer.
3. **SDK Token Normalization (`google-genai==1.75.0`)**:
   - Confirmed through SDK inspection that `types.GenerateContentResponseUsageMetadata.candidates_token_count` **already includes** `thoughts_token_count`.
   - Fixed mapping to prevent double-counting: candidate tokens are preserved directly as `output_tokens`, while `cached_content_token_count` and `thoughts_token_count` are captured into response metadata and `AIUsageRecord` fields (`cached_tokens`, `thoughts_tokens`).
4. **Verified Pricing Schedule**:
   - Updated `backend/app/modules/ai_engine/usage.py` with date-aware, tier-aware pricing for Gemini 3.8 Flash (2026 standard/batch vs 2027 standard/batch).
   - If batch tier is called with `cached_tokens > 0` (unsupported by Google Batch API), the calculation returns `None` rather than inventing an arbitrary cost.
5. **Quality Gates**:
   - 54/54 tests passed in `backend/tests/test_ai_foundation.py`.
   - 98/98 tests passed in the entire backend regression test suite.
   - 0 errors in frontend TypeScript verification (`npx tsc --noEmit`).
   - 0 database migrations created or run; 0 schema modifications.
   - No Git commits created.

---

## 2. DATABASE SCHEMA CONSTRAINT & PERSISTENCE POLICY

### 2.1 Existing Model Definition (`backend/app/modules/ai_tutor/models.py`)

```python
class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
```

### 2.2 Semantic State Classification

| Semantic State | Input Tokens | Output Tokens | Persistence Action | Telemetry Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **Actual Zero Tokens** | `0` (int) | `0` (int) | **Persist** to `ai_usage_logs` | Row saved: `prompt=0, completion=0, cost=0.0`. Valid audit row. |
| **Normal Usage** | `> 0` (int) | `> 0` (int) | **Persist** to `ai_usage_logs` | Row saved with exact tokens and calculated cost (or `cost=0.0` if model unpriced). |
| **Metadata Unavailable** | `None` | `None` (or one is `None`) | **SKIP PERSISTENCE** | `record_usage_to_db` returns `None`. Safe warning logged. No fake row written. |
| **Provider Failed** | N/A | N/A | **N/A** | Error raised. No usage record created. |

### 2.3 Sanitized Telemetry Logging
When metadata is unavailable, `record_usage_to_db` logs:
```python
logger.warning(
    "Skipping AIUsageLog persistence: usage metadata unavailable (input=%s, output=%s) for model '%s'",
    usage_record.input_tokens,
    usage_record.output_tokens,
    usage_record.model_name,
)
```
- **Security Check**: Never logs prompt text, user responses, PII, or API keys.
- **Isolation Check**: Never raises an exception; caller continues cleanly with business logic.

---

## 3. GOOGLE GENAI SDK TOKEN NORMALIZATION (`google-genai==1.75.0`)

### 3.1 SDK Field Semantics
Inspection of `google.genai.types.GenerateContentResponseUsageMetadata` reveals the exact official field definitions:
- `prompt_token_count`: Total tokens in prompt, including text, images, and cached content.
- `cached_content_token_count`: Output only. Number of tokens served from context cache.
- `candidates_token_count`: Total tokens in generated candidates.
- `thoughts_token_count`: Output only. Number of tokens that were part of the model's generated "thoughts" output.
- `total_token_count`: Sum of `prompt_token_count` + `candidates_token_count`.

### 3.2 Double-Counting Prevention
Because `candidates_token_count` **already includes** `thoughts_token_count`, the normalization code strictly maps:
```python
raw_out = getattr(usage, "candidates_token_count", None)
output_tokens = int(raw_out) if isinstance(raw_out, (int, float)) else None

raw_thoughts = getattr(usage, "thoughts_token_count", None)
thoughts_tokens = int(raw_thoughts) if isinstance(raw_thoughts, (int, float)) else None
```
**Invariant**: `output_tokens` remains `candidates_token_count`. Under no circumstances is `thoughts_token_count` added to `candidates_token_count`.

---

## 4. PRICING SCHEDULE & COST CALCULATION MATRIX

### 4.1 Verified Rates for Gemini 3.8 Flash

| Tier | Window | Input / 1M | Output / 1M | Cached Input / 1M |
| :--- | :--- | :--- | :--- | :--- |
| **Standard** | 2026-01-01 to 2026-12-31 | \$0.75 | \$3.75 | \$0.075 |
| **Standard** | 2027-01-01 to 2099-12-31 | \$1.50 | \$7.50 | \$0.150 |
| **Batch** | 2026-01-01 to 2026-12-31 | \$0.375 (50% off) | \$1.875 (50% off) | *Unsupported (None)* |
| **Batch** | 2027-01-01 to 2099-12-31 | \$0.750 (50% off) | \$3.750 (50% off) | *Unsupported (None)* |

### 4.2 Cost Calculation Integrity
- Formula:
  $$\text{cost} = \left(\frac{\text{regular\_input}}{10^6} \times P_{\text{in}}\right) + \left(\frac{\text{cached\_tokens}}{10^6} \times P_{\text{cache}}\right) + \left(\frac{\text{output\_tokens}}{10^6} \times P_{\text{out}}\right)$$
- If `input_tokens is None` or `output_tokens is None` $\rightarrow \text{cost} = \text{None}$.
- If model or date is unmapped $\rightarrow \text{cost} = \text{None}$.
- If `tier == "batch"` and `cached_tokens > 0` $\rightarrow \text{cost} = \text{None}$ (cannot calculate without verified cache pricing).

---

## 5. TEST VERIFICATION EVIDENCE

### 5.1 AI Foundation Suite (`backend/tests/test_ai_foundation.py`)
Ran:
```powershell
$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests/test_ai_foundation.py -v
```
**Result**: 54 passed in 2.38s.

Key Phase 7.1.2 Test Cases:
1. `test_google_provider_normalizes_usage_metadata_without_double_counting_thoughts`: PASSED (confirms 50 candidates, 20 thoughts $\rightarrow$ output=50, not 70).
2. `test_google_provider_normalizes_missing_usage_metadata`: PASSED (confirms None tokens when metadata is missing).
3. `test_record_usage_skips_persistence_when_input_tokens_none`: PASSED (0 rows inserted in DB).
4. `test_record_usage_skips_persistence_when_output_tokens_none`: PASSED (0 rows inserted in DB).
5. `test_record_usage_skips_persistence_when_both_tokens_none`: PASSED (0 rows inserted in DB).
6. `test_record_usage_persists_when_actual_zero_tokens`: PASSED (persists prompt=0, completion=0, cost=0.0).
7. `test_record_usage_with_cost_none_persists_cost_zero`: PASSED (persists cost=0.0 safely when unpriced).
8. `test_pricing_batch_tier_rejects_cached_tokens`: PASSED (returns None when cached tokens in batch).
9. `test_pricing_2027_batch`: PASSED (calculates $0.75/$3.75 rates accurately).
10. `test_create_usage_record_preserves_cached_and_thoughts_tokens`: PASSED (extracts metadata cleanly).

### 5.2 Full Backend Regression Suite
Ran:
```powershell
$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests -v
```
**Result**: 98 passed in 18.29s (100% pass rate, 0 regressions across exam, autosave, auth, classrooms, questions, curriculum, RBAC).

### 5.3 Frontend TypeScript Verification
Ran:
```powershell
cd frontend; npx tsc --noEmit; cd ..
```
**Result**: Exit code 0, 0 errors.

---

## 6. GIT & REPOSITORY INTEGRITY

- Baseline HEAD: `d6326e5415cb125b62fbe12aea077ecf921d3a88`
- Modified tracked files:
  - `.env.example`
  - `backend/app/config.py`
  - `backend/requirements.txt`
- Untracked files:
  - `backend/app/modules/ai_engine/`
  - `backend/tests/test_ai_foundation.py`
  - `docs/PHASE_6_3_9_POSTGRESQL_TRANSACTION_AUDIT.md`
  - `docs/PHASE_7_0_AI_ARCHITECTURE_ASSESSMENT.md`
  - `docs/PHASE_7_1_1_INDEPENDENT_AUDIT_REPORT.md`
  - `docs/PHASE_7_1_AI_FOUNDATION_REPORT.md`
  - `docs/PHASE_7_1_2_USAGE_DATA_INTEGRITY_REPORT.md`
- Database migrations: 0 added, 0 executed.
- Database schema: Unmodified.
- Commits: 0 created (clean stop).

---

## 7. CONCLUSION & IMPLEMENTATION READINESS

Phase 7.1.2 has conclusively solved the usage data integrity issue. All token accounting, pricing models, and database telemetry boundaries are verified, secure, and regression-free. The system is ready for Phase 7.2 upon user instruction.
