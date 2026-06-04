# Mobile Article Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mobile article detail flow where tapping an article on mobile opens `/articles/:id`, shows AI summary before article content, and keeps desktop on the existing `/articles?id=:id` workbench.

**Architecture:** Keep `/articles` as the desktop workbench route and use `/articles/:id` only as the mobile detail route. Split article header, AI summary, and markdown body into shared display components so the workbench and mobile page do not duplicate rendering logic. `MobileArticleDetailPage` must check `useIsMobile()` at the top level and redirect desktop users before mounting any detail-query component.

**Tech Stack:** React 18, Vite, React Router, TanStack Query, Tailwind CSS v4, coss-style local UI components, lucide-react, Playwright.

**Source Spec:** `docs/mobile-article-detail/design.md`

---

## File Map

- Create: `apps/web/src/routes/articles/components.tsx`  
  Responsibility: shared article display helpers for date formatting, article header, mobile-safe AI summary, and markdown body.

- Modify: `apps/web/src/routes/articles/workbench.tsx`  
  Responsibility: keep desktop workbench behavior, make mobile `/articles` list-only, and navigate mobile list clicks to `/articles/:id`.

- Modify: `apps/web/src/routes/articles/detail.tsx`  
  Responsibility: turn the unused standalone detail route into a mobile-only detail page with desktop redirect.

- Modify: `apps/web/src/router.tsx`  
  Responsibility: route `/articles/:id` to `ArticleDetailPage` instead of redirecting all users to `/articles`.

- Modify: `apps/web/tests/e2e/articles.spec.ts`  
  Responsibility: cover mobile list-to-detail behavior, desktop detail redirect, AI-before-body ordering, and auto-mark-read.

---

## Implementation Notes

- Use `useIsMobile()` from `apps/web/src/hooks/use-media-query.ts`. Its mobile breakpoint is `max-md`.
- Keep existing API calls: `GET /articles`, `GET /articles/{id}`, `POST /articles/{id}/read`.
- Keep existing query keys from `apps/web/src/lib/query-keys.ts`.
- Do not add mobile actions for “重新 AI 分析” or “标记未读”.
- Do not change backend code.
- Do not remove the existing desktop workbench query-param behavior.
- Desktop `/articles/:id` must redirect before article detail query hooks mount.

---

### Task 1: Baseline Checks

**Files:**
- Read: `docs/mobile-article-detail/design.md`
- Read: `apps/web/src/routes/articles/workbench.tsx`
- Read: `apps/web/src/routes/articles/detail.tsx`
- Read: `apps/web/src/router.tsx`
- Read: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Confirm working tree**

Run:

```bash
git status --short
```

Expected: only intentional docs changes from this planning work, or other unrelated user changes that must not be reverted.

- [ ] **Step 2: Run baseline lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS. If it fails before edits, record the failure and continue only after deciding whether it blocks this feature.

- [ ] **Step 3: Run baseline build**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS. If it fails before edits, record the failure and continue only after deciding whether it blocks this feature.

---

### Task 2: Add Shared Article Display Components

**Files:**
- Create: `apps/web/src/routes/articles/components.tsx`
- Uses: `apps/web/src/components/markdown-content.tsx`
- Uses: `apps/web/src/components/recommendation-badge.tsx`
- Uses: `apps/web/src/lib/api.ts`
- Uses: `apps/web/src/lib/utils.ts`

- [ ] **Step 1: Create shared components file**

Create `apps/web/src/routes/articles/components.tsx`:

```tsx
import { ExternalLinkIcon, SparklesIcon } from "lucide-react"

import { MarkdownContent } from "@/components/markdown-content"
import { RecommendationBadge } from "@/components/recommendation-badge"
import type { ArticleDetail } from "@/lib/api"
import { cn } from "@/lib/utils"

export function formatArticleDate(value: string | null) {
  if (!value) return "未发布"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

export function ArticleHeader({
  article,
  className,
  titleClassName,
}: {
  article: ArticleDetail
  className?: string
  titleClassName?: string
}) {
  return (
    <header className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{article.source_title}</span>
        <span aria-hidden="true">/</span>
        <span>{formatArticleDate(article.published_at)}</span>
      </div>

      <h1
        className={cn(
          "text-2xl font-semibold leading-tight text-foreground",
          titleClassName,
        )}
      >
        {article.title}
      </h1>

      <a
        href={article.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-1 text-sm font-medium text-foreground underline-offset-4 hover:underline"
      >
        阅读原文
        <ExternalLinkIcon aria-hidden="true" className="size-3.5" />
      </a>
    </header>
  )
}

export function ArticleAiSummary({
  article,
  className,
}: {
  article: ArticleDetail
  className?: string
}) {
  const hasAiContent =
    article.reading_recommendation ||
    article.one_sentence_summary ||
    article.reading_reason

  return (
    <section
      aria-labelledby="article-ai-summary-heading"
      className={cn("flex flex-col gap-3 rounded-lg border bg-card p-4", className)}
    >
      <div className="flex items-center gap-2">
        <SparklesIcon aria-hidden="true" className="size-4 text-muted-foreground" />
        <h2 id="article-ai-summary-heading" className="text-sm font-semibold">
          AI 总结
        </h2>
        {article.reading_recommendation ? (
          <div className="ml-auto">
            <RecommendationBadge value={article.reading_recommendation} />
          </div>
        ) : null}
      </div>

      {hasAiContent ? (
        <div className="flex flex-col gap-3">
          {article.one_sentence_summary ? (
            <p className="text-sm leading-6 text-foreground">
              {article.one_sentence_summary}
            </p>
          ) : null}

          {article.reading_reason ? (
            <p className="text-sm leading-6 text-muted-foreground">
              {article.reading_reason}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">AI 总结处理中</p>
      )}
    </section>
  )
}

export function ArticleBody({
  contentMarkdown,
  className,
}: {
  contentMarkdown: string | null
  className?: string
}) {
  return (
    <div className={cn("border-t pt-6", className)}>
      <MarkdownContent markdown={contentMarkdown ?? "正文处理中……"} />
    </div>
  )
}
```

- [ ] **Step 2: Run lint on the new file**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS, or failures unrelated to `apps/web/src/routes/articles/components.tsx`.

---

### Task 3: Make `/articles` List-Only On Mobile

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Uses: `apps/web/src/hooks/use-media-query.ts`
- Uses: `apps/web/src/routes/articles/components.tsx`

- [ ] **Step 1: Update imports**

In `apps/web/src/routes/articles/workbench.tsx`, replace the current route and icon imports:

```tsx
import { useSearchParams } from "react-router-dom"
import {
  SparklesIcon,
  ExternalLinkIcon,
  BookOpenIcon,
  InboxIcon,
} from "lucide-react"

import { MarkdownContent } from "@/components/markdown-content"
```

with:

```tsx
import { useNavigate, useSearchParams } from "react-router-dom"
import { SparklesIcon, BookOpenIcon, InboxIcon } from "lucide-react"
```

Then add these imports below the existing local imports:

```tsx
import {
  ArticleAiSummary,
  ArticleBody,
  ArticleHeader,
  formatArticleDate,
} from "./components"
import { useIsMobile } from "@/hooks/use-media-query"
```

- [ ] **Step 2: Remove local date formatter**

Delete the local `formatDate()` function from `workbench.tsx`.

Replace every usage of:

```tsx
formatDate(article.published_at)
```

with:

```tsx
formatArticleDate(article.published_at)
```

- [ ] **Step 3: Replace article content rendering with shared components**

Inside `ArticleContentPanel`, replace the loaded article return block with:

```tsx
return (
  <main className="min-w-0 flex-1 overflow-y-auto bg-card">
    <article className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8 md:px-8">
      <ArticleHeader article={article} />
      <ArticleBody contentMarkdown={article.content_markdown} />
    </article>
  </main>
)
```

- [ ] **Step 4: Replace AI side panel summary body with shared component**

Inside `AISummaryPanel`, replace the `article?.reading_recommendation ? (...) : null` branch with:

```tsx
) : article ? (
  <ArticleAiSummary article={article} />
) : null}
```

The surrounding panel should still be:

```tsx
<aside className="flex w-[340px] shrink-0 flex-col border-l bg-background max-xl:w-[300px] max-lg:w-full max-lg:border-l-0 max-lg:border-t">
  <div className="flex-1 overflow-y-auto px-5 py-4">
    {/* loading or ArticleAiSummary */}
  </div>
</aside>
```

- [ ] **Step 5: Add mobile navigation in `ArticleWorkbenchPage`**

At the top of `ArticleWorkbenchPage`, after `status` is computed, add:

```tsx
const navigate = useNavigate()
const isMobile = useIsMobile()
```

Replace `handleSelectArticle` with:

```tsx
function handleSelectArticle(id: string) {
  if (isMobile) {
    navigate(`/articles/${id}`)
    return
  }

  setSearchParams((prev) => {
    const next = new URLSearchParams(prev)
    next.set("id", id)
    return next
  })
}
```

- [ ] **Step 6: Return list-only layout on mobile**

Before the current final `return` in `ArticleWorkbenchPage`, add:

```tsx
if (isMobile) {
  return (
    <div className="min-h-[calc(100vh-49px)] bg-background">
      <ArticleListPanel
        articles={articlesQuery.data}
        selectedId={selectedId}
        onSelect={handleSelectArticle}
        status={status}
        onStatusChange={handleStatusChange}
        isLoading={articlesQuery.isLoading}
        isError={articlesQuery.isError}
        errorMessage={articlesQuery.error?.message ?? "加载文章列表失败"}
      />
    </div>
  )
}
```

Expected behavior: mobile `/articles` renders only the list panel. It does not render `ArticleContentPanel` or `AISummaryPanel`.

- [ ] **Step 7: Run lint and build after workbench changes**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both PASS.

---

### Task 4: Implement Mobile-Only Article Detail Page

**Files:**
- Modify: `apps/web/src/routes/articles/detail.tsx`
- Uses: `apps/web/src/routes/articles/components.tsx`
- Uses: `apps/web/src/hooks/use-media-query.ts`

- [ ] **Step 1: Replace `detail.tsx` with mobile-only route component**

Replace the full contents of `apps/web/src/routes/articles/detail.tsx` with:

```tsx
import { useEffect, useRef } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Link, Navigate, useParams } from "react-router-dom"
import { ArrowLeftIcon } from "lucide-react"

import { Spinner } from "@/components/ui/spinner"
import { useIsMobile } from "@/hooks/use-media-query"
import { apiGet, apiPost, type ArticleDetail } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"
import { ArticleAiSummary, ArticleBody, ArticleHeader } from "./components"

function MobileArticleDetailContent({ id }: { id: string }) {
  const markedReadIdRef = useRef<string | null>(null)

  const articleQuery = useQuery({
    queryKey: queryKeys.articles.detail(id),
    queryFn: () => apiGet<ArticleDetail>(`/articles/${id}`),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      if (
        data.extraction_status === "processing" ||
        data.analysis_status === "processing"
      ) {
        return 3000
      }
      return false
    },
  })

  const markReadMutation = useMutation({
    mutationFn: (articleId: string) => apiPost(`/articles/${articleId}/read`),
    onSuccess: (_, articleId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.detail(articleId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.all,
      })
    },
  })

  useEffect(() => {
    if (markedReadIdRef.current === id) return
    markedReadIdRef.current = id
    markReadMutation.mutate(id)
  }, [id, markReadMutation])

  useEffect(() => {
    document.title = articleQuery.data?.title
      ? `${articleQuery.data.title} - RSSWise`
      : "文章详情 - RSSWise"
  }, [articleQuery.data?.title])

  if (articleQuery.isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
        <Spinner />
        <span>加载文章中</span>
      </div>
    )
  }

  if (articleQuery.isError) {
    return (
      <div className="py-8 text-sm text-destructive-foreground">
        {articleQuery.error.message || "加载文章失败"}
      </div>
    )
  }

  const article = articleQuery.data
  if (!article) return null

  return (
    <article className="flex flex-col gap-6 py-5">
      <Link
        to="/articles"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon aria-hidden="true" className="size-4" />
        返回文章列表
      </Link>

      <ArticleHeader article={article} titleClassName="text-2xl" />
      <ArticleAiSummary article={article} />
      <ArticleBody contentMarkdown={article.content_markdown} className="pt-5" />
    </article>
  )
}

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const isMobile = useIsMobile()

  if (!id) {
    return <div className="text-sm text-destructive-foreground">文章 ID 无效</div>
  }

  if (!isMobile) {
    return <Navigate to={`/articles?id=${encodeURIComponent(id)}`} replace />
  }

  return <MobileArticleDetailContent id={id} />
}
```

Important implementation detail: `ArticleDetailPage` must not call `useQuery()` directly. The query hooks live in `MobileArticleDetailContent`, which only mounts after the mobile check passes.

- [ ] **Step 2: Run lint and build after detail page changes**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both PASS.

---

### Task 5: Wire `/articles/:id` Route

**Files:**
- Modify: `apps/web/src/router.tsx`

- [ ] **Step 1: Import the detail page**

In `apps/web/src/router.tsx`, add:

```tsx
import { ArticleDetailPage } from "./routes/articles/detail"
```

- [ ] **Step 2: Replace the old redirect route**

Replace:

```tsx
{ path: "articles/:id", element: <Navigate to="/articles" replace /> },
```

with:

```tsx
{ path: "articles/:id", element: <ArticleDetailPage /> },
```

- [ ] **Step 3: Remove unused `Navigate` import if necessary**

If no route still uses `Navigate`, replace:

```tsx
import { createBrowserRouter, Navigate } from "react-router-dom"
```

with:

```tsx
import { createBrowserRouter } from "react-router-dom"
```

Expected final `router.tsx`:

```tsx
import { createBrowserRouter } from "react-router-dom"
import { App } from "./App"
import { FeedsPage } from "./routes/feeds/list"
import { HomePage } from "./routes/home"
import { ArticleWorkbenchPage } from "./routes/articles/workbench"
import { ArticleDetailPage } from "./routes/articles/detail"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "articles", element: <ArticleWorkbenchPage /> },
      { path: "articles/:id", element: <ArticleDetailPage /> },
      { path: "feeds", element: <FeedsPage /> },
    ],
  },
])
```

- [ ] **Step 4: Run lint and build after route changes**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both PASS.

---

### Task 6: Add Playwright Coverage

**Files:**
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Replace article E2E spec with route fixtures**

Replace `apps/web/tests/e2e/articles.spec.ts` with:

```tsx
import { expect, test, type Page } from "@playwright/test"

const articleList = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    title: "移动端文章详情测试",
    source_title: "RSSWise 测试源",
    published_at: "2026-06-04T08:00:00Z",
    one_sentence_summary: "这是一句话 AI 摘要",
    reading_recommendation: "deep_read",
    is_read: false,
  },
]

const articleDetail = {
  id: "11111111-1111-1111-1111-111111111111",
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

async function mockArticleRoutes(page: Page) {
  await page.route("**/api/articles?**", async (route) => {
    await route.fulfill({ json: articleList })
  })

  await page.route("**/api/articles/11111111-1111-1111-1111-111111111111", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: articleDetail })
      return
    }

    await route.fallback()
  })
}

test("article list has required filters", async ({ page }) => {
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
  await mockArticleRoutes(page)

  let readRequestCount = 0
  await page.route(
    "**/api/articles/11111111-1111-1111-1111-111111111111/read",
    async (route) => {
      readRequestCount += 1
      await route.fulfill({ status: 204, body: "" })
    },
  )

  await page.goto("/articles")
  await expect(page.getByRole("heading", { name: "文章列表" })).toBeVisible()
  await expect(page.getByText("选择一篇文章开始阅读")).toHaveCount(0)

  await page.getByRole("button", { name: /移动端文章详情测试/ }).click()
  await expect(page).toHaveURL(/\/articles\/11111111-1111-1111-1111-111111111111$/)

  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "AI 总结" })).toBeVisible()
  await expect(page.getByText("这是一句话 AI 摘要")).toBeVisible()
  await expect(page.getByText("这篇文章和当前关注主题高度相关。")).toBeVisible()
  await expect(page.getByRole("heading", { name: "正文标题" })).toBeVisible()
  expect(readRequestCount).toBe(1)
})

test("mobile detail shows AI summary before article body", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockArticleRoutes(page)
  await page.route(
    "**/api/articles/11111111-1111-1111-1111-111111111111/read",
    async (route) => {
      await route.fulfill({ status: 204, body: "" })
    },
  )

  await page.goto("/articles/11111111-1111-1111-1111-111111111111")

  const aiBox = page.getByRole("heading", { name: "AI 总结" })
  const bodyHeading = page.getByRole("heading", { name: "正文标题" })
  await expect(aiBox).toBeVisible()
  await expect(bodyHeading).toBeVisible()

  const aiBoxTop = await aiBox.evaluate((node) => node.getBoundingClientRect().top)
  const bodyTop = await bodyHeading.evaluate((node) => node.getBoundingClientRect().top)
  expect(aiBoxTop).toBeLessThan(bodyTop)
})

test("desktop article detail route redirects to workbench selection", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })

  await page.goto("/articles/11111111-1111-1111-1111-111111111111")

  await expect(page).toHaveURL(/\/articles\?id=11111111-1111-1111-1111-111111111111$/)
})

test("desktop workbench list click keeps query-param detail behavior", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockArticleRoutes(page)
  await page.route(
    "**/api/articles/11111111-1111-1111-1111-111111111111/read",
    async (route) => {
      await route.fulfill({ status: 204, body: "" })
    },
  )

  await page.goto("/articles")
  await page.getByRole("button", { name: /移动端文章详情测试/ }).click()

  await expect(page).toHaveURL(/\/articles\?id=11111111-1111-1111-1111-111111111111$/)
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
})
```

- [ ] **Step 2: Run article e2e tests**

Run:

```bash
pnpm --dir apps/web test:e2e -- tests/e2e/articles.spec.ts
```

Expected: all article tests PASS.

---

### Task 7: Final Verification

**Files:**
- Verify: `apps/web/src/routes/articles/components.tsx`
- Verify: `apps/web/src/routes/articles/workbench.tsx`
- Verify: `apps/web/src/routes/articles/detail.tsx`
- Verify: `apps/web/src/router.tsx`
- Verify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

- [ ] **Step 2: Run build**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS.

- [ ] **Step 3: Run full web e2e suite**

Run:

```bash
pnpm --dir apps/web test:e2e
```

Expected: PASS.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git diff -- apps/web/src/routes/articles/components.tsx apps/web/src/routes/articles/workbench.tsx apps/web/src/routes/articles/detail.tsx apps/web/src/router.tsx apps/web/tests/e2e/articles.spec.ts
```

Expected:

- No backend files changed.
- `/articles/:id` routes to `ArticleDetailPage`.
- `ArticleDetailPage` redirects desktop before mounting query hooks.
- Mobile `/articles` returns list-only layout.
- AI summary appears before `ArticleBody` in mobile detail.

- [ ] **Step 5: Commit if requested**

Run only if commits are part of the execution request:

```bash
git add apps/web/src/routes/articles/components.tsx apps/web/src/routes/articles/workbench.tsx apps/web/src/routes/articles/detail.tsx apps/web/src/router.tsx apps/web/tests/e2e/articles.spec.ts docs/mobile-article-detail/design.md docs/mobile-article-detail/plan.md
git commit -m "feat(web): add mobile article detail route"
```

Expected: one focused feature commit.
