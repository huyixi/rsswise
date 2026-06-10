# Plan: 前后端 API 类型自动同步

## 总体策略

分 4 个阶段，按依赖顺序执行。每阶段结束有验证检查点，确认无误再进入下一阶段。

---

## 阶段 0：准备工作

### 0.1 确认 OpenAPI 现状

- [ ] 启动后端，访问 `http://localhost:8000/openapi.json`，确认可用
- [ ] 访问 `http://localhost:8000/docs`，浏览 Swagger UI 检查现有 schema 质量
- [ ] 记录当前 `/openapi.json` 中哪些端点缺少 response schema（返回裸 dict）

**验证**：`curl -s http://localhost:8000/openapi.json | jq '.paths | keys'` 输出所有端点路径

---

## 阶段 1：后端补齐 Pydantic 响应模型

### 1.1 新增 `FeedRefreshResponse`

**文件**：`apps/api/app/schemas.py`

```python
class FeedRefreshResponse(BaseModel):
    feed_id: UUID
    status: str = "queued"
```

### 1.2 给路由加 `response_model`

**文件**：`apps/api/app/routers/feeds.py`

- [ ] `POST /feeds` → `response_model=FeedRead`
- [ ] `POST /feeds/{feed_id}/refresh` → `response_model=FeedRefreshResponse`

**文件**：`apps/api/app/routers/articles.py`

- [ ] `GET /articles` → `response_model=list[ArticleListItem]`
- [ ] `GET /articles/{article_id}` → `response_model=ArticleDetail`

### 1.3 OpenAPI 元数据增强

**文件**：`apps/api/app/routers/auth.py`

- [ ] router 加 `tags=["auth"]`

**文件**：`apps/api/app/routers/feeds.py`

- [ ] router 加 `tags=["feeds"]`

**文件**：`apps/api/app/routers/articles.py`

- [ ] router 加 `tags=["articles"]`

**文件**：`apps/api/app/routers/settings.py`

- [ ] router 加 `tags=["settings"]`

**文件**：`apps/api/app/schemas.py`

- [ ] 关键字段加 `Field(description=...)`，例如：
  - `FeedImportCreate.source_type` → `Field(description="导入来源：opml 文件或 URL 列表")`
  - `EmailDigestSettingsUpdate.send_time` → `Field(description="发送时间，格式 HH:MM", examples=["08:00"])`
  - `ArticleListItem.one_sentence_summary` → `Field(description="AI 生成的一句话摘要")`
  - `ArticleListItem.reading_recommendation` → `Field(description="阅读建议：deep_read / skim / skip")`

### 1.4 验证

- [ ] 重启后端，`/openapi.json` 应包含所有 `response_model` 的完整 schema
- [ ] Swagger UI (`/docs`) 应能展示 `tags` 分组
- [ ] `curl localhost:8000/openapi.json | jq '.components.schemas | keys'` 确认所有 Pydantic 模型都在

---

## 阶段 2：前端安装工具 + 生成类型

### 2.1 安装依赖

```bash
cd apps/web
pnpm add openapi-fetch
pnpm add -D openapi-typescript
```

### 2.2 配置生成脚本

**文件**：`apps/web/package.json`

```json
{
  "scripts": {
    "gen-types": "openapi-typescript http://localhost:8000/openapi.json -o ./src/lib/schema.d.ts"
  }
}
```

### 2.3 首次生成 + 提交

- [ ] 确保后端在 `localhost:8000` 运行
- [ ] 执行 `pnpm gen-types`
- [ ] 确认 `src/lib/schema.d.ts` 生成成功
- [ ] 提交 `schema.d.ts` 到 git

### 2.4 验证

- [ ] 打开 `schema.d.ts`，检查 `paths` 类型包含所有端点的请求/响应类型
- [ ] `components["schemas"]` 应包含所有 Pydantic 模型对应的 TS 类型

---

## 阶段 3：前端替换客户端代码

### 3.1 新建 `lib/sse.ts`（从 api.ts 迁移 SSE）

- [ ] 从 `api.ts` 移出 `openApiEventSource` 函数
- [ ] 如有 `buildApiUrl` 依赖，同步迁移

### 3.2 新建 `lib/client.ts`

- [ ] `createClient<paths>` 实例化，`baseUrl` 从 `VITE_API_BASE_URL` 读取，`credentials: "include"`
- [ ] 导出 `{ GET, POST, PUT, DELETE }`
- [ ] 封装 `queryFn<T>()` 辅助函数

### 3.3 改造 `lib/auth.ts`（4 个调用）

| 原调用 | 改为 |
|--------|------|
| `apiGet<CurrentUser>("/auth/me")` | `queryFn(GET("/auth/me"))` |
| `apiPost<CurrentUser>("/auth/login", p)` | `queryFn(POST("/auth/login", { body: p }))` |
| `apiPost<CurrentUser>("/auth/register", p)` | `queryFn(POST("/auth/register", { body: p }))` |
| `apiPost<void>("/auth/logout")` | `POST("/auth/logout")` |

- [ ] 删除 `CurrentUser` 类型定义，从 `schema.d.ts` 导入 `components["schemas"]["UserRead"]`
- [ ] 删除 `import { apiGet, apiPost } from "./api"`，改为 `import { GET, POST, queryFn } from "./client"`

### 3.4 改造 `routes/articles/list.tsx`（1 个调用）

| 原调用 | 改为 |
|--------|------|
| `apiGet<ArticleListItem[]>(\`/articles?status_filter=...\`)` | `queryFn(GET("/articles", { params: { query: { status_filter: status } } }))` |

### 3.5 改造 `routes/articles/detail.tsx`（2 个调用）

| 原调用 | 改为 |
|--------|------|
| `apiGet<ArticleDetail>(\`/articles/${id}\`)` | `queryFn(GET("/articles/{article_id}", { params: { path: { article_id: id } } }))` |
| `apiPost(\`/articles/${id}/read\`)` | `POST("/articles/{article_id}/read", { params: { path: { article_id: id } } })` |

### 3.6 改造 `routes/articles/workbench.tsx`（3 个调用）

同 list.tsx + detail.tsx 模式：

| 原调用 | 改为 |
|--------|------|
| `apiGet<ArticleListItem[]>(...)` | `queryFn(GET("/articles", { params: { query: { status_filter } } }))` |
| `apiGet<ArticleDetail>(...)` | `queryFn(GET("/articles/{article_id}", { params: { path: { article_id } } }))` |
| `apiPost(...)` | `POST("/articles/{article_id}/read", ...)` |

### 3.7 改造 `routes/feeds/list.tsx`（6 个调用）

| 原调用 | 改为 |
|--------|------|
| `apiGet<Feed[]>("/feeds")` | `queryFn(GET("/feeds"))` |
| `apiPost("/feeds", { url })` | `POST("/feeds", { body: { url } })` |
| `apiPost(\`/feeds/${id}/refresh\`)` | `POST("/feeds/{feed_id}/refresh", { params: { path: { feed_id: id } } })` |
| `apiDelete(\`/feeds/${id}\`)` | `DELETE("/feeds/{feed_id}", { params: { path: { feed_id: id } } })` |
| `apiGet<FeedImportJob>(\`/feeds/imports/${id}\`)` | `queryFn(GET("/feeds/imports/{import_id}", { params: { path: { import_id: id } } }))` |
| `apiPost<FeedImportJob>("/feeds/imports", p)` | `queryFn(POST("/feeds/imports", { body: p }))` |

### 3.8 改造 `components/email-digest-settings-dialog.tsx`（4 个调用）

| 原调用 | 改为 |
|--------|------|
| `apiGet<EmailDigestSettings>("/settings/email-digest")` | `queryFn(GET("/settings/email-digest"))` |
| `apiPut<EmailDigestSettings>("/settings/email-digest", p)` | `queryFn(PUT("/settings/email-digest", { body: p }))` |
| `apiPost("/settings/email-digest/test")` | `POST("/settings/email-digest/test")` |

### 3.9 改造 `routes/articles/use-article-analysis-events.ts`（1 个调用）

- [ ] 改 `import { openApiEventSource } from "@/lib/api"` 为 `import { openApiEventSource } from "@/lib/sse"`

### 3.10 清理 `lib/api.ts`

- [ ] 删除手写 TypeScript 类型：`ReadingRecommendation`, `AiBlock`, `ArticleListItem`, `ArticleDetail`, `Feed`, `FeedImportSourceType`, `FeedImportJobStatus`, `FeedImportItemStatus`, `FeedImportItem`, `FeedImportJob`, `FeedImportCreateRequest`, `EmailDigestSettings`, `EmailDigestSettingsUpdate`
- [ ] 删除辅助函数：`apiGet`, `apiPost`, `apiPut`, `apiDelete`, `parseResponse`, `buildApiUrl`, `getApiBaseUrl`
- [ ] 删除文件（已全部迁移完成）或保留为 re-export 的兼容层

### 3.11 类型导入清理

- [ ] 检查所有 import 语句，删除 `from "./api"` 的类型导入
- [ ] 改为 `import type { components } from "@/lib/schema"` 或 `import type { paths } from "@/lib/schema"`
- [ ] 按需定义类型别名，例如：`type Feed = components["schemas"]["FeedRead"]`

### 3.12 验证

- [ ] `pnpm typecheck` 或 `pnpm tsc --noEmit` 通过
- [ ] `pnpm dev` 启动前端，逐页面测试（登录、文章列表、文章详情、订阅管理、邮件设置）
- [ ] 测试 204 端点（登出、标记已读）
- [ ] 测试 SSE 流（AI 分析）
- [ ] 测试错误响应（无效请求）

---

## 阶段 4：CI 校验 + 文档

### 4.1 CI 类型同步检查

**文件**：`.github/workflows/check.yml`

在现有 check job 中新增步骤：

```yaml
- name: Check generated API types
  working-directory: apps/web
  run: |
    pnpm gen-types
    git diff --exit-code src/lib/schema.d.ts
```

### 4.2 添加本地开发说明

**文件**：`apps/web/README.md`（如有）或项目根 `README.md` 的开发部分

- [ ] 加一行说明后端类型变更后需要执行 `pnpm gen-types`
- [ ] 说明 `schema.d.ts` 不要手动编辑

### 4.3 最终验证

- [ ] 完整走一遍 CI 流程（typescript check + gen-types check）
- [ ] 确认 `schema.d.ts` 在 git 中正确追踪

---

## 回滚方案

如需回滚：
1. 删除 `apps/web/src/lib/schema.d.ts`
2. 删除 `apps/web/src/lib/client.ts`
3. 删除 `apps/web/src/lib/sse.ts`
4. `git checkout` 恢复 `apps/web/src/lib/api.ts`
5. 恢复 7 个调用文件的 `import` 语句

后端改动无需回滚（仅添加 `response_model`，不改变行为）。

---

## 工时估算

| 阶段 | 预估 |
|------|------|
| 阶段 1：后端补齐 | 15 min |
| 阶段 2：装包生成 | 10 min |
| 阶段 3：前端改造 | 45 min |
| 阶段 4：CI + 文档 | 15 min |
| **总计** | **~1.5 h** |
