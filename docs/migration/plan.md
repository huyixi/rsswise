# Migration Plan: Next.js → React + Vite

基于 `design.md`，将 `apps/web` 从 Next.js App Router 迁移为 React 18 + Vite + React Router + TanStack Query 的纯客户端 SPA。

本计划只迁移前端运行时、路由、数据请求、构建和部署方式；不修改 FastAPI 后端，不新增业务功能，不做 UI 改版。

---

## Goals

* 移除 Next.js App Router、Server Components、Server Actions
* 使用 Vite 构建纯静态前端应用
* 使用 React Router 处理客户端路由
* 使用 TanStack Query 管理远端数据、缓存和 mutation
* 使用 Caddy 托管 `dist/` 静态文件
* 保持现有页面功能不变：

  * `/` redirect 到 `/articles`
  * `/articles` 文章列表
  * `/articles/:id` 文章详情
  * `/feeds` Feed 管理

---

## Non-goals

* 不修改 FastAPI 后端接口
* 不重做 UI
* 不引入 SSR
* 不引入 PWA / Service Worker
* 不新增国际化、a11y、测试覆盖率专项优化
* 不同时使用 React Router loader/action 与 TanStack Query 管理同一份远端数据

---

## Migration Principles

1. Router 只负责路由和 URL 状态。
2. 远端数据统一由 TanStack Query 管理。
3. API 请求统一走 `src/lib/api.ts`。
4. 所有 mutation 成功后通过 query key 精准失效缓存。
5. 先保证开发环境可跑，再迁移页面，最后清理 Next.js 文件。
6. 先验证本地构建，再改 Docker 和 Caddy。

---

## Phase 1: Dependencies and Project Skeleton

### Step 1 — Update dependencies

**变更文件：**

* `apps/web/package.json`

**移除依赖：**

```txt
next
eslint-config-next
```

**新增依赖：**

```txt
vite
@vitejs/plugin-react
react-router-dom
@tanstack/react-query
```

**新增开发依赖：**

```txt
@eslint/js
typescript-eslint
eslint-plugin-react-hooks
eslint-plugin-react-refresh
```

**建议 scripts：**

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview --host 0.0.0.0",
    "lint": "eslint src"
  }
}
```

**验证：**

```bash
pnpm install
pnpm list vite @vitejs/plugin-react react-router-dom @tanstack/react-query
```

---

### Step 2 — Create Vite entry files

**新增文件：**

```txt
apps/web/index.html
apps/web/src/main.tsx
apps/web/src/App.tsx
```

**`index.html`:**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RSSWise</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**`src/App.tsx` 先使用占位内容：**

```tsx
export function App() {
  return (
    <div>
      <header>
        <nav>RSSWise</nav>
      </header>
      <main>App ready</main>
    </div>
  )
}
```

**`src/main.tsx`:**

```tsx
import React from "react"
import ReactDOM from "react-dom/client"
import { App } from "./App"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**验证：**

```bash
pnpm dev
```

浏览器打开本地端口，应能看到 `App ready`。

---

### Step 3 — Move shared source files into `src`

**变更：**

将当前根级前端源码移动到 `src/`：

```txt
apps/web/components/        → apps/web/src/components/
apps/web/lib/               → apps/web/src/lib/
apps/web/app/globals.css    → apps/web/src/globals.css
```

**保留：**

```txt
apps/web/public/
apps/web/tests/
apps/web/components.json
```

**注意：**

迁移后 `@/components/...` 和 `@/lib/...` 应指向 `src/` 下的文件。

**更新 `src/main.tsx`:**

```tsx
import "./globals.css"
```

**验证：**

先不要求页面可用，只确认文件移动后没有明显路径遗漏。

---

### Step 4 — Create Vite config

**新增文件：**

```txt
apps/web/vite.config.ts
```

**内容：**

```ts
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "node:path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  envPrefix: "VITE_",
  server: {
    port: 3000,
  },
  preview: {
    port: 3000,
  },
})
```

**验证：**

```bash
pnpm build
```

此时允许出现业务 import 错误，但不应出现 Vite 配置本身错误。

---

### Step 5 — Rewrite TypeScript config

**变更文件：**

```txt
apps/web/tsconfig.json
```

**建议配置：**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowImportingTsExtensions": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "types": ["vite/client"]
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "vite.config.ts"],
  "references": []
}
```

**删除：**

```txt
next-env.d.ts
tsconfig 中的 Next.js plugin
```

**验证：**

```bash
pnpm build
```

此时仍可能因为页面未迁移报错，但不应出现 Next.js 类型相关错误。

---

## Phase 2: Runtime Infrastructure

### Step 6 — Create Query Client and Query Keys

**新增文件：**

```txt
apps/web/src/lib/query-client.ts
apps/web/src/lib/query-keys.ts
```

**`src/lib/query-client.ts`:**

```ts
import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
```

**`src/lib/query-keys.ts`:**

```ts
export const queryKeys = {
  articles: {
    all: ["articles"] as const,
    list: (status: string) => ["articles", "list", { status }] as const,
    detail: (id: string) => ["articles", "detail", id] as const,
  },
  feeds: {
    all: ["feeds"] as const,
    list: () => ["feeds", "list"] as const,
  },
}
```

**验证：**

```bash
pnpm build
```

---

### Step 7 — Update API client for Vite

**变更文件：**

```txt
apps/web/src/lib/api.ts
```

**变更点：**

* `process.env.NEXT_PUBLIC_API_BASE_URL`
* 改为 `import.meta.env.VITE_API_BASE_URL`

**建议实现：**

```ts
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text().catch(() => "")
    throw new Error(message || `API request failed: ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  return parseResponse<T>(response)
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  return parseResponse<T>(response)
}

export async function apiDelete<T = unknown>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
  })

  return parseResponse<T>(response)
}
```

**如果后端依赖 Cookie 认证：**

需要在 `fetch` 中增加：

```ts
credentials: "include"
```

同时确认 FastAPI CORS 允许 credentials。

**验证：**

```bash
pnpm build
```

---

### Step 8 — Set up React Router and Providers

**新增文件：**

```txt
apps/web/src/router.tsx
apps/web/src/providers.tsx
apps/web/src/routes/home.tsx
apps/web/src/routes/articles/list.tsx
apps/web/src/routes/articles/detail.tsx
apps/web/src/routes/feeds/list.tsx
```

**先创建占位页面：**

```tsx
export function ArticlesPage() {
  return <div>Articles</div>
}
```

```tsx
export function ArticleDetailPage() {
  return <div>Article Detail</div>
}
```

```tsx
export function FeedsPage() {
  return <div>Feeds</div>
}
```

**`src/routes/home.tsx`:**

```tsx
import { Navigate } from "react-router-dom"

export function HomePage() {
  return <Navigate to="/articles" replace />
}
```

**`src/router.tsx`:**

```tsx
import { createBrowserRouter } from "react-router-dom"
import { App } from "./App"
import { HomePage } from "./routes/home"
import { ArticlesPage } from "./routes/articles/list"
import { ArticleDetailPage } from "./routes/articles/detail"
import { FeedsPage } from "./routes/feeds/list"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "articles", element: <ArticlesPage /> },
      { path: "articles/:id", element: <ArticleDetailPage /> },
      { path: "feeds", element: <FeedsPage /> },
    ],
  },
])
```

**`src/providers.tsx`:**

```tsx
import type { ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider } from "react-router-dom"
import { queryClient } from "./lib/query-client"
import { router } from "./router"

export function Providers({ children }: { children?: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children ?? <RouterProvider router={router} />}
    </QueryClientProvider>
  )
}
```

**更新 `src/main.tsx`:**

```tsx
import React from "react"
import ReactDOM from "react-dom/client"
import { Providers } from "./providers"
import "./globals.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Providers />
  </React.StrictMode>,
)
```

**更新 `src/App.tsx`:**

从原 `app/layout.tsx` 迁移 header/nav。

* `next/link` 改为 `react-router-dom` 的 `Link` 或 `NavLink`
* `{children}` 改为 `<Outlet />`

示例：

```tsx
import { Link, Outlet } from "react-router-dom"

export function App() {
  return (
    <div>
      <header>
        <nav>
          <Link to="/articles">Articles</Link>
          <Link to="/feeds">Feeds</Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
```

**验证：**

```bash
pnpm dev
```

确认以下路由可访问：

```txt
/
 /articles
/articles/test-id
/feeds
```

---

## Phase 3: Page Migration

### Step 9 — Migrate Articles List Page

**变更文件：**

```txt
apps/web/src/routes/articles/list.tsx
```

**从这里迁移：**

```txt
apps/web/app/articles/page.tsx
```

**迁移规则：**

* 删除 `export const dynamic = "force-dynamic"`
* 删除 Server Component async 函数
* `searchParams` 改为 `useSearchParams`
* `apiGet` 改为 `useQuery`
* `next/link` 改为 `react-router-dom` 的 `Link`
* loading 时显示 `Spinner` 或 skeleton
* error 时显示错误提示

**建议查询：**

```tsx
const [searchParams] = useSearchParams()
const status = searchParams.get("status_filter") ?? "all"

const articlesQuery = useQuery({
  queryKey: queryKeys.articles.list(status),
  queryFn: () =>
    apiGet<ArticleListItem[]>(`/articles?status_filter=${status}`),
})
```

**注意：**

如果原 URL 使用的是 `status` 而不是 `status_filter`，保持原 URL 参数，不要为了后端字段名破坏前端路由兼容性。只在请求 API 时转换成 `status_filter`。

**验证：**

```txt
/articles
/articles?status_filter=unread
/articles?status_filter=read
```

确认列表、状态 tab、文章跳转正常。

---

### Step 10 — Migrate Article Detail Page

**变更文件：**

```txt
apps/web/src/routes/articles/detail.tsx
```

**从这里迁移：**

```txt
apps/web/app/articles/[id]/page.tsx
apps/web/app/articles/[id]/actions.ts
```

**迁移规则：**

* `params` 改为 `useParams`
* 详情数据用 `useQuery`
* `markUnread` 改为 `useMutation`
* `reanalyze` 改为 `useMutation`
* `revalidatePath` 改为 `queryClient.invalidateQueries`
* `next/navigation` 改为 `react-router-dom`
* 文章 markdown 渲染保持原组件

**详情查询：**

```tsx
const { id } = useParams<{ id: string }>()

const articleQuery = useQuery({
  queryKey: queryKeys.articles.detail(id ?? ""),
  queryFn: () => apiGet<ArticleDetail>(`/articles/${id}`),
  enabled: Boolean(id),
})
```

**标记已读：**

如果进入详情页需要触发：

```tsx
const markReadMutation = useMutation({
  mutationFn: (articleId: string) => apiPost(`/articles/${articleId}/read`),
  onSuccess: (_, articleId) => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.articles.detail(articleId),
    })
    queryClient.invalidateQueries({
      queryKey: queryKeys.articles.all,
    })
  },
})
```

为了避免 React StrictMode 开发环境重复触发：

```tsx
const markedReadRef = useRef(false)

useEffect(() => {
  if (!id || markedReadRef.current) return
  markedReadRef.current = true
  markReadMutation.mutate(id)
}, [id])
```

**标记未读：**

```tsx
const markUnreadMutation = useMutation({
  mutationFn: (articleId: string) => apiPost(`/articles/${articleId}/unread`),
  onSuccess: (_, articleId) => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.articles.detail(articleId),
    })
    queryClient.invalidateQueries({
      queryKey: queryKeys.articles.all,
    })
  },
})
```

**重新分析：**

```tsx
const reanalyzeMutation = useMutation({
  mutationFn: (articleId: string) => apiPost(`/articles/${articleId}/reanalyze`),
  onSuccess: (_, articleId) => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.articles.detail(articleId),
    })
  },
})
```

**验证：**

```txt
/articles/:id
```

确认：

* 详情正常展示
* markdown 正常渲染
* 推荐 badge 正常展示
* 进入详情后可标记已读
* 按钮可标记未读
* 按钮可重新分析
* mutation 后列表 / 详情状态刷新正常

---

### Step 11 — Migrate Feeds Page

**变更文件：**

```txt
apps/web/src/routes/feeds/list.tsx
```

**从这里迁移：**

```txt
apps/web/app/feeds/page.tsx
apps/web/app/feeds/actions.ts
```

**迁移规则：**

* Server Component 改为普通 Client Component
* `form action={...}` 改为 `onSubmit`
* `addFeed` 改为 `useMutation`
* `refreshFeed` 改为 `useMutation`
* `deleteFeed` 改为 `useMutation`
* 成功后 invalidate `queryKeys.feeds.all`
* 表单提交中需要 disabled
* mutation error 需要显示错误信息

**Feed 列表查询：**

```tsx
const feedsQuery = useQuery({
  queryKey: queryKeys.feeds.list(),
  queryFn: () => apiGet<Feed[]>("/feeds"),
})
```

**新增 Feed：**

```tsx
const addFeedMutation = useMutation({
  mutationFn: (url: string) => apiPost("/feeds", { url }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
  },
})
```

**刷新 Feed：**

```tsx
const refreshFeedMutation = useMutation({
  mutationFn: (feedId: string) => apiPost(`/feeds/${feedId}/refresh`),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
    queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
  },
})
```

**删除 Feed：**

```tsx
const deleteFeedMutation = useMutation({
  mutationFn: (feedId: string) => apiDelete(`/feeds/${feedId}`),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
    queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
  },
})
```

**验证：**

```txt
/feeds
```

确认：

* Feed 列表正常展示
* 添加 Feed 正常
* 刷新 Feed 正常
* 删除 Feed 正常
* 操作后列表自动刷新
* 操作中按钮 disabled
* 操作失败有错误提示

---

### Step 12 — Set document title

**变更文件：**

```txt
apps/web/src/routes/articles/list.tsx
apps/web/src/routes/articles/detail.tsx
apps/web/src/routes/feeds/list.tsx
```

**规则：**

不引入 `react-helmet-async`，第一版直接用 `useEffect` 设置。

```tsx
useEffect(() => {
  document.title = "文章 - RSSWise"
}, [])
```

文章详情页在数据加载后设置：

```tsx
useEffect(() => {
  if (articleQuery.data?.title) {
    document.title = `${articleQuery.data.title} - RSSWise`
  }
}, [articleQuery.data?.title])
```

**验证：**

切换页面时浏览器 tab title 正常变化。

---

## Phase 4: Build, CSS and Lint

### Step 13 — Verify Tailwind and CSS pipeline

**变更文件：**

```txt
apps/web/src/globals.css
apps/web/postcss.config.mjs
apps/web/tailwind.config.ts
```

**检查点：**

* `src/main.tsx` 已 import `./globals.css`
* Tailwind v4 配置在 Vite 下可用
* `tw-animate-css` 生效
* shadcn-style primitives 样式正常

**验证：**

```bash
pnpm build
pnpm preview
```

打开页面确认样式不是裸 HTML。

---

### Step 14 — Replace ESLint config

**变更文件：**

```txt
apps/web/eslint.config.js
apps/web/package.json
```

**建议配置：**

```js
import js from "@eslint/js"
import tseslint from "typescript-eslint"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
)
```

**验证：**

```bash
pnpm lint
```

---

## Phase 5: Remove Next.js Artifacts

### Step 15 — Delete unused Next.js files

**删除：**

```txt
apps/web/app/
apps/web/.next/
apps/web/next-env.d.ts
apps/web/next.config.mjs
```

**从 package.json 删除：**

```txt
next
eslint-config-next
next lint
```

**不要删除：**

```txt
apps/web/.dockerignore
apps/web/public/
apps/web/tests/
apps/web/components.json
```

**如果存在 `.dockerignore`，更新为：**

```txt
node_modules
.next
dist
coverage
playwright-report
test-results
.env
.env.local
.env.*.local
```

**验证：**

```bash
pnpm build
pnpm lint
```

---

## Phase 6: Docker and Deployment

### Step 16 — Decide Docker build context

在修改 Dockerfile 前，先确认项目结构。

如果 `apps/web` 有自己的 `pnpm-lock.yaml`，可以使用：

```yaml
build:
  context: ./apps/web
  dockerfile: Dockerfile.prod
```

如果项目是 monorepo，`pnpm-lock.yaml` 和 `pnpm-workspace.yaml` 在仓库根目录，则应使用：

```yaml
build:
  context: .
  dockerfile: apps/web/Dockerfile.prod
```

优先按 monorepo 处理。

---

### Step 17 — Update Dockerfile.prod for monorepo

**变更文件：**

```txt
apps/web/Dockerfile.prod
```

**推荐 monorepo 版本：**

```dockerfile
FROM node:22-slim AS builder

WORKDIR /repo

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json

RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm --filter web build

FROM caddy:2-alpine

COPY --from=builder /repo/apps/web/dist /app/dist
COPY apps/web/Caddyfile /etc/caddy/Caddyfile
```

**注意：**

`pnpm --filter web build` 中的 `web` 必须与 `apps/web/package.json` 里的 `name` 一致。如果实际 package name 不是 `web`，需要替换成真实名称。

如果 `apps/web` 是独立包，则使用简化版本：

```dockerfile
FROM node:22-slim AS builder

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm build

FROM caddy:2-alpine

COPY --from=builder /app/dist /app/dist
COPY Caddyfile /etc/caddy/Caddyfile
```

**验证：**

monorepo：

```bash
docker build \
  -f apps/web/Dockerfile.prod \
  --build-arg VITE_API_BASE_URL=https://your-api-domain.example.com \
  .
```

独立包：

```bash
docker build \
  -f apps/web/Dockerfile.prod \
  --build-arg VITE_API_BASE_URL=https://your-api-domain.example.com \
  apps/web
```

---

### Step 18 — Add Caddyfile for SPA hosting

**新增或变更文件：**

```txt
apps/web/Caddyfile
```

**内容：**

```caddyfile
:80 {
    root * /app/dist
    try_files {path} /index.html
    file_server
}
```

如果该 Caddy 同时负责反向代理 API，可以使用：

```caddyfile
:80 {
    handle /api/* {
        reverse_proxy api:8000
    }

    handle {
        root * /app/dist
        try_files {path} /index.html
        file_server
    }
}
```

**关键点：**

`try_files {path} /index.html` 必须存在，否则直接刷新 `/articles/:id` 会 404。

**验证：**

```bash
caddy validate --config apps/web/Caddyfile
```

如果本地没有 caddy 命令，则用 Docker 容器启动后验证。

---

### Step 19 — Update docker-compose.prod.yml

**变更文件：**

```txt
docker-compose.prod.yml
```

**monorepo 推荐配置：**

```yaml
services:
  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile.prod
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL}
    ports:
      - "127.0.0.1:8080:80"
    restart: unless-stopped
```

**注意：**

Vite 的 `VITE_API_BASE_URL` 是构建期变量，不是运行时变量。修改 `.env` 后需要重新 build 镜像才会生效。

**验证：**

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d web
```

---

## Phase 7: E2E and Final Verification

### Step 20 — Update Playwright tests

**变更文件：**

```txt
apps/web/tests/e2e/articles.spec.ts
apps/web/tests/e2e/feeds.spec.ts
```

**迁移规则：**

* 删除对 Next.js SSR 初始 HTML 的假设
* 等待 CSR 数据加载完成后再断言
* 优先等待可见 UI，不要依赖固定 timeout
* 必要时等待 API response

**示例：**

```ts
await page.goto("/articles")
await expect(page.getByRole("heading", { name: /文章/ })).toBeVisible()
await expect(page.getByText(/Loading/)).not.toBeVisible()
```

或：

```ts
await page.waitForResponse((response) =>
  response.url().includes("/articles") && response.ok(),
)
```

**验证：**

```bash
pnpm test:e2e
```

---

### Step 21 — Final verification checklist

本地开发：

```bash
pnpm dev
```

确认：

* `/` 自动跳转到 `/articles`
* `/articles` 正常展示
* `/articles?status_filter=unread` 正常展示
* `/articles/:id` 正常展示
* `/feeds` 正常展示
* 页面间导航不刷新整页

构建：

```bash
pnpm build
pnpm preview
```

确认：

* build 成功
* preview 页面正常
* CSS 正常
* markdown 渲染正常
* 直接刷新 `/articles/:id` 正常

质量检查：

```bash
pnpm lint
pnpm test:e2e
```

确认：

* lint 通过
* E2E 通过

Docker：

```bash
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d web
```

确认：

* 容器启动正常
* 静态页面可访问
* API 请求地址正确
* 直接刷新深层路由不 404

---

## Recommended Execution Order

```txt
1. Update dependencies
2. Create Vite entry files
3. Move shared files into src
4. Create vite.config.ts
5. Rewrite tsconfig.json
6. Create query-client and query-keys
7. Update api.ts
8. Set up router and providers
9. Migrate articles list
10. Migrate article detail
11. Migrate feeds page
12. Set document title
13. Verify CSS pipeline
14. Replace ESLint config
15. Remove Next.js artifacts
16. Decide Docker build context
17. Update Dockerfile.prod
18. Add Caddyfile
19. Update docker-compose.prod.yml
20. Update Playwright tests
21. Run final verification
```

---

## Dependency Graph

```txt
Step 1
 └── Step 2
      ├── Step 3
      │    └── Step 4
      │         └── Step 5
      └── Step 6
           └── Step 7
                └── Step 8
                     ├── Step 9
                     ├── Step 10
                     └── Step 11

Step 9 + Step 10 + Step 11
 └── Step 12
      └── Step 13
           └── Step 14
                └── Step 15
                     └── Step 16
                          └── Step 17
                               └── Step 18
                                    └── Step 19
                                         └── Step 20
                                              └── Step 21
```

---

## Common Pitfalls

### 1. `VITE_API_BASE_URL` 修改后没有生效

Vite 环境变量是构建期注入。修改生产环境变量后，需要重新执行：

```bash
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d web
```

### 2. 直接刷新 `/articles/:id` 404

说明 Caddy 缺少 SPA fallback。确认 Caddyfile 有：

```caddyfile
try_files {path} /index.html
```

### 3. React StrictMode 下 mark read 请求触发两次

开发环境下 effect 可能重复执行。使用 `useRef` guard，或者确保后端接口幂等。

### 4. `@/components` import 报错

确认：

```ts
alias: {
  "@": path.resolve(__dirname, "./src")
}
```

并确认 `components`、`lib` 已经移动到 `src/`。

### 5. Docker build 找不到 `pnpm-lock.yaml`

说明 build context 配错。monorepo 应使用：

```yaml
build:
  context: .
  dockerfile: apps/web/Dockerfile.prod
```

而不是：

```yaml
build:
  context: ./apps/web
```

