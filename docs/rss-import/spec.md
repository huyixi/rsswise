# RSS Import Spec

## Summary

Add a batch RSS import workflow to RSSWise. Users can import subscriptions from either an OPML file or a pasted multi-line URL list. The import runs in the background, reports per-feed results, and reuses the existing feed fetching, article upsert, extraction, and analysis pipeline.

This feature imports subscriptions only. It does not import folders, read state, favorites, article history, or reading progress.

## Decisions From Requirement Discovery

- Import sources:
  - OPML files (`.opml` / `.xml`).
  - Multi-line RSS URL text, one URL per line.
- Imported data scope:
  - Import feed subscriptions only.
  - After import, RSSWise fetches latest feed entries through the existing feed pipeline.
  - Do not import read state, favorites, folders, historical articles from another reader, or reading progress.
- Duplicate handling:
  - Detect duplicates within the same import batch before network fetching.
  - Keep duplicate input rows in the item list so the user can see they were skipped.
  - If the current user already subscribes to a feed, mark it as skipped.
  - If the feed exists globally but the current user is not subscribed, create only the user subscription.
  - If the feed does not exist, fetch it, create it, subscribe the user, upsert articles, and enqueue extraction for new articles.
- URL matching:
  - First version uses conservative normalized URL matching.
  - Do not attempt aggressive equivalence detection between different feed URLs.
- Execution model:
  - Imports are submitted as background jobs.
  - The API returns an import ID immediately.
  - The frontend polls import status and displays progress.
- Result visibility:
  - First version supports the current import task result by import ID.
  - No dedicated import history list.
  - A refreshed page can recover the current result if the frontend still has the import ID.
- OPML folders:
  - Recursively read OPML `outline` nodes.
  - Ignore folder hierarchy.
  - Preserve source titles where available for display and diagnostics.
- Failure handling:
  - Per-feed failures do not stop the whole import.
  - Failed items show a reason.
- Size limit:
  - A single import can contain at most 200 unique feed URLs.
  - Imports above this limit are rejected before a job is created.

## Current State

Relevant backend files:

```text
apps/api/app/routers/feeds.py
apps/api/app/services/feed_service.py
apps/api/app/tasks.py
apps/api/app/models.py
apps/api/app/schemas.py
apps/api/alembic/versions/
apps/api/tests/test_feed_service.py
apps/api/tests/test_feeds_api.py
apps/api/tests/test_tasks.py
```

Relevant frontend files:

```text
apps/web/src/routes/feeds/list.tsx
apps/web/src/lib/api.ts
apps/web/src/lib/query-keys.ts
apps/web/tests/e2e/feeds.spec.ts
```

Current feed behavior:

- `POST /feeds` adds one feed URL for the current user.
- `GET /feeds` lists the current user's subscriptions.
- `POST /feeds/{feed_id}/refresh` enqueues one feed refresh.
- `DELETE /feeds/{feed_id}` removes the current user's subscription.
- `Feed.url` is globally unique.
- `UserFeedSubscription` connects users to global feeds.
- New feed articles enqueue extraction through `extract_article_task`.

This feature should extend that model rather than introducing user-specific duplicate feed records.

## Goals

- Let users batch-import RSS subscriptions from OPML or pasted URL lists.
- Keep the import workflow reliable for slow or partially broken feed lists.
- Show progress and per-item results for the current import.
- Preserve existing single-feed add, refresh, delete, article extraction, and AI analysis behavior.
- Keep the first version scoped to Feed management.
- Make duplicate outcomes explicit: created, subscribed, skipped, failed.

## Non-Goals

- No OPML export.
- No import history page or full historical archive.
- No folder/category/tag import.
- No read state, favorite, saved item, annotation, or reading progress import.
- No automatic feed discovery from normal website URLs.
- No SSE or WebSocket progress stream.
- No aggressive duplicate detection across semantically similar but different URLs.
- No new article ownership model.

## Product Behavior

### Feed Management Page

The existing Feed management page keeps the single-feed URL form and adds a batch import entry point.

The entry point opens an import dialog or panel with two tabs:

- `OPML 文件`
- `多行 URL`

### OPML Import

The user selects an `.opml` or `.xml` file. The frontend reads the file as text and sends the XML string to the backend.

The backend parses OPML recursively. A feed candidate is any outline node with a feed URL, preferring `xmlUrl`. If a title exists, use `title` or `text` as the source title for the import item.

Folder outlines without feed URLs are traversal containers only.

### Multi-line URL Import

The user pastes URLs into a textarea. The backend splits by line, trims whitespace, drops empty lines, validates URL shape, normalizes conservatively, and detects duplicates within the batch.

### Import Result Display

After submit, the API returns an import ID. The frontend shows the current task result on the Feed management page or inside the dialog:

- Total count.
- Processed count.
- Created count.
- Subscribed count.
- Skipped count.
- Failed count.
- A list of items with title or URL, status, and failure reason when relevant.

The frontend polls the job endpoint, for example every 2 seconds, while the job is pending or processing. Polling stops when the job reaches a terminal state.

When the job completes, the frontend invalidates feed and article queries.

## Data Model

Add a database migration for import jobs and items.

### FeedImportJob

Suggested table: `feed_import_jobs`

Fields:

- `id`: UUID primary key.
- `user_id`: UUID foreign key to `users.id`, indexed, cascade delete.
- `source_type`: enum or string, values `opml` and `urls`.
- `status`: enum or string, values `pending`, `processing`, `completed`, `failed`.
- `total_count`: integer, counting all created import items, including duplicate items that will be skipped.
- `processed_count`: integer.
- `created_count`: integer.
- `subscribed_count`: integer.
- `skipped_count`: integer.
- `failed_count`: integer.
- `error_message`: nullable text for task-level failures.
- `created_at`: datetime.
- `started_at`: nullable datetime.
- `finished_at`: nullable datetime.

Status semantics:

- `pending`: job and items are created, Celery task has been queued.
- `processing`: worker has started processing.
- `completed`: all items were processed. This includes jobs where some items failed.
- `failed`: task-level failure prevented normal item processing.

### FeedImportItem

Suggested table: `feed_import_items`

Fields:

- `id`: UUID primary key.
- `job_id`: UUID foreign key to `feed_import_jobs.id`, indexed, cascade delete.
- `source_title`: nullable string.
- `raw_url`: string.
- `normalized_url`: string, indexed.
- `dedupe_key`: string, indexed. For the first version this can match `normalized_url`.
- `status`: enum or string, values `pending`, `created`, `subscribed`, `skipped`, `failed`.
- `feed_id`: nullable UUID foreign key to `feeds.id`.
- `message`: nullable text for a short user-facing result or failure reason.
- `created_at`: datetime.
- `processed_at`: nullable datetime.

Item status semantics:

- `pending`: not processed yet.
- `created`: a new global `Feed` was created and subscribed for the current user.
- `subscribed`: an existing global `Feed` was subscribed for the current user.
- `skipped`: no work was needed because the current user already subscribed, or because the item duplicated an earlier item in the same import.
- `failed`: this item could not be imported.

## Backend API

### Create Import

`POST /feeds/imports`

Request shape:

```json
{
  "source_type": "urls",
  "urls_text": "https://example.com/feed.xml\nhttps://example.org/rss"
}
```

or:

```json
{
  "source_type": "opml",
  "opml_xml": "<?xml version=\"1.0\"?><opml>...</opml>"
}
```

Behavior:

- Requires authentication.
- Parses candidates from the selected source.
- Detects duplicates conservatively by normalized URL.
- Rejects if no valid feed URLs are found.
- Rejects if more than 200 unique URLs are found.
- Creates one job and one item per accepted input candidate, including duplicates.
- Enqueues a Celery import task.
- Returns the created job summary.

Response shape:

```json
{
  "id": "uuid",
  "source_type": "urls",
  "status": "pending",
  "total_count": 2,
  "processed_count": 0,
  "created_count": 0,
  "subscribed_count": 0,
  "skipped_count": 0,
  "failed_count": 0,
  "items": []
}
```

The create response returns a job summary with `items: []`. The get endpoint returns full item details.

### Get Import

`GET /feeds/imports/{import_id}`

Behavior:

- Requires authentication.
- Returns 404 if the import does not exist or does not belong to the current user.
- Returns job summary and item results.

Response shape:

```json
{
  "id": "uuid",
  "source_type": "opml",
  "status": "completed",
  "total_count": 3,
  "processed_count": 3,
  "created_count": 1,
  "subscribed_count": 1,
  "skipped_count": 1,
  "failed_count": 0,
  "error_message": null,
  "created_at": "2026-06-10T12:00:00",
  "started_at": "2026-06-10T12:00:01",
  "finished_at": "2026-06-10T12:00:30",
  "items": [
    {
      "id": "uuid",
      "source_title": "Example Feed",
      "raw_url": "https://example.com/feed.xml",
      "normalized_url": "https://example.com/feed.xml",
      "status": "created",
      "feed_id": "uuid",
      "message": null,
      "processed_at": "2026-06-10T12:00:05"
    }
  ]
}
```

## Backend Services

Add a feed import service module or extend the existing feed service with small, testable functions:

- `parse_urls_text(text: str) -> list[FeedImportCandidate]`
- `parse_opml_feeds(xml: str) -> list[FeedImportCandidate]`
- `normalize_feed_url(url: str) -> str`
- `prepare_import_candidates(candidates) -> PreparedImport`
- `create_feed_import_job(db, user, source_type, candidates) -> FeedImportJob`
- `process_feed_import_job(db, job_id) -> None`
- `import_feed_item(db, user, item) -> FeedImportItemResult`

The import path should reuse existing feed parsing and article upsert behavior. If the existing `add_feed_from_url` service is too coarse, split out a lower-level function that can report whether it created a feed, subscribed to an existing feed, skipped an existing subscription, or failed.

Recommended lower-level result statuses:

- `created`
- `subscribed`
- `skipped`
- `failed`

## Background Task Flow

Add a Celery task named `feeds.import`.

Flow:

1. Load the job.
2. Mark the job `processing` and set `started_at`.
3. Process pending items in a stable order.
4. For each item:
   - If an earlier item in the same job already used the same `dedupe_key`, mark `skipped`.
   - Else check if current user already subscribes to `normalized_url`.
   - If yes, mark `skipped`.
   - Else check whether global `Feed.url == normalized_url`.
   - If global feed exists, create `UserFeedSubscription`, mark `subscribed`.
   - Else fetch feed XML, parse feed items, create `Feed`, upsert articles, enqueue extraction, mark `created`.
   - On item-level exception, mark `failed` with a concise reason.
   - Increment processed and status counters.
5. Mark the job `completed` and set `finished_at`.
6. If an unexpected task-level exception prevents normal processing, mark the job `failed`, set `error_message`, and set `finished_at`.

Each item should commit its result independently or in small transactions so one broken feed does not discard previous progress.

## URL Normalization

First-version normalization should be conservative:

- Trim leading and trailing whitespace.
- Require `http` or `https`.
- Preserve path, query string, and scheme.
- Preserve trailing slashes.

Do not:

- Convert `http` to `https`.
- Drop query parameters.
- Remove trailing slashes.
- Resolve redirects for dedupe.
- Guess that different paths are the same feed.

## Frontend Design

### API Types

Add frontend types for:

- `FeedImportSourceType`
- `FeedImportJobStatus`
- `FeedImportItemStatus`
- `FeedImportItem`
- `FeedImportJob`
- `FeedImportCreateRequest`

Add API helpers through existing `apiPost` and `apiGet`.

### Feed Import Dialog

The dialog or panel should include:

- Tabs for `OPML 文件` and `多行 URL`.
- File picker for OPML/XML.
- Textarea for multi-line URLs.
- Submit button with loading state.
- Validation message for missing input.
- Import progress section after submit.
- Item results with compact status labels.

The UI should remain consistent with the current restrained Feed management page. It should not become a separate landing flow.

### Polling

After creating a job:

- Store the current `import_id` in component state.
- Poll `GET /feeds/imports/{import_id}` while status is `pending` or `processing`.
- Stop polling on `completed` or `failed`.
- Invalidate `queryKeys.feeds.all` and `queryKeys.articles.all` when the job reaches a terminal state.

Persist the current `import_id` in local storage so the Feed management page can recover the current import after refresh. Clear it once the user dismisses the result or starts another import.

## Error Handling

Create import endpoint errors:

- Invalid request shape: 422.
- OPML parse failure: 400.
- OPML or URL input contains no feed URLs: 400.
- More than 200 unique URLs: 400.

Get import endpoint errors:

- Missing or unauthorized import: 404.

Item-level failures:

- Invalid URL.
- Fetch timeout.
- Network failure.
- Invalid or empty feed XML.
- Feed parser errors that prevent extracting feed metadata.
- Database integrity conflicts that cannot be recovered.

Feeds with zero current entries can still be imported if feed metadata is readable.

Failure messages should be concise and user-facing. Internal exception details should stay out of API responses.

## Accessibility

- The import entry point must be keyboard accessible.
- The dialog must have an accessible title.
- Tabs must expose selected state.
- File input and textarea need visible labels.
- Progress and result text must not rely only on color.
- Status labels should use visible words such as `新建`, `已订阅`, `已存在`, `失败`.

## Testing

Backend service tests:

- Parse multi-line URLs and ignore blank lines.
- Parse nested OPML outlines and ignore folder-only outlines.
- Reject OPML with no feed URLs.
- Detect duplicate candidates within a batch.
- Preserve duplicate input rows as skipped import items.
- Enforce 200 unique URL limit.
- Existing current-user subscription becomes `skipped`.
- Existing global feed without current-user subscription becomes `subscribed`.
- New feed becomes `created` and enqueues extraction for new articles.
- Item-level fetch or parse failure marks only that item failed.

Backend API tests:

- Authenticated user can create URL import.
- Authenticated user can create OPML import.
- Unauthenticated requests are rejected.
- User cannot read another user's import job.
- Create endpoint rejects too many URLs.
- Get endpoint returns job counters and item results.

Celery task tests:

- Job moves from `pending` to `processing` to `completed`.
- Counters match item outcomes.
- Partial failures do not fail the whole job.
- Task-level failure marks the job failed.

Frontend tests:

- Feed page exposes batch import entry point.
- Multi-line URL import submits and displays progress.
- OPML file import reads file text and submits.
- Completed import refreshes feed and article queries.
- Failed item messages are visible.

Regression coverage:

- Existing single-feed add still works.
- Existing feed refresh still works.
- Existing feed delete still works.
