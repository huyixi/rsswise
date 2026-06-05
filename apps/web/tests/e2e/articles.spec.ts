import { expect, test, type Page } from "@playwright/test"

const firstArticleId = "11111111-1111-1111-1111-111111111111"
const secondArticleId = "22222222-2222-2222-2222-222222222222"

const articleList = [
  {
    id: firstArticleId,
    title: "移动端文章详情测试",
    source_title: "RSSWise 测试源",
    published_at: "2026-06-04T08:00:00Z",
    one_sentence_summary: "这是一句话 AI 摘要",
    reading_recommendation: "deep_read",
    is_read: false,
  },
  {
    id: secondArticleId,
    title: "第二篇桌面键盘测试",
    source_title: "RSSWise 测试源",
    published_at: "2026-06-05T08:00:00Z",
    one_sentence_summary: "这是第二篇文章的一句话摘要",
    reading_recommendation: "skim",
    is_read: false,
  },
]

const articleDetail = {
  id: firstArticleId,
  title: "移动端文章详情测试",
  source_title: "RSSWise 测试源",
  published_at: "2026-06-04T08:00:00Z",
  url: "https://example.com/mobile-article",
  one_sentence_summary: "这是一句话 AI 摘要",
  reading_recommendation: "deep_read",
  reading_reason: "这篇文章和当前关注主题高度相关。",
  content_markdown: "## 正文标题\n\n这是正文内容。",
  extraction_status: "success",
  analysis_status: "success",
}

const secondArticleDetail = {
  id: secondArticleId,
  title: "第二篇桌面键盘测试",
  source_title: "RSSWise 测试源",
  published_at: "2026-06-05T08:00:00Z",
  url: "https://example.com/desktop-keyboard-article",
  one_sentence_summary: "这是第二篇文章的一句话摘要",
  reading_recommendation: "skim",
  reading_reason: "这篇文章用于验证桌面端键盘切换。",
  content_markdown: "## 第二篇正文\n\n这是第二篇正文内容。",
  extraction_status: "success",
  analysis_status: "success",
}

const articleDetails: Record<
  string,
  typeof articleDetail | typeof secondArticleDetail
> = {
  [firstArticleId]: articleDetail,
  [secondArticleId]: secondArticleDetail,
}

async function mockAuthenticatedUser(page: Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      json: { id: "00000000-0000-0000-0000-000000000001", email: "user@example.com" },
    })
  })
}

async function mockArticleRoutes(page: Page) {
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: articleList })
  })

  await page.route(/\/api\/articles\/[^/]+$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback()
      return
    }

    const articleId = new URL(route.request().url()).pathname.split("/").at(-1)
    const detail = articleId ? articleDetails[articleId] : undefined

    if (!detail) {
      await route.fallback()
      return
    }

    await route.fulfill({ json: detail })
  })
}

async function mockReadRoute(page: Page, onRead?: (articleId: string) => void) {
  await page.route(/\/api\/articles\/[^/]+\/read$/, async (route) => {
    expect(route.request().method()).toBe("POST")
    const parts = new URL(route.request().url()).pathname.split("/")
    const articleId = parts.at(-2) ?? ""
    onRead?.(articleId)
    await route.fulfill({ status: 204, body: "" })
  })
}

test("article list has required filters", async ({ page }) => {
  await mockAuthenticatedUser(page)
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: [] })
  })

  await page.goto("/articles")
  await expect(page.getByRole("heading", { name: "文章列表" })).toBeVisible()
  await expect(page.getByRole("button", { name: "全部" })).toBeVisible()
  await expect(page.getByRole("button", { name: "已读" })).toBeVisible()
  await expect(page.getByRole("button", { name: "未读" })).toBeVisible()
  await expect(page.getByText("暂无文章")).toBeVisible()

  await page.getByRole("button", { name: "未读" }).click()
  await expect(page).toHaveURL(/\/articles\?status=unread$/)
})

test("mobile article list opens standalone detail page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)

  let readRequestCount = 0
  await mockReadRoute(page, () => {
    readRequestCount += 1
  })

  await page.goto("/articles")
  await expect(page.getByRole("heading", { name: "文章列表" })).toBeVisible()
  await expect(page.getByText("选择一篇文章开始阅读")).toHaveCount(0)

  await page.getByRole("button", { name: /移动端文章详情测试/ }).click()
  await expect(page).toHaveURL(
    /\/articles\/11111111-1111-1111-1111-111111111111$/,
  )

  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "AI 总结" })).toBeVisible()
  await expect(page.getByText("这是一句话 AI 摘要")).toBeVisible()
  await expect(page.getByText("这篇文章和当前关注主题高度相关。")).toBeVisible()
  await expect(page.getByText("这是正文内容。")).toBeVisible()
  expect(readRequestCount).toBe(1)
})

test("mobile detail shows AI summary before article body", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles/11111111-1111-1111-1111-111111111111")

  const aiBox = page.getByRole("heading", { name: "AI 总结" })
  const bodyContent = page.getByText("这是正文内容。")
  await expect(aiBox).toBeVisible()
  await expect(bodyContent).toBeVisible()

  const aiBoxTop = await aiBox.evaluate((node) => node.getBoundingClientRect().top)
  const bodyTop = await bodyContent.evaluate((node) =>
    node.getBoundingClientRect().top,
  )
  expect(aiBoxTop).toBeLessThan(bodyTop)
})

test("desktop article detail route redirects to workbench selection", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles/11111111-1111-1111-1111-111111111111")

  await expect(page).toHaveURL(
    /\/articles\?id=11111111-1111-1111-1111-111111111111$/,
  )
})

test("desktop workbench selects the first article by default", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles")

  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${firstArticleId}$`))
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
  await expect(page.getByText("这是正文内容。")).toBeVisible()
})

test("desktop workbench arrow keys move selection without wrapping", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto(`/articles?id=${firstArticleId}`)
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
  await expect(
    page.getByRole("button", { name: /第二篇桌面键盘测试/ }),
  ).toBeVisible()

  await page.keyboard.press("ArrowUp")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${firstArticleId}$`))
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()

  await page.keyboard.press("ArrowDown")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${secondArticleId}$`))
  await expect(page.getByRole("heading", { name: "第二篇桌面键盘测试" })).toBeVisible()
  await expect(page.getByText("这是第二篇正文内容。")).toBeVisible()

  await page.keyboard.press("ArrowDown")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${secondArticleId}$`))
  await expect(page.getByRole("heading", { name: "第二篇桌面键盘测试" })).toBeVisible()

  await page.keyboard.press("ArrowUp")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${firstArticleId}$`))
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
  await expect(page.getByText("这是正文内容。")).toBeVisible()
})

test("desktop workbench list click keeps query-param detail behavior", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles")
  await page.getByRole("button", { name: /移动端文章详情测试/ }).click()

  await expect(page).toHaveURL(
    /\/articles\?id=11111111-1111-1111-1111-111111111111$/,
  )
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
})
