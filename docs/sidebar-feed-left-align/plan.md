# Sidebar Feed Left-Align — 执行计划

## Task 1: 修改 navButtonClassName

**文件**: `apps/web/src/routes/articles/workbench.tsx`

在 `navButtonClassName` 函数中将 `justify-between` 替换为 `justify-start gap-2`。

```diff
 function navButtonClassName(active: boolean) {
   return cn(
-    "flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-sm transition-colors",
+    "flex w-full items-center justify-start gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
     active
       ? "bg-accent font-medium text-foreground"
       : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
   )
 }
```

**影响分析**:
- 带 favicon 的 feed 按钮：favicon + 标题现在靠左紧挨显示 ✅
- 不带 favicon 的 feed 按钮：单独 span 仍靠左 ✅
- "All Articles" 按钮：单独 span 仍靠左，不受影响 ✅

## Task 2: 验证

```bash
cd apps/web && npx tsc --noEmit
```

确认无类型错误。

## Task 3: 视觉确认

1. 启动 dev server：`cd apps/web && npm run dev`
2. 在浏览器中打开工作台，检查左侧栏：
   - 有 favicon 的 feed：favicon 与标题靠左紧挨排列
   - 无 favicon 的 feed：标题单独靠左
   - "All Articles" 按钮：文本靠左
3. 切换 feed 选中态，确认 active/inactive 样式正确
