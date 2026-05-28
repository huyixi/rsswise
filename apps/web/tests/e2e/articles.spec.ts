import { expect, test } from "@playwright/test";

test("article list has required filters", async ({ page }) => {
  await page.goto("/articles");
  await expect(page.getByRole("heading", { name: "文章" })).toBeVisible();
  await expect(page.getByRole("link", { name: "全部" })).toBeVisible();
  await expect(page.getByRole("link", { name: "已读" })).toBeVisible();
  await expect(page.getByRole("link", { name: "未读" })).toBeVisible();
});
