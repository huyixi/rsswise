# Markdown Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Markdown readability for article bodies, streaming AI Markdown, and final AI summary blocks without changing backend behavior.

**Architecture:** Keep the feature frontend-only. Turn `MarkdownContent` into an explicit, variant-aware renderer for article and compact contexts, then update article and AI call sites to choose the right variant. Add lightweight labels to final `ai_blocks` in `ArticleAiSummary` while preserving existing block ordering and legacy fallback behavior.

**Tech Stack:** React 18, Vite, React Router, TanStack Query, Tailwind CSS v4, `react-markdown`, `remark-gfm`, `rehype-sanitize`, Playwright.

**Source Spec:** `docs/markdown-readability/spec.md`

---

## File Map

- Modify: `apps/web/src/components/markdown-content.tsx`  
  Responsibility: render Markdown with explicit `article` and `compact` variants, optional leading heading stripping, and safe element overrides for headings, paragraphs, links, lists, blockquotes, code, tables, and images.

- Modify: `apps/web/src/routes/articles/components.tsx`  
  Responsibility: pass the correct `MarkdownContent` options for article body and AI streaming Markdown; add lightweight labels to final AI blocks.

- Modify: `apps/web/tests/e2e/articles.spec.ts`  
  Responsibility: verify article heading stripping, streaming heading preservation, AI block labels, and no mobile viewport overflow for wide Markdown content.

---

## Implementation Notes

- Do not modify backend files.
- Do not change `AiBlock` types in `apps/web/src/lib/api.ts`.
- Do not change AI prompt, SSE event format, or article API response shape.
- Keep `ArticleAiSummary` sorting via `visibleAiBlocks(article.ai_blocks)`.
- Keep legacy fallback display for old analyses with no `ai_blocks`.
- Use ASCII punctuation in new code unless existing Chinese UI copy requires Chinese text.
- The plan intentionally avoids syntax highlighting, copy buttons, image lightboxes, collapsible sections, and nested AI cards.

---

### Task 1: Add Failing E2E Coverage

**Files:**
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Confirm working tree**

Run:

```bash
git status --short
```

Expected: docs changes from this planning work may be present. Do not revert unrelated user changes.

- [ ] **Step 2: Expand the first article fixture with wide Markdown**

In `apps/web/tests/e2e/articles.spec.ts`, replace the existing `content_markdown` value inside `articleDetail`:

```ts
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
].join("\\n"),
```

- [ ] **Step 3: Add final AI block label assertions**

In the existing test `mobile article list opens standalone detail page`, after the assertion for `AI 总结`, add these assertions:

```ts
await expect(page.getByText("问题")).toBeVisible()
await expect(page.getByText("摘录")).toBeVisible()
await expect(page.getByText("一句话摘要")).toBeVisible()
await expect(page.getByText("阅读理由")).toBeVisible()
```

Expected after this step and before implementation: the test fails because the labels are not rendered yet.

- [ ] **Step 4: Add heading stripping and overflow assertions for article body**

Append this new test after `mobile detail shows AI summary before article body`:

```ts
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
```

Expected after this step and before implementation: the heading strip assertion may pass today, but the overflow assertion can expose unsafe wide elements after the fixture expands.

- [ ] **Step 5: Add streaming heading preservation assertions**

In both existing streaming tests, after:

```ts
await expect(page.getByText("这篇文章正在生成什么问题？")).toBeVisible()
```

add:

```ts
await expect(page.getByRole("heading", { name: "问题" })).toBeVisible()
```

Expected after this step and before implementation: FAIL because current `MarkdownContent` strips the first `## 问题` heading.

- [ ] **Step 6: Run targeted E2E and verify failure**

Run:

```bash
pnpm --dir apps/web test:e2e -- articles.spec.ts
```

Expected: FAIL on at least the new AI labels and streaming heading preservation assertions.

---

### Task 2: Make MarkdownContent Variant-Aware

**Files:**
- Modify: `apps/web/src/components/markdown-content.tsx`

- [ ] **Step 1: Replace the component with explicit props and reusable classes**

Update `apps/web/src/components/markdown-content.tsx` to this structure:

```tsx
import type { ComponentPropsWithoutRef } from "react"
import ReactMarkdown from "react-markdown"
import rehypeSanitize from "rehype-sanitize"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"

type MarkdownContentVariant = "article" | "compact"

type MarkdownContentProps = {
  markdown: string
  variant?: MarkdownContentVariant
  stripLeadingHeading?: boolean
}

function stripLeadingHeading(markdown: string) {
  return markdown.replace(/^#{1,2}\s+[^\n]+(?:\n\n?)?/, "")
}

const variantClasses: Record<MarkdownContentVariant, string> = {
  article:
    "text-[16.5px] leading-8 text-foreground [overflow-wrap:anywhere] md:text-[17px]",
  compact:
    "text-sm leading-6 text-foreground [overflow-wrap:anywhere]",
}

const headingClasses: Record<MarkdownContentVariant, string> = {
  article:
    "mt-8 scroll-mt-20 text-xl font-semibold leading-snug text-foreground first:mt-0",
  compact:
    "mt-4 scroll-mt-20 text-xs font-semibold uppercase tracking-normal text-muted-foreground first:mt-0",
}

const paragraphClasses: Record<MarkdownContentVariant, string> = {
  article: "my-4 leading-8",
  compact: "my-2 leading-6",
}

const listClasses: Record<MarkdownContentVariant, string> = {
  article: "my-4 space-y-2 pl-6",
  compact: "my-2 space-y-1 pl-5",
}

const listItemClasses: Record<MarkdownContentVariant, string> = {
  article: "pl-1 leading-8",
  compact: "pl-1 leading-6",
}

function createMarkdownComponents(variant: MarkdownContentVariant) {
  return {
    h1({ className, ...props }: ComponentPropsWithoutRef<"h1">) {
      return <h2 className={cn(headingClasses[variant], className)} {...props} />
    },
    h2({ className, ...props }: ComponentPropsWithoutRef<"h2">) {
      return <h2 className={cn(headingClasses[variant], className)} {...props} />
    },
    h3({ className, ...props }: ComponentPropsWithoutRef<"h3">) {
      return (
        <h3
          className={cn(
            variant === "article"
              ? "mt-6 scroll-mt-20 text-lg font-semibold leading-snug text-foreground first:mt-0"
              : "mt-3 scroll-mt-20 text-xs font-medium text-muted-foreground first:mt-0",
            className,
          )}
          {...props}
        />
      )
    },
    p({ className, ...props }: ComponentPropsWithoutRef<"p">) {
      return <p className={cn(paragraphClasses[variant], className)} {...props} />
    },
    ul({ className, ...props }: ComponentPropsWithoutRef<"ul">) {
      return (
        <ul
          className={cn("list-disc", listClasses[variant], className)}
          {...props}
        />
      )
    },
    ol({ className, ...props }: ComponentPropsWithoutRef<"ol">) {
      return (
        <ol
          className={cn("list-decimal", listClasses[variant], className)}
          {...props}
        />
      )
    },
    li({ className, ...props }: ComponentPropsWithoutRef<"li">) {
      return <li className={cn(listItemClasses[variant], className)} {...props} />
    },
    blockquote({ className, ...props }: ComponentPropsWithoutRef<"blockquote">) {
      return (
        <blockquote
          className={cn(
            "my-4 border-l-2 border-muted-foreground/30 pl-4 italic text-muted-foreground",
            variant === "compact" && "my-3 pl-3",
            className,
          )}
          {...props}
        />
      )
    },
    a({ className, ...props }: ComponentPropsWithoutRef<"a">) {
      return (
        <a
          className={cn(
            "break-words text-foreground underline underline-offset-4",
            className,
          )}
          target="_blank"
          rel="noreferrer"
          {...props}
        />
      )
    },
    pre({ className, ...props }: ComponentPropsWithoutRef<"pre">) {
      return (
        <pre
          className={cn(
            "my-4 max-w-full overflow-x-auto rounded-md border border-border bg-muted p-3 text-sm leading-6 text-foreground",
            variant === "compact" && "my-3 p-2 text-xs leading-5",
            className,
          )}
          {...props}
        />
      )
    },
    code({ className, ...props }: ComponentPropsWithoutRef<"code">) {
      return (
        <code
          className={cn(
            "rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]",
            className,
          )}
          {...props}
        />
      )
    },
    table({ className, ...props }: ComponentPropsWithoutRef<"table">) {
      return (
        <div className="my-4 max-w-full overflow-x-auto">
          <table
            className={cn(
              "w-full min-w-max border-collapse text-left text-sm",
              variant === "compact" && "text-xs",
              className,
            )}
            {...props}
          />
        </div>
      )
    },
    th({ className, ...props }: ComponentPropsWithoutRef<"th">) {
      return (
        <th
          className={cn("border-b border-border px-3 py-2 font-medium", className)}
          {...props}
        />
      )
    },
    td({ className, ...props }: ComponentPropsWithoutRef<"td">) {
      return (
        <td
          className={cn("border-b border-border px-3 py-2 align-top", className)}
          {...props}
        />
      )
    },
    img({ className, ...props }: ComponentPropsWithoutRef<"img">) {
      return (
        <img
          className={cn("my-4 h-auto max-w-full rounded-lg", className)}
          loading="lazy"
          {...props}
        />
      )
    },
  }
}

export function MarkdownContent({
  markdown,
  variant = "article",
  stripLeadingHeading: shouldStripLeadingHeading = false,
}: MarkdownContentProps) {
  const renderedMarkdown = shouldStripLeadingHeading
    ? stripLeadingHeading(markdown)
    : markdown

  return (
    <article className={cn("max-w-none", variantClasses[variant])}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={createMarkdownComponents(variant)}
      >
        {renderedMarkdown}
      </ReactMarkdown>
    </article>
  )
}
```

- [ ] **Step 2: Run lint for type and JSX issues**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS. If TypeScript component typing fails because of the installed `react-markdown` version, keep the same behavior but adjust the `createMarkdownComponents` function typing to match the package's exported `Components` type.

---

### Task 3: Wire Markdown Variants Into Article Surfaces

**Files:**
- Modify: `apps/web/src/routes/articles/components.tsx`

- [ ] **Step 1: Update AI streaming Markdown to use compact mode**

Find the streaming fallback in `ArticleAiSummary`:

```tsx
<MarkdownContent markdown={streamText} />
```

Replace it with:

```tsx
<MarkdownContent markdown={streamText} variant="compact" />
```

Expected: streaming AI headings are preserved because heading stripping now defaults to `false`.

- [ ] **Step 2: Update article body Markdown to use article mode and explicit heading stripping**

Find `ArticleBody`:

```tsx
<MarkdownContent markdown={contentMarkdown ?? "正文处理中……"} />
```

Replace it with:

```tsx
<MarkdownContent
  markdown={contentMarkdown ?? "正文处理中……"}
  variant="article"
  stripLeadingHeading
/>
```

Expected: article body keeps duplicate-title prevention while no longer affecting other Markdown contexts.

- [ ] **Step 3: Run targeted E2E for streaming heading preservation**

Run:

```bash
pnpm --dir apps/web test:e2e -- articles.spec.ts -g "streaming AI summary"
```

Expected: PASS for both desktop and mobile streaming tests.

---

### Task 4: Add Lightweight Labels To Final AI Blocks

**Files:**
- Modify: `apps/web/src/routes/articles/components.tsx`

- [ ] **Step 1: Add a label helper near `visibleAiBlocks`**

Add this helper below `visibleAiBlocks`:

```tsx
function aiBlockLabel(block: AiBlock) {
  switch (block.type) {
    case "reading_question":
      return "问题"
    case "highlights":
      return "摘录"
    case "summary":
      return "一句话摘要"
    case "reading_reason":
      return "阅读理由"
    case "chapters":
      return "章节"
  }
}
```

- [ ] **Step 2: Wrap each rendered AI block with a visible label**

In `ArticleAiSummary`, replace:

```tsx
blocks.map((block) => (
  <div key={block.type}>
```

with:

```tsx
blocks.map((block) => (
  <section key={block.type} className="flex flex-col gap-1.5">
    <h3 className="text-xs font-medium text-muted-foreground">
      {aiBlockLabel(block)}
    </h3>
```

Then replace the matching closing `</div>` for that mapped block with:

```tsx
  </section>
```

Expected: labels are visible text, the block order remains unchanged, and no nested card UI is introduced.

- [ ] **Step 3: Preserve existing content styling**

Keep the current block-specific renderers:

```tsx
{block.type === "reading_question" ? (
  <p className="text-sm font-medium text-foreground">{block.content}</p>
) : null}
```

Keep the existing highlights, summary, reading reason, and chapters markup unless lint requires formatting changes.

- [ ] **Step 4: Run targeted E2E for final AI labels and block ordering**

Run:

```bash
pnpm --dir apps/web test:e2e -- articles.spec.ts -g "mobile article list opens standalone detail page|mobile detail renders blocks in order"
```

Expected: PASS.

---

### Task 5: Verify Wide Markdown Does Not Break Mobile Layout

**Files:**
- Modify if needed: `apps/web/src/components/markdown-content.tsx`
- Modify if needed: `apps/web/src/routes/articles/components.tsx`
- Test: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Run the overflow test**

Run:

```bash
pnpm --dir apps/web test:e2e -- articles.spec.ts -g "mobile article body strips duplicate leading heading and avoids viewport overflow"
```

Expected: PASS.

- [ ] **Step 2: If the page still overflows, constrain table/code/image containers**

If the test fails on `hasPageOverflow`, inspect the culprit in browser devtools or through Playwright. The most likely fixes are:

```tsx
<pre className="my-4 max-w-full overflow-x-auto ...">
```

```tsx
<div className="my-4 max-w-full overflow-x-auto">
  <table className="w-full min-w-max ...">
```

```tsx
<img className="my-4 h-auto max-w-full rounded-lg" ... />
```

Also confirm the Markdown root keeps:

```tsx
<article className={cn("max-w-none", variantClasses[variant])}>
```

and the variant classes include:

```ts
"[overflow-wrap:anywhere]"
```

- [ ] **Step 3: Re-run the overflow test**

Run:

```bash
pnpm --dir apps/web test:e2e -- articles.spec.ts -g "mobile article body strips duplicate leading heading and avoids viewport overflow"
```

Expected: PASS.

---

### Task 6: Full Verification

**Files:**
- Read: `docs/markdown-readability/spec.md`
- Verify: all modified files

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

- [ ] **Step 3: Run full article E2E suite**

Run:

```bash
pnpm --dir apps/web test:e2e -- articles.spec.ts
```

Expected: PASS.

- [ ] **Step 4: Run the full web E2E suite if time allows**

Run:

```bash
pnpm --dir apps/web test:e2e
```

Expected: PASS.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git diff -- apps/web/src/components/markdown-content.tsx apps/web/src/routes/articles/components.tsx apps/web/tests/e2e/articles.spec.ts
```

Expected:

- `MarkdownContent` has explicit `variant` and `stripLeadingHeading` props.
- Article body opts into heading stripping.
- AI streaming Markdown uses compact mode and does not strip headings.
- Final AI blocks show visible labels.
- E2E tests cover labels, heading preservation, heading stripping, and overflow safety.

---

## Plan Self-Review

- Spec coverage: Covered article body Markdown, AI streaming Markdown, final AI summary block labels, explicit heading stripping, basic wide-element usability, and frontend-only constraints.
- Placeholder scan: No TBD/TODO placeholders.
- Type consistency: `variant`, `stripLeadingHeading`, `AiBlock`, `ArticleAiSummary`, and `ArticleBody` names match the current code and spec.
