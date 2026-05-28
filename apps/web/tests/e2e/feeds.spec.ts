import { expect, test } from "@playwright/test";

test("feed management exposes MVP actions", async ({ page }) => {
  await page.goto("/feeds");
  await expect(page.getByRole("heading", { name: "Feed 管理" })).toBeVisible();
  await expect(page.getByLabel("Feed URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "添加 Feed" })).toBeVisible();
});
