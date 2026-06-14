# Markdown Readability Spec

## Summary

Improve Markdown readability across RSSWise article reading surfaces without changing backend APIs, AI output format, or stored data.

This feature covers three frontend surfaces:

- Article body Markdown.
- Streaming AI Markdown shown while analysis is running.
- Final structured AI summary blocks shown after analysis succeeds.

The implementation should keep RSSWise's restrained, tool-like interface. The article body should become easier to read for long-form content, while AI Markdown inside compact panels should remain dense and scannable.

## Decisions From Requirement Discovery

- Scope includes article body Markdown, AI streaming Markdown, and final AI summary blocks.
- Final AI summary blocks should keep the current order but add lightweight section labels.
- Article body styling should use a restrained reader style, not a heavy editorial/blog layout.
- Markdown support should include basic usability for code blocks, tables, images, and long links.
- Do not add syntax highlighting, copy-code buttons, image lightboxes, collapsible sections, or complex cards.
- Heading stripping should become explicit:
  - Article body may strip the first leading heading to avoid duplicating the page title.
  - AI streaming Markdown must preserve headings such as `## 问题` and `## Highlights`.

## Current State

Relevant files:

```text
apps/web/src/components/markdown-content.tsx
apps/web/src/routes/articles/components.tsx
apps/web/src/routes/articles/detail.tsx
apps/web/src/routes/articles/workbench.tsx
apps/web/src/lib/api.ts
apps/web/tests/e2e/articles.spec.ts
```

Current `MarkdownContent` behavior:

- Uses `ReactMarkdown` with `remark-gfm` and `rehype-sanitize`.
- Uses one shared Tailwind Typography class for all Markdown surfaces.
- Always calls `stripLeadingHeading(markdown)`.
- Does not distinguish long article body content from compact AI streaming content.
- Does not customize individual Markdown elements through `ReactMarkdown` component overrides.

This causes two main problems:

- Long article bodies do not get enough reader-focused spacing and line rhythm.
- AI streaming Markdown can lose its first structural heading, making streamed output less readable.

Final structured AI blocks are rendered manually in `ArticleAiSummary`. They already show content in the correct order, but the UI does not label each block clearly, so users can have trouble distinguishing the question, quotes, summary, reason, and chapters at a glance.

## Goals

- Make article body Markdown more readable for long-form RSS articles.
- Keep AI streaming Markdown compact but structurally clear.
- Preserve AI streaming headings.
- Add lightweight labels to final AI summary blocks.
- Prevent code blocks, tables, images, and long links from breaking layout.
- Keep the implementation frontend-only.
- Keep existing data contracts and backend behavior unchanged.

## Non-Goals

- No backend API changes.
- No database or migration changes.
- No changes to AI prompt, AI output format, `ai_blocks`, or SSE event format.
- No syntax highlighting.
- No copy-code button.
- No image lightbox or gallery behavior.
- No collapsible AI sections.
- No redesign of the article workbench layout.
- No new Markdown parser library.

## Target Behavior

### Article Body Markdown

Article body content should use a restrained reader style:

- Slightly larger body text than compact UI text.
- Comfortable line height for Chinese and English long-form reading.
- Clear paragraph spacing.
- Headings with stronger hierarchy and more top spacing.
- Lists with readable item spacing.
- Blockquotes styled as quotes or excerpts, not plain paragraphs.
- Inline code visually distinct but not loud.
- Code blocks scroll horizontally instead of stretching the page.
- Tables are wrapped in horizontal overflow containers.
- Images are responsive, rounded, and constrained to the content width.
- Long URLs and long inline text can wrap without overflowing.

The article page title remains the canonical title. Article body Markdown may strip one leading `#` or `##` heading when rendering article content to avoid duplicate titles.

### AI Streaming Markdown

Streaming Markdown shown while AI analysis is running should use compact styling:

- Preserve AI section headings.
- Use smaller text and tighter spacing than article body Markdown.
- Make `h2`/`h3` headings readable inside the AI summary panel.
- Keep lists, blockquotes, code, tables, and links safe from overflow.

The first heading must not be stripped in this mode.

### Final AI Summary Blocks

Final AI blocks should keep the existing sorted order:

1. `reading_question`
2. `highlights`
3. `summary`
4. `reading_reason`
5. `chapters`

Each block should get a lightweight label:

- `问题`
- `摘录`
- `一句话摘要`
- `阅读理由`
- `章节`

Labels should improve scanability without making the AI panel feel like a stack of heavy cards. The existing reading recommendation badge remains in the AI summary header.

Highlights should continue to read as quoted excerpts. Chapters should continue to render as compact labels or chips, and empty chapters remain hidden.

## Component Design

### MarkdownContent

Update `MarkdownContent` to accept explicit rendering options:

```ts
type MarkdownContentVariant = "article" | "compact"

type MarkdownContentProps = {
  markdown: string
  variant?: MarkdownContentVariant
  stripLeadingHeading?: boolean
}
```

Recommended defaults:

- `variant`: `"article"`
- `stripLeadingHeading`: `false`

Call sites should opt into heading stripping where needed.

Article body call:

```tsx
<MarkdownContent
  markdown={contentMarkdown ?? "正文处理中……"}
  variant="article"
  stripLeadingHeading
/>
```

AI streaming call:

```tsx
<MarkdownContent markdown={streamText} variant="compact" />
```

### Element Overrides

Use `ReactMarkdown` `components` overrides for important Markdown elements:

- `h1`, `h2`, `h3`
- `p`
- `ul`, `ol`, `li`
- `blockquote`
- `a`
- `code`, `pre`
- `table`, `thead`, `tbody`, `tr`, `th`, `td`
- `img`

The overrides should be shared where possible, with variant-specific class names for typography and spacing.

Table rendering should wrap the actual `<table>` in an overflow container. If direct wrapping through a `table` override is awkward, use a `div` wrapper inside the table component override.

### ArticleBody

`ArticleBody` should render article Markdown with:

- `variant="article"`
- `stripLeadingHeading`

This preserves the current duplicate-title prevention for article bodies while avoiding global heading stripping.

### ArticleAiSummary

`ArticleAiSummary` should:

- Continue using `visibleAiBlocks(article.ai_blocks)` and sort by `order`.
- Add a small label for each visible block.
- Render streaming Markdown with `variant="compact"` and no heading stripping.
- Keep legacy fallback behavior for old rows with only `one_sentence_summary` and `reading_reason`.
- Keep the existing pending and error states.

## Accessibility

- Labels in the AI summary should be visible text, not only decorative styling.
- Existing `aria-labelledby="article-ai-summary-heading"` should remain.
- Decorative icons should keep `aria-hidden="true"`.
- Links rendered from Markdown should remain keyboard accessible and visibly identifiable.
- Code blocks and table overflow containers should not trap keyboard focus.

## Visual Constraints

- Keep the current neutral RSSWise theme.
- Do not introduce a new color palette.
- Do not use nested cards for each AI block.
- Do not add large hero-style typography.
- Keep article content within the existing max-width constraints.
- Ensure mobile text and table/code overflow do not push the page wider than the viewport.

## Testing And Acceptance

The implementation should verify:

- Article body rendering strips a leading `#` or `##` heading only when `stripLeadingHeading` is set.
- AI streaming Markdown preserves the first `##` heading.
- Article body and AI streaming Markdown use different variants.
- Final AI summary blocks show visible labels for question, highlights, summary, reason, and chapters.
- Empty chapters remain hidden.
- Code blocks and tables do not expand beyond their container.
- Long links wrap instead of overflowing.
- Existing article list/detail behavior still works.

Recommended validation commands:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
```

## Out Of Scope

- Reworking backend article extraction.
- Changing article Markdown before storage.
- Backfilling existing articles.
- Changing the AI prompt or AI parser.
- Adding new article actions or summary regeneration controls.
