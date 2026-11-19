import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test.describe("Stage B — Teacher Mutations & Ownership E2E", () => {
  const API_URL = "http://127.0.0.1:8000/api/v1";
  let teacherTokenA: string;
  let teacherTokenB: string;
  let teacherEmailB: string;
  let createdClassroomId: string;
  let createdExamId: string;
  let createdAssignmentId: string;

  test.beforeAll(async ({ request }) => {
    // 1. Get Teacher A Token
    const loginA = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: "giaovien.toan@smartlearning.vn",
        password: "TeacherPassword123!",
      },
    });
    expect(loginA.status()).toBe(200);
    teacherTokenA = (await loginA.json()).access_token;

    // 2. Register & Login Teacher B for ownership verification
    const suffix = Date.now().toString(36);
    teacherEmailB = `teacher.b.${suffix}@smartlearning.vn`;
    const regB = await request.post(`${API_URL}/auth/register`, {
      data: {
        email: teacherEmailB,
        password: "TeacherPassword123!",
        full_name: "Giáo Viên B Khác",
        role: "TEACHER",
      },
    });
    expect(regB.status()).toBe(201);

    const loginB = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: teacherEmailB,
        password: "TeacherPassword123!",
      },
    });
    expect(loginB.status()).toBe(200);
    teacherTokenB = (await loginB.json()).access_token;
  });

  test("1-2. Create Classroom in UI and verify list presence", async ({ page }) => {
    await page.goto("/login");
    await page.locator("button:has-text('Giáo viên')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/teacher/dashboard");

    await page.goto("/teacher/classrooms");
    await expect(page.locator("h2:has-text('Quản lý Lớp học')")).toBeVisible();

    // Click "Tạo lớp học mới"
    await page.locator("button:has-text('Tạo lớp học mới')").click();
    await expect(page.locator("h3:has-text('Tạo Lớp học mới')")).toBeVisible();

    const uniqueClassName = `Lớp 11A E2E ${Date.now().toString().slice(-4)}`;
    await page.locator("input[placeholder*='10A1']").fill(uniqueClassName);
    await page.locator("button[type='submit']:has-text('Tạo lớp học')").click();

    // Wait for modal to close
    await expect(page.locator("h3:has-text('Tạo Lớp học mới')")).not.toBeVisible();

    // Verify classroom appears in list
    const classCard = page.locator(`h3:has-text('${uniqueClassName}')`);
    await expect(classCard).toBeVisible();

    // Extract classroom ID from "Vào lớp" button link
    const enterBtn = page.locator(`div:has(h3:has-text('${uniqueClassName}')) button:has-text('Vào lớp')`).first();
    await enterBtn.click();
    await page.waitForURL("**/teacher/classrooms/*");
    const url = page.url();
    createdClassroomId = url.split("/").pop() || "";
    expect(createdClassroomId).toBeTruthy();
  });

  test("3-5. Create Exam, Add Questions (API), and Publish Exam in UI", async ({ page, request }) => {
    await page.goto("/login");
    await page.locator("button:has-text('Giáo viên')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/teacher/dashboard");

    await page.goto("/teacher/exams");
    await expect(page.locator("h2:has-text('Ngân hàng Đề thi')")).toBeVisible();

    // 3. Create Exam in UI
    await page.locator("button:has-text('Tạo đề thi mới')").click();
    await expect(page.locator("h3:has-text('Tạo Đề thi mới')")).toBeVisible();
    const uniqueExamTitle = `Đề Khảo Sát E2E ${Date.now().toString().slice(-4)}`;
    await page.locator("input[placeholder='Ví dụ: Đề kiểm tra 1 tiết — Đại số 10']").fill(uniqueExamTitle);
    await page.locator("button[type='submit']:has-text('Tạo đề thi')").click();

    // Wait for modal to close
    await expect(page.locator("h3:has-text('Tạo Đề thi mới')")).not.toBeVisible();

    // Wait for exam card to appear in DRAFT
    const examTitleLocator = page.locator(`h3:has-text('${uniqueExamTitle}')`);
    await expect(examTitleLocator).toBeVisible();

    // Get exam ID via API for Teacher A
    const listRes = await request.get(`${API_URL}/exams?page_size=50`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
    });
    const examsList = await listRes.json();
    const createdExam = examsList.items.find((e: { title: string }) => e.title === uniqueExamTitle);
    expect(createdExam).toBeDefined();
    createdExamId = createdExam.id;

    // 4. Add Question to Exam via API:
    // Note: The UI matrix question-picker is NOT IMPLEMENTED in the Phase 6 frontend foundation.
    // The backend endpoint POST /exams/{id}/questions is verified here.
    const addQ1 = await request.post(`${API_URL}/exams/${createdExamId}/questions`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
      data: { question_id: "q-toan11-01", points: 5.0, order_index: 1 },
    });
    expect(addQ1.status()).toBe(200);

    const addQ2 = await request.post(`${API_URL}/exams/${createdExamId}/questions`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
      data: { question_id: "q-toan11-02", points: 5.0, order_index: 2 },
    });
    expect(addQ2.status()).toBe(200);

    // 5. Publish Exam in UI (now that it has questions)
    await page.reload();
    const examCard = page.locator(".shadow-xs").filter({ hasText: uniqueExamTitle });
    await examCard.locator("button:has-text('Xuất bản mở phòng luyện')").click();

    // Verify status changed to published
    await expect(examCard.locator("text=✓ Sẵn sàng để giao bài")).toBeVisible();
  });

  test("6-9. Create Assignment from Exam, Publish, and Cancel in UI", async ({ page, request }) => {
    // Navigate to Classroom Detail
    await page.goto("/login");
    await page.locator("button:has-text('Giáo viên')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/teacher/dashboard");

    await page.goto(`/teacher/classrooms/${createdClassroomId}`);
    await expect(page.locator("button:has-text('Bài tập của Lớp')")).toBeVisible();
    await page.locator("button:has-text('Bài tập của Lớp')").click();

    // 6. Create Assignment in UI
    await page.locator("button:has-text('Giao bài tập mới')").click();
    await expect(page.locator("h3:has-text('Giao Bài tập về nhà mới')")).toBeVisible();

    const uniqueAssignTitle = `Bài Tập Tuần E2E ${Date.now().toString().slice(-4)}`;
    await page.locator("input[placeholder='Ví dụ: Bài tập tuần 3 — Phương trình Lượng giác']").fill(uniqueAssignTitle);
    await page.locator("select").selectOption({ value: createdExamId });
    await page.locator("input[type='datetime-local']").fill("2026-12-31T23:59");
    await page.locator("button[type='submit']:has-text('Giao bài ngay')").click();

    // Wait for modal to close
    await expect(page.locator("h3:has-text('Giao Bài tập về nhà mới')")).not.toBeVisible();

    // Verify assignment card appears with "Đang phát hành" badge (modal defaults to PUBLISHED)
    const assignCard = page.locator(".shadow-xs").filter({ hasText: uniqueAssignTitle });
    await expect(assignCard).toBeVisible();
    await expect(assignCard.locator("text=Đang phát hành")).toBeVisible();

    // 7. Cancel Assignment in UI
    page.once("dialog", (dialog) => dialog.accept());
    await assignCard.locator("button:has-text('Hủy bài')").click();
    await expect(assignCard.locator("text=Đã hủy")).toBeVisible();

    // 8. Create a DRAFT assignment via API to verify Publish in UI
    const draftTitle = `Bài Tập Draft ${Date.now().toString().slice(-4)}`;
    await request.post(`${API_URL}/classrooms/${createdClassroomId}/assignments`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
      data: {
        title: draftTitle,
        exam_id: createdExamId,
        due_date: "2026-12-31T23:59:00",
        status: "DRAFT",
      },
    });
    await page.reload();
    await page.locator("button:has-text('Bài tập của Lớp')").click();
    const draftCard = page.locator(".shadow-xs").filter({ hasText: draftTitle });
    await expect(draftCard.locator("text=Bản nháp")).toBeVisible();
    await draftCard.locator("button:has-text('Phát hành')").click();
    await expect(draftCard.locator("text=Đang phát hành")).toBeVisible();

    // 9. Check Submissions / Gradebook:
    // UI displays "Xem sổ điểm" which triggers an alert (detailed gradebook view NOT IMPLEMENTED in UI).
    // Verify backend API GET /assignments/{id}/submissions responds with 200 OK.
    const assignListRes = await request.get(`${API_URL}/classrooms/${createdClassroomId}/assignments`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
    });
    expect(assignListRes.status()).toBe(200);
    const assignItems = await assignListRes.json();
    const targetAssign = assignItems.find((a: { title: string }) => a.title === uniqueAssignTitle);
    expect(targetAssign).toBeDefined();
    createdAssignmentId = targetAssign.id;

    const gradebookRes = await request.get(`${API_URL}/assignments/${createdAssignmentId}/submissions`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
    });
    expect(gradebookRes.status()).toBe(200);
    const gradebook = await gradebookRes.json();
    expect(gradebook).toHaveProperty("items");
    expect(Array.isArray(gradebook.items)).toBe(true);
  });

  test("10. Teacher Ownership Boundary: Teacher B cannot modify Teacher A's resources", async ({ request }) => {
    // 1. Teacher B tries to access Teacher A's classroom details
    const accessRes = await request.get(`${API_URL}/classrooms/${createdClassroomId}`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(accessRes.status()).toBe(403);
    const accessErr = await accessRes.json();
    expect(accessErr.detail).toContain("Bạn không có quyền truy cập thông tin lớp học này");

    // 2. Teacher B tries to regenerate invite code for Teacher A's classroom
    const regenRes = await request.post(`${API_URL}/classrooms/${createdClassroomId}/regenerate-invite-code`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(regenRes.status()).toBe(403);

    // 3. Teacher B tries to modify Teacher A's exam
    const editExamRes = await request.patch(`${API_URL}/exams/${createdExamId}`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
      data: { title: "Hacked Exam Title" },
    });
    expect(editExamRes.status()).toBe(403);

    // 4. Teacher B tries to archive Teacher A's exam
    const archiveExamRes = await request.post(`${API_URL}/exams/${createdExamId}/archive`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(archiveExamRes.status()).toBe(403);
  });
});

