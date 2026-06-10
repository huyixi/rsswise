# Inline Feed Management Panel — 需求规格说明

## 1. 概述

当前在文章工作台（`/articles`）中点击侧边栏的 "+" 按钮会触发路由跳转到 `/feeds`，导致整个页面布局切换（顶部 AppHeader 出现、内容变为单列居中布局）。用户需要离开阅读视图来完成 Feed 管理操作，体验割裂。

本需求的目标：点击 "+" 后，工作台布局保持不变（侧边栏不动），仅将右侧的两列区域（文章列表 + 文章正文）替换为 Feed 管理面板，实现内联操作。

---

## 2. Current State（现状）

### 2.1 布局结构

- **`App.tsx`**（71-111 行）：`isWorkbench = pathname === "/articles"` 时，不渲染 `<AppHeader>`，`<Outlet>` 直接渲染。
- **`workbench.tsx`**（614-646 行）：三列布局 `flex h-screen overflow-hidden`：
  - 左列 `WorkbenchSidebar`（220px）
  - 中列 `ArticleListPanel`（320px）
  - 右列 `ArticleContentPanel`（flex-1）
- **`feeds/list.tsx`**：`FeedsPage` 是一个独立页面，包含添加表单、批量导入、Feed 列表（刷新/删除）。

### 2.2 当前行为

1. 用户在 `/articles` 工作台点击侧边栏 "+" 按钮
2. 按钮是 `<Link to="/feeds">`，触发路由跳转
3. URL 变为 `/feeds`，`isWorkbench` 变为 `false`
4. `<AppHeader>` 重新出现，内容区变为 `max-w-5xl` 单列居中布局
5. `<FeedsPage>` 渲染在这个容器中

### 2.3 关键代码位置

| 文件 | 行号 | 说明 |
|------|------|------|
| `apps/web/src/routes/articles/workbench.tsx` | 120-126 | 侧边栏 "+" Link，指向 `/feeds` |
| `apps/web/src/routes/articles/workbench.tsx` | 614-646 | 三列布局 return |
| `apps/web/src/routes/articles/workbench.tsx` | 97-206 | `WorkbenchSidebar` 组件 |
| `apps/web/src/routes/feeds/list.tsx` | 55-406 | `FeedsPage` 完整组件 |
| `apps/web/src/App.tsx` | 71-111 | `App` 布局切换逻辑 |

---

## 3. Target State（目标）

### 3.1 桌面端

- 点击侧边栏 "+" → 侧边栏保持不变，右侧两列（文章列表 + 文章正文）**替换为** Feed 管理面板。
- Feed 管理面板内容与当前 `/feeds` 页面完全一致（添加表单、批量导入、错误提示、导入结果、Feed 列表含刷新/删除操作）。
- URL 不变，保持在 `/articles?view=...&id=...`。
- 面板顶部有一个 **标题栏**（标题 "Feed 管理" + 关闭按钮）。
- 点击关闭按钮 → 面板消失，恢复原来的文章列表 + 文章正文两列。
- 侧边栏 "+" 按钮在面板打开时切换为关闭样式（提供视觉反馈）。
- 成功添加/导入 Feed 后，侧边栏 Feed 列表自动刷新（已有机制：`invalidateQueries`）。
- 面板关闭时，文章列表和侧边栏 Feed 列表保持刷新后的最新状态。
- 删除最后一个 Feed 后，面板内显示空状态（与当前 `/feeds` 一致），面板不自动关闭。

### 3.2 移动端（<800px）

- 当前移动端渲染单列文章列表（594-612 行）。
- 点击 "+" → 整个视口切换为 Feed 管理面板（整屏覆盖，不显示侧边栏）。
- 面板顶部有 **返回按钮** + 标题，点击返回到文章列表。
- 面板内容与桌面端一致。

### 3.3 独立 `/feeds` 路由

- `/feeds` 路由仍然保留，行为和现在完全一致（带 AppHeader 的单列布局）。
- AppHeader 中的 "Feed" 标签仍然跳转到 `/feeds`，不受影响。
- 实现方式：抽取可复用的 Feed 管理内容组件，`FeedsPage` 和 inline panel 共享。

---

## 4. Detailed Requirements

### R1：可复用的 Feed 管理内容组件

从 `FeedsPage` 中抽取纯内容部分为独立组件 `FeedManagementPanel`，不包含页面级外层包裹（标题 "Feed 管理" + RssIcon），不包含 `document.title` 设置。

提取后结构：
```
FeedsPage
  └── <div className="flex flex-col gap-6">
        └── <h1>Feed 管理</h1>
        └── <FeedManagementContent />   ← 纯内容

Workbench（桌面端）
  └── <WorkbenchSidebar />
  └── <FeedPanel isOpen>                ← 新组件
        └── <h2>Feed 管理</h2> + 关闭按钮
        └── <FeedManagementContent />

Workbench（移动端）
  └── <MobileFeedPanel isOpen>          ← 新组件，整屏
        └── 返回按钮 + <h2>Feed 管理</h2>
        └── <FeedManagementContent />
```

### R2：面板开关状态

- 使用 `useState<boolean>(false)` 管理 `isFeedPanelOpen` 状态，位于 `ArticleWorkbenchPage` 中。
- 状态仅存在于内存，不写入 URL，不写入 localStorage。
- 面板关闭时不保留表单状态（重新打开是空白表单）。
- 路由切换（离开 `/articles`）时面板自动关闭（组件卸载，state 自然丢失）。

### R3：侧边栏按钮变化

- "+" 改为 `<button>`（不再是 `<Link>`），点击切换 `isFeedPanelOpen`。
- 面板打开时图标变为 `X`（关闭），面板关闭时显示 `+`（打开）。
- aria-label 相应变化："添加 Feed" ↔ "关闭 Feed 管理"。
- 同时保留原有的 `<Link to="/feeds">` 作为次要入口：侧边栏底部空 Feed 状态中的文案仍然链接到 `/feeds`（149 行），不作改动。

### R4：桌面端面板样式

- 面板占据右侧剩余空间（`flex-1` 或替换掉原来的 `ArticleListPanel` + `ArticleContentPanel` 所在区域）。
- 面板带顶部标题栏：
  - 左：标题文字 "Feed 管理"
  - 右：关闭按钮（X 图标）
- 面板内容可滚动（`overflow-y-auto`）。
- 面板背景与文章内容区一致（`bg-card`）。

### R5：移动端整屏面板

- 面板渲染为 `fixed inset-0 z-50` 整屏覆盖层。
- 顶部有 sticky 标题栏：左侧返回箭头 + "Feed 管理"，右侧关闭按钮。
- 面板内容可滚动。

### R6：Feed 操作后的数据刷新

- `FeedManagementContent` 内的 mutation `onSuccess` 回调已有的 `invalidateQueries` 逻辑保持不变，确保侧边栏 Feed 列表也得到刷新。

---

## 5. Non-Goals（明确不做）

- 不改变 `/feeds` 独立路由的行为。
- 不改变 AppHeader 中 "Feed" 标签的跳转。
- 不在 URL 中编码面板开关状态。
- 不记住面板关闭前的滚动位置或表单输入。
- 不添加面板打开/关闭的过渡动画（如有需要可后续迭代）。
- 不支持面板与文章区域同时可见（非分屏模式）。
- 不做面板宽度可拖拽调整。

---

## 6. 影响范围

| 文件 | 变更类型 |
|------|----------|
| `apps/web/src/routes/feeds/list.tsx` | 修改：抽取 `FeedManagementContent` 组件，`FeedsPage` 改为引用它 |
| `apps/web/src/routes/articles/workbench.tsx` | 修改：添加面板 state、修改侧边栏按钮、条件渲染面板、移动端整屏面板 |
| `apps/web/src/App.tsx` | **不变**（`/feeds` 路由保持原样） |
