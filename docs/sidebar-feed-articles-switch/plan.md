# Plan: 左侧栏点击 Feed 后右侧文章列表切换

## Step 1: 更新 queryKeys.articles.list 签名

**文件**: `apps/web/src/lib/query-keys.ts`

- `list` 函数增加第二个参数 `feedId?: string | null`
- 将 `feedId` 纳入返回的 query key 中

```ts
// 改前
list: (status: string) => ["articles", "list", { status }] as const,

// 改后
list: (status: string, feedId?: string | null) =>
  ["articles", "list", { status, feedId: feedId || undefined }] as const,
```

## Step 2: 更新 workbench.tsx 中的 articlesQuery

**文件**: `apps/web/src/routes/articles/workbench.tsx`

- `articlesQuery` 的 `queryKey` 从 `queryKeys.articles.list(status)` 改为 `queryKeys.articles.list(status, feedId)`

```ts
// 改前
queryKey: queryKeys.articles.list(status),

// 改后
queryKey: queryKeys.articles.list(status, feedId),
```

## Step 3: 增加 e2e 回归测试

**文件**: `apps/web/tests/e2e/articles.spec.ts`

增加桌面端 workbench 用例：

1. mock `/api/feeds` 返回至少 1 个 feed
2. mock `/api/articles?status_filter=all` 返回全局文章列表
3. mock `/api/articles?status_filter=all&feed_id=<id>` 返回该 feed 的不同文章列表
4. 进入 `/articles`
5. 点击左侧栏 feed，断言 URL 包含 `feed_id=<id>`
6. 断言中间栏显示该 feed 的文章，不显示全局文章
7. 再次点击同一个 feed，断言 URL 删除 `feed_id`
8. 断言中间栏恢复全局文章
9. 断言 `view` 和 `recommendation` 查询参数在 feed 切换后保留

注意：桌面端当前会在文章列表非空时自动选中第一篇文章，因此测试不应断言右侧内容区停留在「选择一篇文章开始阅读」空态。

## Step 4: 验证

运行前端：

```sh
cd apps/web
pnpm dev
```

执行以下手工验证：

1. 点击左侧栏任意 Feed → 中间栏文章列表切换为该 feed 的文章
2. 文章列表在加载中显示 Skeleton 占位符
3. 选中 feed 下有文章时，桌面端右侧内容区自动加载该列表第一篇文章
4. 点击已选中的 Feed → 回到 All Articles，文章列表恢复为全局文章
5. view 筛选器（Today/Unread/All）在 feed 切换后保持选中状态
6. recommendation 筛选器在 feed 切换后保持选中状态
7. 选中一个无文章的 Feed → 中间栏显示「暂无文章」，右侧内容区显示「选择一篇文章开始阅读」

运行自动化验证：

```sh
cd apps/web
pnpm test:e2e -- tests/e2e/articles.spec.ts
pnpm build
```
