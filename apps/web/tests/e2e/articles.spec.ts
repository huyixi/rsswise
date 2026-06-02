import { expect, test } from "@playwright/test";

test("article list has required filters", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/articles?**", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/articles");
  await expect(page.getByRole("heading", { name: "文章" })).toBeVisible();
  await expect(page.getByRole("link", { name: "全部" })).toBeVisible();
  await expect(page.getByRole("link", { name: "已读" })).toBeVisible();
  await expect(page.getByRole("link", { name: "未读" })).toBeVisible();
  await expect(page.getByText("暂无文章")).toBeVisible();

  await page.getByRole("link", { name: "未读" }).click();
  await expect(page).toHaveURL(/\/articles\?status=unread$/);
});
