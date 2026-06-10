import { expect, test, type Page } from "@playwright/test";

async function mockAuthenticatedUser(page: Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      json: { id: "00000000-0000-0000-0000-000000000001", email: "user@example.com" },
    });
  });
}

async function mockEmptyFeeds(page: Page) {
  await page.route("**/api/feeds", async (route) => {
    await route.fulfill({ json: [] });
  });
}

test("feed management exposes MVP actions", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockEmptyFeeds(page);

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

test("submits multi-line feed import and displays completed results", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockEmptyFeeds(page);

  await page.route("**/api/feeds/imports", async (route) => {
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({
        source_type: "urls",
        urls_text: "https://example.com/feed.xml\nhttps://example.com/feed.xml",
      });
      await route.fulfill({
        status: 201,
        json: {
          id: "99999999-9999-9999-9999-999999999999",
          source_type: "urls",
          status: "pending",
          total_count: 2,
          processed_count: 0,
          created_count: 0,
          subscribed_count: 0,
          skipped_count: 0,
          failed_count: 0,
          error_message: null,
          created_at: "2026-06-10T12:00:00",
          started_at: null,
          finished_at: null,
          items: [],
        },
      });
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/feeds/imports/99999999-9999-9999-9999-999999999999", async (route) => {
    await route.fulfill({
      json: {
        id: "99999999-9999-9999-9999-999999999999",
        source_type: "urls",
        status: "completed",
        total_count: 2,
        processed_count: 2,
        created_count: 1,
        subscribed_count: 0,
        skipped_count: 1,
        failed_count: 0,
        error_message: null,
        created_at: "2026-06-10T12:00:00",
        started_at: "2026-06-10T12:00:01",
        finished_at: "2026-06-10T12:00:03",
        items: [
          {
            id: "item-1",
            source_title: null,
            raw_url: "https://example.com/feed.xml",
            normalized_url: "https://example.com/feed.xml",
            dedupe_key: "https://example.com/feed.xml",
            status: "created",
            feed_id: "feed-1",
            message: "已新建并订阅 Feed",
            created_at: "2026-06-10T12:00:00",
            processed_at: "2026-06-10T12:00:02",
          },
          {
            id: "item-2",
            source_title: null,
            raw_url: "https://example.com/feed.xml",
            normalized_url: "https://example.com/feed.xml",
            dedupe_key: "https://example.com/feed.xml",
            status: "skipped",
            feed_id: null,
            message: "同一批导入中已包含该 Feed",
            created_at: "2026-06-10T12:00:00",
            processed_at: "2026-06-10T12:00:03",
          },
        ],
      },
    });
  });

  await page.goto("/feeds");
  await page.getByRole("button", { name: "批量导入" }).click();
  await page.getByLabel("Feed URL 列表").fill("https://example.com/feed.xml\nhttps://example.com/feed.xml");
  await page.getByRole("button", { name: "开始导入" }).click();

  await expect(page.getByText("已处理 2 / 2")).toBeVisible();
  await expect(page.getByText("新建 1")).toBeVisible();
  await expect(page.getByText("跳过 1")).toBeVisible();
  await expect(page.getByText("同一批导入中已包含该 Feed")).toBeVisible();
});

test("submits OPML file import", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockEmptyFeeds(page);

  await page.route("**/api/feeds/imports", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      source_type: "opml",
      opml_xml: "<opml><body><outline text=\"Example\" xmlUrl=\"https://example.com/feed.xml\" /></body></opml>",
    });
    await route.fulfill({
      status: 201,
      json: {
        id: "88888888-8888-8888-8888-888888888888",
        source_type: "opml",
        status: "completed",
        total_count: 1,
        processed_count: 1,
        created_count: 1,
        subscribed_count: 0,
        skipped_count: 0,
        failed_count: 0,
        error_message: null,
        created_at: "2026-06-10T12:00:00",
        started_at: "2026-06-10T12:00:01",
        finished_at: "2026-06-10T12:00:03",
        items: [],
      },
    });
  });

  await page.goto("/feeds");
  await page.getByRole("button", { name: "批量导入" }).click();
  await page.getByRole("tab", { name: "OPML 文件" }).click();
  await page.getByLabel("OPML 文件").setInputFiles({
    name: "feeds.opml",
    mimeType: "text/xml",
    buffer: Buffer.from("<opml><body><outline text=\"Example\" xmlUrl=\"https://example.com/feed.xml\" /></body></opml>"),
  });
  await page.getByRole("button", { name: "开始导入" }).click();

  await expect(page.getByText("已处理 1 / 1")).toBeVisible();
});
