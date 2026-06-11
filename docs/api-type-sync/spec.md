# Spec: 前后端 API 类型自动同步

## 背景与问题

当前 RSSWise 前后端类型完全手工同步：
- **后端**：20 个 Pydantic 模型（`apps/api/app/schemas.py`），FastAPI 未显式使用 `response_model`
- **前端**：13 个 TypeScript 类型（`apps/web/src/lib/api.ts`），与后端是独立副本
- 后端改字段时前端无法感知，编译期无法发现不匹配
- FastAPI 已自动生成 `/openapi.json`，但未被利用

## 目标

以 Pydantic 模型为唯一真相源，通过 OpenAPI 规范自动生成 TypeScript 类型，消除手工同步。

## 非目标

- 不引入 gRPC / GraphQL / tRPC
- 不替换 TanStack Query
- 不改变 SSE 流式传输机制
- 不改变 cookie-based session 认证方式

## 技术选型

| 角色 | 工具 | 原因 |
|------|------|------|
| 类型生成 | `openapi-typescript` | 最主流的 OpenAPI → TypeScript 工具，只生成类型不生成请求函数 |
| HTTP 客户端 | `openapi-fetch` | 同作者出品，2KB，消费生成的类型，类型安全的 fetch 封装 |
| 错误处理 | 封装 `queryFn<T>()` 辅助函数 | 统一将 `{ data, error }` 转为 TanStack Query 兼容的抛异常模式 |
| SSE 流 | 保留原生 `EventSource`，独立文件 `lib/sse.ts` | openapi-fetch 不支持 SSE |

## 接口契约

### 端点清单（19 个）

| 方法 | 路径 | 请求体 | 响应 | 认证 |
|------|------|--------|------|------|
| POST | `/auth/register` | `AuthRequest` | `UserRead` (201) | 无 |
| POST | `/auth/login` | `AuthRequest` | `UserRead` (200) | 无 |
| POST | `/auth/logout` | — | 204 | 无 |
| GET | `/auth/me` | — | `UserRead` (200) | 有 |
| GET | `/feeds` | — | `FeedRead[]` (200) | 有 |
| POST | `/feeds` | `FeedCreate` | `FeedRead` (201) | 有 |
| POST | `/feeds/imports` | `FeedImportCreate` | `FeedImportJobRead` (201) | 有 |
| GET | `/feeds/imports/{import_id}` | — | `FeedImportJobRead` (200) | 有 |
| POST | `/feeds/{feed_id}/refresh` | — | `FeedRefreshResponse` (202) | 有 |
| DELETE | `/feeds/{feed_id}` | — | 204 | 有 |
| GET | `/articles` | q: `status_filter` | `ArticleListItem[]` (200) | 有 |
| GET | `/articles/{article_id}` | — | `ArticleDetail` (200) | 有 |
| GET | `/articles/{article_id}/analysis/events` | — | SSE stream | 有 |
| POST | `/articles/{article_id}/read` | — | 204 | 有 |
| POST | `/articles/{article_id}/unread` | — | 204 | 有 |
| GET | `/settings/email-digest` | — | `EmailDigestSettingsRead` (200) | 有 |
| PUT | `/settings/email-digest` | `EmailDigestSettingsUpdate` | `EmailDigestSettingsRead` (200) | 有 |
| POST | `/settings/email-digest/test` | — | `EmailDigestTestResponse` (200) | 有 |
| GET | `/health` | — | `{"status":"ok"}` (200) | 无 |

### 需要后端补齐的响应模型

目前部分路由返回裸 `dict`，OpenAPI 无法推断精确类型。需改为 `response_model=`：

| 端点 | 当前 | 改为 | 文件 |
|------|------|------|------|
| `POST /feeds` | `{"id", "title", "url"}` 裸 dict | `FeedRead` (已有) | `routers/feeds.py` |
| `POST /feeds/{id}/refresh` | `{"feed_id","status"}` 裸 dict | 新增 `FeedRefreshResponse` | `routers/feeds.py`、`schemas.py` |
| `GET /articles` | 裸 dict 列表 | `ArticleListItem` (已有) | `routers/articles.py` |
| `GET /articles/{id}` | 裸 dict | `ArticleDetail` (已有) | `routers/articles.py` |

### OpenAPI 元数据增强

为提升生成类型的可读性和自文档化，统一补充：

- **路由层**：每个 router 加 `tags=["auth" | "feeds" | "articles" | "settings"]`
- **Schema 层**：关键字段加 `Field(description=...)`、`Field(examples=[...])`
- 涉及文件：`routers/*.py`、`schemas.py`

## 前端文件结构变更

```
apps/web/src/lib/
  api.ts            → 删除（原 13 个手写类型 + 5 个 fetch helper）
  schema.d.ts       → 新增（openapi-typescript 生成，提交到 git）
  client.ts         → 新增（createClient<paths> 实例 + queryFn 辅助函数）
  sse.ts            → 新增（从 api.ts 迁入 openApiEventSource）
  auth.ts           → 改造：apiGet/apiPost → GET/POST
  query-client.ts   → 不变
  query-keys.ts     → 不变
```

## 调用点迁移矩阵（21 个调用）

| 调用文件 | GET | POST | PUT | DELETE | SSE |
|-----------|-----|------|-----|--------|-----|
| `lib/auth.ts` | 1 | 3 | 0 | 0 | 0 |
| `routes/feeds/list.tsx` | 2 | 3 | 0 | 1 | 0 |
| `routes/articles/list.tsx` | 1 | 0 | 0 | 0 | 0 |
| `routes/articles/detail.tsx` | 1 | 1 | 0 | 0 | 0 |
| `routes/articles/workbench.tsx` | 2 | 1 | 0 | 0 | 0 |
| `components/email-digest-settings-dialog.tsx` | 1 | 1 | 2 | 0 | 0 |
| `routes/articles/use-article-analysis-events.ts` | 0 | 0 | 0 | 0 | 1 |

## 边界条件与约束

### 运行时
- **Base URL**：`VITE_API_BASE_URL` 构建时确定，默认 `/api`
- **认证**：`credentials: "include"`，cookie-based session
- **SSE**：`GET /articles/{id}/analysis/events` 返回 `text/event-stream`，`openapi-fetch` 不支持，保留 `EventSource`
- **204 No Content**：`openapi-fetch` 原生支持，`data` 为 `undefined`
- **错误响应**：FastAPI 错误格式 `{"detail": "..."}`，`openapi-fetch` 的 `error` 字段包含 `{ error: string; code: number }`

### TanStack Query 集成

```typescript
// client.ts 中封装
async function queryFn<T>(promise: Promise<{ data?: T; error?: ... }>): Promise<T> {
  const { data, error } = await promise;
  if (error) throw new Error(error);
  return data!;
}

// 使用
const query = useQuery({
  queryKey: articleKeys.list(status),
  queryFn: () => queryFn(GET('/articles', {
    params: { query: { status_filter: status } }
  })),
});
```

**不变**：`staleTime: 30s`、`retry: 1`、`refetchOnWindowFocus: false` 等 TanStack Query 配置。
**不变**：轮询逻辑（article detail 3s / feed import 2s）。
**不变**：`invalidateQueries` 在 mutation `onSuccess` 中的使用模式。

### CI 校验

`.github/workflows/check.yml` 新增步骤：确保 `schema.d.ts` 与 OpenAPI spec 同步，未同步则 CI 失败。

### 兼容性与回滚

- 新增的 `schema.d.ts` 是独立文件，不影响现有代码
- `client.ts` 是新增文件，旧 `api.ts` 可在迁移期保留
- 如出问题，删除 `client.ts` + `schema.d.ts`，恢复 `api.ts` 即可回滚
