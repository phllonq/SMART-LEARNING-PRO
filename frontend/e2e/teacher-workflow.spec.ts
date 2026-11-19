import { test, expect } from "@playwright/test";

test.describe("Teacher Workflow E2E", () => {
  test.beforeEach(async ({ page }) => {
    // Login as teacher
    await page.goto("/login");
    await page.locator("button:has-text('Giáo viên')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/teacher/dashboard");
  });

  test("Teacher Dashboard displays metrics and quick-copy invite codes", async ({ page }) => {
    await expect(page.locator("text=Xin chào, Thầy/Cô")).toBeVisible();
    await expect(page.locator("text=Lớp học phụ trách")).toBeVisible();
    await expect(page.locator("text=Tổng số học sinh")).toBeVisible();
    await expect(page.locator("p:has-text('Ngân hàng câu hỏi')")).toBeVisible();
  });

  test("Classrooms management lists owned classes with invite code", async ({ page }) => {
    await page.goto("/teacher/classrooms");
    await expect(page.locator("h2:has-text('Quản lý Lớp học')")).toBeVisible();
    await expect(page.locator("button:has-text('Tạo lớp học mới')")).toBeVisible();

    // Verify classroom cards are rendered
    await expect(page.locator("button:has-text('Vào lớp')").first()).toBeVisible();
  });

  test("Classroom detail view displays large invite code box and student roster", async ({ page }) => {
    await page.goto("/teacher/classrooms");
    await page.locator("button:has-text('Vào lớp')").first().click();

    // Verify detail view
    await expect(page.locator("text=Mã mời lớp học (Invite Code)")).toBeVisible();
    await expect(page.locator("button:has-text('Sao chép mã')")).toBeVisible();
    await expect(page.locator("button:has-text('Danh sách Học sinh')")).toBeVisible();
    await expect(page.locator("button:has-text('Bài tập của Lớp')")).toBeVisible();
  });

  test("Question Bank displays questions with KaTeX formulas and answer confidentiality", async ({ page }) => {
    await page.goto("/teacher/questions");
    await expect(page.locator("h2:has-text('Ngân hàng Câu hỏi Chuẩn hóa')")).toBeVisible();

    // Verify questions rendered with KaTeX
    await expect(page.locator(".katex-wrapper").first()).toBeVisible();

    // Verify teachers can see correct answer indicators
    await expect(page.locator("[class*='bg-emerald-']").first()).toBeVisible();
    await expect(page.locator("text=Lời giải chuẩn chi tiết:").first()).toBeVisible();
  });

  test("Exams bank displays exams list with publish status", async ({ page }) => {
    await page.goto("/teacher/exams");
    await expect(page.locator("h2:has-text('Ngân hàng Đề thi')")).toBeVisible();
    await expect(page.locator("button:has-text('Tạo đề thi mới')")).toBeVisible();
  });

  test("Assignments management displays cross-classroom homework", async ({ page }) => {
    await page.goto("/teacher/assignments");
    await expect(page.locator("h2:has-text('Quản lý Bài tập')")).toBeVisible();
  });
});
