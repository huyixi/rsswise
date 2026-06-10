# Inline Feed Management Panel — 实施计划

## 分步执行顺序

### Step 1：抽取 `FeedManagementContent` 组件

**文件**：`apps/web/src/routes/feeds/list.tsx`

**操作**：
1. 将 `FeedsPage` 中 `return` 语句内 `<form>`, `<div>`(错误提示), `<div>`(导入结果), `<div>`(Feed 列表) 四段内容抽取为独立的 `FeedManagementContent` 组件。
2. `FeedManagementContent` 是一个纯内容组件，接收**无 props**（所需的 query/mutation hooks 全部内聚在组件内部）。
3. `FeedsPage` 改为渲染：
   ```tsx
   <div className="flex flex-col gap-6">
     <div className="flex items-center gap-2">
       <RssIcon ... />
       <h1>Feed 管理</h1>
     </div>
     <FeedManagementContent />
   </div>
   ```
4. 保持 `document.title` 在 `FeedsPage` 的 `useEffect` 中。

**验证**：启动 dev server，访问 `/feeds`，确保页面功能完全不变。

---

### Step 2：在 `workbench.tsx` 中添加面板状态与按钮逻辑

**文件**：`apps/web/src/routes/articles/workbench.tsx`

**操作**：
1. 在 `ArticleWorkbenchPage` 中新增 `const [isFeedPanelOpen, setIsFeedPanelOpen] = useState(false)`。
2. 导入 `XIcon` 和 `FeedManagementContent`。
3. 修改 `WorkbenchSidebar`：
   - 接收新 prop `isFeedPanelOpen` + `onToggleFeedPanel: () => void`。
   - "+" `<Link>` 改为 `<button>`，`onClick={onToggleFeedPanel}`。
   - 面板打开时图标 `XIcon`，aria-label "关闭 Feed 管理"；关闭时图标 `PlusIcon`，aria-label "添加 Feed"。

**验证**：dev server，访问 `/articles`，点击按钮可切换图标，但面板区域尚未渲染任何内容（下一步实现）。

---

### Step 3：在 `workbench.tsx` 中实现桌面端 Feed 面板

**文件**：`apps/web/src/routes/articles/workbench.tsx`

**操作**：
1. 新建本地组件 `FeedPanel`（放在同一文件中或独立文件）：
   ```tsx
   function FeedPanel({ onClose }: { onClose: () => void }) {
     return (
       <div className="flex flex-1 flex-col overflow-hidden bg-card">
         <div className="flex items-center justify-between border-b px-4 py-3">
           <h2 className="text-sm font-semibold text-foreground">Feed 管理</h2>
           <button onClick={onClose} aria-label="关闭 Feed 管理"
             className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
             <XIcon className="size-4" />
           </button>
         </div>
         <div className="flex-1 overflow-y-auto p-4">
           <FeedManagementContent />
         </div>
       </div>
     )
   }
   ```
2. 修改 `ArticleWorkbenchPage` 的 return（614-646 行）：
   ```tsx
   return (
     <div className="flex h-screen overflow-hidden">
       <WorkbenchSidebar ... isFeedPanelOpen={isFeedPanelOpen} onToggleFeedPanel={...} />
       {isFeedPanelOpen ? (
         <FeedPanel onClose={() => setIsFeedPanelOpen(false)} />
       ) : (
         <>
           <ArticleListPanel ... />
           <ArticleContentPanel ... />
         </>
       )}
     </div>
   )
   ```

**验证**：
- 点击 "+" 按钮 → 右侧出现 Feed 管理面板，侧边栏不变。
- 点击关闭按钮 → 恢复文章列表 + 正文。
- 添加 Feed → 侧边栏 Feed 列表实时刷新。
- 删除 Feed → 侧边栏和面板内列表同步更新。

---

### Step 4：实现移动端整屏 Feed 面板

**文件**：`apps/web/src/routes/articles/workbench.tsx`

**操作**：
1. 新建本地组件 `MobileFeedPanel`：
   ```tsx
   function MobileFeedPanel({ onClose }: { onClose: () => void }) {
     return (
       <div className="fixed inset-0 z-50 flex flex-col bg-background">
         <div className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background px-4 py-3">
           <button onClick={onClose} aria-label="返回"
             className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent">
             <ArrowLeftIcon className="size-4" />
           </button>
           <h2 className="text-sm font-semibold text-foreground">Feed 管理</h2>
         </div>
         <div className="flex-1 overflow-y-auto p-4">
           <FeedManagementContent />
         </div>
       </div>
     )
   }
   ```
2. 在移动端分支（594-612 行）增加面板判断：
   ```tsx
   if (isMobile) {
     return (
       <>
         {isFeedPanelOpen ? (
           <MobileFeedPanel onClose={() => setIsFeedPanelOpen(false)} />
         ) : (
           <div className="min-h-[calc(100vh-49px)] bg-background">
             <ArticleListPanel ... />
           </div>
         )}
       </>
     )
   }
   ```
3. 在移动端也需要引入 `WorkbenchSidebar`？**不需要**，移动端本身就不渲染侧边栏。但 "+" 按钮在哪？检查一下：当前移动端只渲染 `ArticleListPanel`，侧边栏不存在。需要增加一个移动端的 "+" 入口。
   - 在 `ArticleListPanel` 顶部（筛选栏上方）添加一个 "+" 按钮，仅移动端可见（`lg:hidden`）。
   - 或者：在 `ArticleListPanel` 组件上接收 `onAddFeed` prop。
   - **推荐方案**：在移动端的 `<div>` 包裹外添加一个顶部栏，包含 "+" 按钮。

4. 修改移动端渲染：
   ```tsx
   if (isMobile) {
     return (
       <>
         {isFeedPanelOpen ? (
           <MobileFeedPanel onClose={() => setIsFeedPanelOpen(false)} />
         ) : (
           <div className="min-h-screen bg-background">
             <div className="flex items-center justify-between border-b px-4 py-2">
               <h1 className="text-sm font-semibold text-foreground">RSSWise</h1>
               <button onClick={() => setIsFeedPanelOpen(true)} aria-label="添加 Feed"
                 className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent">
                 <PlusIcon className="size-4" />
               </button>
             </div>
             <ArticleListPanel ... />
           </div>
         )
       </>
     )
   }
   ```

**验证**：
- 缩小浏览器窗口到 <800px，顶部出现 "+" 按钮。
- 点击 "+" → 整屏 Feed 管理面板覆盖。
- 点击返回箭头 → 回到文章列表。
- 点击关闭按钮可返回（移动端可有或无关闭X，保留最简返回箭头即可）。

---

### Step 5：最终验证与清理

**验证清单**：
1. `/feeds` 独立页面功能完整（添加、导入、刷新、删除、错误提示、导入结果展示）。
2. 桌面端工作台：从侧边栏 "+" 打开面板 → 添加 Feed → 面板保持打开，侧边栏刷新 → 关闭面板恢复文章视图。
3. 面板关闭后文章列表和侧边栏数据为最新。
4. 移动端：顶部 "+" 入口 → 整屏面板 → 返回文章列表。
5. 键盘导航（ArrowUp/ArrowDown）在面板关闭后正常工作。
6. 面板内 scroll 独立，不影响外部。

---

## 涉及文件

| 文件 | 变更 |
|------|------|
| `apps/web/src/routes/feeds/list.tsx` | 抽取 `FeedManagementContent` 组件导出 |
| `apps/web/src/routes/articles/workbench.tsx` | 添加 state、修改侧边栏按钮、桌面/移动端面板渲染 |

## 不涉及的文件

| 文件 | 原因 |
|------|------|
| `apps/web/src/App.tsx` | 布局逻辑不变，`/feeds` 路由保持原样 |
| `apps/web/src/lib/api.ts` | 不添加新 API |
| `apps/web/src/lib/query-keys.ts` | 不添加新 query key |
