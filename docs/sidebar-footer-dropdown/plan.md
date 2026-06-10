# Sidebar Footer Dropdown Implementation Plan

> **Source Spec:** `docs/sidebar-footer-dropdown/spec.md`

**Goal:** 将侧边栏底部信息区收敛到顶部账户名的 DropdownMenu 中，移除头像占位符。

**Scope:** 仅修改 `WorkbenchSidebar` 组件，不涉及后端或其他页面。

---

## File Map

- Modify: `apps/web/src/routes/articles/workbench.tsx`
  - 重构 `WorkbenchSidebar` 顶部布局和底部区域。

---

## Implementation Notes

- 复用现有 `DropdownMenu*` 组件（`@/components/ui/menu`）。
- 不再需要使用 `UserIcon`，移除对应 import。
- `EmailDigestSettingsDialog` 和 `onLogout` 的调用方式不变。
- 不修改 `workbench.tsx` 中 `WorkbenchSidebar` 以外的任何代码。

---

### Task 1: 重构 WorkbenchSidebar 顶部与底部

**File:** `apps/web/src/routes/articles/workbench.tsx`

- [ ] **Step 1: 确认工作区干净**

```bash
git status --short
```

- [ ] **Step 2: 修改 imports**

移除 `UserIcon` 的 import。

新增 `DropdownMenu*` 相关 import：

```ts
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/menu"
```

保留 `EmailDigestSettingsDialog` 的 import。

- [ ] **Step 3: 重构顶部区域（第 114-132 行）**

将原有顶部改为：

```tsx
<div className="flex items-center gap-2">
  <h1 className="min-w-0 truncate text-base font-semibold text-foreground">
    RSSWise
  </h1>
  <DropdownMenu>
    <DropdownMenuTrigger
      className="min-w-0 flex-1 truncate rounded-md px-2 py-1 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      aria-label="用户菜单"
    >
      {userEmail ?? "当前用户"}
    </DropdownMenuTrigger>
    <DropdownMenuContent align="start" sideOffset={4}>
      <EmailDigestSettingsDialog />
      <DropdownMenuItem
        onSelect={onLogout}
        disabled={isLoggingOut}
      >
        退出登录
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
  <Link
    to="/feeds"
    aria-label="添加 Feed"
    className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
  >
    <PlusIcon aria-hidden="true" className="size-4" />
  </Link>
</div>
```

注意：`EmailDigestSettingsDialog` 作为 menu item 嵌入时，需要在其内部处理 `onSelect` 关闭菜单。如果当前 `EmailDigestSettingsDialog` 是一个独立按钮，需要将其改为 `DropdownMenuItem` 包裹触发其弹窗的交互。

- [ ] **Step 4: 移除底部区域（第 173-190 行）**

删除整个 `mt-3 border-t pt-3` 的 `<div>` 块及其内容。

- [ ] **Step 5: 处理 EmailDigestSettingsDialog 的嵌入方式**

`EmailDigestSettingsDialog` 当前是独立组件（包含触发按钮 + Dialog）。嵌入 DropdownMenu 后需要调整为：将触发按钮替换为 `DropdownMenuItem` 形式，点击后打开 Dialog。

新增一个内联 menu item，点击时打开 EmailDigestSettingsDialog 的 dialog：

```tsx
<DropdownMenuItem
  onSelect={() => openEmailDigestDialog()}
>
  邮件摘要设置
</DropdownMenuItem>
```

这可能需要 `EmailDigestSettingsDialog` 支持受控模式（`open` / `onOpenChange`）或暴露 `open` 方法。如果当前不支持，需要在该组件中添加 `open` prop。

- [ ] **Step 6: 验证**

```bash
pnpm --dir apps/web lint
```

```bash
pnpm --dir apps/web build
```

确认编译通过且无 lint 错误。
