# Design: External Link EPUB From Feed Item

## Summary

RSSWise will support creating a scheduled EPUB from external links contained in a selected feed item. The user explicitly marks one article as an external-link source. RSSWise parses links from that source article ahead of the configured send time, creates or reuses normal `Article` records for the linked pages, starts the existing extraction pipeline, and generates the EPUB at the scheduled time.

The EPUB generation deadline is fixed. Failed, pending, or still-processing linked articles do not block the EPUB. They appear as placeholder chapters that explain why full text was not included and preserve the original URL.

## Decisions From Requirement Discovery

- The user chooses the feed item that should be parsed for external links.
- RSSWise does not automatically infer which feed entries are weekly recommendation posts in the first version.
- Link parsing and full-text extraction happen before the daily EPUB generation time.
- At generation time, RSSWise always produces the EPUB for due collections.
- A linked article with successful extraction appears with full article content.
- A linked article with failed extraction appears as a placeholder chapter.
- A linked article still pending or processing at the deadline appears as a placeholder chapter.
- AI analysis does not block EPUB generation. If AI summary data is already available and successful, the EPUB may include it; otherwise it is omitted.
- Linked articles reuse the existing `Article`, `ArticleContent`, extraction, AI analysis, and EPUB rendering pipeline where practical.
- The source feed item order is preserved in the generated EPUB.
- A broken linked article is item-level failure, not collection-level failure.
- Collection-level failure is reserved for failures that prevent EPUB generation or sending entirely.

## Current State

Relevant backend files:

```text
apps/api/app/models.py
apps/api/app/services/feed_service.py
apps/api/app/services/extraction_service.py
apps/api/app/services/epub_service.py
apps/api/app/services/email_digest_service.py
apps/api/app/tasks.py
apps/api/app/beat.py
apps/api/alembic/versions/
```

Current behavior:

- Feed refresh uses `feedparser` to create `Article` rows from feed entries.
- Each new article gets `ArticleContent` and `ArticleAIAnalysis` rows.
- `extract_article_task` fetches article HTML and stores extracted Markdown.
- Successful extraction enqueues AI analysis.
- `build_digest_epub()` builds an EPUB from a list of `Article` objects.
- Existing email digest scheduling runs through Celery beat and sends an EPUB attachment.
- Existing EPUB article chapters already degrade when article body Markdown is missing.

This feature should extend the existing article and EPUB model rather than introducing a separate crawler store.

## Goals

- Let the user create an EPUB from links inside a selected feed item.
- Preserve the selected feed item as the source of the collection.
- Preserve linked article order from the source item.
- Start linked article extraction ahead of the scheduled EPUB generation time.
- Generate the EPUB at the configured time even when some linked articles fail.
- Make incomplete linked articles visible through placeholder chapters.
- Keep link parsing, extraction, EPUB generation, and sending idempotent.
- Avoid blocking the daily EPUB on external website failures or AI analysis delays.

## Non-Goals

- No automatic discovery of recommendation-style feed items.
- No browser automation crawler.
- No paywall bypassing.
- No guarantee that every external website can be extracted.
- No waiting for all linked articles to finish before generating the EPUB.
- No requirement that AI summaries exist before EPUB generation.
- No manual rich editing of parsed link lists in the first version.
- No multi-user scheduling redesign in this feature.

## Target Behavior

### Source Selection

From the article list, the user can open a feed item context menu and choose an action such as `Create external-link EPUB`. On desktop this is available through right-click on the feed item row. The same action must also be reachable through a visible overflow/menu button so keyboard users, touch devices, and mobile layouts are not blocked by a right-click-only interaction.

The article row implementation must not nest the overflow/menu trigger inside another interactive element such as a row-level `<button>` or `<a>`. If the row is clickable/selectable, structure it as a non-interactive row container with separate interactive controls, for example one button or link for opening/selecting the article and one adjacent menu button for row actions. Opening the menu must not also select or navigate to the article.

The backend treats the selected item as the source feed item and records:

```text
ExternalLinkCollection.source_article_id = selected Article.id
```

The source article may contain links in:

- `summary_from_feed`, which often preserves feed-provided HTML.
- `content_markdown`, if extraction has already produced Markdown.

The parser should prefer `summary_from_feed` when available because it is closest to the original feed item payload. It should also support Markdown links from `content_markdown`.

### Collection Settings Dialog

Selecting `Create external-link EPUB` opens a dialog before creating the collection.

The dialog shows the selected feed item title and source URL, then lets the user configure:

- Collection title, defaulting to the source article title.
- Target send date, defaulting to the next local date if today's send time has already passed, otherwise today.
- Send time, defaulting to `08:00`.
- Prepare offset in hours, defaulting to `6`.
- Link source mode, defaulting to `auto`.

Link source mode values:

```text
auto
summary_from_feed
content_markdown
```

Mode semantics:

- `auto`: parse `summary_from_feed` first, then also parse `content_markdown` when available and dedupe by normalized URL.
- `summary_from_feed`: parse only feed-provided summary HTML.
- `content_markdown`: parse only extracted Markdown content.

The dialog includes a `Preview links` action. Preview parses links without creating a collection and displays:

- Total accepted link count.
- Link title or anchor text.
- Normalized URL.
- Duplicate or filtered link count if useful for diagnostics.

The primary action creates the scheduled collection and queues extraction for linked articles. The dialog should surface a clear error when no links are found.

### Link Preview And Collection Creation

The first version can combine preview and creation into one flow, but the backend boundary should still be clear:

1. Parse links from the selected source article.
2. Normalize and filter candidate URLs.
3. Drop duplicate target URLs within the same source article.
4. Create an external-link collection.
5. Create collection items in source order.
6. Upsert or reuse normal `Article` records for each target URL.
7. Enqueue extraction for linked articles that do not already have successful content.

The user-visible result is a collection containing all accepted external links and their current extraction status.

### Daily Prepare Task

A Celery beat task runs periodically, for example every 5 minutes, and checks whether external-link collections need preparation for the current day.

The task should use configured local time, matching the existing digest timezone convention of `Asia/Shanghai`.

Preparation is due when:

- A collection is not yet generated or sent.
- Its `target_send_date` is today or earlier.
- Current local time is at or after `send_time - prepare_offset`.
- It has not already completed preparation for that send date.

Default scheduling values:

```text
send_time: 08:00
prepare_offset_hours: 6
prepare_time: 02:00
timezone: Asia/Shanghai
```

The prepare task is idempotent. Running it more than once should not duplicate collection items or enqueue unnecessary extraction tasks for articles already extracted successfully.

### Daily Generate Task

A separate scheduled task checks due collections at or after `send_time`.

Generation is due when:

- A collection has not been generated for its `target_send_date`.
- Current local time is at or after `send_time`.
- The collection has at least one item.

At this point the task generates the EPUB regardless of individual item extraction state.

After successful EPUB generation, the task sends it through the existing email service and SMTP configuration used by the email digest workflow. Sending success marks the collection `sent`. If EPUB generation or email delivery fails at the collection level, the collection is marked `failed` with an error summary and can be retried by a later task.

The first version does not persist EPUB binaries. `generated_at` means the scheduled task successfully built the EPUB during that run. `sent_at` means delivery succeeded. Manual download endpoints generate a fresh EPUB from the current collection state.

### Delivery

External-link EPUB delivery reuses the existing email digest recipient and SMTP settings. If the email digest recipient is not configured, due external-link collections fail at collection level with a clear `last_error`.

The email subject should distinguish this workflow from normal article digests, for example:

```text
RSSWise 外链文章合集 - <target_send_date>
```

The attachment filename should include the date and collection title slug where practical:

```text
RSSWise-External-Links-2026-06-21.epub
```

### EPUB Contents

The EPUB keeps the source order from the selected feed item.

For each linked article:

- If `ArticleContent.extraction_status == success` and `content_markdown` is non-empty, render the normal article chapter with title, source link, optional successful AI summary, and body.
- If extraction failed, render a placeholder chapter:

```text
正文抓取失败，未收入全文。

原文链接：<url>
失败原因：<short error if available>
```

- If extraction is still pending or processing at the deadline, render a placeholder chapter:

```text
到生成时间时正文仍未抓取完成，未收入全文。

原文链接：<url>
```

The EPUB should include a front matter page that identifies:

- Source feed item title.
- Source feed item URL.
- Target send date.
- Number of linked articles.
- Number included with full text.
- Number included as placeholders.

## Data Model

Add an external-link collection model and item model.

### ExternalLinkCollection

Suggested table: `external_link_collections`

Fields:

- `id`: UUID primary key.
- `source_article_id`: UUID foreign key to `articles.id`, indexed, cascade delete.
- `title`: string, derived from source article title but editable later if needed.
- `target_send_date`: date, indexed.
- `timezone`: string, default `Asia/Shanghai`.
- `send_time`: time, default `08:00`.
- `prepare_offset_hours`: integer, default `6`.
- `link_source_mode`: string, default `auto`.
- `status`: string or enum.
- `prepared_at`: nullable datetime.
- `generated_at`: nullable datetime.
- `sent_at`: nullable datetime.
- `last_error`: nullable text.
- `created_at`: datetime.
- `updated_at`: datetime.

Collection status values:

```text
collecting
prepared
generated
sent
failed
```

Status semantics:

- `collecting`: collection exists and linked articles may be extracting.
- `prepared`: prepare task has parsed or refreshed items and queued needed extraction.
- `generated`: EPUB was generated for the target send date.
- `sent`: EPUB was delivered by email through the existing email service.
- `failed`: collection-level generation or sending failed.

Individual linked article failures do not set collection status to `failed`.

### ExternalLinkCollectionItem

Suggested table: `external_link_collection_items`

Fields:

- `id`: UUID primary key.
- `collection_id`: UUID foreign key to `external_link_collections.id`, indexed, cascade delete.
- `article_id`: nullable UUID foreign key to `articles.id`, indexed.
- `position`: integer.
- `source_url`: string.
- `normalized_url`: string, indexed.
- `anchor_text`: nullable string.
- `title_hint`: nullable string.
- `status`: string or enum.
- `error_message`: nullable text.
- `created_at`: datetime.
- `updated_at`: datetime.

Item status values:

```text
pending
extracting
success
failed
timed_out
```

Item status can be stored for diagnostics, but the generation task should derive the final chapter behavior from the linked `ArticleContent` state at generation time.

Unique constraints:

- `(collection_id, normalized_url)` to avoid duplicate links in one collection.
- `(collection_id, position)` to keep stable ordering.

## URL Parsing And Filtering

The parser should extract links from HTML and Markdown using structured parsers where possible:

- HTML: parse `<a href="">` from `summary_from_feed`.
- Markdown: parse Markdown links from `content_markdown`.

Normalization rules for the first version:

- Resolve relative links against the source article URL when possible.
- Keep only `http` and `https` URLs.
- Strip fragments.
- Remove common tracking parameters such as `utm_*`.
- Trim whitespace.
- Preserve the final normalized URL as the dedupe key.

Filtering rules:

- Exclude the source article URL itself.
- Exclude feed URLs and obvious RSS/Atom links.
- Exclude image, video, audio, archive, and document file extensions in the first version unless explicitly allowed later.
- Exclude `mailto:`, `javascript:`, and non-web schemes.

Redirect-following canonicalization can be added later. The first version should avoid network requests during link parsing except when extraction is queued.

## Backend API

### Preview Links

`POST /articles/{article_id}/external-links/preview`

Returns parsed candidate links without creating a collection.

Request shape:

```json
{
  "link_source_mode": "auto"
}
```

Response shape:

```json
{
  "source_article_id": "uuid",
  "links": [
    {
      "url": "https://example.com/post",
      "normalized_url": "https://example.com/post",
      "anchor_text": "Example post",
      "position": 1
    }
  ]
}
```

### Create Collection

`POST /articles/{article_id}/external-links/collections`

Request shape:

```json
{
  "title": "Weekly Reading Picks",
  "target_send_date": "2026-06-21",
  "send_time": "08:00",
  "prepare_offset_hours": 6,
  "link_source_mode": "auto"
}
```

Behavior:

- Parses links from the source article.
- Creates a collection and items.
- Creates or reuses linked `Article` rows.
- Queues extraction where needed.
- Returns the collection with item statuses.

### Get Collection

`GET /external-link-collections/{collection_id}`

Returns collection metadata, source article metadata, items, and current extraction status derived from linked article content.

### Retry Collection Preparation

`POST /external-link-collections/{collection_id}/prepare`

Re-runs parsing and extraction enqueueing for the collection. This is useful if the source article was extracted after the initial collection creation or if some linked articles failed and should be retried.

### Download EPUB

`GET /external-link-collections/{collection_id}/epub`

Generates and returns an EPUB from the current collection state. The first version does not read a stored EPUB binary. On-demand download before `send_time` can be rejected unless explicitly allowed later.

## Services

Add focused backend services:

```text
app/services/external_link_parser.py
app/services/external_link_collection_service.py
app/services/external_link_epub_service.py
```

Responsibilities:

- `external_link_parser.py`: extract, normalize, filter, and dedupe links from a source article.
- `external_link_collection_service.py`: create collections, upsert items, upsert linked articles, enqueue extraction, compute status.
- `external_link_epub_service.py`: query collection items in order and render full-text or placeholder chapters.

`epub_service.py` should be extended carefully rather than duplicated wholesale. The shared EPUB packaging helpers can remain in `epub_service.py`; collection-specific chapter/front matter rendering can live in `external_link_epub_service.py`.

## Scheduling

Add Celery tasks:

```text
external_links.prepare_due
external_links.generate_due
```

Beat schedule can run both as lightweight polling tasks:

```text
external-links-prepare-due-every-five-minutes
external-links-generate-due-every-five-minutes
```

The tasks should perform date/time checks in service code instead of dynamically rewriting Celery beat configuration.

## Error Handling

Item-level failures:

- Link could not be converted into an article.
- Article extraction failed.
- Article extraction is still incomplete at the generation deadline.

These failures produce placeholder EPUB chapters.

Collection-level failures:

- No links were found in the selected feed item.
- EPUB packaging failed.
- Email recipient or SMTP configuration is missing.
- Email delivery failed.
- Database transaction failed.

Collection-level failures set `ExternalLinkCollection.status = failed` and store a short `last_error`.

## Testing

Backend tests should cover:

- HTML link parsing from `summary_from_feed`.
- Markdown link parsing from `content_markdown`.
- URL normalization, tracking parameter removal, and duplicate removal.
- Collection creation from a selected source article.
- Reuse of an existing `Article` for a linked URL.
- Extraction enqueue only when content is missing or failed.
- Prepare task idempotency.
- Generate task includes successful articles with full text.
- Generate task includes failed articles as placeholders.
- Generate task includes still-processing articles as timed-out placeholders.
- EPUB output order matches source link order.

Frontend tests can be added if a UI action is implemented in the same iteration:

- Article list exposes the external-link EPUB action through a visible row menu button.
- Desktop article list exposes the same action through the row context menu.
- Preview displays parsed links.
- Collection status displays full-text and placeholder counts.
