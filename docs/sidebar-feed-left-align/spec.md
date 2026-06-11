# Sidebar Feed Left-Align

## Problem

左侧栏（`WorkbenchSidebar`）的 feed 列表项中，favicon 与标题文字被 `justify-between` 推到了两端：favicon 紧贴左侧、标题紧贴右侧，视觉效果分散。

## Scope

- **只改左侧栏**（`apps/web/src/routes/articles/workbench.tsx` 中的 `WorkbenchSidebar` 组件）
- Feed 管理面板（`FeedManagementContent`）和其他区域不做改动

## Current Behavior

`navButtonClassName` 返回 `flex w-full items-center justify-between ...`，当 feed 有 favicon 时，`justify-between` 将 img 和 span 两个 flex 子项分别推到容器两端。

## Expected Behavior

favicon 与标题文字在按钮内**靠左紧挨排列**，间距 `gap-2`。

- 有 favicon 时：`[favicon] —— [标题文字]` 整体靠左
- 无 favicon 时：标题文字单独靠左（与现有行为一致）
- "All Articles" 按钮不受影响（只有一个 span 子项）

## Technical Change

修改 `navButtonClassName` 的 Tailwind 类：

| 当前 | 改为 |
|---|---|
| `justify-between` | `justify-start gap-2` |

## Files

| File | Change |
|---|---|
| `apps/web/src/routes/articles/workbench.tsx` | `navButtonClassName` 中的 `justify-between` → `justify-start gap-2` |

## Non-goals

- 不改 sidebar 整体布局（220px 宽度、border-r、padding 等不变）
- 不改文章列表、阅读面板等任何其他区域
- 不改 Feed 管理面板中的卡片样式
