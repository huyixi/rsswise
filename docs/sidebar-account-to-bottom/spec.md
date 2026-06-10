# Sidebar Account to Bottom Spec

## Summary

将 `WorkbenchSidebar` 顶部的账号入口（邮箱 + DropdownMenu）迁移到底部，顶部只保留 RSSWise 品牌名和添加 Feed 的 `+` 按钮。同时移除侧栏导航中多余的 Feeds 链接。

## Goals

- 侧栏顶部精简为 `RSSWise | +`，移除邮箱和 DropdownMenu。
- 侧栏底部新增账号区：邮箱文字 + 可点击 DropdownMenu（邮件摘要设置 / 退出登录）。
- 底部账号区与上方导航区之间以 `border-t` 分隔。
- 移除侧栏导航中现有的 Feeds 导航链接（功能已由顶部 `+` 按钮承载）。
- 保持现有功能行为不变（邮件摘要设置弹窗、退出登录逻辑、`+` 跳转 `/feeds`）。

## Non-Goals

- 不引入 Avatar 头像组件。
- 不改变邮件摘要设置弹窗的内部实现。
- 不改变退出登录的流程。
- 不改变其他页面（/feeds、/login 等）的布局。
- 不新增后端接口或数据库变更。

## Current State

`WorkbenchSidebar`（`apps/web/src/routes/articles/workbench.tsx`）顶部（第 118-153 行）：

```tsx
<aside className="flex w-[220px] shrink-0 flex-col border-r bg-background px-3 py-3">
  <div className="flex items-center gap-2">
    <h1>RSSWise</h1>
    <DropdownMenu>
      <DropdownMenuTrigger>{userEmail ?? "当前用户"}</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onSelect={...}>邮件摘要设置</DropdownMenuItem>
        <DropdownMenuItem onSelect={onLogout}>退出登录</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    <Link to="/feeds"><PlusIcon /></Link>
  </div>
  <nav>
    ...
    <div className="mt-auto">
      <Link to="/feeds">Feeds</Link>  <!-- 多余入口 -->
    </div>
  </nav>
  <EmailDigestSettingsDialog ... />
</aside>
```

## Target State

### Desktop Sidebar Layout

```
┌───────────────────────────┐
│ RSSWise             [+]  │  ← 顶部：品牌名 + 添加按钮
├───────────────────────────┤
│ Today                     │
│ Unread                    │
│ All Articles              │
├───────────────────────────┤
│ AI                        │
│ Deep Read                 │
│ Skim                      │
│ Skip                      │
├───────────────────────────┤  ← border-t 分隔线
│ 用户邮箱 ▼                │  ← 底部：账号区（点击弹出 DropdownMenu）
└───────────────────────────┘
```

### 顶部区域

```
RSSWise                        [+]
```

- `RSSWise`：品牌名，左对齐，不可点击（保持不变）。
- `+`：跳转 `/feeds`，右侧对齐（保持不变）。
- 移除原有的 `DropdownMenu` 和邮箱触发器。

### 底部账号区

侧栏最底部，位于导航区域下方，通过 `border-t` 与上方内容分隔。

- 显示当前邮箱文字，样式与当前顶部 `DropdownMenuTrigger` 一致：
  - `rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground`
  - 支持 `truncate` 处理长邮箱。
- 点击邮箱弹出 DropdownMenu（复用现有实现），包含：
  1. **邮件摘要设置** — 打开 `EmailDigestSettingsDialog`。
  2. **退出登录** — 触发 `onLogout` 回调，disable 时显示 `isLoggingOut` 状态。
- `DropdownMenuTrigger` 设置 `aria-label="用户菜单"`。

### 移除内容

- 侧栏 `<nav>` 中的 Feeds `<Link>` 链接（`mt-auto` 块）删除。
- `EmailDigestSettingsDialog` 从侧栏底部提到顶部同层级渲染（位置改变但逻辑不变）。

## Behavior

- DropdownMenu 行为不变：点击触发器展开、点击菜单项后关闭。
- `EmailDigestSettingsDialog` 仍通过 `open`/`onOpenChange` 受控。
- `+` 按钮跳转 `/feeds` 行为不变。
- 选中 Feeds 时 URL 行为不变。

## Component Dependencies

- 复用 `components/ui/menu.tsx` 中的 `DropdownMenu`、`DropdownMenuTrigger`、`DropdownMenuContent`、`DropdownMenuItem`。
- 复用 `EmailDigestSettingsDialog` 组件。
- 不引入新的 UI 组件。

## Accessibility

- 底部邮箱触发器使用 `button` 语义，设置 `aria-label="用户菜单"`。
- DropdownMenu 的 `aria-haspopup` 和 `aria-expanded` 由 Menu 组件自动处理。
- `+` 按钮保持 `aria-label="添加 Feed"`。
- 菜单项保持键盘可导航。

## Acceptance

- 侧栏顶部显示 `RSSWise | +`，无邮箱和下拉。
- 侧栏底部显示邮箱文字，上方有 `border-t` 分隔线。
- 点击底部邮箱弹出下拉菜单，包含「邮件摘要设置」和「退出登录」。
- 点击「邮件摘要设置」打开邮件摘要设置弹窗。
- 点击「退出登录」触发退出登录。
- Feeds 导航链接已从侧栏移除。
- 原有功能（邮件摘要、退出、添加 Feed）仍正常工作。
