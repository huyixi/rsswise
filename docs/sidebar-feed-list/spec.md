# Spec: 左侧栏 Feed 列表 & 中间栏筛选

## 目标

将侧边栏改造为展示所有订阅 Feed，筛选控件移至中间栏顶部。

## 布局定稿

```
┌───────────────────┬──────────────────────┬────────────────────┐
│  左侧栏 220px     │  中间栏 320px        │  右侧栏 flex-1     │
│                   │                      │                    │
│ RSSWise      [+]  │ [Today][Unr][All]    │  文章正文          │
│                   │ [Deep][Skim][Skip]   │                    │
| ● All Articles    │ ──────────────────── │                    │
│ ───────────────── │ 文章列表             │                    │
│ ○ Feed A          │                      │                    │
│ ○ Feed B          │                      │                    │
│ ○ Feed C          │                      │                    │
│                   │                      │                    │
│ 用户菜单          │                      │                    │
└───────────────────┴──────────────────────┴────────────────────┘
```

## 改动清单

### 1. 后端：`apps/api/app/routers/articles.py`

- `list_articles()` 新增参数 `feed_id: UUID | None = None`
- 当 `feed_id` 非空时，在 `statement` 上追加 `.where(Article.feed_id == feed_id)`

### 2. 前端：`apps/web/src/routes/articles/workbench.tsx`

#### 2a) `ArticleWorkbenchPage` 主组件

**新增：**
- `useQuery` feeds：`queryKeys.feeds.list()` → `apiGet<Feed[]>("/feeds")`
- `feedId` 从 URL：`searchParams.get("feed_id")`
- `handleSelectFeed(feedId: string | null)`：toggle `feed_id`，点同一 feed 取消选中，不影响其他 params
- 文章 API 追加 `&feed_id=${feedId || ""}` 参数
- Props 传递：`feeds`/`feedId`/`onSelectFeed` → `WorkbenchSidebar`
- Props 传递：`view`/`recommendation`/`onSelectView`/`onSelectRecommendation`/`feedName` → `ArticleListPanel`

**修改：**
- `handleSelectView`：不再删除 `recommendation`，保留彼此独立
- `handleSelectRecommendation`：不再删除 `view` 和 `status`，保留彼此独立

**新增 `feedName` 计算：**
```ts
const selectedFeed = feeds?.find(f => f.id === feedId)
const feedName = selectedFeed?.title ?? selectedFeed?.url ?? null
```

#### 2b) `WorkbenchSidebar`（左侧）

**Props 变更：**
- 移除：`view`, `recommendation`, `onSelectView`, `onSelectRecommendation`
- 新增：`feeds: Feed[] | undefined`, `feedId: string | null`, `onSelectFeed: (id: string | null) => void`

**UI 布局（自上而下）：**
1. Logo + Plus 链接 → 保留不变
2. `All Articles` 按钮 → `navButtonClassName(feedId === null)`，点击调用 `onSelectFeed(null)`
3. 分隔线 `<div className="mx-2 border-t my-1" />`
4. Feed 列表区域（`flex-1 overflow-y-auto`）：
   - 每个 feed 按钮：`navButtonClassName(feed.id === feedId)`，点击调用 `onSelectFeed(feed.id)`
   - 有 favicon 时左侧显示 `<img>`，无 favicon 不占位
   - 标题 `truncate`
5. 用户菜单 → 保留不变

**加载/空态：**
- feeds 加载中 → Skeleton 占位符
- feeds 为空 → "暂无订阅" 提示 + 链接到 `/feeds`

#### 2c) `ArticleListPanel`（中间）

**Props 变更：**
- 移除：`title`
- 新增：`view`, `recommendation`, `onSelectView`, `onSelectRecommendation`, `feedName`

**Header 改造：**

两行 segmented-control 按钮组（`rounded-md bg-muted p-0.5` 包裹，选中项 `bg-background shadow-sm`），紧凑尺寸适配 320px 宽度。

行一：`Today` / `Unread` / `All Articles`
行二：`Deep Read` / `Skim` / `Skip`

选中 feed 时顶部显示 feed 名小字副标题。

样式复用现有 `navButtonClassName` 风格但更紧凑（`text-xs`）。

### 3. Search Params 独立性

| Param | 来源 | 作用 |
|-------|------|------|
| `feed_id` | URL | 后端过滤特定 Feed |
| `status` | URL | 后端过滤 read/unread |
| `view` | URL | 前端过滤 today |
| `recommendation` | URL | 前端过滤 deep_read/skim/skip |

四个参数完全独立：
- `feed_id` toggle 自己，不碰其他
- `view` 设置自己，不碰 `recommendation` 和 `feed_id`（`status` 联动保留：unread → status=unread）
- `recommendation` 设置自己，不碰 `view` 和 `feed_id`
