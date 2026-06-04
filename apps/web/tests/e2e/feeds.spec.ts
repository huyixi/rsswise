import { expect, test, type Page } from "@playwright/test";

async function mockAuthenticatedUser(page: Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      json: { id: "00000000-0000-0000-0000-000000000001", email: "user@example.com" },
    });
  });
}

test("feed management exposes MVP actions", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await page.route("**/api/feeds", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/feeds");
  await expect(page.getByRole("heading", { name: "Feed 管理" })).toBeVisible();
  await expect(page.getByLabel("Feed URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "添加 Feed" })).toBeVisible();
  await expect(page.getByText("暂无 Feed")).toBeVisible();
});

test("redirects unauthenticated users to login", async ({ page }) => {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      json: { detail: "not authenticated" },
    });
  });

  await page.goto("/feeds");

  await expect(page).toHaveURL(/\/login$/);
});
