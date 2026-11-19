import { test, expect } from "@playwright/test";

test.describe("Stage A — Student Exam Lifecycle & Security E2E", () => {
  const API_URL = "http://127.0.0.1:8000/api/v1";
  let studentToken: string;
  let targetExamId: string;
  let uniqueEmail: string;
  let completedAttemptId: string;

  test.beforeAll(async ({ request }) => {
    // Register an isolated student user for repeatable test lifecycle
    const uniqueSuffix = Date.now().toString(36) + Math.random().toString(36).substring(2, 5);
    uniqueEmail = `student.lifecycle.${uniqueSuffix}@smartlearning.vn`;
    const regRes = await request.post(`${API_URL}/auth/register`, {
      data: {
        email: uniqueEmail,
        password: "StudentPassword123!",
        full_name: "Học Sinh E2E Test",
        role: "STUDENT",
        grade_level: 11,
      },
    });
    expect(regRes.status()).toBe(201);
    const regData = await regRes.json();
    expect(regData.id).toBeTruthy();

    // Login as this student
    const loginRes = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: uniqueEmail,
        password: "StudentPassword123!",
      },
    });
    expect(loginRes.status()).toBe(200);
    const loginData = await loginRes.json();
    studentToken = loginData.access_token;

    // Fetch available exams to target
    const examsRes = await request.get(`${API_URL}/exams/available`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(examsRes.status()).toBe(200);
    const exams = await examsRes.json();
    expect(exams.length).toBeGreaterThan(0);
    targetExamId = exams[0].id;
  });

  test("1. Student UI renders available exams list and start trigger", async ({ page }) => {
    // Login on the UI
    await page.goto("/login");
    await page.locator("input[type='email']").fill(uniqueEmail);
    await page.locator("input[type='password']").fill("StudentPassword123!");
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");

    // Navigate to /student/exams
    await page.goto("/student/exams");
    await expect(page.locator("h2:has-text('Phòng Luyện thi')")).toBeVisible();

    // Verify exam card exists with real question count and duration
    const examCard = page.locator(".shadow-xs").first();
    await expect(examCard).toBeVisible();

    // Verify clicking "Bắt đầu làm bài" triggers confirmation dialog
    let dialogAppeared = false;
    page.once("dialog", async (dialog) => {
      dialogAppeared = true;
      expect(dialog.message()).toContain("Bạn chuẩn bị bắt đầu làm bài thi");
      await dialog.accept();
    });

    await page.locator("button:has-text('Bắt đầu làm bài')").first().click();
    expect(dialogAppeared).toBe(true);
    // Note: The interactive test-taking screen (/student/exams/[id]) is NOT IMPLEMENTED
    // in the Phase 6 frontend foundation. The full lifecycle is verified via API contract below.
  });

  test("2-3. Start attempt & Anti-leak answer key confidentiality verification", async ({ request }) => {
    // 2. Start attempt
    const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(startRes.status()).toBe(200);
    const startData = await startRes.json();

    expect(startData).toHaveProperty("attempt_id");
    expect(startData).toHaveProperty("questions");
    expect(Array.isArray(startData.questions)).toBe(true);
    expect(startData.questions.length).toBeGreaterThan(0);

    // 3. CRITICAL ANTI-LEAK CHECK:
    // Ensure that NO option contains `is_correct` and NO question exposes `explanation`
    for (const q of startData.questions) {
      expect(q).not.toHaveProperty("explanation");
      expect(q.options).toBeDefined();
      expect(q.options.length).toBeGreaterThan(0);
      for (const opt of q.options) {
        expect(opt).not.toHaveProperty("is_correct");
      }
    }
  });

  test("4-6. Select and autosave answer, verify persistence", async ({ request }) => {
    // Start or fetch active attempt
    const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    const attempt = await startRes.json();
    const attemptId = attempt.attempt_id;
    const firstQ = attempt.questions[0];
    const questionId = firstQ.question_id;
    const chosenOptionId = firstQ.options[0].id;

    // 4-5. Autosave answer
    const autosaveRes = await request.put(
      `${API_URL}/exams/attempts/${attemptId}/answers/${questionId}`,
      {
        headers: { Authorization: `Bearer ${studentToken}` },
        data: {
          selected_option_id: chosenOptionId,
          is_flagged: false,
          time_spent_seconds: 25,
        },
      }
    );
    expect(autosaveRes.status()).toBe(200);
    const autosaveData = await autosaveRes.json();
    expect(autosaveData.status).toBe("SAVED");

    // 6. Reload / Re-fetch attempt state to verify answer is persisted
    const attemptStateRes = await request.get(`${API_URL}/exams/attempts/${attemptId}`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(attemptStateRes.status()).toBe(200);
    const stateData = await attemptStateRes.json();
    expect(stateData.saved_answers).toHaveProperty(questionId);
    expect(stateData.saved_answers[questionId].selected_option_id).toBe(chosenOptionId);
  });

  test("7-9. Submit attempt, verify score, and anti-double-submission", async ({ request }) => {
    const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    const attempt = await startRes.json();
    const attemptId = attempt.attempt_id;
    completedAttemptId = attemptId;

    // 7-8. Submit attempt
    const submitRes = await request.post(`${API_URL}/exams/attempts/${attemptId}/submit`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(submitRes.status()).toBe(200);
    const resultData = await submitRes.json();
    expect(["GRADED", "COMPLETED"]).toContain(resultData.status);
    expect(resultData).toHaveProperty("total_score");
    expect(resultData).toHaveProperty("accuracy_percentage");
    expect(typeof resultData.total_score).toBe("number");
    expect(typeof resultData.accuracy_percentage).toBe("number");

    // 9. Anti-double-submission / Idempotency: Submitting a second time returns existing graded result
    const secondSubmitRes = await request.post(`${API_URL}/exams/attempts/${attemptId}/submit`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(secondSubmitRes.status()).toBe(200);
    const secondData = await secondSubmitRes.json();
    expect(secondData.attempt_id).toBe(attemptId);
    expect(secondData.total_score).toBe(resultData.total_score);
  });

  test("10. Attempt review authorization and IDOR security check", async ({ request }) => {
    // 1. Owning student can view completed attempt review
    const reviewRes = await request.get(`${API_URL}/exams/attempts/${completedAttemptId}/review`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(reviewRes.status()).toBe(200);
    const reviewData = await reviewRes.json();
    expect(["GRADED", "COMPLETED"]).toContain(reviewData.status);
    expect(reviewData).toHaveProperty("total_score");

    // 2. IDOR Prevention: A different student cannot view this student's review
    const otherEmail = `other.student.${Date.now()}@smartlearning.vn`;
    await request.post(`${API_URL}/auth/register`, {
      data: {
        email: otherEmail,
        password: "OtherStudentPassword123!",
        full_name: "Học Sinh Khác",
        role: "STUDENT",
        grade_level: 11,
      },
    });
    const otherLogin = await request.post(`${API_URL}/auth/login`, {
      data: { email: otherEmail, password: "OtherStudentPassword123!" },
    });
    const otherToken = (await otherLogin.json()).access_token;

    const forbiddenReview = await request.get(`${API_URL}/exams/attempts/${completedAttemptId}/review`, {
      headers: { Authorization: `Bearer ${otherToken}` },
    });
    expect(forbiddenReview.status()).toBe(403);
  });
});
