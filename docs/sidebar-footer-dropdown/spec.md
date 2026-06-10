# Sidebar Footer Dropdown Spec

## Summary

将侧边栏底部的用户信息区域收敛到顶部账户名的 DropdownMenu 中，同时移除头像占位符，精简顶部为 `RSSWise | 账户名 | +` 的结构。

## Goals

- 顶部去掉头像占位符，改为 `RSSWise`（左侧）+ `账户名`（中间）+ `+`（右侧）的水平排列。
- 点击账户名弹出 DropdownMenu，包含「邮件摘要设置」和「退出登录」两项。
- 移除侧边栏底部整块区域（邮箱文本、邮件摘要按钮、退出按钮）。
- 保持现有功能行为不变（邮件摘要设置弹窗、退出登录逻辑）。

## Non-Goals

- 不改变邮件摘要设置弹窗的内部实现。
- 不改变退出登录的流程。
- 不改变账户名的获取方式（仍通过 `useOutletContext` 传入的 `email`）。
- 不新增后端接口或数据库变更。

## Current State

侧边栏 `WorkbenchSidebar`（`apps/web/src/routes/articles/workbench.tsx`）顶部：

```tsx
<div className="flex items-center gap-2">
  <h1>RSSWise</h1>
  <Link to="/feeds"><PlusIcon /></Link>
  <div aria-label="当前用户"><UserIcon /></div>
</div>
```

侧边栏底部（第 173-190 行）：

```tsx
<div className="mt-3 border-t pt-3">
  <div className="truncate px-2.5 text-xs text-muted-foreground">
    {userEmail ?? "当前用户"}
  </div>
  <div className="mt-2 flex items-center gap-1">
    <EmailDigestSettingsDialog />
    <Button onClick={onLogout}><LogOutIcon /></Button>
  </div>
</div>
```

## Target State

### 顶部区域

```
RSSWise ｜ 账户名(可点击)  ｜  +
```

- `RSSWise`：品牌名，左对齐，不可点击。
- `账户名`：显示当前邮箱，可点击触发 DropdownMenu。样式为链接/按钮风格，视觉上可区分于 `RSSWise`。
- `+`：跳转 `/feeds`，右侧对齐。

### DropdownMenu

点击账户名弹出 DropdownMenu，包含两个纯文字菜单项：

1. **邮件摘要设置** — 点击后打开邮件摘要设置弹窗（复用现有 `EmailDigestSettingsDialog`）。
2. **退出登录** — 点击后触发退出登录（复用现有 `onLogout` 回调）。

菜单项为纯文字，不带图标。

### 底部区域

完全移除。不再显示独立的邮箱文本、邮件摘要图标按钮、退出图标按钮。

## Behavior

- DropdownMenu 通过 `open` 状态控制开关。
- 点击菜单项后关闭 DropdownMenu。
- 账户名仍支持 title/tooltip 显示完整邮箱（作为 `title` 属性）。

## Component Dependencies

- 复用 `components/ui/menu.tsx` 中的 `DropdownMenu`、`DropdownMenuTrigger`、`DropdownMenuContent`、`DropdownMenuItem`。
- 复用 `EmailDigestSettingsDialog` 组件。
- 移除对 `UserIcon` 的引用（如果其他地方未使用）。

## Accessibility

- 账户名触发器使用 `button` 语义，设置 `aria-label`。
- DropdownMenu 的 `aria-haspopup="menu"` 和 `aria-expanded` 由 Menu 组件自动处理。
- 菜单项保持键盘可导航。

## Acceptance

- 侧边栏顶部显示 `RSSWise | 账户名 | +`，无头像。
- 点击账户名弹出下拉菜单，包含「邮件摘要设置」和「退出登录」。
- 点击「邮件摘要设置」打开邮件摘要设置弹窗。
- 点击「退出登录」触发退出登录。
- 侧边栏底部不再显示邮箱文本、摘要按钮和退出按钮。
- 原有功能（邮件摘要、退出）仍正常工作。
