import { expect, test, type Page, type Route } from "@playwright/test"

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

  const requests: string[] = []
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

  await page.route("**/api/settings/email-digest", async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        contentType: "application/json",
        json: savedSettings,
      })
      return
    }

    expect(route.request().method()).toBe("PUT")
    requests.push("PUT")
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
    requests.push("POST")
    await route.fulfill({
      contentType: "application/json",
      json: { status: "sent" },
    })
  })

  await page.goto("/articles")
  await page.getByRole("button", { name: "文章推送设置" }).click()
  await page.getByLabel("收件邮箱").fill("reader@example.com")
  await page.getByPlaceholder("选择天数...").click()
  await page.getByRole("option", { name: "7 天" }).click()
  await page.getByLabel("发送时间").fill("07:30")
  await page.getByRole("switch", { name: /启用文章推送/ }).click()

  await expect
    .poll(() => requests.filter((method) => method === "PUT").length)
    .toBeGreaterThanOrEqual(1)

  await page.getByRole("button", { name: "发送测试邮件" }).click()

  await expect
    .poll(() => requests.slice(-2))
    .toEqual(["PUT", "POST"])
  await expect(page.getByText("测试邮件已发送")).toBeVisible()
})

test("email digest settings dialog does not overwrite saved settings on open", async ({
  page,
}) => {
  await mockAuthenticatedUser(page)
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: [] })
  })

  const savedSettings = {
    recipient_email: "reader@example.com",
    enabled: true,
    send_interval_days: 7,
    send_time: "07:30",
    timezone: "Asia/Shanghai",
    last_run_date: null,
    last_sent_at: null,
    last_attempted_at: null,
    last_send_status: null,
    last_send_error: null,
    last_sent_article_count: 0,
  }
  let putCount = 0

  await page.route("**/api/settings/email-digest", async (route) => {
    if (route.request().method() === "GET") {
      await new Promise((resolve) => setTimeout(resolve, 600))
      await route.fulfill({
        contentType: "application/json",
        json: savedSettings,
      })
      return
    }

    putCount += 1
    await route.fulfill({
      contentType: "application/json",
      json: {
        ...savedSettings,
        ...route.request().postDataJSON(),
      },
    })
  })

  await page.goto("/articles")
  await page.getByRole("button", { name: "文章推送设置" }).click()

  await expect(page.getByLabel("收件邮箱")).toHaveValue("reader@example.com")
  await page.waitForTimeout(700)
  expect(putCount).toBe(0)
})

test("email digest settings dialog shows translated test failure toast", async ({
  page,
}) => {
  await mockAuthenticatedUser(page)
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: [] })
  })

  let savedSettings = {
    recipient_email: "reader@example.com",
    enabled: true,
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

    savedSettings = {
      ...savedSettings,
      ...route.request().postDataJSON(),
    }
    await route.fulfill({
      contentType: "application/json",
      json: savedSettings,
    })
  })

  await page.route("**/api/settings/email-digest/test", async (route) => {
    await route.fulfill({
      status: 502,
      contentType: "application/json",
      json: { detail: "邮箱认证失败，请检查 SMTP 授权码或密码" },
    })
  })

  await page.goto("/articles")
  await page.getByRole("button", { name: "文章推送设置" }).click()
  await page.getByRole("button", { name: "发送测试邮件" }).click()

  await expect(page.getByText("发送失败")).toBeVisible()
  await expect(page.getByText("邮箱认证失败，请检查 SMTP 授权码或密码")).toBeVisible()
  await expect(page.getByText(/"detail"/)).toHaveCount(0)
})

test("email digest settings dialog moves next send estimate past current time", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const fixedNow = new Date("2026-06-08T01:57:00.000Z").valueOf()
    const RealDate = Date

    class MockDate extends RealDate {
      constructor(...args: ConstructorParameters<typeof Date>) {
        if (args.length === 0) {
          super(fixedNow)
          return
        }
        super(...args)
      }

      static now() {
        return fixedNow
      }
    }

    window.Date = MockDate as DateConstructor
  })
  await mockAuthenticatedUser(page)
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: [] })
  })

  const savedSettings = {
    recipient_email: "reader@example.com",
    enabled: true,
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

    await route.fulfill({
      contentType: "application/json",
      json: {
        ...savedSettings,
        ...route.request().postDataJSON(),
      },
    })
  })

  await page.goto("/articles")
  await page.getByRole("button", { name: "文章推送设置" }).click()

  await expect(page.getByText("下次预计")).toBeVisible()
  await expect(page.getByText("2026-06-09 08:00")).toBeVisible()
  await expect(page.getByText("2026-06-08 08:00")).toHaveCount(0)
})
