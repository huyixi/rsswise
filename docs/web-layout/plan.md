# Web Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the RSSWise web article surface into a Folo-style three-column reader with left navigation, title-summary article stream, and a reordered reader panel.

**Architecture:** Keep the existing React Router, TanStack Query, and API contracts. Refactor `ArticleWorkbenchPage` into smaller local components for navigation, stream, and reader layout, then reuse existing article display primitives for AI and Markdown. Filtering stays client-side except the existing unread/read status filter.

**Tech Stack:** React 18, Vite, React Router, TanStack Query, Tailwind CSS v4, local coss-style UI components, lucide-react, Playwright.

**Source Spec:** `docs/web-layout/spec.md`

---

## File Map

- Modify: `apps/web/src/App.tsx`  
  Responsibility: remove the desktop article workbench dependence on the top navigation; keep non-article pages wrapped in the existing centered main layout.

- Modify: `apps/web/src/routes/articles/workbench.tsx`  
  Responsibility: implement left navigation, article stream filtering, desktop three-column shell, mobile list behavior, URL state, and keyboard movement within the filtered stream.

- Modify: `apps/web/src/routes/articles/components.tsx`  
  Responsibility: support the new reader header order and ensure AI Block can be reused inside the reader panel.

- Modify: `apps/web/src/routes/articles/detail.tsx`  
  Responsibility: align mobile article detail ordering with the new reader order.

- Modify: `apps/web/tests/e2e/articles.spec.ts`  
  Responsibility: update article fixtures and assertions for Folo-style navigation, simplified stream rows, recommendation filters, and reader ordering.

## Implementation Notes

- Do not modify backend code.
- Do not modify `apps/web/src/lib/api.ts` types unless TypeScript reveals an existing type mismatch.
- Keep `/articles/:id` mobile-only behavior.
- Keep desktop selection in `/articles?id=<id>`.
- The left header `add` icon navigates to `/feeds`.
- The avatar is a placeholder; do not build an account menu.
- Treat `source_title` as the author/source line because there is no author field.

---

### Task 1: Baseline And Test Intent

**Files:**
- Read: `docs/web-layout/spec.md`
- Read: `apps/web/src/routes/articles/workbench.tsx`
- Read: `apps/web/src/routes/articles/detail.tsx`
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Confirm working tree**

Run:

```bash
git status --short
```

Expected: only intentional docs changes or unrelated user changes. Do not revert unrelated changes.

- [ ] **Step 2: Run current web checks**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both pass before layout edits. If either fails, record the exact failure in the implementation notes before proceeding.

- [ ] **Step 3: Expand article fixtures**

In `apps/web/tests/e2e/articles.spec.ts`, keep the existing three articles and ensure their recommendations cover all nav filters:

```ts
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
```

- [ ] **Step 4: Add failing desktop navigation test**

Add this test near the existing article list tests:

```ts
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
```

- [ ] **Step 5: Add failing stream simplification test**

Add:

```ts
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
```

- [ ] **Step 6: Add failing recommendation filter test**

Add:

```ts
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
```

- [ ] **Step 7: Add failing reader order test**

Add:

```ts
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
```

- [ ] **Step 8: Run new tests and verify they fail**

Run:

```bash
pnpm --dir apps/web test:e2e -- tests/e2e/articles.spec.ts
```

Expected: FAIL because the new navigation and reader structure are not implemented yet.

---

### Task 2: Add Layout State Helpers

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`

- [ ] **Step 1: Add view types and navigation model**

Near the top of `workbench.tsx`, after imports, add:

```tsx
type ArticleView = "all" | "today" | "unread"
type RecommendationView = "deep_read" | "skim" | "skip"

const primaryNavItems: Array<{
  label: string
  view: ArticleView
}> = [
  { label: "Today", view: "today" },
  { label: "Unread", view: "unread" },
  { label: "All Articles", view: "all" },
]

const recommendationNavItems: Array<{
  label: string
  recommendation: RecommendationView
}> = [
  { label: "Deep Read", recommendation: "deep_read" },
  { label: "Skim", recommendation: "skim" },
  { label: "Skip", recommendation: "skip" },
]
```

- [ ] **Step 2: Add URL normalization helpers**

Add:

```tsx
function normalizeView(value: string | null): ArticleView {
  return value === "today" || value === "unread" ? value : "all"
}

function normalizeRecommendation(value: string | null): RecommendationView | null {
  if (value === "deep_read" || value === "skim" || value === "skip") return value
  return null
}

function isToday(value: string | null) {
  if (!value) return false
  const date = new Date(value)
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}
```

- [ ] **Step 3: Replace status derivation in `ArticleWorkbenchPage`**

Replace:

```tsx
const status = normalizeStatus(searchParams.get("status"))
```

with:

```tsx
const view = normalizeView(searchParams.get("view"))
const recommendation = normalizeRecommendation(searchParams.get("recommendation"))
const status = view === "unread" ? "unread" : normalizeStatus(searchParams.get("status"))
```

- [ ] **Step 4: Add filtered articles derivation**

After `articlesQuery`, add:

```tsx
const visibleArticles = (articlesQuery.data ?? []).filter((article) => {
  if (recommendation) {
    return article.reading_recommendation === recommendation
  }
  if (view === "today") {
    return isToday(article.published_at)
  }
  return true
})
```

- [ ] **Step 5: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS or only failures from tests added in Task 1 that reference not-yet-existing UI.

---

### Task 3: Build Left Navigation

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Update imports**

Replace the lucide import with:

```tsx
import {
  BookOpenIcon,
  InboxIcon,
  LogOutIcon,
  PlusIcon,
  RssIcon,
  SparklesIcon,
  UserIcon,
} from "lucide-react"
```

Add `Link` to the router import:

```tsx
import { Link, useNavigate, useSearchParams } from "react-router-dom"
```

- [ ] **Step 2: Add navigation button class helper**

Add:

```tsx
function navButtonClassName(active: boolean) {
  return cn(
    "flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-sm transition-colors",
    active
      ? "bg-accent font-medium text-foreground"
      : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
  )
}
```

- [ ] **Step 3: Add `WorkbenchSidebar` component**

Add before `ArticleListPanel`:

```tsx
function WorkbenchSidebar({
  view,
  recommendation,
  userEmail,
  isLoggingOut,
  onLogout,
  onSelectView,
  onSelectRecommendation,
}: {
  view: ArticleView
  recommendation: RecommendationView | null
  userEmail: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
  onSelectView: (view: ArticleView) => void
  onSelectRecommendation: (recommendation: RecommendationView) => void
}) {
  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r bg-background px-3 py-3">
      <div className="flex items-center gap-2">
        <h1 className="min-w-0 flex-1 truncate text-base font-semibold text-foreground">
          RSSWise
        </h1>
        <Link
          to="/feeds"
          aria-label="添加 Feed"
          className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <PlusIcon aria-hidden="true" className="size-4" />
        </Link>
        <div
          aria-label="当前用户"
          title={userEmail}
          className="inline-flex size-8 items-center justify-center rounded-full border bg-card text-muted-foreground"
        >
          <UserIcon aria-hidden="true" className="size-4" />
        </div>
      </div>

      <nav className="mt-5 flex flex-1 flex-col gap-5" aria-label="文章导航">
        <div className="flex flex-col gap-1">
          {primaryNavItems.map((item) => (
            <button
              key={item.view}
              type="button"
              className={navButtonClassName(!recommendation && view === item.view)}
              onClick={() => onSelectView(item.view)}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-1">
          <div className="px-2.5 text-xs font-medium text-muted-foreground">AI</div>
          {recommendationNavItems.map((item) => (
            <button
              key={item.recommendation}
              type="button"
              className={navButtonClassName(recommendation === item.recommendation)}
              onClick={() => onSelectRecommendation(item.recommendation)}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="mt-auto flex flex-col gap-1">
          <Link
            to="/feeds"
            className="flex items-center gap-2 rounded-md px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/70 hover:text-foreground"
          >
            <RssIcon aria-hidden="true" className="size-4" />
            Feeds
          </Link>
        </div>
      </nav>

      <div className="mt-3 border-t pt-3">
        <div className="truncate px-2.5 text-xs text-muted-foreground">
          {userEmail ?? "当前用户"}
        </div>
        <div className="mt-2 flex items-center gap-1">
          <EmailDigestSettingsDialog />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="退出登录"
            loading={isLoggingOut}
            onClick={onLogout}
          >
            <LogOutIcon aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </div>
    </aside>
  )
}
```

Also add the required imports:

```tsx
import { EmailDigestSettingsDialog } from "@/components/email-digest-settings-dialog"
import { Button } from "@/components/ui/button"
```

- [ ] **Step 4: Add selection handlers**

Inside `ArticleWorkbenchPage`, add:

```tsx
function handleSelectView(nextView: ArticleView) {
  setSearchParams((prev) => {
    const next = new URLSearchParams(prev)
    next.delete("id")
    next.delete("recommendation")
    next.delete("status")
    if (nextView === "unread") {
      next.set("view", "unread")
      next.set("status", "unread")
    } else if (nextView === "today") {
      next.set("view", "today")
    } else {
      next.delete("view")
    }
    return next
  })
}

function handleSelectRecommendation(nextRecommendation: RecommendationView) {
  setSearchParams((prev) => {
    const next = new URLSearchParams(prev)
    next.delete("id")
    next.delete("view")
    next.delete("status")
    next.set("recommendation", nextRecommendation)
    return next
  })
}
```

- [ ] **Step 5: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

---

### Task 4: Simplify Article Stream

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`

- [ ] **Step 1: Replace `ArticleListPanel` props**

Change the props from `status` and `onStatusChange` to `title` only:

```tsx
function ArticleListPanel({
  articles,
  selectedId,
  onSelect,
  title,
  isLoading,
  isError,
  errorMessage,
}: {
  articles: ArticleListItem[] | undefined
  selectedId: string | null
  onSelect: (id: string) => void
  title: string
  isLoading: boolean
  isError: boolean
  errorMessage: string
}) {
```

- [ ] **Step 2: Replace the panel header**

Replace the current header with:

```tsx
<div className="border-b px-4 py-3">
  <h2 className="text-sm font-semibold text-foreground">{title}</h2>
</div>
```

- [ ] **Step 3: Replace article row content**

Inside the article row button, replace the current row body with:

```tsx
<div className="flex items-start gap-2 px-4 py-3">
  {!article.is_read ? (
    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground" />
  ) : (
    <span className="mt-1.5 size-1.5 shrink-0" />
  )}
  <div className="min-w-0 flex-1">
    <p
      className={cn(
        "line-clamp-2 text-sm leading-snug",
        article.is_read ? "font-normal text-muted-foreground" : "font-medium text-foreground",
        isSelected && "text-foreground",
      )}
    >
      {article.title}
    </p>
    {article.one_sentence_summary ? (
      <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
        {article.one_sentence_summary}
      </p>
    ) : null}
  </div>
</div>
```

- [ ] **Step 4: Add stream title helper**

Add:

```tsx
function streamTitle(view: ArticleView, recommendation: RecommendationView | null) {
  if (recommendation) {
    return recommendationNavItems.find((item) => item.recommendation === recommendation)?.label ?? "AI"
  }
  return primaryNavItems.find((item) => item.view === view)?.label ?? "All Articles"
}
```

- [ ] **Step 5: Pass filtered data to `ArticleListPanel`**

Replace all `articles={articlesQuery.data}` in `ArticleWorkbenchPage` with:

```tsx
articles={visibleArticles}
```

Pass:

```tsx
title={streamTitle(view, recommendation)}
```

Remove `status` and `onStatusChange` from `ArticleListPanel` usage.

- [ ] **Step 6: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

---

### Task 5: Rebuild Desktop Reader Layout

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Modify: `apps/web/src/routes/articles/components.tsx`

- [ ] **Step 1: Add compact metadata component**

In `components.tsx`, export a metadata helper:

```tsx
export function ArticleMetadata({ article }: { article: ArticleDetail }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <span className="font-medium text-foreground">{article.source_title}</span>
      <span aria-hidden="true">/</span>
      <span>{formatArticleDate(article.published_at)}</span>
    </div>
  )
}
```

- [ ] **Step 2: Import `ArticleMetadata`**

In `workbench.tsx`, update the article component import:

```tsx
import {
  ArticleAiSummary,
  ArticleBody,
  ArticleMetadata,
} from "./components"
```

Remove the old `ArticleHeader` and `formatArticleDate` imports from `workbench.tsx`.

- [ ] **Step 3: Replace `ArticleContentPanel` article rendering**

Inside `ArticleContentPanel`, replace the article block with:

```tsx
<main className="min-w-0 flex-1 overflow-y-auto bg-card">
  <article className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8 md:px-8">
    <header className="flex flex-col gap-3">
      <h1 className="text-2xl font-semibold leading-tight text-foreground">
        {article.title}
      </h1>
      <ArticleMetadata article={article} />
    </header>
    <ArticleAiSummary article={article} />
    <ArticleBody contentMarkdown={article.content_markdown} className="pt-0" />
  </article>
</main>
```

- [ ] **Step 4: Remove `AISummaryPanel` from desktop render**

Delete the `AISummaryPanel` call from the desktop return. Keep the function temporarily only if it is still referenced elsewhere; otherwise remove it after lint confirms it is unused.

- [ ] **Step 5: Render sidebar in desktop shell**

Replace the desktop return with:

```tsx
return (
  <div className="flex h-screen overflow-hidden">
    <WorkbenchSidebar
      view={view}
      recommendation={recommendation}
      userEmail={appChrome.email}
      isLoggingOut={appChrome.isLoggingOut}
      onLogout={appChrome.onLogout}
      onSelectView={handleSelectView}
      onSelectRecommendation={handleSelectRecommendation}
    />

    <ArticleListPanel
      articles={visibleArticles}
      selectedId={selectedId}
      onSelect={handleSelectArticle}
      title={streamTitle(view, recommendation)}
      isLoading={articlesQuery.isLoading}
      isError={articlesQuery.isError}
      errorMessage={articlesQuery.error?.message ?? "加载文章列表失败"}
    />

    <ArticleContentPanel
      article={articleQuery.data}
      isLoading={articleQuery.isLoading}
      isError={articleQuery.isError}
      errorMessage={articleQuery.error?.message ?? "加载文章失败"}
    />
  </div>
)
```

- [ ] **Step 6: Read app chrome context**

In `workbench.tsx`, import `useOutletContext`:

```tsx
import { Link, useNavigate, useOutletContext, useSearchParams } from "react-router-dom"
```

Add the context type:

```tsx
type AppChromeContext = {
  email: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
}
```

Inside `ArticleWorkbenchPage`, add:

```tsx
const appChrome = useOutletContext<AppChromeContext>()
```

- [ ] **Step 7: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS. Remove unused imports or unused functions reported by ESLint.

---

### Task 6: Integrate Top Bar Into Left Sidebar

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/routes/articles/workbench.tsx`

- [ ] **Step 1: Keep top header off `/articles`**

In `App.tsx`, keep the existing `isWorkbench` branch so `/articles` renders only the workbench:

```tsx
{isWorkbench ? (
  <Outlet
    context={{
      email: meQuery.data?.email,
      isLoggingOut: logoutMutation.isPending,
      onLogout: () => logoutMutation.mutate(),
    }}
  />
) : (
  <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 animate-fade-in md:px-6">
    <Outlet />
  </main>
)}
```

Then wrap the header so it does not render on `/articles`:

```tsx
{!isWorkbench ? (
  <AppHeader
    email={meQuery.data?.email}
    isLoggingOut={logoutMutation.isPending}
    onLogout={() => logoutMutation.mutate()}
  />
) : null}
```

Create `AppHeader` in the same file by moving the current `<header>` JSX into a local component:

```tsx
function AppHeader({
  email,
  isLoggingOut,
  onLogout,
}: {
  email: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
}) {
  const location = useLocation()

  return (
    <header className="border-b bg-background">
      <nav className="flex h-12 items-center gap-6 px-4 md:px-6">
        <Link to="/articles" className="text-sm font-semibold text-foreground">
          RSSWise
        </Link>
        <div className="flex items-center gap-1">
          <Link
            to="/articles"
            aria-current={location.pathname === "/articles" ? "page" : undefined}
            className={navLinkClassName(location.pathname === "/articles")}
          >
            文章
          </Link>
          <Link
            to="/feeds"
            aria-current={location.pathname === "/feeds" ? "page" : undefined}
            className={navLinkClassName(location.pathname === "/feeds")}
          >
            Feed
          </Link>
        </div>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <span className="hidden truncate text-sm text-muted-foreground sm:block">
            {email}
          </span>
          <EmailDigestSettingsDialog />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="退出登录"
            loading={isLoggingOut}
            onClick={onLogout}
          >
            <LogOutIcon aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </nav>
    </header>
  )
}
```

- [ ] **Step 2: Add sidebar global actions**

Confirm `WorkbenchSidebar` renders `EmailDigestSettingsDialog` and the logout icon button from the outlet context. Do not keep a duplicate top header on `/articles`.

- [ ] **Step 3: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

---

### Task 7: Fix Selection And Keyboard Behavior For Filtered Lists

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`

- [ ] **Step 1: Auto-select from `visibleArticles`**

Replace the auto-selection effect body so it uses `visibleArticles`:

```tsx
useEffect(() => {
  if (isMobile) return
  if (visibleArticles.length === 0) return
  if (selectedId && visibleArticles.some((article) => article.id === selectedId)) return

  setSearchParams((prev) => {
    const next = new URLSearchParams(prev)
    next.set("id", visibleArticles[0].id)
    return next
  })
}, [isMobile, visibleArticles, selectedId, setSearchParams])
```

- [ ] **Step 2: Move keyboard navigation within `visibleArticles`**

In the keyboard effect, replace `articlesQuery.data` references with `visibleArticles`:

```tsx
if (visibleArticles.length === 0) return
if (!selectedId) return

const currentIndex = visibleArticles.findIndex((a) => a.id === selectedId)
if (currentIndex === -1) return

let nextIndex = currentIndex
if (event.key === "ArrowDown") {
  nextIndex = Math.min(currentIndex + 1, visibleArticles.length - 1)
} else if (event.key === "ArrowUp") {
  nextIndex = Math.max(currentIndex - 1, 0)
} else {
  return
}

event.preventDefault()

if (nextIndex === currentIndex) return

setSearchParams((prev) => {
  const next = new URLSearchParams(prev)
  next.set("id", visibleArticles[nextIndex].id)
  return next
})
```

- [ ] **Step 3: Update effect dependencies**

Use:

```tsx
}, [isMobile, visibleArticles, selectedId, setSearchParams])
```

- [ ] **Step 4: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

---

### Task 8: Align Mobile Detail Order

**Files:**
- Modify: `apps/web/src/routes/articles/detail.tsx`
- Modify: `apps/web/src/routes/articles/components.tsx`

- [ ] **Step 1: Import metadata helper**

In `detail.tsx`, change the article component import to:

```tsx
import {
  ArticleAiSummary,
  ArticleBody,
  ArticleMetadata,
} from "./components"
```

- [ ] **Step 2: Replace mobile article header order**

In `MobileArticleDetailContent`, replace:

```tsx
<ArticleHeader article={article} titleClassName="text-2xl" />
<ArticleAiSummary article={article} />
<ArticleBody contentMarkdown={article.content_markdown} className="pt-5" />
```

with:

```tsx
<header className="flex flex-col gap-3">
  <h1 className="text-2xl font-semibold leading-tight text-foreground">
    {article.title}
  </h1>
  <ArticleMetadata article={article} />
</header>
<ArticleAiSummary article={article} />
<ArticleBody contentMarkdown={article.content_markdown} className="pt-0" />
```

- [ ] **Step 3: Run lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

---

### Task 9: Final Verification

**Files:**
- Verify: `apps/web/src/App.tsx`
- Verify: `apps/web/src/routes/articles/workbench.tsx`
- Verify: `apps/web/src/routes/articles/detail.tsx`
- Verify: `apps/web/src/routes/articles/components.tsx`
- Verify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Run web lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

- [ ] **Step 2: Run web build**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS.

- [ ] **Step 3: Run focused E2E tests**

Run:

```bash
pnpm --dir apps/web test:e2e -- tests/e2e/articles.spec.ts
```

Expected: PASS.

- [ ] **Step 4: Run full web E2E suite if local services are available**

Run:

```bash
pnpm --dir apps/web test:e2e
```

Expected: PASS. If local services are unavailable, record that only focused mocked tests were run.

- [ ] **Step 5: Manual browser check**

Run:

```bash
pnpm --dir apps/web dev
```

Open `http://127.0.0.1:3000/articles` and verify:

- Left sidebar header shows `RSSWise`, add icon, and avatar placeholder.
- Middle stream only shows title and summary.
- Right reader order is title, source/time, AI Block, body.
- `Deep Read`, `Skim`, and `Skip` filters change the stream without backend changes.
- Mobile viewport still opens `/articles/:id` for article details.

---

## Self-Review

- Spec coverage: The plan covers left navigation, add icon, avatar placeholder, middle stream simplification, right reader ordering, URL state, mobile behavior, and tests.
- Placeholder scan: No implementation step uses TBD/TODO language.
- Type consistency: `ArticleView` and `RecommendationView` are introduced before they are referenced. `ArticleMetadata` is exported before use in workbench and detail routes.
