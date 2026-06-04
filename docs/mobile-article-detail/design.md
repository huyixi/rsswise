# Design: Mobile Article Detail

## Summary

为 RSSWise 增加移动端文章详情阅读链路：移动端从文章列表点击进入独立详情页，详情页上方展示 AI 总结，下方展示文章正文。

桌面端保持现有 `/articles` 工作台形态不变：左侧文章列表、中间正文、右侧 AI 分析侧栏。移动端使用 `/articles/:id` 独立详情页，桌面端直接打开 `/articles/:id` 时自动回到 `/articles?id=:id` 工作台视图。

本次只改前端路由、组件拆分、移动端展示和前端测试，不改后端 API、数据库 schema 或 AI 分析流程。

## Decisions From Requirement Discovery

- 路由策略：桌面保留 `/articles?id=<articleId>` 工作台；移动端点击列表进入 `/articles/:id`。
- 桌面直链：桌面端打开 `/articles/:id` 自动重定向到 `/articles?id=<articleId>`，不渲染独立详情页。
- 移动端列表页：`/articles` 在移动端只显示文章列表和筛选，不在列表页下方堆叠详情。
- 移动端详情顺序：返回入口、文章标题区、AI 总结、正文。
- 移动端 AI 区域：只展示阅读建议、一句话摘要、阅读理由。
- 移动端详情不展示处理状态、不展示“重新 AI 分析”、不展示“标记未读”。
- 移动端进入详情页后自动标记已读，和现有桌面工作台行为一致。
- 实现方式：新增移动详情页入口，并抽出共享展示组件，避免工作台和移动详情重复维护展示逻辑。

## Current State

RSSWise Web 是 React + Vite + React Router + TanStack Query 应用。

相关文件：

```text
apps/web/src/router.tsx                     # 当前 /articles/:id 会重定向到 /articles
apps/web/src/routes/articles/workbench.tsx  # 当前 /articles 工作台
apps/web/src/routes/articles/detail.tsx     # 旧独立详情实现，当前未接入路由
apps/web/src/hooks/use-media-query.ts       # 已有 useIsMobile()，max-md 作为移动端判断
apps/web/src/lib/api.ts                     # ArticleListItem / ArticleDetail 类型
apps/web/src/lib/query-keys.ts              # articles list/detail query key
apps/web/src/components/markdown-content.tsx
apps/web/src/components/recommendation-badge.tsx
apps/web/tests/e2e/articles.spec.ts
```

当前路由中：

```text
/articles      -> ArticleWorkbenchPage
/articles/:id  -> Navigate to /articles
```

当前工作台中：

- 列表点击只修改 search param：`?id=<articleId>`。
- 选中文章后请求 `GET /articles/{id}`。
- 进入选中文章后调用 `POST /articles/{id}/read` 自动标记已读。
- 处理中的正文或 AI 分析会每 3 秒轮询详情接口。
- 桌面为工作台形态；窄屏当前会把列表、正文、AI 侧栏堆叠在同一个 `/articles` 页面里。

## Target Behavior

### `/articles`

桌面端：

- 保持现有工作台行为。
- 列表点击只更新 `?id=<articleId>`。
- 详情和 AI 侧栏继续在工作台内展示。
- 操作能力不减少，包括标记已读、重新分析等现有能力。

移动端：

- 只显示文章列表和状态筛选。
- 列表项点击进入 `/articles/:id`。
- 不在列表页下方堆叠正文或 AI 侧栏。
- 保留现有列表信息：标题、来源、发布时间、一句话摘要、阅读建议、已读/未读状态。

### `/articles/:id`

移动端：

- 渲染独立文章详情页。
- 顶部提供返回文章列表入口。
- 展示文章标题区：来源、发布时间、标题、阅读原文链接。
- 在正文前展示 AI 总结区。
- AI 总结区只展示阅读建议、一句话摘要、阅读理由。
- 正文区使用 `MarkdownContent` 渲染完整 `content_markdown`。
- 进入页面后自动标记已读。

桌面端：

- `MobileArticleDetailPage` 顶层使用 `useIsMobile()` 判断。
- 非移动端不请求详情数据、不渲染详情内容。
- 直接重定向到 `/articles?id=<articleId>`。

## Component Design

### Route Components

`ArticleWorkbenchPage` 继续负责 `/articles`。

需要调整的点：

- 根据 `useIsMobile()` 区分列表项目标：
  - 桌面：调用现有 `handleSelectArticle(id)`，更新 search param。
  - 移动：导航到 `/articles/${id}`。
- 移动端只渲染 `ArticleListPanel`。
- 桌面端继续渲染列表、正文和 AI 侧栏。

`MobileArticleDetailPage` 负责 `/articles/:id`。

职责：

- 读取 route param `id`。
- 顶层判断 `useIsMobile()`。
- 桌面端返回 `<Navigate to={`/articles?id=${id}`} replace />`。
- 移动端请求文章详情、处理加载/错误/空状态。
- 移动端进入详情后调用标记已读 mutation。
- 处理中的详情沿用现有 3 秒轮询策略。

### Shared Display Components

为减少重复，抽出小型共享组件。建议放在文章路由目录内，例如：

```text
apps/web/src/routes/articles/components.tsx
```

建议组件：

- `ArticleHeader`
  - 输入：`ArticleDetail`
  - 输出：来源、发布时间、标题、阅读原文链接
- `ArticleAiSummary`
  - 输入：`ArticleDetail`
  - 输出：阅读建议、一句话摘要、阅读理由，缺失时显示轻量处理中状态
- `ArticleBody`
  - 输入：`contentMarkdown`
  - 输出：`MarkdownContent` 或“正文处理中……”

工作台正文区复用 `ArticleHeader` 和 `ArticleBody`。工作台 AI 侧栏可以复用 `ArticleAiSummary` 的部分展示，也可以保留侧栏布局，但不应复制摘要文案映射逻辑。

## Data Flow

继续使用现有 API：

```text
GET  /articles?status_filter=<all|read|unread>
GET  /articles/{id}
POST /articles/{id}/read
```

不新增后端接口。

移动详情页使用：

- `apiGet<ArticleDetail>(/articles/${id})`
- `apiPost(/articles/${id}/read)`
- `queryKeys.articles.detail(id)`
- `queryKeys.articles.all`

进入移动详情后：

1. 如果 `id` 缺失，显示“文章 ID 无效”。
2. 如果是桌面端，立即重定向，不请求详情。
3. 如果是移动端，请求文章详情。
4. 首次进入该 `id` 后调用标记已读 mutation。
5. 标记已读成功后 invalidate 当前详情和文章列表缓存。
6. 当 `extraction_status` 或 `analysis_status` 为 `processing` 时，每 3 秒轮询详情。

## Loading, Empty, And Error States

列表页：

- 加载中：保留现有 skeleton。
- 加载失败：显示现有错误文案。
- 空列表：显示“暂无文章”。

移动详情页：

- 无效 ID：显示“文章 ID 无效”。
- 加载中：显示 spinner 和“加载文章中”。
- 加载失败：显示 API 错误或“加载文章失败”。
- AI 无可展示内容：显示“AI 总结处理中”。
- 正文缺失：显示“正文处理中……”。

## Visual Design

移动详情页延续当前 coss docs 风格：

- 浅色背景、细边框、紧凑信息层级。
- 不新增抽屉、sheet、菜单、复杂手势或营销式布局。
- 文章标题使用清晰但不过大的移动端字号。
- AI 总结区是正文前的轻量 section，不使用厚重卡片。
- 正文区域保持 `MarkdownContent` 的可读排版。
- 图标使用 `lucide-react`，装饰性图标带 `aria-hidden="true"`。

## Testing And Acceptance

前端 E2E 需要覆盖：

- 移动端 `/articles` 只显示列表和筛选，不显示详情空状态。
- 移动端点击文章列表项进入 `/articles/:id`。
- 移动端详情页中 AI 总结出现在正文之前。
- 移动端进入详情页会请求 `POST /articles/{id}/read`。
- 桌面端打开 `/articles/:id` 会重定向到 `/articles?id=:id`。
- 桌面端 `/articles` 工作台列表点击仍停留在 `/articles?id=:id`。

验证命令：

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
```

## Out Of Scope

- 不改后端 API、数据库模型或 AI 分析任务。
- 不新增收藏、稍后读、阅读进度、分享按钮或搜索。
- 不在移动详情页提供“重新 AI 分析”或“标记未读”。
- 不新增桌面独立详情形态。
- 不改 Feed 管理页。
