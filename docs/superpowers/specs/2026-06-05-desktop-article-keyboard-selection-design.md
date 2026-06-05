# Design: Desktop Article Default Selection And Keyboard Navigation

## Summary

Desktop `/articles` should open directly into a readable state. When the article list loads and no article is selected, the workbench selects the first article by default and shows its body. Desktop users can press ArrowUp and ArrowDown to move through the article list.

Mobile behavior stays unchanged: `/articles` shows only the list, tapping an article opens `/articles/:id`, and mobile does not auto-select a list item or handle keyboard article navigation.

## Current State

RSSWise web uses React, React Router, TanStack Query, and Vite.

Relevant files:

```text
apps/web/src/routes/articles/workbench.tsx
apps/web/src/routes/articles/detail.tsx
apps/web/tests/e2e/articles.spec.ts
```

Desktop workbench selection currently comes only from the `id` search param:

```text
/articles?id=<articleId>
```

If `/articles` has no `id`, the list renders but the center pane shows the empty prompt asking the user to select an article.

## Target Behavior

Desktop `/articles`:

- After the article list finishes loading, if no `id` is present and the list has at least one article, set `id` to the first article's id.
- Respect an existing `id` search param when present.
- Keep the selected article in the URL so refresh, sharing, browser navigation, and existing redirect behavior continue to work.
- Pressing ArrowDown selects the next article in the loaded list.
- Pressing ArrowUp selects the previous article in the loaded list.
- Navigation stops at boundaries. ArrowUp on the first article and ArrowDown on the last article do nothing.
- Status filter changes keep the existing behavior of clearing `id`; after the new filtered list loads, the first article in that filtered list becomes selected.
- Empty, loading, and error list states do not auto-select anything.

Mobile:

- Keep the current mobile list and detail behavior unchanged.
- Do not auto-select the first article on the mobile list.
- Do not add global keyboard navigation for mobile.

## Design

Use `?id=` as the single source of truth for selected article state. This matches the existing desktop workbench and avoids introducing a second React state value that can drift from the URL.

Add a desktop-only effect in `ArticleWorkbenchPage`:

1. Wait until the view is not mobile.
2. Wait until article list data exists and has at least one item.
3. If `selectedId` is absent, set `id` to the first article id using `setSearchParams`.

Add a desktop-only keydown effect:

1. Ignore mobile.
2. Ignore loading, empty, or missing selected article states.
3. Handle only `ArrowUp` and `ArrowDown`.
4. Find the current selected article index in `articlesQuery.data`.
5. Compute the next index without wrapping.
6. If the next index differs from the current index, update `id` through `setSearchParams`.

The handler should call `event.preventDefault()` only when it handles ArrowUp or ArrowDown for article navigation, so unrelated keys and text entry behavior remain unaffected.

## Testing And Acceptance

Update `apps/web/tests/e2e/articles.spec.ts` with desktop coverage:

- Visiting `/articles` with desktop viewport and at least one article automatically shows the first article body and updates the URL to `?id=<firstId>`.
- ArrowDown selects the next article and updates the body and URL.
- ArrowUp selects the previous article and updates the body and URL.
- ArrowUp at the first article stays on the first article.
- ArrowDown at the last article stays on the last article.
- Existing mobile tests continue to pass, proving mobile behavior was not changed.

Verification commands:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
```

## Out Of Scope

- No backend API changes.
- No database changes.
- No new route shape.
- No pagination, search, multi-select, focus ring redesign, or roving tabindex implementation.
- No keyboard shortcuts beyond ArrowUp and ArrowDown in the desktop article workbench.
