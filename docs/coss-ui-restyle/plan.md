# coss UI Docs Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the existing RSSWise web app so `/articles` and `/feeds` closely match the shallow, neutral, compact visual style of `https://coss.com/ui/docs` while preserving all current behavior.

**Architecture:** This is a presentation-layer change only. Keep React Router routes, TanStack Query data flow, API helpers, and backend contracts unchanged; update global tokens, the app shell, shared business UI components, and page-level layout classes in focused passes.

**Tech Stack:** React 18, Vite, React Router, TanStack Query, Tailwind CSS v4, local coss-style components, Base UI, lucide-react.

**Source Spec:** `docs/coss-ui-restyle/design.md`

---

## File Map

- Modify: `apps/web/src/globals.css`  
  Responsibility: global semantic tokens, body background, font defaults, coss-style base visual system.

- Modify: `apps/web/src/App.tsx`  
  Responsibility: global top nav, active route styling, full-width vs constrained route layout.

- Modify: `apps/web/src/components/recommendation-badge.tsx`  
  Responsibility: reading recommendation label visual style.

- Modify: `apps/web/src/components/workflow-stepper.tsx`  
  Responsibility: extraction/analysis/ready stepper visual style.

- Modify: `apps/web/src/components/markdown-content.tsx`  
  Responsibility: markdown reading typography, links, inline code, code blocks, images.

- Modify: `apps/web/src/routes/articles/workbench.tsx`  
  Responsibility: `/articles` workbench shell, article list sidebar, reading pane, AI summary sidebar, responsive fallback.

- Modify: `apps/web/src/routes/feeds/list.tsx`  
  Responsibility: `/feeds` settings-style page, add Feed form, Feed list rows, loading/error/empty states.

- Existing tests: `apps/web/tests/e2e/articles.spec.ts`, `apps/web/tests/e2e/feeds.spec.ts`  
  Responsibility: ensure required user-facing controls and empty states remain visible.

---

## Implementation Principles

- Preserve all route paths, query params, mutation handlers, query keys, API paths, labels used by E2E tests, and document titles.
- Prefer coss component props and semantic tokens over raw palette classes.
- Use `flex flex-col gap-*` rather than `space-y-*` in new or heavily edited sections.
- Use lucide icons only through existing imports or minimal import additions; decorative icons must include `aria-hidden="true"`.
- Do not introduce command menu, theme toggle, drawers, sheets, new routes, new API calls, or backend changes.
- Keep mobile basic and robust: no horizontal overflow, no clipped button text, no new hidden interaction model.

---

### Task 1: Baseline Check

**Files:**
- Read: `docs/coss-ui-restyle/design.md`
- Read: `apps/web/src/App.tsx`
- Read: `apps/web/src/routes/articles/workbench.tsx`
- Read: `apps/web/src/routes/feeds/list.tsx`

- [ ] **Step 1: Confirm working tree before implementation**

Run:

```bash
git status --short
```

Expected: note any existing unrelated changes and do not revert them.

- [ ] **Step 2: Run baseline lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS. If it fails before changes, record the exact failures in the implementation notes before editing.

- [ ] **Step 3: Run baseline build**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS. If it fails before changes, record the exact failures in the implementation notes before editing.

- [ ] **Step 4: Commit checkpoint if requested by the user**

Run only when commits are part of the execution request:

```bash
git add docs/coss-ui-restyle/design.md docs/coss-ui-restyle/plan.md
git commit -m "docs: plan coss ui restyle"
```

Expected: documentation-only commit.

---

### Task 2: Restyle Global Tokens And App Shell

**Files:**
- Modify: `apps/web/src/globals.css`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Update global tokens toward coss docs neutral style**

In `apps/web/src/globals.css`, keep Tailwind v4 imports and semantic variable names. Adjust the light token values toward near-white backgrounds, neutral borders, black primary, and muted gray text.

Use this shape:

```css
@theme inline {
  --color-background: #fbfbfb;
  --color-foreground: #171717;
  --color-card: #ffffff;
  --color-card-foreground: #171717;
  --color-muted: #f5f5f5;
  --color-muted-foreground: #737373;
  --color-border: #e5e5e5;
  --color-input: #e5e5e5;
  --color-ring: #a3a3a3;

  --color-primary: #171717;
  --color-primary-foreground: #ffffff;
  --color-secondary: #f5f5f5;
  --color-secondary-foreground: #171717;
  --color-accent: #f5f5f5;
  --color-accent-foreground: #171717;

  --color-destructive: #dc2626;
  --color-destructive-foreground: var(--color-red-700);
  --color-info: var(--color-blue-500);
  --color-info-foreground: var(--color-blue-700);
  --color-success: var(--color-emerald-500);
  --color-success-foreground: var(--color-emerald-700);
  --color-warning: var(--color-amber-500);
  --color-warning-foreground: var(--color-amber-700);

  --radius-xs: 0.25rem;
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.625rem;
  --radius-xl: 0.75rem;

  --shadow-xs: 0 1px 2px 0 rgb(0 0 0 / 0.03);
  --shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.04);

  --font-sans: ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
}
```

- [ ] **Step 2: Keep body coss-compatible**

Ensure `body` keeps neutral background, foreground, and relative positioning for future portal safety:

```css
body {
  position: relative;
  margin: 0;
  background: var(--color-background);
  color: var(--color-foreground);
  font-feature-settings: "cv02", "cv03", "cv04", "cv11";
}
```

- [ ] **Step 3: Restyle `App.tsx` top nav**

Keep the existing route behavior and `isWorkbench` conditional. Replace the current slate-heavy header classes with a thin docs-style header:

```tsx
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
  </nav>
</header>
```

Add this helper in `App.tsx`:

```tsx
function navLinkClassName(active: boolean) {
  return active
    ? "rounded-md bg-accent px-2.5 py-1.5 text-sm font-medium text-foreground"
    : "rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
}
```

- [ ] **Step 4: Keep page layout behavior**

Keep `/articles` full-bleed:

```tsx
{isWorkbench ? (
  <Outlet />
) : (
  <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 animate-fade-in md:px-6">
    <Outlet />
  </main>
)}
```

- [ ] **Step 5: Verify shell**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

- [ ] **Step 6: Commit shell changes if requested**

```bash
git add apps/web/src/globals.css apps/web/src/App.tsx
git commit -m "style: restyle app shell with coss docs tokens"
```

Expected: one focused commit.

---

### Task 3: Restyle Shared Recommendation, Stepper, And Markdown Components

**Files:**
- Modify: `apps/web/src/components/recommendation-badge.tsx`
- Modify: `apps/web/src/components/workflow-stepper.tsx`
- Modify: `apps/web/src/components/markdown-content.tsx`

- [ ] **Step 1: Convert recommendation badge to local coss Badge**

In `apps/web/src/components/recommendation-badge.tsx`, import `Badge` and use coss variants instead of hand-written colored pills:

```tsx
import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { ReadingRecommendation } from "@/lib/api";

const labels: Record<ReadingRecommendation, string> = {
  deep_read: "值得精读",
  skim: "适合略读",
  skip: "可以跳过",
};

const variants: Record<ReadingRecommendation, BadgeProps["variant"]> = {
  deep_read: "success",
  skim: "secondary",
  skip: "warning",
};

export function RecommendationBadge({
  value,
}: {
  value: ReadingRecommendation;
}) {
  return (
    <Badge size="sm" variant={variants[value]}>
      {labels[value]}
    </Badge>
  );
}
```

Expected: labels unchanged, visuals move to coss muted badge variants.

- [ ] **Step 2: Neutralize workflow stepper config**

In `apps/web/src/components/workflow-stepper.tsx`, update `statusConfig` to use semantic tokens and restrained color:

```tsx
const statusConfig = {
  pending: {
    icon: ClockIcon,
    iconClass: "text-muted-foreground/50",
    borderClass: "border-border bg-background",
    labelClass: "text-muted-foreground",
    connectorClass: "bg-border",
  },
  processing: {
    icon: Loader2Icon,
    iconClass: "text-info-foreground",
    borderClass: "border-info/20 bg-info/5",
    labelClass: "text-foreground",
    connectorClass: "bg-info/20",
  },
  success: {
    icon: CheckCircle2Icon,
    iconClass: "text-success-foreground",
    borderClass: "border-success/20 bg-success/5",
    labelClass: "text-foreground",
    connectorClass: "bg-success/20",
  },
  failed: {
    icon: AlertCircleIcon,
    iconClass: "text-destructive-foreground",
    borderClass: "border-destructive/20 bg-destructive/5",
    labelClass: "text-destructive-foreground",
    connectorClass: "bg-destructive/20",
  },
}
```

Also replace body text classes in the component:

```tsx
<p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
  {step.description}
</p>
```

Failure message:

```tsx
<p className="mt-1 text-xs leading-relaxed text-destructive-foreground">
  {step.failureMessage}
</p>
```

- [ ] **Step 3: Restyle markdown typography neutrally**

In `apps/web/src/components/markdown-content.tsx`, replace `prose-slate`, blue links, and dark pre styling with neutral coss docs-like classes:

```tsx
<article className="prose max-w-none prose-neutral prose-headings:scroll-mt-20 prose-headings:font-semibold prose-a:text-foreground prose-a:underline prose-a:underline-offset-4 prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:text-sm prose-pre:border prose-pre:border-border prose-pre:bg-muted prose-pre:text-foreground prose-img:rounded-lg">
```

Expected: markdown remains readable and link behavior remains native.

- [ ] **Step 4: Verify shared component types**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS. If `BadgeProps` is not exported as a named type by TypeScript settings, change the import to:

```tsx
import { Badge } from "@/components/ui/badge";
import type { BadgeProps } from "@/components/ui/badge";
```

- [ ] **Step 5: Commit shared component changes if requested**

```bash
git add apps/web/src/components/recommendation-badge.tsx apps/web/src/components/workflow-stepper.tsx apps/web/src/components/markdown-content.tsx
git commit -m "style: align shared reading components with coss docs"
```

Expected: one focused commit.

---

### Task 4: Restyle `/articles` Workbench

**Files:**
- Modify: `apps/web/src/routes/articles/workbench.tsx`

- [ ] **Step 1: Replace status filter helper with neutral segmented styling**

Replace `statusLinkClassName` with:

```tsx
function statusFilterClassName(active: boolean) {
  return active
    ? "rounded-md bg-foreground px-2.5 py-1.5 text-xs font-medium text-background"
    : "rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
}
```

Update callers from `statusLinkClassName` to `statusFilterClassName`.

- [ ] **Step 2: Restyle `SkeletonCard`**

Use a flatter neutral skeleton:

```tsx
function SkeletonCard() {
  return (
    <div className="animate-pulse border-b px-4 py-3">
      <div className="flex flex-col gap-2">
        <div className="h-3.5 w-4/5 rounded bg-muted" />
        <div className="h-3 w-3/5 rounded bg-muted" />
        <div className="h-3 w-2/5 rounded bg-muted" />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Restyle `ArticleListPanel` container and header**

Use docs sidebar classes:

```tsx
<aside className="flex w-[320px] shrink-0 flex-col border-r bg-background max-lg:w-full max-lg:border-r-0 max-lg:border-b">
  <div className="border-b px-4 py-3">
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-sm font-semibold text-foreground">文章列表</h2>
      <div className="flex rounded-lg border bg-card p-0.5">
        {filters}
      </div>
    </div>
  </div>
</aside>
```

Keep the heading text `文章列表` because `articles.spec.ts` depends on it.

- [ ] **Step 4: Restyle article list items**

For each article button, use neutral selected state:

```tsx
className={cn(
  "w-full border-l-2 text-left transition-colors",
  isSelected
    ? "border-foreground bg-accent"
    : "border-transparent hover:bg-accent/60",
)}
```

Use text classes:

```tsx
article.is_read
  ? "font-normal text-muted-foreground"
  : "font-medium text-foreground"
```

Use selected title class:

```tsx
isSelected && "text-foreground"
```

Use metadata and summary classes:

```tsx
<p className="mt-1 truncate text-xs text-muted-foreground">
<p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
```

For unread dot fallback:

```tsx
<span className="inline-block size-2 rounded-full bg-foreground" />
```

- [ ] **Step 5: Restyle list loading/error/empty states**

Use semantic classes:

```tsx
<div className="flex items-center justify-center p-8">
  <p className="text-sm text-destructive-foreground">{errorMessage}</p>
</div>
```

Empty icon:

```tsx
<InboxIcon aria-hidden="true" className="size-9 text-muted-foreground/40" />
```

Texts:

```tsx
<p className="text-sm text-muted-foreground">暂无文章</p>
<p className="text-xs text-muted-foreground/70">添加 Feed 后文章将自动出现</p>
```

- [ ] **Step 6: Restyle `ArticleContentPanel` empty, loading, and error states**

Use neutral pane background:

```tsx
<div className="flex flex-1 items-center justify-center bg-card max-lg:min-h-[320px]">
```

Use icon frame:

```tsx
<div className="flex size-12 items-center justify-center rounded-lg border bg-background">
  <BookOpenIcon aria-hidden="true" className="size-5 text-muted-foreground" />
</div>
```

Use text classes:

```tsx
<p className="text-sm font-medium text-foreground">选择一篇文章开始阅读</p>
<p className="mt-1 text-sm text-muted-foreground">从左侧列表中选择文章后，正文将显示在这里</p>
```

- [ ] **Step 7: Restyle reading pane**

Use docs content classes:

```tsx
<main className="min-w-0 flex-1 overflow-y-auto bg-card">
  <article className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8 md:px-8">
```

Header metadata:

```tsx
<div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
  <span className="font-medium text-foreground">{article.source_title}</span>
  <span aria-hidden="true">/</span>
  <span>{formatDate(article.published_at)}</span>
</div>
```

Title:

```tsx
<h1 className="text-2xl font-semibold leading-tight text-foreground">
  {article.title}
</h1>
```

Original link:

```tsx
<a
  href={article.url}
  target="_blank"
  rel="noreferrer"
  className="inline-flex w-fit items-center gap-1 text-sm font-medium text-foreground underline-offset-4 hover:underline"
>
  阅读原文
  <ExternalLinkIcon aria-hidden="true" className="size-3.5" />
</a>
```

Markdown divider:

```tsx
<div className="border-t pt-6">
  <MarkdownContent markdown={article.content_markdown ?? "正文处理中……"} />
</div>
```

- [ ] **Step 8: Restyle `AISummaryPanel` shell**

Use a docs right rail:

```tsx
<aside className="flex w-[340px] shrink-0 flex-col border-l bg-background max-xl:w-[300px] max-lg:w-full max-lg:border-l-0 max-lg:border-t">
```

Header:

```tsx
<div className="border-b px-5 py-3">
  <div className="flex items-center gap-2">
    <SparklesIcon aria-hidden="true" className="size-4 text-muted-foreground" />
    <h2 className="text-sm font-semibold text-foreground">AI 分析</h2>
  </div>
</div>
```

Empty icon:

```tsx
<div className="flex size-10 items-center justify-center rounded-lg border bg-card">
  <SparklesIcon aria-hidden="true" className="size-5 text-muted-foreground" />
</div>
```

- [ ] **Step 9: Restyle AI recommendation and status sections**

Replace AI summary card classes with:

```tsx
<div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
```

Section labels:

```tsx
<p className="mb-1 text-xs font-medium text-muted-foreground">摘要</p>
<p className="text-sm leading-relaxed text-foreground">{article.one_sentence_summary}</p>
<p className="mb-1 text-xs font-medium text-muted-foreground">理由</p>
<p className="text-sm leading-relaxed text-muted-foreground">{article.reading_reason}</p>
```

Status card:

```tsx
<div className="flex flex-col gap-2 rounded-lg border bg-card px-4 py-3">
  <p className="text-xs font-medium text-muted-foreground">当前状态</p>
</div>
```

Use status text classes:

```tsx
article.extraction_status === "success" && "text-success-foreground"
article.extraction_status === "processing" && "text-info-foreground"
article.extraction_status === "failed" && "text-destructive-foreground"
(!article.extraction_status || article.extraction_status === "pending") && "text-muted-foreground"
```

Apply the same mapping for `article.analysis_status`.

- [ ] **Step 10: Restyle root responsive layout**

Replace root container:

```tsx
<div className="flex h-[calc(100vh-49px)] overflow-hidden max-lg:h-auto max-lg:min-h-[calc(100vh-49px)] max-lg:flex-col">
```

Expected:

- Desktop keeps article list, reading pane, AI sidebar in one row.
- Narrow screens stack panels vertically.
- No new drawer or menu interaction is introduced.

- [ ] **Step 11: Verify articles page behavior**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both PASS.

Run E2E when test server dependencies are available:

```bash
pnpm --dir apps/web test:e2e -- --grep "article list has required filters"
```

Expected: PASS. The test should still find heading `文章列表`, buttons `全部`, `已读`, `未读`, and text `暂无文章`.

- [ ] **Step 12: Commit article workbench changes if requested**

```bash
git add apps/web/src/routes/articles/workbench.tsx
git commit -m "style: restyle article workbench in coss docs style"
```

Expected: one focused commit.

---

### Task 5: Restyle `/feeds` Management Page

**Files:**
- Modify: `apps/web/src/routes/feeds/list.tsx`

- [ ] **Step 1: Restyle page container and title**

Change outer structure from `space-y-*` to flex/gap:

```tsx
<div className="flex flex-col gap-6">
```

Header:

```tsx
<div className="flex items-center gap-2">
  <RssIcon aria-hidden="true" className="size-4 text-muted-foreground" />
  <h1 className="text-xl font-semibold text-foreground">Feed 管理</h1>
</div>
```

Keep heading text `Feed 管理` because `feeds.spec.ts` depends on it.

- [ ] **Step 2: Restyle add Feed form as docs section**

Use:

```tsx
<form onSubmit={handleAddFeed} className="rounded-lg border bg-card p-4">
  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
```

Label:

```tsx
<label className="mb-1.5 block text-sm font-medium text-foreground" htmlFor="url">
  Feed URL
</label>
```

Input remains:

```tsx
<Input
  id="url"
  name="url"
  type="url"
  required
  nativeInput
  disabled={addFeedMutation.isPending}
  placeholder="https://example.com/feed.xml"
/>
```

Button remains:

```tsx
<Button
  type="submit"
  className="sm:w-auto"
  loading={addFeedMutation.isPending}
  disabled={addFeedMutation.isPending}
>
  添加 Feed
</Button>
```

- [ ] **Step 3: Restyle mutation error**

Use semantic destructive text:

```tsx
<div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive-foreground">
  <span aria-hidden="true" className="size-1.5 rounded-full bg-destructive" />
  {mutationError.message}
</div>
```

- [ ] **Step 4: Restyle feed list container**

Use:

```tsx
<div className="overflow-hidden rounded-lg border bg-card">
```

Keep divide behavior inside rows:

```tsx
<div className="divide-y">
```

If keeping a single wrapper, use:

```tsx
<div className="divide-y overflow-hidden rounded-lg border bg-card">
```

- [ ] **Step 5: Restyle `SkeletonCard`**

Use:

```tsx
function SkeletonCard() {
  return (
    <div className="flex animate-pulse flex-col gap-4 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-col gap-3">
          <div className="h-4 w-2/5 rounded bg-muted" />
          <div className="h-3.5 w-3/5 rounded bg-muted" />
          <div className="h-3.5 w-2/5 rounded bg-muted" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-7 w-14 rounded-md bg-muted" />
        <div className="h-7 w-14 rounded-md bg-muted" />
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Restyle error and empty states**

Error:

```tsx
<div className="flex items-center gap-2 p-6 text-sm text-destructive-foreground">
  <span aria-hidden="true" className="size-1.5 rounded-full bg-destructive" />
  {feedsQuery.error.message || "加载 Feed 失败"}
</div>
```

Empty:

```tsx
<div className="flex flex-col items-center gap-3 py-16 text-center">
  <RssIcon aria-hidden="true" className="size-9 text-muted-foreground/40" />
  <p className="text-sm text-muted-foreground">暂无 Feed</p>
  <p className="text-xs text-muted-foreground/70">在上方输入 RSS 地址开始使用</p>
</div>
```

- [ ] **Step 7: Restyle feed rows**

Use row classes:

```tsx
className="flex flex-col gap-4 p-4 transition-colors hover:bg-accent/50 sm:flex-row sm:items-start sm:justify-between"
```

Title:

```tsx
<h2 className="font-medium text-foreground">
  {feed.title ?? feed.url}
</h2>
```

URL and site URL:

```tsx
<p className="break-all text-sm text-muted-foreground">{feed.url}</p>
<p className="break-all text-sm text-muted-foreground">{feed.site_url}</p>
```

Last fetched:

```tsx
<p className="text-sm text-muted-foreground">
  最后抓取时间：{formatDate(feed.last_fetched_at)}
</p>
```

- [ ] **Step 8: Keep action behavior unchanged**

Leave mutation calls exactly as they are:

```tsx
onClick={() => refreshFeedMutation.mutate(feed.id)}
onClick={() => deleteFeedMutation.mutate(feed.id)}
```

Use buttons:

```tsx
<Button type="button" variant="outline" size="sm" ...>
  刷新
</Button>
<Button type="button" variant="destructive-outline" size="sm" ...>
  删除
</Button>
```

- [ ] **Step 9: Verify feeds page behavior**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both PASS.

Run E2E when test server dependencies are available:

```bash
pnpm --dir apps/web test:e2e -- --grep "feed management exposes MVP actions"
```

Expected: PASS. The test should still find heading `Feed 管理`, label `Feed URL`, button `添加 Feed`, and text `暂无 Feed`.

- [ ] **Step 10: Commit feeds changes if requested**

```bash
git add apps/web/src/routes/feeds/list.tsx
git commit -m "style: restyle feed management in coss docs style"
```

Expected: one focused commit.

---

### Task 6: Responsive And Visual Polish Pass

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Modify: `apps/web/src/routes/feeds/list.tsx`
- Modify: `apps/web/src/components/markdown-content.tsx`

- [ ] **Step 1: Search for remaining dominant raw color classes**

Run:

```bash
rg "slate|blue|emerald|amber|red" apps/web/src/App.tsx apps/web/src/routes apps/web/src/components
```

Expected:

- `blue` should not appear in selected states or primary links.
- `emerald` and `amber` should not appear in recommendation badge hand-written classes.
- `red` should only remain where the existing coss component tokens or destructive semantics require it.

- [ ] **Step 2: Replace remaining layout `space-y-*` in touched UI sections**

For edited page-level sections, prefer:

```tsx
<div className="flex flex-col gap-4">
```

Do not refactor unrelated small stable code solely to remove every existing `space-y-*`.

- [ ] **Step 3: Verify narrow-screen overflow guards**

Ensure article titles, summaries, URLs, and feed URLs use at least one of:

```tsx
className="min-w-0"
className="truncate"
className="line-clamp-2"
className="break-all"
className="break-words"
```

Apply `min-w-0` to flex children that contain long text.

- [ ] **Step 4: Run final static checks**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both PASS.

- [ ] **Step 5: Run full E2E when environment is available**

Run:

```bash
pnpm --dir apps/web test:e2e
```

Expected: PASS. If backend or browser dependencies are unavailable, record the exact blocking output.

- [ ] **Step 6: Manual visual QA**

Start the web dev server:

```bash
pnpm --dir apps/web dev
```

Check:

- `/articles` at 1440px: top nav is thin, article list is neutral, selected article is gray/black, AI sidebar remains visible.
- `/articles` at 1024px: columns remain usable without clipped text.
- `/articles` at 375px: panels stack, controls remain tappable, no horizontal overflow.
- `/feeds` at 1440px: page reads like a docs settings/resource page, not a dashboard card grid.
- `/feeds` at 375px: Feed URL input, add button, row actions, and long URLs wrap correctly.

- [ ] **Step 7: Commit final polish if requested**

```bash
git add apps/web/src
git commit -m "style: polish responsive coss docs restyle"
```

Expected: only files touched by this restyle are staged.

---

## Final Verification Checklist

- [ ] `/articles` still supports status filter query params.
- [ ] Selecting an article still sets `id` in the URL.
- [ ] Opening an article still triggers mark-read behavior.
- [ ] `重新 AI 分析` still calls the existing reanalysis mutation.
- [ ] `标记未读` still calls the existing unread mutation.
- [ ] `/feeds` still adds Feed from the URL form.
- [ ] `/feeds` still refreshes and deletes Feed rows.
- [ ] Empty states still show `暂无文章` and `暂无 Feed`.
- [ ] UI no longer uses blue as the primary selected state.
- [ ] UI uses semantic tokens for normal text/background/border styling.
- [ ] `pnpm --dir apps/web lint` passes.
- [ ] `pnpm --dir apps/web build` passes.
- [ ] E2E passes or the blocker is documented with exact command output.

## Self-Review Notes

- Spec coverage: global shell, `/articles`, `/feeds`, shared recommendation/stepper/markdown components, responsive behavior, accessibility, and verification are covered.
- Scope control: no task adds new routes, backend changes, command search, theme toggle, drawer, or business functionality.
- Placeholder scan: no task relies on open-ended implementation placeholders; each step lists concrete files, class patterns, commands, and expected behavior.
