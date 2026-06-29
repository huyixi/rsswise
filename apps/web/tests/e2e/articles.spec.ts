import { expect, test, type Page } from "@playwright/test"

const firstArticleId = "11111111-1111-1111-1111-111111111111"
const secondArticleId = "22222222-2222-2222-2222-222222222222"
const streamingArticleId = "33333333-3333-3333-3333-333333333333"

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
  {
    id: streamingArticleId,
    title: "流式 AI 摘要测试",
    source_title: "RSSWise 测试源",
    published_at: "2026-06-06T08:00:00Z",
    one_sentence_summary: "这是一篇应该跳过的测试文章",
    reading_recommendation: "skip",
    is_read: true,
  },
]

const articleDetail = {
  id: firstArticleId,
  title: "移动端文章详情测试",
  source_title: "RSSWise 测试源",
  published_at: "2026-06-04T08:00:00Z",
  url: "https://example.com/mobile-article",
  one_sentence_summary: null,
  reading_recommendation: "deep_read",
  reading_reason: null,
  content_markdown: [
    "## 正文标题",
    "",
    "这是正文内容。",
    "",
    "这是一个很长的链接：https://example.com/articles/this-is-a-very-long-url-that-should-wrap-inside-the-reader-without-forcing-horizontal-page-overflow",
    "",
    "```ts",
    "const veryLongIdentifier = \"this-code-block-is-intentionally-long-and-should-scroll-inside-the-code-block-instead-of-widening-the-page\"",
    "```",
    "",
    "| 指标 | 说明 |",
    "| --- | --- |",
    "| 很长的表格内容 | 这个单元格故意包含很长很长的文本以验证表格不会撑爆移动端布局 |",
    "",
    "![测试图片](https://example.com/image.png)",
  ].join("\n"),
  extraction_status: "success",
  analysis_status: "success",
  ai_blocks: [
    {
      type: "summary" as const,
      title: "一句话摘要" as const,
      content: "来自 block 的一句话摘要",
      order: 10,
    },
    {
      type: "reading_question" as const,
      title: "问题" as const,
      content: "这篇文章要回答什么问题？",
      order: 20,
    },
    {
      type: "reading_reason" as const,
      title: "阅读理由" as const,
      content: "来自 block 的阅读理由。",
      order: 30,
    },
    {
      type: "highlights" as const,
      title: "Highlights" as const,
      content: [
        {
          text: "\"Agents are becoming capable of doing more of the work involved in building software, but they’re still mostly individual productivity tools, useful to one person at a time.\"",
          quote_verified: false,
        },
        {
          text: "\"Coding sessions let Linear Agent natively move directly from an issue to implementation.\"",
          quote_verified: false,
        },
        {
          text: "\"Diffs provides a native way to understand code changes and review pull requests in Linear.\"",
          quote_verified: false,
        },
      ],
      order: 40,
    },
    {
      type: "chapters" as const,
      title: "章节" as const,
      content: [
        { title: "Agent 协作模式" },
        { title: "代码审查体验" },
      ],
      order: 50,
    },
  ],
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
  ai_blocks: null,
}

const streamingArticleDetail = {
  id: streamingArticleId,
  title: "流式 AI 摘要测试",
  source_title: "RSSWise 测试源",
  published_at: "2026-06-06T08:00:00Z",
  url: "https://example.com/streaming-ai-article",
  one_sentence_summary: "这是一篇应该跳过的测试文章",
  reading_recommendation: "skip",
  reading_reason: null,
  content_markdown: "## 流式正文\n\n这是流式测试正文。",
  extraction_status: "success",
  analysis_status: "processing",
  ai_blocks: null,
}

const articleDetails: Record<
  string,
  typeof articleDetail | typeof secondArticleDetail | typeof streamingArticleDetail
> = {
  [firstArticleId]: articleDetail,
  [secondArticleId]: secondArticleDetail,
  [streamingArticleId]: streamingArticleDetail,
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

async function mockAnalysisStreamRoute(page: Page) {
  await page.route(
    `**/api/articles/${streamingArticleId}/analysis/events`,
    async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
        },
        body:
          `id: 1-0\n` +
          `event: started\n` +
          `data: {"article_id":"${streamingArticleId}"}\n\n` +
          `id: 2-0\n` +
          `event: chunk\n` +
          `data: {"text":"## 问题\\n这篇文章正在生成什么问题？\\n\\n"}\n\n`,
      })
    },
  )
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
  await expect(page.getByText("这篇文章要回答什么问题？")).toBeVisible()
  await expect(page.getByText("来自 block 的一句话摘要")).toBeVisible()
  await expect(page.getByText("来自 block 的阅读理由。")).toBeVisible()
  await expect(page.getByText("Agent 协作模式")).toBeVisible()
  await expect(page.getByText("这是正文内容。")).toBeVisible()
  await expect(page.getByRole("heading", { name: "问题" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "摘录" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "一句话摘要" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "阅读理由" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "章节" })).toBeVisible()
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
  await expect(
    page.getByText(
      "Agents are becoming capable of doing more of the work involved in building software, but they’re still mostly individual productivity tools, useful to one person at a time.",
    ),
  ).toBeVisible()
  await expect(page.getByText("\"Agents are becoming")).toHaveCount(0)
  await expect(
    page
      .getByRole("heading", { name: "摘录" })
      .locator("xpath=..")
      .locator("ul li"),
  ).toHaveCount(3)
  await expect(
    page
      .getByRole("heading", { name: "章节" })
      .locator("xpath=..")
      .locator("ol li"),
  ).toHaveCount(2)

  const aiBoxTop = await aiBox.evaluate((node) => node.getBoundingClientRect().top)
  const bodyTop = await bodyContent.evaluate((node) =>
    node.getBoundingClientRect().top,
  )
  expect(aiBoxTop).toBeLessThan(bodyTop)
})

test("mobile article body strips duplicate leading heading and avoids viewport overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles/11111111-1111-1111-1111-111111111111")

  await expect(page.getByText("这是正文内容。")).toBeVisible()
  await expect(page.getByRole("heading", { name: "正文标题" })).toHaveCount(0)
  await expect(page.locator("pre")).toBeVisible()
  await expect(page.locator("table")).toBeVisible()
  await expect(page.locator("img[alt='测试图片']")).toBeVisible()

  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  )
  expect(hasPageOverflow).toBe(false)
})

test("mobile detail renders blocks in order", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles/11111111-1111-1111-1111-111111111111")

  const summaryTop = await page.getByText("来自 block 的一句话摘要").evaluate(
    (node) => node.getBoundingClientRect().top,
  )
  const questionTop = await page.getByText("这篇文章要回答什么问题？").evaluate(
    (node) => node.getBoundingClientRect().top,
  )
  const reasonTop = await page.getByText("来自 block 的阅读理由。").evaluate(
    (node) => node.getBoundingClientRect().top,
  )
  const highlightTop = await page
    .getByText("Agents are becoming capable of doing more")
    .evaluate((node) => node.getBoundingClientRect().top)
  const chaptersTop = await page
    .getByText("Agent 协作模式")
    .evaluate((node) => node.getBoundingClientRect().top)
  expect(summaryTop).toBeLessThan(questionTop)
  expect(questionTop).toBeLessThan(reasonTop)
  expect(reasonTop).toBeLessThan(highlightTop)
  expect(highlightTop).toBeLessThan(chaptersTop)
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

test("desktop workbench shows streaming AI summary text", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)
  await mockAnalysisStreamRoute(page)

  await page.goto(`/articles?id=${streamingArticleId}`)

  await expect(page.getByRole("heading", { name: "流式 AI 摘要测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "AI 总结" })).toBeVisible()
  await expect(page.getByText("这篇文章正在生成什么问题？")).toBeVisible()
  await expect(page.getByRole("heading", { name: "问题" })).toBeVisible()
  await expect(page.getByText("重新 AI 分析")).toHaveCount(0)
})

test("mobile detail shows streaming AI summary text", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)
  await mockAnalysisStreamRoute(page)

  await page.goto(`/articles/${streamingArticleId}`)

  await expect(page.getByRole("heading", { name: "流式 AI 摘要测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "AI 总结" })).toBeVisible()
  await expect(page.getByText("这篇文章正在生成什么问题？")).toBeVisible()
  await expect(page.getByRole("heading", { name: "问题" })).toBeVisible()
  await expect(page.getByText("重新 AI 分析")).toHaveCount(0)
})

test("desktop article workbench shows Folo-style navigation", async ({ page }) => {
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles")

  await expect(page.getByRole("heading", { name: "RSSWise" })).toBeVisible()
  await expect(page.getByRole("link", { name: "添加 Feed" })).toHaveAttribute(
    "href",
    "/feeds",
  )
  await expect(page.getByLabel("当前用户")).toBeVisible()
  await expect(page.getByRole("button", { name: "Today" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Unread" })).toBeVisible()
  await expect(page.getByRole("button", { name: "All Articles" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Deep Read" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Skim" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Skip" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Feeds" })).toHaveAttribute(
    "href",
    "/feeds",
  )
})

test("article stream only shows title and summary", async ({ page }) => {
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles")

  const firstRow = page.getByRole("button", { name: /移动端文章详情测试/ })
  await expect(firstRow).toContainText("移动端文章详情测试")
  await expect(firstRow).toContainText("这是一句话 AI 摘要")
  await expect(firstRow).not.toContainText("RSSWise 测试源")
  await expect(firstRow).not.toContainText("2026")
})

test("recommendation navigation filters the article stream", async ({ page }) => {
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles")
  await page.getByRole("button", { name: "Deep Read" }).click()

  await expect(page).toHaveURL(/recommendation=deep_read/)
  await expect(page.getByRole("button", { name: /移动端文章详情测试/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /第二篇桌面键盘测试/ })).toHaveCount(0)
  await expect(page.getByRole("button", { name: /流式 AI 摘要测试/ })).toHaveCount(0)
})

test("desktop reader shows title metadata AI block then body", async ({ page }) => {
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto(`/articles?id=${firstArticleId}`)

  const title = page.getByRole("heading", { name: "移动端文章详情测试" })
  const metadata = page.getByText(/RSSWise 测试源/)
  const aiHeading = page.getByRole("heading", { name: "AI 总结" })
  const body = page.getByText("这是正文内容。")

  await expect(title).toBeVisible()
  await expect(metadata).toBeVisible()
  await expect(aiHeading).toBeVisible()
  await expect(body).toBeVisible()

  const positions = await Promise.all(
    [title, metadata, aiHeading, body].map(async (locator) => {
      const box = await locator.boundingBox()
      expect(box).not.toBeNull()
      return box!.y
    }),
  )

  expect(positions[0]).toBeLessThan(positions[1])
  expect(positions[1]).toBeLessThan(positions[2])
  expect(positions[2]).toBeLessThan(positions[3])
})

test("desktop sidebar feed click filters articles and toggles back", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)

  const feedId = "ffffffff-ffff-ffff-ffff-ffffffffffff"
  const feedName = "Test Feed"
  const feedArticleId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

  const feedArticleDetail = {
    id: feedArticleId,
    title: "Feed 专属文章",
    source_title: feedName,
    published_at: "2026-06-04T08:00:00Z",
    url: "https://example.com/feed-article",
    one_sentence_summary: "这是 Feed 里的文章",
    reading_recommendation: "deep_read",
    reading_reason: null,
    content_markdown: "这是 Feed 专属文章的正文。",
    extraction_status: "success",
    analysis_status: "success",
    ai_blocks: null,
  }

  await page.route("**/api/feeds", async (route) => {
    await route.fulfill({
      json: [
        {
          id: feedId,
          url: "https://example.com/feed.xml",
          title: feedName,
          site_url: null,
          favicon_url: null,
          last_fetched_at: null,
        },
      ],
    })
  })

  await page.route("**/api/articles?**", async (route) => {
    const url = new URL(route.request().url())
    const feedIdParam = url.searchParams.get("feed_id")
    if (feedIdParam === feedId) {
      await route.fulfill({
        json: [
          {
            id: feedArticleId,
            title: "Feed 专属文章",
            source_title: feedName,
            published_at: "2026-06-04T08:00:00Z",
            one_sentence_summary: "这是 Feed 里的文章",
            reading_recommendation: "deep_read",
            is_read: false,
          },
        ],
      })
    } else {
      await route.fulfill({ json: articleList })
    }
  })

  await page.route(/\/api\/articles\/[^/]+$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback()
      return
    }
    const articleId = new URL(route.request().url()).pathname.split("/").at(-1)
    if (articleId === feedArticleId) {
      await route.fulfill({ json: feedArticleDetail })
    } else if (articleId === firstArticleId) {
      await route.fulfill({ json: articleDetail })
    } else if (articleId === secondArticleId) {
      await route.fulfill({ json: secondArticleDetail })
    } else {
      await route.fallback()
    }
  })

  await mockReadRoute(page)

  await page.goto("/articles")

  // Desktop auto-selects first global article
  await expect(page).toHaveURL(/\/articles\?id=11111111/)
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()

  // Click feed in sidebar
  await page.getByRole("button", { name: feedName }).click()

  // URL should contain feed_id
  await expect(page).toHaveURL(/feed_id=ffffffff/)

  // Middle column shows feed article, not global articles
  await expect(page.getByRole("button", { name: "Feed 专属文章" })).toBeVisible()
  await expect(
    page.getByRole("button", { name: /移动端文章详情测试/ }),
  ).toHaveCount(0)

  // Desktop auto-selects the feed article in the reader
  await expect(page.getByRole("heading", { name: "Feed 专属文章" })).toBeVisible()

  // Toggle off — click the same feed again
  await page.getByRole("button", { name: feedName }).click()

  // URL should no longer contain feed_id
  await expect(page).not.toHaveURL(/feed_id/)

  // Middle column shows global articles again
  await expect(
    page.getByRole("button", { name: /移动端文章详情测试/ }),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Feed 专属文章" })).toHaveCount(
    0,
  )
})

test("desktop sidebar feed context menu unsubscribes selected feed", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)

  const feedId = "ffffffff-ffff-ffff-ffff-ffffffffffff"
  const feedName = "Test Feed"
  const feedArticleId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
  let feeds = [
    {
      id: feedId,
      url: "https://example.com/feed.xml",
      title: feedName,
      site_url: null,
      favicon_url: null,
      last_fetched_at: null,
    },
  ]
  let deleteRequestCount = 0

  await page.route("**/api/feeds", async (route) => {
    await route.fulfill({ json: feeds })
  })

  await page.route(`**/api/feeds/${feedId}`, async (route) => {
    expect(route.request().method()).toBe("DELETE")
    deleteRequestCount += 1
    feeds = []
    await route.fulfill({ status: 204, body: "" })
  })

  await page.route("**/api/articles?**", async (route) => {
    const url = new URL(route.request().url())
    if (url.searchParams.get("feed_id") === feedId) {
      await route.fulfill({
        json: [
          {
            id: feedArticleId,
            title: "Feed 专属文章",
            source_title: feedName,
            published_at: "2026-06-04T08:00:00Z",
            one_sentence_summary: "这是 Feed 里的文章",
            reading_recommendation: "deep_read",
            is_read: false,
          },
        ],
      })
      return
    }

    await route.fulfill({ json: articleList })
  })

  await page.route(/\/api\/articles\/[^/]+$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback()
      return
    }

    const articleId = new URL(route.request().url()).pathname.split("/").at(-1)
    if (articleId === feedArticleId) {
      await route.fulfill({
        json: {
          id: feedArticleId,
          title: "Feed 专属文章",
          source_title: feedName,
          published_at: "2026-06-04T08:00:00Z",
          url: "https://example.com/feed-article",
          one_sentence_summary: "这是 Feed 里的文章",
          reading_recommendation: "deep_read",
          reading_reason: null,
          content_markdown: "这是 Feed 专属文章的正文。",
          extraction_status: "success",
          analysis_status: "success",
          ai_blocks: null,
        },
      })
    } else if (articleId === firstArticleId) {
      await route.fulfill({ json: articleDetail })
    } else {
      await route.fallback()
    }
  })

  await mockReadRoute(page)

  await page.goto(`/articles?feed_id=${feedId}`)
  await expect(page).toHaveURL(/feed_id=ffffffff/)
  await expect(page.getByRole("heading", { name: "Feed 专属文章" })).toBeVisible()

  await page.getByRole("button", { name: feedName }).click({ button: "right" })
  await expect(page.getByRole("menuitem", { name: "退订" })).toBeVisible()

  await page.getByRole("menuitem", { name: "退订" }).click()
  await expect(
    page.getByRole("heading", { name: `退订「${feedName}」？` }),
  ).toBeVisible()

  await page.getByRole("button", { name: "退订" }).click()

  await expect(page).not.toHaveURL(/feed_id/)
  await expect(page.getByRole("button", { name: feedName })).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: /移动端文章详情测试/ }),
  ).toBeVisible()
  expect(deleteRequestCount).toBe(1)
})

test("desktop sidebar feed switch preserves view and recommendation filters", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)

  const feedId = "ffffffff-ffff-ffff-ffff-ffffffffffff"
  const feedName = "Test Feed"

  await page.route("**/api/feeds", async (route) => {
    await route.fulfill({
      json: [
        {
          id: feedId,
          url: "https://example.com/feed.xml",
          title: feedName,
          site_url: null,
          favicon_url: null,
          last_fetched_at: null,
        },
      ],
    })
  })

  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: articleList })
  })

  await page.route(/\/api\/articles\/[^/]+$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback()
      return
    }
    const articleId = new URL(route.request().url()).pathname.split("/").at(-1)
    if (articleId === firstArticleId) {
      await route.fulfill({ json: articleDetail })
    } else if (articleId === secondArticleId) {
      await route.fulfill({ json: secondArticleDetail })
    } else {
      await route.fallback()
    }
  })

  await mockReadRoute(page)

  // Apply view and recommendation filters first
  await page.goto("/articles")
  await page.getByRole("button", { name: "Unread" }).click()
  await expect(page).toHaveURL(/\/articles\?view=unread&status=unread/)
  await page.getByRole("button", { name: "Deep Read" }).click()
  await expect(page).toHaveURL(
    /\/articles\?view=unread&status=unread&recommendation=deep_read/,
  )

  // Click feed — view and recommendation should persist
  await page.getByRole("button", { name: feedName }).click()
  await expect(page).toHaveURL(/feed_id=ffffffff/)
  await expect(page).toHaveURL(/view=unread/)
  await expect(page).toHaveURL(/recommendation=deep_read/)

  // Toggle off — view and recommendation should still persist
  await page.getByRole("button", { name: feedName }).click()
  await expect(page).not.toHaveURL(/feed_id/)
  await expect(page).toHaveURL(/view=unread/)
  await expect(page).toHaveURL(/recommendation=deep_read/)
})
