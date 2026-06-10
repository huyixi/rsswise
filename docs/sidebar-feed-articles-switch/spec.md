# Spec: 左侧栏点击 Feed 后右侧文章列表切换

## 问题

当前左侧栏点击 Feed 后，URL 中的 `feed_id` 参数已正确更新，`handleSelectFeed` 逻辑完整，API 调用也已拼接 `&feed_id=` 参数。但由于 `articlesQuery` 的 `queryKey` 只依赖 `status`，不包含 `feedId`，导致 React Query 不会重新发起请求——用户看到的是缓存中的旧数据，文章列表不会切换。

## 根因

`apps/web/src/routes/articles/workbench.tsx:489-490`：

```ts
const articlesQuery = useQuery({
  queryKey: queryKeys.articles.list(status),  // ← 缺少 feedId
  queryFn: () => {
    let url = `/articles?status_filter=${encodeURIComponent(status)}`
    if (feedId) url += `&feed_id=${encodeURIComponent(feedId)}`
    return apiGet<ArticleListItem[]>(url)
  },
})
```

以及 `apps/web/src/lib/query-keys.ts:6-8`：

```ts
articles: {
  all: ["articles"] as const,
  list: (status: string) => ["articles", "list", { status }] as const,  // ← 无 feedId 参数
  detail: (id: string) => ["articles", "detail", id] as const,
},
```

## 解决方案

将 `feedId` 纳入 `queryKey`，使 React Query 在 feed 切换时自动 refetch。

## 行为定稿

### 点击 Feed 时的状态变化

| 行为 | 说明 |
|------|------|
| `id`（当前选中文章） | 清空 |
| `view`（Today/Unread/All） | 保留不重置 |
| `recommendation`（Deep Read/Skim/Skip） | 保留不重置 |
| 文章列表 | 重新请求该 feed 下的文章 |
| 右侧内容区（桌面端） | 若新列表有文章，沿用当前 workbench 行为自动选中第一篇并加载详情；若无文章，显示「选择一篇文章开始阅读」空态 |
| 右侧内容区（移动端） | 仍停留在文章列表，点击文章后进入独立详情页 |

### Toggle 行为

- 点击未选中的 feed → 选中该 feed，设置 `feed_id`
- 点击已选中的 feed → 取消选中，删除 `feed_id`，回到 All Articles

### 加载状态

- 切换 feed 时，因 `queryKey` 变化，若新 key 无缓存数据，`isLoading` 为 `true`，文章列表显示 Skeleton 占位符
- 回到 All Articles 时，若已有缓存且未过期（staleTime 30s），直接展示缓存数据；否则后台 refetch

### 自动选中文章与空文章状态

- 选中 feed 下无文章时，文章列表显示「暂无文章」空态
- 右侧内容区继续显示「选择一篇文章开始阅读」
- 选中 feed 下有文章时，桌面端会自动选中该列表第一篇文章；这是现有 workbench 行为，本次修复不改变

### 不应添加

- Feed 列表项上不显示未读文章数徽标

## 涉及文件

| 文件 | 改动 |
|------|------|
| `apps/web/src/lib/query-keys.ts` | `articles.list()` 增加 `feedId` 参数 |
| `apps/web/src/routes/articles/workbench.tsx` | `articlesQuery` 的 `queryKey` 传入 `feedId` |
