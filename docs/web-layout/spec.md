# Web Layout Redesign Spec

## Summary

RSSWise Web 端改为 Folo 优先的现代聚合阅读布局。目标是在不修改后端 API、数据库和持久化模型的前提下，重塑 `/articles` 的信息架构：左栏承载应用导航和全局入口，中栏承载紧凑文章流，右栏承载阅读内容。

本次是布局和信息架构优化，不是新增 RSS 产品功能。

## Goals

- 桌面端使用 Folo 式三栏布局：左侧导航、中间文章流、右侧阅读区。
- 左栏顶部集成原顶栏核心能力，减少顶部横向导航对内容区的占用。
- 中栏只展示文章标题和摘要，降低列表噪音，提高扫描效率。
- 右栏阅读区按固定顺序展示：标题、作者与时间、AI Block、正文。
- 左栏提供 `Today`、`Unread`、`All Articles`、`Deep Read`、`Skim`、`Skip`、`Feeds` 入口。
- 移动端保持列表到详情的两级导航，不引入三栏。
- 保留现有 API 合约和数据模型，所有入口都基于当前 `GET /articles?status_filter=` 与已返回字段完成。

## Non-Goals

- 不新增后端接口、数据库字段或迁移。
- 不新增收藏、稍后读、Feed 分组、文件夹、搜索或阅读进度。
- 不实现真实用户头像上传；头像只用占位符。
- 不把 Feed 添加做成新弹窗。左栏 `add` 图标第一版跳转到现有 `/feeds` 页面。
- 不改变 AI 分析的数据结构和生成流程。
- 不重写 Markdown 渲染或文章正文排版系统。

## Current State

当前 `/articles` 桌面端已经是工作台布局：

- `apps/web/src/App.tsx` 提供顶部横向导航、用户邮箱、邮件设置和退出按钮。
- `apps/web/src/routes/articles/workbench.tsx` 提供文章列表、正文阅读区、独立 AI 侧栏。
- `apps/web/src/routes/articles/detail.tsx` 在移动端提供 `/articles/:id` 详情页，桌面端重定向回 `/articles?id=...`。
- `apps/web/src/routes/articles/components.tsx` 提供文章头部、AI 总结、正文组件。
- `apps/web/src/routes/feeds/list.tsx` 负责 Feed 添加、刷新和删除。

当前问题：

- 顶栏和工作台分离，内容区没有形成 Folo 式应用外壳。
- 中栏文章项信息偏多，来源、时间、标签和摘要同时出现，扫描成本较高。
- AI 总结是独立右侧栏，导致正文阅读宽度和注意力被长期分割。
- 左侧没有 Today、AI 推荐等现代聚合入口。

## Target Information Architecture

### Desktop

桌面端 `/articles` 使用三栏：

```text
┌──────────────────────┬──────────────────────────────┬──────────────────────────────────────────────┐
│ Left navigation       │ Article stream                │ Reader                                       │
│                      │                              │                                              │
│ RSSWise  +  Avatar    │ Title                        │ Article title                                │
│ Today                 │ Summary                      │ Author/source + time                         │
│ Unread                │                              │ AI Block                                     │
│ All Articles          │ Title                        │ Body                                         │
│                       │ Summary                      │                                              │
│ AI                    │                              │                                              │
│ Deep Read             │                              │                                              │
│ Skim                  │                              │                                              │
│ Skip                  │                              │                                              │
│                       │                              │                                              │
│ Feeds                 │                              │                                              │
└──────────────────────┴──────────────────────────────┴──────────────────────────────────────────────┘
```

### Left Navigation

左栏替代当前顶部导航的主要空间职责。

Header：

- 左侧显示 `RSSWise`。
- 右侧显示 `add` icon，作为 Feed 添加入口。
- `add` icon 第一版跳转到 `/feeds`。
- 右侧显示用户头像占位符。可以使用邮箱首字母、固定圆形占位或 lucide 用户图标。
- 原顶栏的邮件摘要设置和退出登录不丢失，第一版放在左栏底部，保持轻量图标按钮形态。

Navigation entries：

- `Today`：当天发布的文章。由于后端没有 today filter，第一版在当前文章列表数据上前端过滤 `published_at` 为本地当天的文章。
- `Unread`：映射现有 `status=unread`。
- `All Articles`：映射现有无 `status` 参数。
- `Deep Read`：前端过滤 `reading_recommendation === "deep_read"`。
- `Skim`：前端过滤 `reading_recommendation === "skim"`。
- `Skip`：前端过滤 `reading_recommendation === "skip"`。
- `Feeds`：跳转 `/feeds`。

如果当前 API 返回的数据不足以支撑某个入口，界面显示空状态，不新增接口。

### Middle Article Stream

中栏只展示：

- 文章标题。
- 一句话摘要。

中栏不展示：

- 来源。
- 时间。
- 已读文字 badge。
- AI 推荐 badge。
- 原文链接。

未读状态用轻量视觉处理表示，例如标题加粗或左侧小圆点。避免占用额外文字空间。

选中态要清晰，支持当前已有的键盘上下切换行为。

### Right Reader

右栏是阅读主区域，不再把 AI 做成独立重侧栏。

顺序固定：

1. 第一行：文章标题。
2. 第二行：作者/来源 + 发布时间。
3. 第三块：AI Block。
4. 第四块：正文。

说明：

- 当前数据模型没有独立作者字段，第一版用 `source_title` 作为作者/来源显示。
- 时间使用现有 `published_at`。
- AI Block 复用 `ArticleAiSummary` 的现有结构化 block 展示能力。
- 正文复用 `ArticleBody` 与现有 Markdown 渲染。

### Global Actions

当前顶部栏中的能力调整：

- 退出登录保留，第一版放在左栏底部。
- 邮件摘要设置保留，第一版放在左栏底部。
- 用户邮箱不再作为顶部横向文本长期展示，可通过头像占位的 `title` 或辅助文本显示。

## Mobile Behavior

移动端不使用三栏。

- `/articles` 仍显示文章列表。
- 点击文章进入 `/articles/:id`。
- 移动列表也采用标题 + 摘要的简化文章项。
- 详情页顺序同步为：标题、作者/来源 + 时间、AI Block、正文。
- 左栏导航在移动端不作为常驻栏出现。第一版可以保留现有顶部应用栏和列表筛选，避免新增抽屉复杂度。

## Routing And URL State

文章入口状态继续使用 URL 查询参数，便于刷新和分享：

- `?view=today`
- `?status=unread`
- 无参数或 `?view=all`
- `?recommendation=deep_read`
- `?recommendation=skim`
- `?recommendation=skip`
- `?id=<article_id>` 继续表示桌面选中文章。

实现时要保证：

- 切换入口时清除 `id`，让系统重新选择当前过滤结果中的第一篇文章。
- 桌面端进入某个入口后，如果列表非空且未选中文章，自动选择第一篇。
- 键盘上下切换只在当前过滤后的列表内移动。

## Data Rules

第一版只使用现有文章列表数据：

- `id`
- `title`
- `published_at`
- `one_sentence_summary`
- `reading_recommendation`
- `is_read`
- `source_title`

过滤规则：

- `Unread` 请求后端 `status_filter=unread`。
- `All Articles` 请求后端 `status_filter=all`。
- `Today` 请求后端 `status_filter=all` 后前端过滤当天。
- `Deep Read / Skim / Skip` 请求后端 `status_filter=all` 后前端过滤推荐值。

如果未来后端增加原生过滤接口，可以在保持 URL 语义不变的前提下替换数据请求实现。

## Accessibility

- 左栏导航使用可识别的链接或按钮，并设置当前入口状态。
- `add` icon 必须有 `aria-label="添加 Feed"`。
- 用户头像占位必须有可访问名称，例如 `aria-label="当前用户"`。
- 中栏文章项继续使用 `button`，支持键盘选择。
- 图标按钮需要 tooltip 或明确 `aria-label`。

## Testing Requirements

需要更新或新增 Playwright 覆盖：

- `/articles` 桌面显示左栏导航，包含 `Today`、`Unread`、`All Articles`、`Deep Read`、`Skim`、`Skip`、`Feeds`。
- 中栏文章项只展示标题和摘要，不展示来源和时间。
- 点击 `Unread` 后 URL 和列表行为符合现有未读筛选。
- 点击 `Deep Read` 后只显示 `reading_recommendation = deep_read` 的文章。
- 点击文章后右栏按标题、来源时间、AI 总结、正文顺序显示。
- 移动端点击文章仍进入 `/articles/:id`，详情顺序与桌面一致。

## Rollout

1. 先改测试，锁定目标行为。
2. 抽出左栏导航和文章流小组件，避免继续扩大 `workbench.tsx`。
3. 调整桌面工作台布局。
4. 调整移动列表与详情排序。
5. 跑 lint、build、Playwright 关键用例。
