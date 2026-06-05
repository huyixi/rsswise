# Desktop Article Keyboard Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make desktop `/articles` show the first article by default and support ArrowUp/ArrowDown article switching without wrapping at list boundaries.

**Architecture:** Keep `?id=` as the only selected-article state for the desktop workbench. Add desktop-only effects in `ArticleWorkbenchPage` for default selection and keyboard navigation. Extend Playwright e2e tests with two article fixtures so URL updates, content changes, and boundary behavior are tested through the user-facing route.

**Tech Stack:** React 18, React Router search params, TanStack Query, Playwright, TypeScript, Vite.

**Source Spec:** `docs/superpowers/specs/2026-06-05-desktop-article-keyboard-selection-design.md`

---

## File Map

- Modify: `apps/web/tests/e2e/articles.spec.ts`  
  Responsibility: add two-article desktop fixtures and failing e2e tests for default selection and keyboard navigation.

- Modify: `apps/web/src/routes/articles/workbench.tsx`  
  Responsibility: add URL-backed desktop default selection and desktop-only ArrowUp/ArrowDown navigation.

---

### Task 1: Baseline And Failing E2E Tests

**Files:**
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Confirm the working tree before changing tests**

Run:

```bash
git status --short
```

Expected: only intentional plan/spec files or a clean tree. Do not revert unrelated user changes.

- [ ] **Step 2: Replace the single-article fixture block with two article fixtures**

In `apps/web/tests/e2e/articles.spec.ts`, replace the existing `articleList` and `articleDetail` constants with this complete block:

```ts
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
```

- [ ] **Step 3: Replace `mockArticleRoutes` with a dynamic detail route**

In the same file, replace the existing `mockArticleRoutes` function with:

```ts
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
```

- [ ] **Step 4: Replace `mockReadRoute` with a dynamic read route**

In the same file, replace the existing `mockReadRoute` function with:

```ts
async function mockReadRoute(page: Page, onRead?: (articleId: string) => void) {
  await page.route(/\/api\/articles\/[^/]+\/read$/, async (route) => {
    const parts = new URL(route.request().url()).pathname.split("/")
    const articleId = parts.at(-2) ?? ""
    onRead?.(articleId)
    await route.fulfill({ status: 204, body: "" })
  })
}
```

- [ ] **Step 5: Add failing desktop default-selection test**

Append this test after `desktop article detail route redirects to workbench selection`:

```ts
test("desktop workbench selects the first article by default", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto("/articles")

  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${firstArticleId}$`))
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "正文标题" })).toBeVisible()
})
```

- [ ] **Step 6: Add failing desktop keyboard navigation test**

Append this test after the default-selection test:

```ts
test("desktop workbench arrow keys move selection without wrapping", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto(`/articles?id=${firstArticleId}`)
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()

  await page.keyboard.press("ArrowUp")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${firstArticleId}$`))
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()

  await page.keyboard.press("ArrowDown")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${secondArticleId}$`))
  await expect(page.getByRole("heading", { name: "第二篇桌面键盘测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "第二篇正文" })).toBeVisible()

  await page.keyboard.press("ArrowDown")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${secondArticleId}$`))
  await expect(page.getByRole("heading", { name: "第二篇桌面键盘测试" })).toBeVisible()

  await page.keyboard.press("ArrowUp")
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${firstArticleId}$`))
  await expect(page.getByRole("heading", { name: "移动端文章详情测试" })).toBeVisible()
})
```

- [ ] **Step 7: Run the new tests and verify they fail for the expected missing behavior**

Run:

```bash
pnpm --dir apps/web test:e2e --grep "desktop workbench selects the first article by default|desktop workbench arrow keys move selection without wrapping"
```

Expected: FAIL. The default-selection test should fail because `/articles` does not become `/articles?id=<firstArticleId>`, and the keyboard test should fail because ArrowDown does not change the selected article yet.

- [ ] **Step 8: Commit the failing tests**

Run:

```bash
git add apps/web/tests/e2e/articles.spec.ts
git commit -m "test(articles): 覆盖桌面文章键盘选择"
```

Expected: commit contains only the e2e fixture and test changes.

---

### Task 2: Desktop Default Article Selection

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Test: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Import `useCallback`**

In `apps/web/src/routes/articles/workbench.tsx`, replace the React import with:

```ts
import { useCallback, useEffect, useRef } from "react"
```

- [ ] **Step 2: Add a URL-backed selection helper**

Inside `ArticleWorkbenchPage`, after `const markedReadIdRef = useRef<string | null>(null)`, add:

```ts
  const selectArticleInSearchParams = useCallback(
    (id: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set("id", id)
        return next
      })
    },
    [setSearchParams],
  )
```

- [ ] **Step 3: Add the desktop-only default selection effect**

After the `markReadMutation` definition and before the existing mark-read `useEffect`, add:

```ts
  useEffect(() => {
    if (isMobile || selectedId || !articlesQuery.data?.length) return
    selectArticleInSearchParams(articlesQuery.data[0].id)
  }, [articlesQuery.data, isMobile, selectedId, selectArticleInSearchParams])
```

- [ ] **Step 4: Reuse the helper in click selection**

Replace the desktop branch in `handleSelectArticle`:

```ts
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("id", id)
      return next
    })
```

with:

```ts
    selectArticleInSearchParams(id)
```

- [ ] **Step 5: Run the default-selection test and verify it passes**

Run:

```bash
pnpm --dir apps/web test:e2e --grep "desktop workbench selects the first article by default"
```

Expected: PASS.

- [ ] **Step 6: Run the keyboard test and keep it failing**

Run:

```bash
pnpm --dir apps/web test:e2e --grep "desktop workbench arrow keys move selection without wrapping"
```

Expected: FAIL because keyboard handling has not been implemented yet.

- [ ] **Step 7: Commit the default-selection implementation**

Run:

```bash
git add apps/web/src/routes/articles/workbench.tsx
git commit -m "feat(articles): 默认选中桌面首篇文章"
```

Expected: commit contains only the default-selection implementation.

---

### Task 3: Desktop Arrow Key Navigation

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Test: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Add a text-entry guard helper**

In `apps/web/src/routes/articles/workbench.tsx`, add this helper after `statusFilterClassName`:

```ts
function isTextEntryTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    target.isContentEditable
  )
}
```

- [ ] **Step 2: Add the desktop-only keyboard navigation effect**

Inside `ArticleWorkbenchPage`, after the default-selection effect, add:

```ts
  useEffect(() => {
    const articles = articlesQuery.data
    if (isMobile || !selectedId || !articles?.length) return

    function handleKeyDown(event: KeyboardEvent) {
      if (
        event.defaultPrevented ||
        isTextEntryTarget(event.target) ||
        (event.key !== "ArrowUp" && event.key !== "ArrowDown")
      ) {
        return
      }

      const currentIndex = articles.findIndex((article) => article.id === selectedId)
      if (currentIndex === -1) return

      const nextIndex =
        event.key === "ArrowDown"
          ? Math.min(currentIndex + 1, articles.length - 1)
          : Math.max(currentIndex - 1, 0)

      event.preventDefault()

      if (nextIndex === currentIndex) return
      selectArticleInSearchParams(articles[nextIndex].id)
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [articlesQuery.data, isMobile, selectedId, selectArticleInSearchParams])
```

- [ ] **Step 3: Run the keyboard navigation test and verify it passes**

Run:

```bash
pnpm --dir apps/web test:e2e --grep "desktop workbench arrow keys move selection without wrapping"
```

Expected: PASS.

- [ ] **Step 4: Run all article e2e tests**

Run:

```bash
pnpm --dir apps/web test:e2e tests/e2e/articles.spec.ts
```

Expected: PASS. Existing mobile behavior and desktop click/redirect behavior remain valid.

- [ ] **Step 5: Commit keyboard navigation**

Run:

```bash
git add apps/web/src/routes/articles/workbench.tsx
git commit -m "feat(articles): 支持桌面键盘切换文章"
```

Expected: commit contains only the keyboard navigation implementation.

---

### Task 4: Final Verification

**Files:**
- Read: `apps/web/src/routes/articles/workbench.tsx`
- Read: `apps/web/tests/e2e/articles.spec.ts`

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

- [ ] **Step 4: Inspect final git state**

Run:

```bash
git status --short
git log --oneline -4
```

Expected: no unstaged implementation changes. Recent commits include the spec, failing tests, default selection, and keyboard navigation.
