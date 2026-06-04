import { expect, test, type Page } from "@playwright/test"

async function mockAuthenticatedUser(page: Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      json: { id: "00000000-0000-0000-0000-000000000001", email: "user@example.com" },
    })
  })
}

test("email digest settings dialog saves settings and sends test email", async ({
  page,
}) => {
  await mockAuthenticatedUser(page)
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: [] })
  })

  let savedSettings = {
    recipient_email: null as string | null,
    enabled: false,
    send_interval_days: 1,
    send_time: "08:00",
    timezone: "Asia/Shanghai",
    last_run_date: null,
    last_sent_at: null,
    last_attempted_at: null,
    last_send_status: null,
    last_send_error: null,
    last_sent_article_count: 0,
  }

  await page.route("**/api/settings/email-digest", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        contentType: "application/json",
        json: savedSettings,
      })
      return
    }

    expect(route.request().method()).toBe("PUT")
    expect(route.request().postDataJSON()).toEqual({
      recipient_email: "reader@example.com",
      enabled: true,
      send_interval_days: 7,
      send_time: "07:30",
    })
    savedSettings = {
      ...savedSettings,
      recipient_email: "reader@example.com",
      enabled: true,
      send_interval_days: 7,
      send_time: "07:30",
    }
    await route.fulfill({
      contentType: "application/json",
      json: savedSettings,
    })
  })

  await page.route("**/api/settings/email-digest/test", async (route) => {
    expect(route.request().method()).toBe("POST")
    await route.fulfill({
      contentType: "application/json",
      json: { status: "sent" },
    })
  })

  await page.goto("/articles")
  await page.getByRole("button", { name: "邮件摘要设置" }).click()
  await page.getByLabel("收件邮箱").fill("reader@example.com")
  await page.getByLabel("发送间隔天数").fill("7")
  await page.getByLabel("发送时间").fill("07:30")
  await page.getByRole("switch", { name: /启用邮件摘要/ }).click()
  await page.getByRole("button", { name: "保存" }).click()
  await page.getByRole("button", { name: "发送测试邮件" }).click()
})
