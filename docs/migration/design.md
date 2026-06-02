# Design: Next.js → React + Vite Migration

## Summary

将 `apps/web` 从 Next.js App Router 迁移到 React 18 + Vite 纯客户端 SPA。

## Motivation

- Next.js App Router 的 Server Components / Server Actions 架构对于纯前端纯消费后端 API 的应用属于过度抽象，增加了心智负担
- 当前应用不需要 SEO、不需要 SSR，所有数据来自 FastAPI 后端，天然适合纯 CSR SPA
- Vite 构建更快，开发体验更轻量
- Caddy 直接托管静态文件比运行 Node 进程更简单可靠

## Current State

```
apps/web/
├── app/                      # Next.js App Router
│   ├── layout.tsx            # RootLayout + metadata + <nav>
│   ├── page.tsx              # GET / → redirect → /articles
│   ├── globals.css           # Tailwind v4 + CSS custom properties
│   ├── articles/
│   │   ├── page.tsx          # Server Component: GET /articles?status_filter=
│   │   └── [id]/
│   │       ├── page.tsx      # Server Component: POST read + GET /articles/:id
│   │       └── actions.ts    # Server Actions: markUnread, reanalyze
│   └── feeds/
│       ├── page.tsx          # Server Component: GET /feeds
│       └── actions.ts        # Server Actions: addFeed, refreshFeed, deleteFeed
├── components/
│   ├── markdown-content.tsx  # react-markdown wrapper
│   ├── recommendation-badge.tsx
│   └── ui/                   # shadcn-style primitives
│       ├── badge.tsx
│       ├── button.tsx
│       ├── input.tsx
│       ├── spinner.tsx
│       ├── table.tsx
│       └── tabs.tsx
├── lib/
│   ├── api.ts                # apiGet<T>, apiPost, types (ArticleListItem, ArticleDetail)
│   └── utils.ts              # cn() helper
├── tests/e2e/
│   ├── articles.spec.ts
│   └── feeds.spec.ts
├── next.config.mjs           # output: "standalone"
├── tailwind.config.ts
├── postcss.config.mjs
├── tsconfig.json
├── Dockerfile                # dev (pnpm install + COPY)
├── Dockerfile.prod           # multi-stage → node server.js
└── package.json
```

### Next.js-specific dependencies to remove

| Current | Replacement |
|---|---|
| `next` | `vite` + `@vitejs/plugin-react` |
| `next/link` | `react-router-dom` `Link` |
| `next/navigation` (`redirect`, `useRouter`) | `react-router-dom` (`Navigate`, `useNavigate`) |
| `next/cache` (`revalidatePath`) | TanStack Query `queryClient.invalidateQueries` |
| Server Actions (`"use server"`) | Client-side `fetch` calls + `useMutation` |
| `next-env.d.ts` + tsconfig `next` plugin | Remove |
| `eslint-config-next` | `@eslint/js` + `eslint-plugin-react-hooks` |
| `output: "standalone"` + `node server.js` | Vite `build.outDir: "dist"` → static files |
| `NEXT_PUBLIC_API_BASE_URL` | `VITE_API_BASE_URL` via `import.meta.env` |
| `next.config.mjs` | `vite.config.ts` |
| `postcss.config.mjs` | Vite CSS pipeline (still PostCSS-compatible) |

### Dependencies to keep unchanged

- `react`, `react-dom` — same runtime
- `react-markdown`, `rehype-sanitize`, `remark-gfm` — pure client library
- `@base-ui/react` — pure client library
- `lucide-react` — icon library
- `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css` — style utilities
- `tailwindcss`, `@tailwindcss/postcss`, `autoprefixer` — CSS pipeline
- `@playwright/test` — E2E tests
- `typescript` — type checker

## Target State

### Architecture Decision Records

**ADR-1: Pure CSR, no SSR**
- 选择：客户端渲染，Vite build 产出纯静态文件
- 原因：无 SEO 需求，所有数据来自后端 API，SSR 增加部署复杂度无收益
- 影响：首屏会有 loading 状态（可用 skeleton 优化体验）

**ADR-2: React Router v7 (library mode)**
- 选择：`react-router-dom` v7 的 library mode（`createBrowserRouter`）
- 原因：最成熟的 React 路由方案，支持嵌套路由、loader/action 模式（不强制使用）
- 路由表：

| Path | Component | 数据请求 |
|---|---|---|
| `/` | Redirect to `/articles` | — |
| `/articles` | `ArticlesPage` | `GET /articles?status_filter=` |
| `/articles/:id` | `ArticleDetailPage` | `POST /articles/:id/read` + `GET /articles/:id` |
| `/feeds` | `FeedsPage` | `GET /feeds` |

**ADR-3: TanStack Query for server state**
- 选择：`@tanstack/react-query` v5
- 原因：自动缓存、loading/error 状态管理、mutation 后自动 invalidate（替代 `revalidatePath`）
- 影响：需要 `<QueryClientProvider>` 包裹在 router 外层

**ADR-4: Caddy static file hosting (production)**
- 选择：Caddy 直接 serve `dist/` 目录
- 原因：纯静态文件无需 Node 进程，Caddy 已存在于基础设施中
- `Caddyfile` 改为 `root * /app/dist` + `file_server` + SPA fallback `try_files {path} /index.html`
- Docker 镜像：`node:22-slim` builder → 产出 `dist/` → Caddy 镜像（`caddy:2-alpine`）serve
- 不再需要 `Dockerfile.prod` 中的 `node server.js` runner 层

**ADR-5: Client-side API calls**
- 选择：客户端直接 fetch FastAPI 后端（`VITE_API_BASE_URL`）
- 所有 Server Actions 逻辑下沉为组件内 `useMutation` + `fetch`
- `lib/api.ts` 保留为纯客户端 fetch 封装，去掉服务端依赖

### Directory Structure (target)

```
apps/web/
├── index.html                # Vite entry HTML
├── public/                   # 静态资源（favicon 等）
├── src/
│   ├── main.tsx              # ReactDOM.createRoot + QueryClientProvider + RouterProvider
│   ├── App.tsx               # Root layout: <nav> + <main> + <Outlet>
│   ├── globals.css           # 保持不变
│   ├── routes/
│   │   ├── articles/
│   │   │   ├── list.tsx       # ArticlesPage (原 app/articles/page.tsx)
│   │   │   └── detail.tsx     # ArticleDetailPage (原 app/articles/[id]/page.tsx)
│   │   ├── feeds/
│   │   │   └── list.tsx       # FeedsPage (原 app/feeds/page.tsx)
│   │   └── home.tsx           # Redirect to /articles (原 app/page.tsx)
│   ├── components/            # 保持原样
│   │   ├── markdown-content.tsx
│   │   ├── recommendation-badge.tsx
│   │   └── ui/
│   └── lib/
│       ├── api.ts             # 去掉 NEXT_PUBLIC_*，改用 import.meta.env.VITE_*
│       └── utils.ts
├── tests/e2e/                 # 保持原样
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── Dockerfile                 # dev (同现在)
├── Dockerfile.prod            # builder → caddy
└── package.json
```

### Data Flow (before / after)

**Before (Next.js):**
```
Browser → Next.js Server (fetch API) → FastAPI Backend
                ↑ server component renders HTML
```

**After (Vite):**
```
Browser → Vite dev server (HMR only)
       ↘ fetch API directly → FastAPI Backend
```

### Key behavioral changes

1. **首屏 loading**：Next.js 服务端渲染 → 首屏即完整 HTML。迁移后 CSR 首屏会短暂显示 loading。使用 TanStack Query 的 `isLoading` 状态渲染 skeleton/placeholder。

2. **Server Actions → useMutation**：所有 `"use server"` 函数改为 TanStack Query `useMutation`，mutation 成功后 `queryClient.invalidateQueries` 刷新关联数据。

3. **`revalidatePath` → `invalidateQueries`**：Next.js 通过路径级缓存失效 → TanStack Query 通过 query key 精准失效。

4. **环境变量**：`NEXT_PUBLIC_API_BASE_URL` → `VITE_API_BASE_URL`。Docker compose 中相应修改。

5. **Metadata / title**：Next.js `export const metadata` → react-helmet-async 或 `<title>` 标签逐页面设置，或用 `document.title`。

6. **代码分割**：Next.js 自动按路由分割 → Vite 默认打包在一起。使用 `React.lazy` + `Suspense` 按路由懒加载。

### Risk Analysis

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Tailwind v4 + PostCSS 在 Vite 下有兼容问题 | Low | Medium | 在 plan 第一步就验证 CSS 构建 |
| `@base-ui/react` 需要 CSSTransition 等浏览器 API | Low | Low | 库本身支持 CSR，只会在 Hydration 时有问题 |
| Playwright E2E 测试断言需要调整 | Medium | Low | 添加 loading 状态等待逻辑 |
| `tw-animate-css` Vite 兼容性 | Low | Low | 验证一次即可 |
| API base URL 从服务端变为客户端暴露 | None | — | 本来就是公开的后端 API，不敏感 |
| index.html 中的 CSP/CORS | Low | Low | FastAPI 已有 CORS 配置，无需额外处理 |

## Out of Scope

- FastAPI 后端任何改动
- 新增功能或 UI 改版
- PWA / Service Worker
- 国际化、a11y 专项改进
- 测试覆盖率提升

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `vite` | ^6.x | Build tool |
| `@vitejs/plugin-react` | ^4.x | React Fast Refresh + JSX transform |
| `react-router-dom` | ^7.x | Client-side routing |
| `@tanstack/react-query` | ^5.x | Server state management |
| `@eslint/js` + `eslint-plugin-react-hooks` | latest | ESLint config (replacing eslint-config-next) |
