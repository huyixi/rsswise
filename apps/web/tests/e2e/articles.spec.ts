import { expect, test } from "@playwright/test";

test("article list has required filters", async ({ page }) => {
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/articles");
  await expect(page.getByRole("heading", { name: "文章列表" })).toBeVisible();
  await expect(page.getByRole("button", { name: "全部" })).toBeVisible();
  await expect(page.getByRole("button", { name: "已读" })).toBeVisible();
  await expect(page.getByRole("button", { name: "未读" })).toBeVisible();
  await expect(page.getByText("暂无文章")).toBeVisible();

  await page.getByRole("button", { name: "未读" }).click();
  await expect(page).toHaveURL(/\/articles\?status=unread$/);
});
