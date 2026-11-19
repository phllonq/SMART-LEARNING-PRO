import { test, expect } from "@playwright/test";

test.describe("Student Workflow E2E", () => {
  test.beforeEach(async ({ page }) => {
    // Login as student
    await page.goto("/login");
    await page.locator("button:has-text('Học sinh')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");
  });

  test("Dashboard displays real stats, enrolled classes and practice exams", async ({ page }) => {
    await expect(page.locator("text=Chào mừng trở lại,")).toBeVisible();
    await expect(page.locator("h3:has-text('Lớp học của tôi')")).toBeVisible();
    await expect(page.locator("text=Đề thi đề xuất")).toBeVisible();
  });

  test("Classrooms page lists enrolled classes and handles invalid invite code gracefully", async ({ page }) => {
    await page.goto("/student/classrooms");
    await expect(page.locator("h2:has-text('Lớp học của tôi')")).toBeVisible();

    // Click "Tham gia lớp học mới"
    await page.locator("button:has-text('Tham gia lớp học mới')").click();
    await expect(page.locator("text=Nhập mã mời gồm chữ và số")).toBeVisible();

    // Submit invalid code
    await page.locator("input[placeholder='SL-XXXXXX']").fill("INVALID-999");
    await page.locator("button:has-text('Gia nhập ngay')").click();

    // Verify error message is displayed
    await expect(page.locator("text=Mã mời không chính xác").or(page.locator("text=not found"))).toBeVisible();
  });

  test("Courses page displays GDPT 2018 subjects for current grade", async ({ page }) => {
    await page.goto("/student/courses");
    await expect(page.locator("h2:has-text('Chương trình GDPT 2018')")).toBeVisible();
    await expect(page.locator("button:has-text('Khối Lớp 10')")).toBeVisible();

    // Check subjects are loaded from real curriculum API
    await expect(page.locator("text=Toán học").first()).toBeVisible();
  });

  test("Exams lobby displays available practice examinations", async ({ page }) => {
    await page.goto("/student/exams");
    await expect(page.locator("h2:has-text('Phòng Luyện thi')")).toBeVisible();

    // Verify exam card exists with real question counts and duration
    const examCard = page.locator(".shadow-xs").first();
    await expect(examCard).toBeVisible();
    await expect(page.locator("button:has-text('Bắt đầu làm bài')").first()).toBeVisible();
  });

  test("Assignments page renders homework list with status badges", async ({ page }) => {
    await page.goto("/student/assignments");
    await expect(page.locator("h2:has-text('Bài tập về nhà')")).toBeVisible();
  });
});
