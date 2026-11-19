import { test, expect } from "@playwright/test";

test.describe("Authentication & RBAC Flows", () => {
  test("Landing page loads successfully with role entry points", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=SMART LEARNING PRO").first()).toBeVisible();
    await expect(page.locator("text=Vào cổng Học sinh")).toBeVisible();
    await expect(page.locator("text=Cổng Giáo viên & Giảng dạy")).toBeVisible();
  });

  test("Student login via quick-fill redirects to Student Dashboard", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("text=Đăng nhập vào tài khoản")).toBeVisible();

    // Click Student quick-fill pill
    await page.locator("button:has-text('Học sinh')").click();
    await expect(page.locator("input[type='email']")).toHaveValue("hocsinh.an@smartlearning.vn");

    // Click Login
    await page.locator("button[type='submit']").click();

    // Verify redirected to /student/dashboard
    await page.waitForURL("**/student/dashboard");
    await expect(page.locator("text=Chào mừng trở lại,")).toBeVisible();
    await expect(page.locator("text=Chuỗi học liên tục")).toBeVisible();
  });

  test("Teacher login via quick-fill redirects to Teacher Dashboard", async ({ page }) => {
    await page.goto("/login");

    // Click Teacher quick-fill pill
    await page.locator("button:has-text('Giáo viên')").click();
    await expect(page.locator("input[type='email']")).toHaveValue("giaovien.toan@smartlearning.vn");

    // Click Login
    await page.locator("button[type='submit']").click();

    // Verify redirected to /teacher/dashboard
    await page.waitForURL("**/teacher/dashboard");
    await expect(page.locator("text=Xin chào, Thầy/Cô")).toBeVisible();
    await expect(page.locator("text=Lớp học phụ trách")).toBeVisible();
  });

  test("Admin login via quick-fill redirects to Admin Dashboard", async ({ page }) => {
    await page.goto("/login");

    // Click Admin quick-fill pill
    await page.locator("button:has-text('Quản trị')").click();
    await expect(page.locator("input[type='email']")).toHaveValue("admin@smartlearning.vn");

    // Click Login
    await page.locator("button[type='submit']").click();

    // Verify redirected to /admin/dashboard
    await page.waitForURL("**/admin/dashboard");
    await expect(page.locator("text=Trung Tâm Điều Hành Toàn Hệ Thống")).toBeVisible();
  });

  test("Unauthenticated user accessing protected route is redirected to /login", async ({ page }) => {
    await page.goto("/student/dashboard");
    await page.waitForURL("**/login");
    await expect(page.locator("text=Đăng nhập vào tài khoản")).toBeVisible();
  });

  test("Student role guard blocks access to Teacher portal", async ({ page }) => {
    // Login as student
    await page.goto("/login");
    await page.locator("button:has-text('Học sinh')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");

    // Attempt direct navigation to teacher dashboard
    await page.goto("/teacher/dashboard");

    // Role guard redirects student away from teacher portal
    await page.waitForURL("**/student/dashboard");
    await expect(page.locator("text=Cổng Học Sinh").first()).toBeVisible();
  });

  test("Logout clears session and redirects to /login", async ({ page }) => {
    // Login as student
    await page.goto("/login");
    await page.locator("button:has-text('Học sinh')").click();
    await page.locator("button[type='submit']").click();
    await page.waitForURL("**/student/dashboard");

    // Click Logout
    await page.locator("button:has-text('Đăng xuất')").first().click();

    // Verify redirected to /login
    await page.waitForURL("**/login");
    await expect(page.locator("text=Đăng nhập vào tài khoản")).toBeVisible();

    // Verify cannot go back to dashboard
    await page.goto("/student/dashboard");
    await page.waitForURL("**/login");
  });
});
