# Sidebar Account to Bottom — Implementation Plan

## Overview

将 `WorkbenchSidebar` 组件的账户入口从顶部迁移到底部，属于纯前端布局调整，不涉及后端或数据变更。

## Tasks

### Task 1 — 移除顶部 DropdownMenu，保留 RSSWise 和 + 按钮

**文件**: `apps/web/src/routes/articles/workbench.tsx`

**改动**:
- 在 `WorkbenchSidebar` 的顶部 `<div>` 中，移除 `<DropdownMenu>` 及其包裹的 `<DropdownMenuTrigger>`、`<DropdownMenuContent>`、`<DropdownMenuItem>`。
- 保留 `<h1>RSSWise</h1>` 和 `<Link to="/feeds">` 的 `<PlusIcon>`。
- 移除不再使用的 import：`DropdownMenu`、`DropdownMenuContent`、`DropdownMenuItem`、`DropdownMenuTrigger`（如果其他位置不再使用）。

**验证**:
- 顶部只显示 RSSWise 和 + 按钮。
- `+` 按钮点击跳转 `/feeds`。
- 无 TypeScript/ESLint 报错。

---

### Task 2 — 移除侧栏导航中的 Feeds 链接

**文件**: `apps/web/src/routes/articles/workbench.tsx`

**改动**:
- 删除 `<nav>` 中 `mt-auto` 包裹的 `<Link to="/feeds">` 块（第 183-191 行）。
- 如果 `RssIcon` 不再使用，移除其 import。
- `<nav>` 的 `flex-1` 布局保持不变。

**验证**:
- 侧栏导航中不再显示 Feeds 入口。
- 导航项排列正常，无多余间距。
- 无 TypeScript/ESLint 报错。

---

### Task 3 — 在侧栏底部新增账号区

**文件**: `apps/web/src/routes/articles/workbench.tsx`

**改动**:
- 在 `<nav>` 结束标签之后、`<EmailDigestSettingsDialog />` 之前，插入底部账号区：

```tsx
<div className="border-t pt-3">
  <DropdownMenu>
    <DropdownMenuTrigger
      className="w-full truncate rounded-md px-2.5 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      aria-label="用户菜单"
    >
      {userEmail ?? "当前用户"}
    </DropdownMenuTrigger>
    <DropdownMenuContent align="start" sideOffset={4}>
      <DropdownMenuItem closeOnClick onSelect={() => setEmailDialogOpen(true)}>
        邮件摘要设置
      </DropdownMenuItem>
      <DropdownMenuItem closeOnClick onSelect={onLogout} disabled={isLoggingOut}>
        退出登录
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</div>
```

- 确保 `DropdownMenu`、`DropdownMenuContent`、`DropdownMenuItem`、`DropdownMenuTrigger` 的 import 存在（Task 1 不要删掉它们）。
- `<EmailDigestSettingsDialog>` 保持在 `</aside>` 之前，位置不变。

**验证**:
- 侧栏底部显示邮箱文字，上方有 `border-t` 分隔线。
- 点击邮箱弹出下拉菜单，包含「邮件摘要设置」和「退出登录」。
- 菜单项 hover 和点击行为正常。
- 长邮箱文字 truncate 正常。

---

### Task 4 — 验证与收尾

**操作**:
1. 运行 `pnpm lint`（在工作目录 `apps/web` 下）确保无 lint 错误。
2. 运行 `pnpm build`（在 `apps/web` 下）确保构建通过。
3. 检查 Playwright e2e 测试是否受布局变化影响，必要时更新选择器。
4. 手动验证：
   - 登录后访问 `/articles`，确认侧栏顶部为 `RSSWise | +`。
   - 底部可见邮箱文字，点击弹出下拉菜单。
   - 邮件摘要设置弹窗正常打开和关闭。
   - 退出登录功能正常。
   - `+` 按钮正常跳转 `/feeds`。
   - `/feeds` 页面的顶部 header 保持不变。

## Sequence

Task 1 → Task 2 → Task 3 → Task 4

Task 1 和 Task 2 可以并行执行（同文件不同区域），但建议串行以避免合并冲突。

## Risk Assessment

| 风险 | 等级 | 缓解 |
|------|------|------|
| e2e 测试选择器失效 | 低 | 账号区的 aria-label 保持不变，测试定位元素应不受影响 |
| import 清理导致编译错误 | 低 | 确认 `DropdownMenu*` 系列组件在底部新位置仍有引用后再清理 |
| 侧栏高度溢出 | 极低 | 移除了底部 Feeds 链接腾出空间，新增账号区高度与删除内容相当 |
