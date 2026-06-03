# Design: coss UI Docs Style Restyle

## Summary

将当前 RSSWise Web 应用重设计为接近 `https://coss.com/ui/docs` 的浅色文档站视觉风格。

本次只修改视觉与布局，不新增业务功能，不改变现有数据流、路由、API 行为或用户工作流。

## Decisions From Requirement Discovery

- 覆盖范围：全部现有可访问页面，包括 `/articles`、`/feeds`、`/` 的基础壳层和空状态。
- 文章工作台：保留现有“左侧文章列表 + 文章详情区”的核心工作流；桌面详情区包含正文阅读区和 AI 分析侧栏。
- 视觉还原程度：高相似度，尽量接近 coss UI docs 的浅色、灰阶、细边框、紧凑界面。
- 主题：只做浅色模式，不新增主题切换，不专门设计暗色模式。
- 状态色：主体灰阶化，状态与推荐只保留克制语义色。
- 移动端：保持基础可用，不新增抽屉、命令菜单或 docs 式移动侧栏交互。

## Current State

RSSWise Web 当前是 React 18 + Vite + React Router + TanStack Query 应用。

重要文件：

```text
apps/web/src/App.tsx                         # 全局 header/nav + route outlet
apps/web/src/globals.css                    # Tailwind v4 token 和全局样式
apps/web/src/routes/articles/workbench.tsx  # /articles 三栏/双栏工作台
apps/web/src/routes/feeds/list.tsx          # /feeds Feed 管理页
apps/web/src/routes/home.tsx                # / 首页跳转
apps/web/src/components/recommendation-badge.tsx
apps/web/src/components/workflow-stepper.tsx
apps/web/src/components/ui/button.tsx
apps/web/src/components/ui/input.tsx
apps/web/src/components/ui/badge.tsx
apps/web/src/components/ui/table.tsx
apps/web/src/components/ui/tabs.tsx
apps/web/src/components/ui/spinner.tsx
```

现状问题：

- 页面仍有较强 dashboard/card 风格，和 coss docs 的文档壳层不一致。
- 色彩以 slate + blue 状态色为主，选中态和推荐标签偏产品化，不够接近 coss docs 的黑白灰基调。
- `/articles` 工作台功能合适，但视觉上左侧列表、详情区、AI 分析区的层级较重。
- `/feeds` 使用大卡片式表单和列表，与 docs 风格的紧凑设置页不一致。
- 部分业务组件直接使用 raw palette class，需要向 coss 的 semantic token 和组件 variant 靠齐。

## Target Visual System

### Overall Style

目标外观采用 coss UI docs 的特征：

- 浅色背景，主色调为白、近白、黑、灰。
- 顶栏薄、克制、边框清晰。
- 内容区使用细边框和分隔线组织，不依赖厚重阴影。
- 控件尺寸紧凑，信息密度高。
- 交互态使用低饱和灰阶背景、边框变化和文字权重变化。
- 卡片只用于真正需要框定的局部内容，避免页面被大块圆角卡片主导。

### Tokens

`apps/web/src/globals.css` 应继续使用 Tailwind v4 与 coss 风格语义变量。

目标 token 倾向：

```text
background           near-white
foreground           near-black
card                 white
muted                very light gray
muted-foreground     medium gray
border/input         soft gray
primary              near-black
primary-foreground   white
accent               light gray
ring                 neutral gray
```

设计要求：

- 优先使用 `bg-background`、`text-foreground`、`text-muted-foreground`、`border-border`、`bg-card` 等语义 token。
- 尽量减少 `text-slate-*`、`bg-blue-*`、`border-emerald-*` 等 raw palette class。
- 不新增复杂品牌色系统。
- 不引入渐变、装饰背景、营销式 hero 或大面积彩色区块。

### Typography

- 保持系统 sans-serif 或 coss token 中的 `--font-sans`。
- 页面标题更接近 docs 风格：中等字号、清晰字重、紧凑行高。
- 列表、元信息和按钮保持小字号与高可扫读性。
- 不使用 viewport-based 字号缩放。
- 字距保持默认，不使用负字距。

### Components

遵循 coss skill 的组件规则：

- 使用已有 coss-style 本地组件优先，不重新发明按钮、输入、badge、table。
- Button 使用 `variant` 和 `size`，避免用 raw class 重写主样式。
- Input 明确 `type`，Feed URL 表单继续使用 `type="url"`。
- Badge 使用 `Badge` 组件和 `variant`，推荐标签不再手写圆角彩色 pill。
- 图标来自 `lucide-react`，装饰性图标使用 `aria-hidden="true"`。
- 表单字段保留可访问 label、错误文本和 disabled/loading 状态。

## Page Design

### Global App Shell

`App.tsx` 负责提供 docs 风格应用壳层。

目标：

- 顶栏高度更紧凑，固定在页面顶部或正常文档流顶部均可，优先简单稳定。
- 顶栏背景为 `bg-background` 或 `bg-card`，底部使用 `border-b`。
- 品牌 `RSSWise` 保留，但视觉上像 docs nav brand，不做 logo 或营销式标题。
- 导航只保留“文章”和“Feed”，使用轻量链接样式。
- 当前路由用灰阶 active state，不使用蓝色选中态。
- `/articles` 继续使用全屏工作台布局；`/feeds` 使用受限宽度内容布局。

不做：

- 不新增搜索框。
- 不新增 command menu。
- 不新增主题切换。
- 不新增右侧用户菜单。

### `/articles` Article Workbench

保留现有功能：

- 文章状态筛选：全部、已读、未读。
- 左侧文章列表。
- 选择文章后右侧展示详情。
- 自动/手动处理正文抽取、AI 分析、标记已读/未读、重新分析、阅读原文。
- 桌面端保留当前三个工作区：左侧文章列表、中间正文阅读区、右侧 AI 分析侧栏。

目标布局：

```text
top app header
└─ article workbench
   ├─ left article sidebar
   │  ├─ compact title/filter row
   │  └─ article list
   ├─ main reading pane
   │  ├─ article header
   │  └─ markdown content
   └─ right AI summary sidebar
      ├─ processing stepper
      ├─ recommendation / summary / reason
      └─ article actions
```

左侧文章 sidebar：

- 宽度保持约 `320px`，可按视觉微调到 `300-360px`。
- 使用 `border-r` 与主内容分隔。
- 背景接近 docs sidebar，优先 `bg-background` 或 `bg-muted/20`。
- 顶部筛选按钮改为 segmented/toolbar 质感：紧凑、高度一致、灰阶 active。
- 列表项使用细分割线、低饱和 hover、灰阶 selected。
- 未读状态可用小圆点或文字权重表达；小圆点应为中性灰或近黑，不使用亮蓝。
- 推荐 badge 使用小型灰阶或克制语义色，不抢文章标题层级。
- loading skeleton、error、empty 状态保持功能不变但改成 docs 风格灰阶。

右侧阅读 pane：

- 空状态像 docs 的空内容提示：图标、标题、说明更轻，不使用大圆角卡片。
- 加载状态保持 spinner + 简短文本。
- 文章 header 采用文档正文布局：来源、时间、标题、原文链接。
- 原文链接使用轻量 button/link 样式，图标用 `ExternalLinkIcon`。
- 正文区保持文档阅读体验，AI 信息不混入正文顶部。

右侧 AI summary sidebar：

- 保留独立侧栏，继续显示处理步骤、阅读建议、摘要、理由、状态和操作。
- 降低卡片感：使用细分隔线、浅色 section 或小型 inset 区块。
- WorkflowStepper 使用灰阶主导，processing/success/failed 只用克制语义色辅助。
- 操作按钮保持全宽或紧凑堆叠，符合当前侧栏宽度。
- MarkdownContent 作为主要阅读内容，应保留可读行宽、标题层级和代码样式。

### `/feeds` Feed Management

保留现有功能：

- 添加 Feed。
- 删除 Feed。
- 刷新 Feed。
- 展示 Feed 标题、URL、站点链接、favicon、最后抓取时间。
- 保持 loading、error、empty 和 mutation error 状态。

目标布局：

- 页面像 docs 的设置/资源列表页，而不是 dashboard 卡片页。
- 标题区简洁，左侧图标可保留但降低视觉权重。
- 添加 Feed 表单使用紧凑横向布局；窄屏自然堆叠。
- 表单容器可使用细边框 section，不使用厚重 shadow。
- Feed 列表采用紧凑列表或 `Table variant="card"` 风格，优先可扫读。
- Feed 行 hover 使用轻微灰阶背景。
- 刷新和删除按钮继续用 `Button`，尺寸 `sm` 或 `xs`，删除使用克制 destructive outline。
- URL 长文本必须换行或断行，不造成横向溢出。

### `/`

`/` 当前只是进入应用的路由入口。继续保持跳转到 `/articles`，不新增 landing page。

## Responsive Design

### Desktop

- `/articles` 使用侧栏 + 内容区布局。
- 左侧文章列表固定宽度，右侧内容弹性撑满。
- 页面高度应允许文章列表和正文独立滚动，避免整个页面出现不可控滚动嵌套。

### Mobile / Narrow Screens

目标是基础可用：

- 不新增抽屉、sheet、menu 或 command palette。
- `/articles` 可退化为上下布局或列表优先布局。
- 确保文字、按钮、URL 和文章标题不溢出容器。
- Feed 表单和列表操作按钮可换行。
- 不追求完全复刻 coss docs mobile navigation。

## Accessibility

- 所有按钮保留 `type`。
- Icon-only 按钮必须有 `aria-label`；本轮不新增 icon-only 主操作。
- 装饰图标设置 `aria-hidden="true"`。
- Feed URL 输入保持关联 label。
- 错误状态继续以文本展示，不只依赖颜色。
- 选中态不能只靠颜色表达，应同时使用边框、背景、字重或 `aria-current`。

## Testing And Verification

本轮是视觉与布局改造，但仍需验证功能不回退。

必须验证：

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web build`
- 如后端和测试环境可用，运行现有 Playwright E2E：
  - `pnpm --dir apps/web test:e2e`

手动视觉检查：

- `/articles`：无选中文章、加载、错误、空列表、有文章、选中文章、AI 处理中/失败/成功。
- `/feeds`：空列表、加载、错误、有 Feed、添加 Feed 表单、刷新/删除 loading。
- 桌面宽度：1440px 和 1024px。
- 移动宽度：375px 和 768px。

## Out Of Scope

- 不修改 FastAPI 后端。
- 不新增文章搜索、Feed 分组、推荐筛选或排序。
- 不新增 docs 站式命令搜索。
- 不新增主题切换或暗色模式专项。
- 不新增移动抽屉/侧栏交互。
- 不新增路由。
- 不重构数据获取逻辑。
- 不改变 API type。
- 不改 Docker、部署和后端任务。

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| 过度 docs 化导致 RSS 工作台效率下降 | Medium | Medium | 保留左侧文章列表 + 右侧详情，不改工作流 |
| 灰阶化后状态识别不足 | Medium | Medium | 推荐和失败等状态保留克制语义色，并用文本/图标辅助 |
| 移动端工作台自然堆叠后阅读路径变长 | Medium | Low | 明确只做基础可用，不新增交互；保证无溢出和可操作 |
| 组件 class 大量修改引入视觉回退 | Medium | Medium | 分阶段改全局 token、shell、业务页面、业务组件，并逐步 build/lint |
| coss API 被误用 | Low | Medium | 只使用已存在本地 coss-style 组件；新增组件前查 coss references |

## Acceptance Criteria

- 所有现有页面功能保持不变。
- `/articles` 和 `/feeds` 视觉明显接近 coss UI docs 的浅色文档站风格。
- UI 主体为黑白灰，蓝/绿/黄状态色不再主导界面。
- 文章工作台仍能高效完成列表筛选、选择文章、阅读正文和 AI 处理操作。
- Feed 管理页仍能添加、刷新、删除 Feed。
- 375px 宽度下无明显横向溢出或按钮文字裁切。
- lint 和 build 通过。
