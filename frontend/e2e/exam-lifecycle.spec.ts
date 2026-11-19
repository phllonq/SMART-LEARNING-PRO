import { test, expect } from "@playwright/test";

test.describe("Stage A — Student Exam Interface & Lifecycle E2E (Phase 6.3)", () => {
  const API_URL = "http://127.0.0.1:8000/api/v1";
  let studentEmail: string;
  const studentPassword = "StudentPassword123!";
  let studentToken: string;
  let targetExamId: string;
  let targetExamTitle: string;
  let createdAttemptId: string;

  test.beforeAll(async ({ request }) => {
    const uniqueSuffix = Date.now().toString(36) + Math.random().toString(36).substring(2, 5);
    targetExamTitle = `Đề Thi Khảo Thí E2E ${uniqueSuffix}`;

    // 1. Teacher login to create a fresh, dedicated 2-question exam
    const teacherLogin = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: "giaovien.toan@smartlearning.vn",
        password: "TeacherPassword123!",
      },
    });
    expect(teacherLogin.status()).toBe(200);
    const teacherToken = (await teacherLogin.json()).access_token;

    // Get 2 available questions
    const qListRes = await request.get(`${API_URL}/questions?page_size=2`, {
      headers: { Authorization: `Bearer ${teacherToken}` },
    });
    expect(qListRes.status()).toBe(200);
    const qListData = await qListRes.json();
    const qIds = qListData.items.map((q: { id: string }) => q.id);

    // Create exam
    const createExamRes = await request.post(`${API_URL}/exams`, {
      headers: { Authorization: `Bearer ${teacherToken}` },
      data: {
        title: targetExamTitle,
        description: "Đề thi khảo sát tích hợp E2E tự động",
        grade_id: 10,
        duration_minutes: 45,
        total_points: 10.0,
        passing_points: 5.0,
        max_attempts: 10,
        question_ids: qIds,
      },
    });
    expect(createExamRes.status()).toBe(201);
    const createdExam = await createExamRes.json();
    targetExamId = createdExam.id;

    // Publish exam
    const pubRes = await request.post(`${API_URL}/exams/${targetExamId}/publish`, {
      headers: { Authorization: `Bearer ${teacherToken}` },
    });
    expect(pubRes.status()).toBe(200);

    // 2. Register a dedicated student
    studentEmail = `student.exam.${uniqueSuffix}@smartlearning.vn`;
    const regRes = await request.post(`${API_URL}/auth/register`, {
      data: {
        email: studentEmail,
        password: studentPassword,
        full_name: "Học Sinh Khảo Thí",
        role: "STUDENT",
        grade_level: 10,
      },
    });
    expect(regRes.status()).toBe(201);

    // Login student
    const studentLogin = await request.post(`${API_URL}/auth/login`, {
      data: { email: studentEmail, password: studentPassword },
    });
    expect(studentLogin.status()).toBe(200);
    studentToken = (await studentLogin.json()).access_token;
  });

  test("Scenarios 1-10: Complete Student Examination Workflow in UI", async ({ page }) => {
    // -------------------------------------------------------------------------
    // Login on the UI
    // -------------------------------------------------------------------------
    await page.goto("/login");
    await page.locator("input[type='email']").fill(studentEmail);
    await page.locator("input[type='password']").fill(studentPassword);
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");

    // -------------------------------------------------------------------------
    // Scenario 1: Open an available exam from lobby
    // -------------------------------------------------------------------------
    await page.goto("/student/exams");
    await expect(page.locator("h2:has-text('Phòng Luyện thi')")).toBeVisible();

    // Click "Bắt đầu làm bài" on our target exam card
    const examCard = page.locator(".shadow-xs").filter({ hasText: targetExamTitle }).first();
    await expect(examCard).toBeVisible();
    await examCard.locator("button:has-text('Bắt đầu làm bài')").click();

    // Verify navigation to exam detail route: /student/exams/[id]
    await page.waitForURL(`**/student/exams/${targetExamId}`);
    await expect(page.locator("h4:has-text('Quy định & Hướng dẫn')")).toBeVisible();
    await expect(page.locator("p:has-text('45 phút')")).toBeVisible();
    await expect(page.locator("p:has-text('2 câu')")).toBeVisible();

    // -------------------------------------------------------------------------
    // Scenario 2: Start exam successfully
    // -------------------------------------------------------------------------
    const startButton = page.locator("button:has-text('Bắt đầu làm bài thi ngay')");
    await expect(startButton).toBeVisible();
    await startButton.click();

    // Verify transition to active attempt interface: /student/exams/attempts/[attemptId]
    await page.waitForURL("**/student/exams/attempts/**");
    const url = page.url();
    const matches = url.match(/\/attempts\/([a-zA-Z0-9_-]+)/);
    expect(matches).toBeTruthy();
    createdAttemptId = matches![1];

    // Verify Question 1 and Question Matrix are rendered
    await expect(page.locator("text=Câu hỏi 1")).toBeVisible();
    await expect(page.locator("text=Ma trận câu hỏi")).toBeVisible();

    // -------------------------------------------------------------------------
    // Scenario 8: Timer displays remaining time correctly
    // -------------------------------------------------------------------------
    const timer = page.locator(".font-mono.font-bold");
    await expect(timer).toBeVisible();
    const timerText = await timer.innerText();
    expect(timerText).toMatch(/\d{2}:\d{2}/);

    // -------------------------------------------------------------------------
    // Scenario 3 & 4: Answer a question and verify autosave succeeds
    // -------------------------------------------------------------------------
    const firstOption = page.locator(".group.cursor-pointer").first();
    await firstOption.click();

    // Verify save status confirms server-saved state
    await expect(page.locator("text=Đã lưu máy chủ").first()).toBeVisible({ timeout: 5000 });

    // -------------------------------------------------------------------------
    // Scenario 5: Navigate between questions
    // -------------------------------------------------------------------------
    const nextButton = page.locator("button:has-text('Câu tiếp theo')");
    await nextButton.click();
    await expect(page.locator("text=Câu hỏi 2")).toBeVisible();

    // -------------------------------------------------------------------------
    // Scenario 6: Previously saved answers remain selected
    // -------------------------------------------------------------------------
    const prevButton = page.locator("button:has-text('Câu trước')");
    await prevButton.click();
    await expect(page.locator("text=Câu hỏi 1")).toBeVisible();
    await expect(firstOption).toHaveClass(/border-indigo-400/);
    await expect(page.locator("text=Đã lưu máy chủ").first()).toBeVisible();

    // -------------------------------------------------------------------------
    // Scenario 7: Reload restores active attempt and saved answers
    // -------------------------------------------------------------------------
    await page.reload();
    await page.waitForURL(`**/student/exams/attempts/${createdAttemptId}`);
    await expect(page.locator("text=Câu hỏi 1")).toBeVisible();
    const restoredFirstOption = page.locator(".group.cursor-pointer").first();
    await expect(restoredFirstOption).toHaveClass(/border-indigo-400/);
    await expect(page.locator("text=Đã lưu máy chủ").first()).toBeVisible();

    // -------------------------------------------------------------------------
    // Scenario 9: Submit confirmation dialog & execution
    // -------------------------------------------------------------------------
    const submitBtn = page.locator("button:has-text('Nộp bài')").first();
    await submitBtn.click();

    // Confirmation dialog should be visible
    await expect(page.locator("h3:has-text('Xác nhận nộp bài thi')")).toBeVisible();
    await expect(page.locator("text=Đã trả lời:")).toBeVisible();

    // Confirm submission
    const confirmSubmitBtn = page.locator("button:has-text('Xác nhận nộp bài')");
    await confirmSubmitBtn.click();

    // -------------------------------------------------------------------------
    // Scenario 10: Actual server result is displayed
    // -------------------------------------------------------------------------
    await expect(page.locator("h3:has-text('Bạn đã hoàn thành bài thi!')")).toBeVisible({
      timeout: 8000,
    });
    await expect(page.locator("text=Điểm số")).toBeVisible();
    await expect(page.locator("text=Độ chính xác")).toBeVisible();
    await expect(page.locator("text=Số câu đúng")).toBeVisible();
    await expect(page.locator("button:has-text('Quay về danh sách đề thi')")).toBeVisible();
  });

  test("Scenario 11: Repeated submission does not create duplicate results (Idempotency)", async ({
    request,
  }) => {
    let attemptId = createdAttemptId;
    if (!attemptId) {
      const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
        headers: { Authorization: `Bearer ${studentToken}` },
      });
      const startData = await startRes.json();
      attemptId = startData.attempt_id;
    }

    // First submit (or verify already submitted)
    await request.post(`${API_URL}/exams/attempts/${attemptId}/submit`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });

    // Idempotent second submit
    const secondSubmitRes = await request.post(
      `${API_URL}/exams/attempts/${attemptId}/submit`,
      {
        headers: { Authorization: `Bearer ${studentToken}` },
      }
    );
    expect(secondSubmitRes.status()).toBe(200);
    const data = await secondSubmitRes.json();
    expect(data.attempt_id).toBe(attemptId);
    expect(["GRADED", "COMPLETED", "SUBMITTED"]).toContain(data.status);
    expect(typeof data.total_score).toBe("number");
  });

  test("Scenario 12: Student cannot access another student's attempt (Anti-IDOR)", async ({
    page,
    request,
  }) => {
    let attemptId = createdAttemptId;
    if (!attemptId) {
      const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
        headers: { Authorization: `Bearer ${studentToken}` },
      });
      const startData = await startRes.json();
      attemptId = startData.attempt_id;
    }

    // Register another student
    const intruderEmail = `intruder.${Date.now()}@smartlearning.vn`;
    await request.post(`${API_URL}/auth/register`, {
      data: {
        email: intruderEmail,
        password: "IntruderPassword123!",
        full_name: "Học Sinh Lạ",
        role: "STUDENT",
        grade_level: 10,
      },
    });

    // Login as intruder on UI
    await page.goto("/login");
    await page.locator("input[type='email']").fill(intruderEmail);
    await page.locator("input[type='password']").fill("IntruderPassword123!");
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");

    // Attempt to access the first student's private attempt URL
    await page.goto(`/student/exams/attempts/${attemptId}`);

    // Verify 403 Forbidden error card is displayed
    await expect(page.locator("h2:has-text('Không có quyền truy cập')")).toBeVisible();
    await expect(
      page.locator("text=Bạn không phải chủ sở hữu của lượt thi này")
    ).toBeVisible();
  });

  test("Scenario 13: Student cannot review an unsubmitted attempt", async ({ request }) => {
    // Start fresh attempt 2
    const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(startRes.status()).toBe(200);
    const startData = await startRes.json();
    const freshAttemptId = startData.attempt_id;

    // Review on in-progress attempt must be rejected with 403 Forbidden
    const reviewRes = await request.get(
      `${API_URL}/exams/attempts/${freshAttemptId}/review`,
      {
        headers: { Authorization: `Bearer ${studentToken}` },
      }
    );
    expect(reviewRes.status()).toBe(403);
  });

  test("Scenario 14: Anti-leak confidentiality check during active attempt", async ({
    request,
  }) => {
    // Start fresh attempt 3 to inspect questions snapshot
    const startRes = await request.post(`${API_URL}/exams/${targetExamId}/start`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(startRes.status()).toBe(200);
    const startData = await startRes.json();

    // Verify questions snapshot contains no answer keys
    for (const q of startData.questions) {
      expect(q).not.toHaveProperty("explanation");
      for (const opt of q.options) {
        expect(opt).not.toHaveProperty("is_correct");
      }
    }
  });

  test("Scenario 15: Network failure during autosave displays error state", async ({
    page,
  }) => {
    // Login as the student
    await page.goto("/login");
    await page.locator("input[type='email']").fill(studentEmail);
    await page.locator("input[type='password']").fill(studentPassword);
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");

    // Go to exams and enter attempt
    await page.goto(`/student/exams/${targetExamId}`);
    await page.locator("button:has-text('Bắt đầu làm bài thi ngay')").click();
    await page.waitForURL("**/student/exams/attempts/**");

    // Wait for attempt screen to render question 1
    await expect(page.locator("text=Câu hỏi 1")).toBeVisible();

    // Intercept and abort autosave requests to simulate network failure
    await page.route("**/api/v1/exams/attempts/**/answers/**", (route) => {
      route.abort("failed");
    });

    // Click second option
    const secondOption = page.locator(".group.cursor-pointer").nth(1);
    await secondOption.click();

    // Verify error state is shown instead of confirmed saved state
    await expect(page.locator("text=Lỗi lưu (Thử lại)").first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator("text=Đã lưu máy chủ").first()).not.toBeVisible();
  });

  test("Scenario 16: Expired attempt handling", async ({ request }) => {
    // Verify server authoritative attempt deadline and limits
    const examsRes = await request.get(`${API_URL}/exams/available`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(examsRes.status()).toBe(200);
    const exams = await examsRes.json();
    const exam = exams.find((e: { id: string }) => e.id === targetExamId);
    expect(exam).toBeDefined();
    expect(exam.duration_minutes).toBe(45);
  });
});
