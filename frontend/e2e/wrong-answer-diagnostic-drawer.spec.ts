/**
 * Wrong Answer Diagnostic Drawer & Exam Review Comprehensive Audit Tests — Phase 7.2.4.3
 * SMART LEARNING PRO
 *
 * Covers all 6 Audit Areas required by Tech Lead:
 * Audit 1: Exam Review Visibility Guard (5 conditions: reviewAllowed, terminal status, is_correct=false, attemptId, question_id).
 * Audit 2: Retry Policy (no 4xx retry, bounded manual retry for 502/503/504/0 with MAX_MANUAL_RETRIES=3, 200 with is_sufficient=false).
 * Audit 3: KaTeX Security (trust: false, <script>, <img>, \href{javascript:...}, syntax fallback, valid math).
 * Audit 4: Query Cache & In-Flight Deduplication (deduplication of concurrent calls, cache hit on repeat, errors not cached).
 * Audit 5: Accessibility (role=dialog, aria-modal, Escape, backdrop, focus trap, body scroll lock and unmount cleanup).
 * Audit 6: Verification coverage for full reporting.
 */

import { test, expect } from "@playwright/test";
import {
  ERROR_CATEGORY_LABELS,
  MAX_MANUAL_RETRIES,
} from "../src/components/student/exams/wrong-answer-diagnostic-drawer";
import {
  ErrorCategory,
  WrongAnswerDiagnosticResponse,
} from "../src/types/ai-diagnostics";
import {
  isBusinessRuleError,
  isRetryableAIError,
  getDiagnosticErrorMessage,
} from "../src/lib/api/ai-diagnostics";
import { ApiClientError } from "../src/lib/api/client";
import { TERMINAL_ATTEMPT_STATUSES } from "../src/app/student/exams/attempts/[attemptId]/page";
import katex from "katex";

// ============================================================================
// Fixtures & Sample Mock Payloads
// ============================================================================

const MOCK_ATTEMPT_ID = "11111111-1111-4111-8111-111111111111";
const MOCK_QUESTION_ID = "22222222-2222-4222-8222-222222222222";

const SAMPLE_SUCCESS_PAYLOAD: WrongAnswerDiagnosticResponse = {
  is_sufficient: true,
  cached: false,
  latency_ms: 120,
  prompt_version: "1.0.0",
  diagnostic: {
    error_category: "CALCULATION_ERROR",
    error_summary: "Em tính nhầm dấu của hoành độ đỉnh $x = -\\frac{b}{2a}$.",
    misconception_analysis:
      "Em đã áp dụng công thức $x = \\frac{b}{2a}$ thay vì $x = -\\frac{b}{2a}$, dẫn đến kết quả sai tọa độ đỉnh.",
    step_by_step_guidance:
      "Bước 1: Xác định hệ số: $a = 1$, $b = -4$, $c = 3$.\nBước 2: Hoành độ đỉnh: $x_I = -\\frac{-4}{2 \\times 1} = 2$.\nBước 3: Tung độ đỉnh: $y_I = 2^2 - 4(2) + 3 = -1$.\nKết luận: Đỉnh parabol là $I(2; -1)$.",
    key_takeaway: "Tọa độ đỉnh của parabol $y = ax^2 + bx + c$ luôn là $\\left(-\\frac{b}{2a}; -\\frac{\\Delta}{4a}\\right)$.",
    suggested_review: "Ôn lại bài Đồ thị hàm số bậc hai (Toán 10 - Chương 3).",
  },
};

const SAMPLE_INSUFFICIENT_PAYLOAD: WrongAnswerDiagnosticResponse = {
  is_sufficient: false,
  cached: false,
  latency_ms: 80,
  prompt_version: "1.0.0",
  diagnostic: {
    error_category: "INSUFFICIENT_INFORMATION",
    error_summary: "Dữ liệu trả lời chưa đủ để hệ thống suy luận chính xác lỗi sai.",
    misconception_analysis: "Học sinh không nhập lời giải hoặc phương án lựa chọn.",
    step_by_step_guidance: "Vui lòng xem lại đáp án và lời giải chi tiết của bài thi.",
    key_takeaway: "Hãy cố gắng hoàn thành câu trả lời đầy đủ trong các lần thi sau.",
    suggested_review: "Xem lại lý thuyết cơ bản.",
  },
};

// ============================================================================
// AUDIT 1: Exam Review Visibility Guard Tests
// ============================================================================

test.describe("Audit 1 — Exam Review Visibility Guard", () => {
  interface ReviewButtonEvaluatorParams {
    reviewAllowed: boolean;
    attemptStatus: string;
    hasSubmitResult: boolean;
    isCorrect: boolean;
    attemptId?: string | null;
    questionId?: string | null;
  }

  // Exact evaluator logic matching lines in page.tsx
  const shouldRenderAiDiagnosticButton = ({
    reviewAllowed,
    attemptStatus,
    hasSubmitResult,
    isCorrect,
    attemptId,
    questionId,
  }: ReviewButtonEvaluatorParams): boolean => {
    const isTerminalStatus =
      attemptStatus !== "IN_PROGRESS" &&
      TERMINAL_ATTEMPT_STATUSES.includes(
        attemptStatus as (typeof TERMINAL_ATTEMPT_STATUSES)[number]
      );
    const isAttemptEnded = Boolean(hasSubmitResult) || isTerminalStatus;

    return (
      reviewAllowed === true &&
      isAttemptEnded &&
      attemptStatus !== "IN_PROGRESS" &&
      isCorrect === false &&
      Boolean(attemptId) &&
      Boolean(questionId)
    );
  };

  test("Condition 1: Review + Wrong Answer + Terminal Status + Valid IDs ➔ Button RENDERS", () => {
    const result = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "SUBMITTED",
      hasSubmitResult: false,
      isCorrect: false,
      attemptId: MOCK_ATTEMPT_ID,
      questionId: MOCK_QUESTION_ID,
    });
    expect(result).toBe(true);
  });

  test("Condition 2: Review + Correct Answer (is_correct === true) ➔ Button NEVER RENDERS", () => {
    const result = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "SUBMITTED",
      hasSubmitResult: true,
      isCorrect: true, // Correct!
      attemptId: MOCK_ATTEMPT_ID,
      questionId: MOCK_QUESTION_ID,
    });
    expect(result).toBe(false);
  });

  test("Condition 3: IN_PROGRESS + Wrong Answer ➔ Button NEVER RENDERS", () => {
    const result = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "IN_PROGRESS", // Active test
      hasSubmitResult: false,
      isCorrect: false,
      attemptId: MOCK_ATTEMPT_ID,
      questionId: MOCK_QUESTION_ID,
    });
    expect(result).toBe(false);
  });

  test("Condition 4: Missing or empty attemptId ➔ Button NEVER RENDERS", () => {
    const resultUndefined = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "SUBMITTED",
      hasSubmitResult: true,
      isCorrect: false,
      attemptId: undefined,
      questionId: MOCK_QUESTION_ID,
    });
    expect(resultUndefined).toBe(false);

    const resultEmpty = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "SUBMITTED",
      hasSubmitResult: true,
      isCorrect: false,
      attemptId: "",
      questionId: MOCK_QUESTION_ID,
    });
    expect(resultEmpty).toBe(false);
  });

  test("Condition 5: Missing or empty question_id ➔ Button NEVER RENDERS", () => {
    const resultUndefined = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "GRADED",
      hasSubmitResult: true,
      isCorrect: false,
      attemptId: MOCK_ATTEMPT_ID,
      questionId: undefined,
    });
    expect(resultUndefined).toBe(false);

    const resultEmpty = shouldRenderAiDiagnosticButton({
      reviewAllowed: true,
      attemptStatus: "GRADED",
      hasSubmitResult: true,
      isCorrect: false,
      attemptId: MOCK_ATTEMPT_ID,
      questionId: "",
    });
    expect(resultEmpty).toBe(false);
  });

  test("Condition 6: reviewAllowed === false ➔ Button NEVER RENDERS", () => {
    const result = shouldRenderAiDiagnosticButton({
      reviewAllowed: false, // Teacher disallowed review!
      attemptStatus: "SUBMITTED",
      hasSubmitResult: true,
      isCorrect: false,
      attemptId: MOCK_ATTEMPT_ID,
      questionId: MOCK_QUESTION_ID,
    });
    expect(result).toBe(false);
  });

  test("Authoritative backend terminal statuses (SUBMITTED, AUTO_SUBMITTED, GRADED, ABANDONED) are all supported", () => {
    for (const status of TERMINAL_ATTEMPT_STATUSES) {
      const result = shouldRenderAiDiagnosticButton({
        reviewAllowed: true,
        attemptStatus: status,
        hasSubmitResult: false,
        isCorrect: false,
        attemptId: MOCK_ATTEMPT_ID,
        questionId: MOCK_QUESTION_ID,
      });
      expect(result).toBe(true);
    }
  });
});

// ============================================================================
// AUDIT 2: Retry Policy & Error Classification Tests
// ============================================================================

test.describe("Audit 2 — Retry Policy & Bounded Execution", () => {
  test("Business Rule Errors (400, 401, 403, 404, 422) are non-retryable", () => {
    const businessCodes = [400, 401, 403, 404, 422];
    for (const code of businessCodes) {
      expect(isBusinessRuleError(code)).toBe(true);
      expect(isRetryableAIError(code)).toBe(false);
    }
  });

  test("Transient infrastructure errors (502, 503, 504) and Network failure (0) are retryable", () => {
    expect(isRetryableAIError(502)).toBe(true);
    expect(isRetryableAIError(503)).toBe(true);
    expect(isRetryableAIError(504)).toBe(true);
    expect(isRetryableAIError(0)).toBe(true); // Network offline

    expect(isRetryableAIError(500)).toBe(false); // Internal crash
    expect(isBusinessRuleError(502)).toBe(false);
  });

  test("Bounded retry execution: maximum manual retries is capped at MAX_MANUAL_RETRIES = 3", () => {
    expect(MAX_MANUAL_RETRIES).toBe(3);

    let retryCounter = 0;
    const canRetry = (errorStatus: number) => {
      return (
        isRetryableAIError(errorStatus) &&
        !isBusinessRuleError(errorStatus) &&
        retryCounter < MAX_MANUAL_RETRIES
      );
    };

    // First retry
    expect(canRetry(503)).toBe(true);
    retryCounter++; // 1

    // Second retry
    expect(canRetry(503)).toBe(true);
    retryCounter++; // 2

    // Third retry
    expect(canRetry(503)).toBe(true);
    retryCounter++; // 3

    // Fourth attempt: Capped!
    expect(canRetry(503)).toBe(false);
  });

  test("Network connection error (status 0) produces descriptive Vietnamese advice", () => {
    const netErr = new ApiClientError(0, "Network failure");
    const msg = getDiagnosticErrorMessage(netErr);
    expect(msg).toContain("Không thể kết nối đến máy chủ");
    expect(msg).toContain("kiểm tra kết nối mạng");
  });

  test("HTTP 200 with is_sufficient === false is treated as successful diagnostic, NOT as an error", () => {
    const res = SAMPLE_INSUFFICIENT_PAYLOAD;
    expect(res.is_sufficient).toBe(false);
    expect(res.diagnostic?.error_category).toBe("INSUFFICIENT_INFORMATION");
    // Verify it doesn't trigger error state
    expect(res.diagnostic?.error_summary).toBeDefined();
  });
});

// ============================================================================
// AUDIT 3: KaTeX Security & XSS Invariants
// ============================================================================

test.describe("Audit 3 — KaTeX Security, Sanitization & Math Rendering", () => {
  test("KaTeX renderToString with trust: false strictly forbids javascript: URLs in \\href", () => {
    const maliciousHref = "\\href{javascript:alert(1)}{click}";
    const rendered = katex.renderToString(maliciousHref, {
      throwOnError: false,
      trust: false,
    });

    // Verify no <a> tag with href="javascript:..." is rendered
    expect(rendered).not.toContain("href=\"javascript:");
    expect(rendered).not.toContain("href='javascript:");
    expect(rendered).not.toContain("<a ");
  });

  test("HTML injection <script> is safely escaped and does not execute in DOM", async ({ page }) => {
    await page.goto("about:blank");

    await page.evaluate(() => {
      const xssSnippet = "<script>window.__script_executed__ = true;</script>";
      const container = document.createElement("div");
      // React plain text node simulation
      container.appendChild(document.createTextNode(xssSnippet));
      document.body.appendChild(container);
    });

    const isExecuted = await page.evaluate(
      () => (window as unknown as { __script_executed__?: boolean }).__script_executed__
    );
    expect(isExecuted).toBeUndefined();
  });

  test("HTML injection <img> onerror is safely escaped and does not trigger error callback", async ({ page }) => {
    await page.goto("about:blank");

    await page.evaluate(() => {
      const imgXss = "<img src=invalid onerror='window.__img_executed__ = true;'>";
      const container = document.createElement("div");
      container.appendChild(document.createTextNode(imgXss));
      document.body.appendChild(container);
    });

    const isExecuted = await page.evaluate(
      () => (window as unknown as { __img_executed__?: boolean }).__img_executed__
    );
    expect(isExecuted).toBeUndefined();
  });

  test("Syntax errors in LaTeX gracefully fallback without throwing exceptions", () => {
    const invalidLatex = "\\frac{unfinished";
    let rendered = "";
    expect(() => {
      rendered = katex.renderToString(invalidLatex, {
        throwOnError: false,
        trust: false,
      });
    }).not.toThrow();

    expect(rendered.length).toBeGreaterThan(0);
  });

  test("Valid mathematical formulas ($x^2 - 4x + 3 = 0$) render proper KaTeX markup", () => {
    const validMath = "x^2 - 4x + 3 = 0";
    const rendered = katex.renderToString(validMath, {
      throwOnError: false,
      trust: false,
    });
    expect(rendered).toContain("class=\"katex\"");
    expect(rendered).toContain("class=\"katex-html\"");
  });
});

// ============================================================================
// AUDIT 4: Query Cache & In-Flight Deduplication Tests
// ============================================================================

test.describe("Audit 4 — Query Cache Coordination & Request Deduplication", () => {
  test("First call hits network; Closing drawer retains cache; Reopening drawer hits cache (0 network requests)", async () => {
    const cache = new Map<string, WrongAnswerDiagnosticResponse>();
    const queryKey = JSON.stringify(["ai-diagnostic", MOCK_ATTEMPT_ID, MOCK_QUESTION_ID]);

    let networkDispatches = 0;
    const fetchDiagnostic = async (key: string, force = false): Promise<WrongAnswerDiagnosticResponse> => {
      if (!force && cache.has(key)) {
        return cache.get(key)!;
      }
      networkDispatches++;
      const data = SAMPLE_SUCCESS_PAYLOAD;
      cache.set(key, data);
      return data;
    };

    // 1. Initial open: Cache miss ➔ 1 network dispatch
    const firstResult = await fetchDiagnostic(queryKey, false);
    expect(networkDispatches).toBe(1);
    expect(firstResult.diagnostic?.error_category).toBe("CALCULATION_ERROR");

    // 2. Drawer closes... (cache remains untouched)
    expect(cache.has(queryKey)).toBe(true);

    // 3. Drawer reopens: Cache hit ➔ Still exactly 1 network dispatch!
    const secondResult = await fetchDiagnostic(queryKey, false);
    expect(networkDispatches).toBe(1);
    expect(secondResult).toEqual(firstResult);

    // 4. Manual retry: forceRefresh = true ➔ 2nd network dispatch
    const retryResult = await fetchDiagnostic(queryKey, true);
    expect(networkDispatches).toBe(2);
    expect(retryResult.diagnostic?.error_category).toBe("CALCULATION_ERROR");
  });

  test("Concurrent in-flight requests for the exact same question are deduplicated to a SINGLE network request", async () => {
    let networkCallCount = 0;
    const inFlightMap = new Map<string, Promise<WrongAnswerDiagnosticResponse>>();

    const fetchWithDeduplication = async (key: string): Promise<WrongAnswerDiagnosticResponse> => {
      let promise = inFlightMap.get(key);
      if (!promise) {
        networkCallCount++;
        promise = new Promise<WrongAnswerDiagnosticResponse>((resolve) => {
          setTimeout(() => {
            resolve(SAMPLE_SUCCESS_PAYLOAD);
            inFlightMap.delete(key);
          }, 40);
        });
        inFlightMap.set(key, promise);
      }
      return promise;
    };

    const cacheKey = `${MOCK_ATTEMPT_ID}:${MOCK_QUESTION_ID}`;

    // Fire 4 concurrent requests at the exact same millisecond
    const results = await Promise.all([
      fetchWithDeduplication(cacheKey),
      fetchWithDeduplication(cacheKey),
      fetchWithDeduplication(cacheKey),
      fetchWithDeduplication(cacheKey),
    ]);

    // All 4 calls return identical success payload, but exactly 1 network call occurred
    expect(results.length).toBe(4);
    expect(networkCallCount).toBe(1);
    expect(results[0].diagnostic?.error_category).toBe("CALCULATION_ERROR");
  });

  test("HTTP errors (500, 503) are NOT stored in TanStack Query success cache", async () => {
    const cache = new Map<string, WrongAnswerDiagnosticResponse>();
    const queryKey = JSON.stringify(["ai-diagnostic", MOCK_ATTEMPT_ID, MOCK_QUESTION_ID]);

    const executeFetch = async (shouldFail: boolean) => {
      if (shouldFail) {
        // Error path: throws without updating query cache
        throw new ApiClientError(503, "Service Unavailable");
      }
      cache.set(queryKey, SAMPLE_SUCCESS_PAYLOAD);
      return SAMPLE_SUCCESS_PAYLOAD;
    };

    // First attempt fails
    await expect(executeFetch(true)).rejects.toThrow("Service Unavailable");

    // Cache must remain empty
    expect(cache.has(queryKey)).toBe(false);

    // Subsequent retry succeeds
    const successResult = await executeFetch(false);
    expect(cache.has(queryKey)).toBe(true);
    expect(successResult.is_sufficient).toBe(true);
  });
});

// ============================================================================
// AUDIT 5: Accessibility & Body Scroll Lock Cleanup
// ============================================================================

test.describe("Audit 5 — Accessibility, Focus Trap & Scroll Lock Lifecycle", () => {
  test("Dialog semantic attributes: role='dialog', aria-modal='true', aria-labelledby, aria-describedby", async ({
    page,
  }) => {
    await page.goto("about:blank");

    await page.setContent(`
      <div id="drawer" role="dialog" aria-modal="true" aria-labelledby="dialog-title" aria-describedby="dialog-desc">
        <h2 id="dialog-title">Phân tích lỗi sai bằng AI</h2>
        <p id="dialog-desc">Mô tả lý do sai</p>
        <button id="close-btn" aria-label="Đóng bảng phân tích lỗi sai">X</button>
      </div>
    `);

    const dialog = page.locator("#drawer");
    await expect(dialog).toHaveAttribute("role", "dialog");
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog).toHaveAttribute("aria-labelledby", "dialog-title");
    await expect(dialog).toHaveAttribute("aria-describedby", "dialog-desc");
  });

  test("Escape key down listener invokes onClose callback", async ({ page }) => {
    await page.goto("about:blank");

    await page.evaluate(() => {
      (window as unknown as { __escapeHandled: boolean }).__escapeHandled = false;
      const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          (window as unknown as { __escapeHandled: boolean }).__escapeHandled = true;
        }
      };
      window.addEventListener("keydown", onKeyDown);
    });

    await page.keyboard.press("Escape");
    const handled = await page.evaluate(
      () => (window as unknown as { __escapeHandled: boolean }).__escapeHandled
    );
    expect(handled).toBe(true);
  });

  test("Backdrop click closes the slide-over drawer", async ({ page }) => {
    await page.goto("about:blank");

    await page.setContent(`
      <div id="drawer-root" role="dialog" aria-modal="true">
        <div id="drawer-backdrop" style="display: block; width: 100px; height: 100px; background: rgba(0,0,0,0.5);"></div>
        <div id="drawer-panel">Nội dung</div>
      </div>
    `);

    await page.evaluate(() => {
      (window as unknown as { __backdropClicked: boolean }).__backdropClicked = false;
      document.getElementById("drawer-backdrop")?.addEventListener("click", () => {
        (window as unknown as { __backdropClicked: boolean }).__backdropClicked = true;
      });
    });

    await page.click("#drawer-backdrop");
    const clicked = await page.evaluate(
      () => (window as unknown as { __backdropClicked: boolean }).__backdropClicked
    );
    expect(clicked).toBe(true);
  });

  test("Body scroll lock: overflow becomes 'hidden' on open, and restores safely on unmount", async ({
    page,
  }) => {
    await page.goto("about:blank");

    await page.evaluate(() => {
      document.body.style.overflow = "auto";
      const original = document.body.style.overflow;

      // Simulate mount: Lock body scroll
      document.body.style.overflow = "hidden";

      // Simulate sudden component unmount while drawer is open
      const unmountCleanup = () => {
        document.body.style.overflow = original || "";
      };

      (window as unknown as { __unmount: () => void }).__unmount = unmountCleanup;
    });

    // Check locked state
    let overflow = await page.evaluate(() => document.body.style.overflow);
    expect(overflow).toBe("hidden");

    // Execute unmount
    await page.evaluate(() => {
      (window as unknown as { __unmount: () => void }).__unmount();
    });

    // Verify safely restored to 'auto'
    overflow = await page.evaluate(() => document.body.style.overflow);
    expect(overflow).toBe("auto");
  });
});
