import { expect, test } from "@playwright/test";

test("feed management exposes MVP actions", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/feeds", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/feeds");
  await expect(page.getByRole("heading", { name: "Feed 管理" })).toBeVisible();
  await expect(page.getByLabel("Feed URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "添加 Feed" })).toBeVisible();
  await expect(page.getByText("暂无 Feed")).toBeVisible();
});
