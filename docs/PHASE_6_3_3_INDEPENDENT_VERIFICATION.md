# PHASE 6.3.3 — INDEPENDENT HARDENING VERIFICATION REPORT

**Project:** SMART LEARNING PRO — Nền tảng Học tập Thông minh Chuẩn GDPT 2018  
**Workspace:** `E:\SMART-LEARNING-PRO`  
**Git Baseline & HEAD:** `7b490e30daad71f598358a91b6d5ee9b407f2f25` (`7b490e3`)  
**Previous Audit:** `docs/PHASE_6_3_1_POST_IMPLEMENTATION_AUDIT.md`  
**Implementation Report:** `docs/PHASE_6_3_2_HARDENING_REPORT.md`  
**Verification Date:** 2026-11-19  
**Audit Mode:** READ-ONLY Independent Technical Verification  

---

## 1. AUDIT OVERVIEW & WORKING-TREE INTEGRITY

An independent, read-only technical audit was executed on Phase 6.3.2 implementation at commit `7b490e3`.  
Before and after the inspection, the Git repository working tree was verified:

- **Git HEAD:** `7b490e30daad71f598358a91b6d5ee9b407f2f25`
- **Working Tree Status (Before):** Clean (`nothing to commit, working tree clean`).
- **Working Tree Status (After):** Clean (only this audit report `docs/PHASE_6_3_3_INDEPENDENT_VERIFICATION.md` created; no application source code, tests, or database files modified).

---

## 2. EXECUTIVE SUMMARY & VERDICT TABLE

| Requirement | Verdict | Evidence & Primary Reference |
| :--- | :---: | :--- |
| **SHORT_ANSWER confidentiality** | **PASS** | `service.py:418-420` (`sanitized_opts = []`); `answer_key_snapshot_json` retained on server; `QuestionCreate` validator; 403 on unsubmitted review. |
| **Autosave atomicity** | **FAIL** | Python-level check before ordinary UPDATE lacks SQL atomicity (`service.py:609`). **Critical Bug:** `versionCounters` in `page.tsx:57` resets on page reload, causing all subsequent student edits to be silently discarded by backend (`client_version 1 < answer.version`). |
| **Duplicate answer prevention** | **PASS** | `uq_attempt_question_answer` UNIQUE index verified in active SQLite DB (`student_answers` columns `attempt_id`, `question_id`). |
| **Transaction safety** | **CONDITIONAL PASS** | Race-insert catches `IntegrityError` and rolls back; however, discarded stale autosaves return false `status="SAVED"` (`service.py:596, 609`), and submission retry recursion lacks depth bounds. |
| **Server-side deadline** | **PASS** | Server UTC clock authoritative; `server_time` mitigates client clock skew (`page.tsx:142-148`); expired attempts auto-submitted. |
| **AUTO_SUBMITTED idempotency** | **PASS** | `submit_exam_attempt` lines 670-695 returns cached result; concurrent submit handles `IntegrityError` on `exam_results`. |
| **Assignment policy** | **PASS** | Assignment policies (`allow_review`, `allow_late_submission`, `due_date`) take precedence over exam policies (`service.py:648-668, 979-985`). |
| **Migration integrity** | **PASS** | `migrate_phase632.py` verified; active DB schema confirmed with `version` column and `uq_attempt_question_answer` index. |
| **Test quality** | **CONDITIONAL PASS** | 35/35 Pytest tests pass in 8.22s. Tests exercise real DB/API, but critical gap exists: no test for page reload version reset or concurrent update race. |

**OVERALL VERDICT: FAIL**  
*(At least one critical defect confirmed: Autosave Atomicity & Page Reload Silent Discard).*

---

## 3. DETAILED FINDINGS BY CATEGORY

### 3.1. AUDIT A — SHORT_ANSWER Confidentiality
- **Question Model & Options:** [backend/app/modules/questions/models.py](file:///E:/SMART-LEARNING-PRO/backend/app/modules/questions/models.py#L40-L65). Question options hold `content` and `is_correct`.
- **Snapshot Creation:** [backend/app/modules/exams/service.py#L418-L453](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L418-L453).
  - Lines 418-420: If `q.question_type == QuestionType.SHORT_ANSWER.value`, `sanitized_opts = []`.
  - Lines 431-440: `q_item_sanitized` contains only `question_id`, `order_index`, `points`, `content`, `question_type`, `difficulty_level`, `hint`, and `options: []`. Neither `is_correct` nor `explanation` is present.
  - Lines 441-450: `q_item_full` retains `explanation` and `full_opts` with `is_correct: True`.
  - Line 463-464: `questions_snapshot_json` stores sanitized snapshot; `answer_key_snapshot_json` stores full snapshot.
- **Start Response:** [backend/app/modules/exams/router.py#L48-L60](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/router.py#L48-L60). `ExamStartResponse` returns sanitized `snapshot`.
- **Attempt Detail Response:** [backend/app/modules/exams/router.py#L77-L115](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/router.py#L77-L115). Returns `questions: snapshot` and `saved_answers` populated strictly from `StudentAnswer`.
- **Autosave Response:** [backend/app/modules/exams/schemas.py#L118-L123](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/schemas.py#L118-L123). Contains only `status`, `attempt_id`, `question_id`, `version`, `saved_at`.
- **Pre-submission Review Access:** [backend/app/modules/exams/service.py#L976-L977](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L976-L977). Attempts in `IN_PROGRESS` raise `PermissionDeniedException("Bài thi chưa được nộp. Không thể xem lại đáp án.")` (HTTP 403).
- **Grading Integrity:** [backend/app/modules/exams/service.py#L786-L792](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L786-L792). Correct answers are retrieved from `answer_key_snapshot_json` and compared normalized (`.strip().lower()`).
- **Verdict: PASS**.

---

### 3.2. AUDIT B — Autosave Atomicity & Page Reload Defect
- **Source References:**
  - Backend: [backend/app/modules/exams/service.py#L571-L623](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L571-L623)
  - Frontend: [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L57, L188-L235](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L57)
- **Defect B1 (CONFIRMED CRITICAL BUG — Page Reload Silent Discard):**
  1. In `page.tsx:57`: `const versionCounters = useRef<Record<string, number>>({})`.
  2. In `page.tsx:188`: `const currentVersion = (versionCounters.current[questionId] || 0) + 1`.
  3. When an exam attempt is in progress and a student has answered question 1 (e.g. version 2 in DB):
     - The student refreshes the browser page (F5), closes/reopens the tab, or switches devices.
     - `versionCounters.current` resets to `{}`.
     - When the student enters a new answer, `versionCounters.current[questionId]` evaluates to `(0) + 1 = 1`.
     - The autosave request sends `client_version: 1`.
  4. In `service.py:609`:
     ```python
     if data.client_version is not None and data.client_version < answer.version:
         return answer
     ```
     Because `client_version (1) < answer.version (2)` is `True`, the backend discards the new answer and returns the old record without modification!
  5. In `router.py:110`: The endpoint wraps the returned answer into `AutosaveAnswerResponse(status="SAVED", ...)`.
  6. The student's browser receives `status: "SAVED"` and displays green badge `"Đã lưu máy chủ"`.
  7. **Impact:** The student believes their new answer was saved, but the server discarded it. The student loses work upon reload.
- **Defect B2 (Lack of Database-Level Atomic UPDATE):**
  - In `service.py:608-623`, the version check is evaluated entirely in Python memory on an attached entity.
  - SQLAlchemy `StudentAnswer` does not define `__mapper_args__ = {"version_id_col": version}`.
  - When two requests execute concurrently, both read `answer.version == V`, both pass the Python check `V < V == False`, and both issue ordinary `UPDATE student_answers SET ... WHERE id = :id`.
  - The later commit overwrites the earlier commit without checking if `version` changed in the database between select and update.
- **Verdict: FAIL**.

---

### 3.3. AUDIT C — IntegrityError and Transaction Safety
- **Source References:**
  - [backend/app/modules/exams/service.py#L587-L606](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L587-L606) (Autosave insert race)
  - [backend/app/modules/exams/service.py#L937-L944](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L937-L944) (Submit race)
- **Insert Race Condition Handling:**
  - Lines 587-594: When two requests simultaneously attempt the initial insert of an answer, the second catches `IntegrityError` from `uq_attempt_question_answer`, rolls back the transaction, queries the winning record (`ans_res2 = await db.execute(existing_query)`), and applies the update.
  - `UNIQUE INDEX uq_attempt_question_answer` guarantees that no two rows can exist for `(attempt_id, question_id)`.
- **False Status Emission (CONFIRMED DEFECT):**
  - Lines 596-597 & 609-610: When a stale packet is discarded via `return answer`, the function does not signal to the caller that the update was dropped.
  - Router returns HTTP 200 with `AutosaveAnswerResponse(status="SAVED", ...)`.
  - An API contract violation: returning `status="SAVED"` for an unsaved/discarded packet.
- **Unbounded Recursion Risk:**
  - Lines 940-943: In `submit_exam_attempt`, `return await submit_exam_attempt(db, attempt_id, user, auto_submitted)` is unbounded. If `attempt.result` is None due to session state after rollback, recursion could continue until stack overflow.
- **Verdict: CONDITIONAL PASS**.

---

### 3.4. AUDIT D — Deadline and Auto-Submission
- **Source References:**
  - [backend/app/modules/exams/router.py#L79-L90](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/router.py#L79-L90)
  - [backend/app/modules/exams/service.py#L659-L695](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L659-L695)
  - [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L140-L158](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L140-L158)
- **GET Request Database Mutation:**
  - In `router.py:82-89`, a `GET /exams/attempts/{attempt_id}` request checks `if attempt.status == IN_PROGRESS and now > deadline: await submit_exam_attempt(..., auto_submitted=True)`.
  - This mutates the attempt status, creates an `ExamResult`, and awards XP points.
  - While violating strict REST idempotency principles (GET requests should be safe per RFC 7231), it guarantees that students cannot hold an expired exam open without it becoming graded.
- **Clock Skew Mitigation:**
  - `ExamStartResponse`, `get_attempt`, and `ExamSubmitResponse` return `server_time`.
  - Frontend computes `serverTimeOffset = serverNowMs - Date.now()`.
  - Timer uses `Date.now() + serverTimeOffset`. A client clock set 10 minutes fast or slow displays the exact server remaining time.
  - Server evaluates deadlines using `datetime.now(timezone.utc)`. Client clock cannot alter server deadline enforcement.
- **Concurrent Submit Idempotency:**
  - Verified: Lines 670-695 return the cached result if status is already `SUBMITTED`, `AUTO_SUBMITTED`, or `GRADED`.
- **Verdict: PASS**.

---

### 3.5. AUDIT E — Assignment Policy
- **Source References:**
  - [backend/app/modules/exams/service.py#L648-L668](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L648-L668)
  - [backend/app/modules/exams/service.py#L979-L985](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L979-L985)
  - [backend/app/modules/classrooms/service.py#L669-L672](file:///E:/SMART-LEARNING-PRO/backend/app/modules/classrooms/service.py#L669-L672)
- **Precedence Verification:**
  - When `attempt.assignment_id` is present, `attempt.assignment.allow_review` and `attempt.assignment.allow_late_submission` are authoritative.
  - Case 1: Exam `allow_review=True`, Assignment `allow_review=False` -> Student review is blocked with HTTP 403 Forbidden.
  - Case 2: Exam `allow_review=False`, Assignment `allow_review=True` -> Student review is allowed with HTTP 200 OK.
  - Case 3: Assignment `allow_late_submission=False` and past `due_date` -> Attempt start raises HTTP 403 Forbidden; In-progress attempt marks `auto_submitted=True`.
- **Verdict: PASS**.

---

### 3.6. AUDIT F — Database Migration
- **Source Reference:** [scripts/migrate_phase632.py](file:///E:/SMART-LEARNING-PRO/scripts/migrate_phase632.py)
- **Active SQLite DB Verification:**
  - `PRAGMA table_info(student_answers)` confirmed column `version` (`INTEGER NOT NULL DEFAULT 1`).
  - `PRAGMA index_list(student_answers)` confirmed unique index `uq_attempt_question_answer` on `(attempt_id, question_id)`.
- **Migration Properties:**
  - Idempotent: checks for column existence via `PRAGMA table_info` and uses `CREATE UNIQUE INDEX IF NOT EXISTS`.
  - Reconciles duplicate answer rows before creating index (keeps newest by `updated_at`, `answered_at`, `time_spent_seconds`).
  - Limitations: Uses Python `sqlite3` driver directly; not portable to PostgreSQL without Alembic.
  - Backup: No automated backup routine inside the script file itself.
- **Verdict: PASS** (for SQLite development baseline).

---

### 3.7. AUDIT G — Test Quality
- **Test Suite Results:**
  - Command: `$env:PYTHONPATH=".;backend"; .venv\Scripts\pytest -c backend/pytest.ini backend/tests`
  - Total: 35 tests. Passed: 35. Failed: 0. Exit code: 0. Duration: 8.22s.
- **Test Analysis (`test_hardening_632.py`):**
  - `test_short_answer_confidentiality_and_validation`: Genuinely tests 422 validation, empty options in snapshot, grading normalization, and review payload.
  - `test_student_answers_unique_constraint_and_autosave_versions`: Tests sequential out-of-order rejection.
  - `test_assignment_policy_enforcement`: Tests dual-policy override (403 and 200).
  - `test_all_four_question_types_e2e`: Tests full lifecycle across all 4 GDPT question types to 10.0 score.
- **Test Gaps:**
  - No test simulates browser reload version counter reset.
  - No test verifies concurrent multithreaded/multitask race on autosave updates.
  - No test checks for false `status="SAVED"` when an update is rejected.
- **Verdict: CONDITIONAL PASS**.

---

## 4. CONFIRMED DEFECTS & ACTIONABLE REMEDIATION PLAN

### Defect 1 [CRITICAL]: Page Reload Causes Autosave Discard (Frontend + Backend Contract)
- **Location:** [frontend/src/app/student/exams/attempts/[attemptId]/page.tsx#L57, L188](file:///E:/SMART-LEARNING-PRO/frontend/src/app/student/exams/attempts/%5BattemptId%5D/page.tsx#L57) & [backend/app/modules/exams/service.py#L609](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L609).
- **Reproduction:**
  1. Student starts exam, answers Question 1 twice (`answer.version` in DB = 2).
  2. Student presses F5 (page reload).
  3. `versionCounters.current` in React resets to `{}`.
  4. Student answers Question 1 again (`client_version = 1`).
  5. Backend evaluates `client_version (1) < answer.version (2)` -> True.
  6. Backend discards answer, router returns `status="SAVED"`.
  7. Client displays "Đã lưu máy chủ", but the new answer is never persisted.
- **Required Remediation:**
  1. In `page.tsx`, when `attempt` data is fetched, initialize `versionCounters.current[qid]` from `attempt.saved_answers[qid].version || 0`.
  2. In `backend/app/modules/exams/service.py`, do not use a simple global counter comparison that assumes monotonic client increment across sessions.

### Defect 2 [HIGH]: Lack of Atomic Database UPDATE in Autosave
- **Location:** [backend/app/modules/exams/service.py#L608-L623](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L608-L623).
- **Problem:** Python-level comparison `client_version < answer.version` does not prevent concurrent lost updates.
- **Required Remediation:** Configure `StudentAnswer` with SQLAlchemy optimistic locking (`__mapper_args__ = {"version_id_col": version}`), or execute an atomic SQL `update().where(StudentAnswer.id == answer.id, StudentAnswer.version == expected_version)`.

### Defect 3 [MEDIUM]: False "SAVED" Status on Discarded Autosaves
- **Location:** [backend/app/modules/exams/service.py#L596, L610](file:///E:/SMART-LEARNING-PRO/backend/app/modules/exams/service.py#L596).
- **Problem:** When an answer is discarded due to stale version, returning the unchanged entity causes the router to emit `AutosaveAnswerResponse(status="SAVED")`.
- **Required Remediation:** Return `status="STALE_IGNORED"` or raise an appropriate conflict exception so the client UI is accurately informed.

---

## 5. FINAL RECOMMENDATION

**DO NOT PROCEED TO PHASE 6.4 (OR PHASE 7 AI ENGINE) UNTIL REMEDIATED.**

Remediate Defect 1 and Defect 3 first:
1. Initialize `versionCounters` from server-loaded `attempt.saved_answers[qid].version`.
2. Differentiate `SAVED` vs `STALE_IGNORED` in autosave response.
3. Add an automated regression test simulating the page reload and version sync workflow.
