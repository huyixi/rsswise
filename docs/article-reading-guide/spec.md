# Article Reading Guide Spec

## Background

RSSWise currently extracts article markdown, runs an automatic Celery AI analysis task, and stores three analysis fields on `article_ai_analyses`: `one_sentence_summary`, `reading_recommendation`, and `reading_reason`. The article detail UI shows an AI summary panel before or beside the original article body. The recent streaming implementation forwards temporary AI chunks from Redis Streams to the browser through the existing article analysis SSE endpoint.

This feature expands the AI summary into a structured reading guide at the start of article detail reading. It should help readers enter the article with one guiding question, selected quote highlights, the existing summary/reason, and optional chapter titles when the article is long enough to benefit from a structure guide.

## Goals

- Replace scattered detail-display fields with an ordered `AiBlock[]` display model for article detail AI content.
- Keep `reading_recommendation` as an independent field for recommendation badges and list-level filtering/display compatibility.
- Generate one required guiding question for each newly successful AI analysis.
- Generate 3-5 required highlights for each newly successful AI analysis.
- Make highlights verbatim quotes from the source article according to prompt instructions.
- Do not verify highlight quotes against the original markdown in the first version.
- Generate chapters only when useful, and force chapters to empty for short/simple articles by backend rules.
- Stream user-readable Markdown while AI analysis is running.
- Parse the completed Markdown into validated structured data before writing the final database result.
- Keep article body markdown unchanged. The reading guide is stored and rendered as AI analysis data, not prepended into `content_markdown`.
- Do not backfill old successful analyses automatically.
- Keep article lists visually unchanged by deriving the old one-sentence summary from the `summary` block.
- Keep EPUB summary behavior by deriving the old one-sentence summary from the `summary` block.

## Non-Goals

- No automatic backfill for old articles.
- No manual "regenerate reading guide" UI.
- No quote verification against article markdown in this version.
- No click-to-jump chapter navigation.
- No chapter summaries or estimated positions.
- No article-list display of reading questions, highlights, or chapters.
- No mutation of extracted article markdown.

## Data Model

The canonical detail AI content is an ordered array named `ai_blocks`.

```ts
type AiBlock =
  | {
      type: "reading_question"
      title: "问题"
      content: string
      order: number
    }
  | {
      type: "highlights"
      title: "Highlights"
      content: Array<{
        text: string
        quote_verified: boolean
      }>
      order: number
    }
  | {
      type: "summary"
      title: "一句话摘要"
      content: string
      order: number
    }
  | {
      type: "reading_reason"
      title: "阅读理由"
      content: string
      order: number
    }
  | {
      type: "chapters"
      title: "章节"
      content: Array<{
        title: string
      }>
      order: number
    }
```

`article_ai_analyses` should migrate to use:

- `ai_blocks: JSON | null`
- `reading_recommendation: deep_read | skim | skip | null`
- `analysis_status`
- existing timestamps

`one_sentence_summary` and `reading_reason` stop being canonical database fields. They may remain temporarily during migration if needed, but the target model derives them from `ai_blocks`.

Derivation rules:

- `one_sentence_summary` is the `content` of the first `summary` block.
- `reading_reason` is the `content` of the first `reading_reason` block.
- If the relevant block is missing, the derived value is `null`.

## Required Blocks

For new successful AI analyses:

- `reading_question` is required.
- `highlights` is required.
- `summary` is required.
- `reading_reason` is required.
- `chapters` is optional and may be absent or have empty content.

Recommended default ordering:

1. `reading_question`
2. `highlights`
3. `summary`
4. `reading_reason`
5. `chapters`

The renderer must sort by `order`, not by array position alone.

## Field Semantics

### Reading Question

- Output language: Chinese.
- Count: exactly one question.
- Purpose: give the reader a concrete question to carry into the article.
- It should frame the central issue the article tries to explain, resolve, or illuminate.

### Highlights

- Count: 3-5 items.
- Each item must be a verbatim quote from the article according to prompt instructions.
- If the source article is English, highlights remain English because verbatim quoting takes precedence over unified Chinese output.
- `quote_verified` is always `false` in this version because backend quote matching is explicitly out of scope.
- The prompt should tell the model not to paraphrase, translate, or invent highlight text.

### Summary

- Output language: Chinese.
- Count: one concise sentence.
- Equivalent to the previous one-sentence summary feature.
- Used by article detail, article list derivation, and EPUB derivation.

### Reading Reason

- Output language: Chinese.
- Count: one concise paragraph or sentence.
- Equivalent to the previous reading reason feature.

### Chapters

- Content shape: array of `{ title: string }`.
- Titles only. No summaries, anchors, or positions.
- Output language: Chinese unless the source title is a proper noun or should remain untranslated.
- May be empty or absent.
- Intended as a structure guide, not a strict extraction of original markdown headings.

Backend must force chapters to empty when either condition is true:

- The markdown text has fewer than 1200 non-whitespace characters.
- The markdown has fewer than 8 non-empty paragraphs when split by blank lines.

This means chapters are allowed only when the article has at least 1200 non-whitespace characters and at least 8 non-empty paragraphs.

## AI Output Format

The AI service should stream Markdown, not JSON, so users can read useful progress while generation is still running.

The generated Markdown must use fixed section headings:

```markdown
## 问题
...

## Highlights
- ...
- ...
- ...

## 一句话摘要
...

## 阅读建议
deep_read

## 阅读理由
...

## 章节
- ...
- ...
```

Allowed reading recommendation values:

- `deep_read`
- `skim`
- `skip`

The worker accumulates all streamed Markdown chunks. After the stream ends, it parses the complete Markdown into:

- `ai_blocks`
- `reading_recommendation`

If parsing or validation fails, the analysis is marked `failed` and no partial structured result is written.

## Parsing And Validation

The parser should be deterministic and independent from the OpenAI client.

Validation rules:

- Required sections must be present: `问题`, `Highlights`, `一句话摘要`, `阅读建议`, `阅读理由`.
- `问题` content must be non-empty.
- `Highlights` must contain 3-5 bullet items.
- Each highlight item must create `{ text, quote_verified: false }`.
- `一句话摘要` content must be non-empty.
- `阅读建议` must be one of `deep_read`, `skim`, or `skip`.
- `阅读理由` content must be non-empty.
- `章节` may be missing, empty, or contain bullet items.
- Chapter items become `{ title }`.
- If the chapter threshold says chapters are not allowed, parsed chapters are discarded and the resulting `chapters` block should either be omitted or stored with `content: []`. The UI must hide an empty chapters block.

Recommended resulting blocks:

```json
[
  {
    "type": "reading_question",
    "title": "问题",
    "content": "这篇文章试图回答什么问题？",
    "order": 10
  },
  {
    "type": "highlights",
    "title": "Highlights",
    "content": [
      {
        "text": "原文中的一句亮点。",
        "quote_verified": false
      }
    ],
    "order": 20
  },
  {
    "type": "summary",
    "title": "一句话摘要",
    "content": "这是一句话摘要。",
    "order": 30
  },
  {
    "type": "reading_reason",
    "title": "阅读理由",
    "content": "这是阅读理由。",
    "order": 40
  },
  {
    "type": "chapters",
    "title": "章节",
    "content": [
      {
        "title": "背景与问题"
      }
    ],
    "order": 50
  }
]
```

## API Behavior

### `GET /articles`

The list response remains compatible with the current UI:

- `one_sentence_summary` is still returned.
- `reading_recommendation` is still returned.
- New guide blocks are not returned in list items.

`one_sentence_summary` is derived from the `summary` block. Old rows without `ai_blocks` may continue to fall back to legacy columns during migration if those columns still exist at that point.

### `GET /articles/{article_id}`

The detail response adds:

- `ai_blocks: AiBlock[] | null`

For compatibility during frontend migration, the API may temporarily keep returning:

- `one_sentence_summary`
- `reading_reason`

Those values must be derived from `ai_blocks` when available.

### `GET /articles/{article_id}/analysis/events`

The SSE protocol stays the same:

- `started`
- `chunk`
- `done`
- `error`
- existing waiting-content behavior

`chunk.data.text` now contains Markdown text chunks rather than JSON text chunks. The endpoint does not need new event names for individual block types.

## Frontend Behavior

`ArticleAiSummary` becomes the single component for all AI content in the detail reading experience.

Final structured display:

- Render visible blocks sorted by `order`.
- Hide missing blocks.
- Hide `chapters` when its content array is empty.
- Render the recommendation badge from independent `reading_recommendation`.
- Render `highlights` as quote items using `content[].text`.
- Render `chapters` as a compact title list.

Streaming display:

- If final `ai_blocks` are missing and there is `streamText`, render `streamText` as Markdown in the AI summary panel.
- Do not show raw JSON during generation.
- On `done`, refresh detail and list queries, then show final structured data.
- On `error`, show the existing AI failure state.

Old successful articles:

- If `ai_blocks` is `null`, display whatever compatible legacy summary/reason fields are still available.
- Do not show placeholder text for missing reading question, highlights, or chapters.

Article body:

- `ArticleBody` continues to render only `content_markdown`.
- The reading guide appears in `ArticleAiSummary`, not inside article markdown.

## Migration Strategy

Target migration:

- Add `ai_blocks` JSON column to `article_ai_analyses`.
- Keep `reading_recommendation` as an existing column.
- Remove or stop using `one_sentence_summary` and `reading_reason` as canonical fields.

Because old articles are not automatically backfilled, old rows may not have `ai_blocks`. The implementation should either:

- keep legacy columns during a transition period for old-data fallback, or
- migrate old values into `summary` and `reading_reason` blocks without calling AI.

No AI-costing backfill should run automatically.

The implementation plan should choose the lower-risk migration path for this codebase.

## Testing Requirements

Backend tests:

- Markdown parser accepts a valid full AI Markdown response.
- Parser rejects missing required sections.
- Parser rejects invalid recommendation values.
- Parser rejects fewer than 3 or more than 5 highlights.
- Parser returns `quote_verified: false` for every highlight.
- Chapter threshold discards chapters for short/simple markdown.
- Chapter threshold preserves chapters for sufficiently long structured markdown.
- AI service streams Markdown chunks without JSON response formatting.
- Worker persists `ai_blocks` and `reading_recommendation` after a successful stream.
- Worker marks analysis failed when parsing fails.
- List API derives `one_sentence_summary` from `ai_blocks`.
- Detail API returns `ai_blocks`.
- EPUB summary derives from the `summary` block.

Frontend tests:

- `ArticleAiSummary` renders final blocks in `order`.
- Empty or missing chapters are hidden.
- Old articles with missing `ai_blocks` do not show empty placeholders.
- Streaming analysis renders Markdown chunks in the AI summary panel.
- Article list still shows a one-sentence summary derived from backend response.

## Acceptance Criteria

- New successful AI analyses store ordered `ai_blocks` plus independent `reading_recommendation`.
- Detail pages show guiding question, highlights, summary, reading reason, and optional chapters in the confirmed order.
- Highlights are prompted as verbatim quotes and stored with `quote_verified: false`.
- Chapters are empty for articles below the configured length or paragraph threshold.
- Analysis streaming shows readable Markdown instead of JSON fragments.
- Article lists and EPUB generation still have access to a one-sentence summary derived from the `summary` block.
- Old articles without new blocks remain readable and do not show missing-field placeholders.
