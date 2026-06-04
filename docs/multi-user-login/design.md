# Multi-User Login Design

## Summary

RSSWise 将从单用户、无鉴权应用升级为开放注册的多用户 Web 应用。

本轮实现邮箱密码注册登录、HTTP-only Cookie Session、用户级 Feed 订阅、用户级文章已读状态。Feed、文章、正文抽取结果和 AI 分析结果继续作为全站共享内容库，避免同一个 Feed 被多个用户重复抓取、重复抽取和重复 AI 分析。

## Decisions

- 开放注册，使用邮箱和密码。
- 不做邮箱验证。
- 不做忘记密码或重置密码。
- 登录态使用 HTTP-only Cookie Session，不在前端保存 Bearer token。
- Feed、文章、正文、AI 分析全站共享。
- 每个用户有独立的 Feed 订阅关系。
- 每个用户有独立的已读/未读状态。
- 用户删除 Feed 时只取消自己的订阅，不删除共享 Feed 和文章。
- 现有历史 Feed 和文章迁移到一个初始默认用户名下。

## Current State

当前后端没有用户表，也没有鉴权依赖。`feeds`、`articles`、`article_contents` 和 `article_ai_analyses` 都是全局数据。

当前 `articles.is_read` 是全局已读状态，这与多用户模型冲突。启用多用户后，文章已读状态必须从用户维度读取。

当前前端所有 API 请求都不携带凭证，也没有登录页、注册页、当前用户状态或路由保护。

## Target Architecture

后端新增认证边界：

- `users` 保存账号。
- `sessions` 保存服务端会话。
- `user_feed_subscriptions` 保存用户订阅哪些共享 Feed。
- `user_article_states` 保存用户对文章的阅读状态。
- `get_current_user` 作为业务 API 的 FastAPI 依赖。

共享内容库保持：

- `feeds`：全站唯一 Feed URL。
- `articles`：全站唯一文章 URL，仍归属于一个共享 Feed。
- `article_contents`：每篇文章一份正文抽取结果。
- `article_ai_analyses`：每篇文章一份 AI 分析结果。

前端新增认证边界：

- 登录页 `/login`。
- 注册页 `/register`。
- `GET /auth/me` 驱动当前用户状态。
- 未登录访问 `/articles`、`/feeds` 等业务页面时跳转登录页。
- 登录、注册、退出登录后清理 React Query 缓存，避免用户切换时看到旧用户数据。

## Data Model

### users

字段：

- `id uuid primary key`
- `email string unique not null`
- `password_hash string not null`
- `created_at datetime not null`

邮箱作为登录标识。邮箱保存前统一去除首尾空白并转小写。

密码哈希使用后端标准库实现 PBKDF2-HMAC-SHA256，格式为：

```text
pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
```

第一版不新增外部密码哈希依赖。后续如果需要 Argon2 或 bcrypt，可以在不改变 API 合同的情况下迁移 `password_hash` 格式。

### sessions

字段：

- `id uuid primary key`
- `user_id uuid not null references users(id) on delete cascade`
- `token_hash string unique not null`
- `expires_at datetime not null`
- `created_at datetime not null`

登录成功时生成随机 session token，只把 token 的 SHA-256 哈希存入数据库。原始 token 只写入 HTTP-only Cookie。

Cookie 策略：

- 名称：`rsswise_session`
- `HttpOnly=true`
- `SameSite=Lax`
- 本地开发 `Secure=false`
- 生产环境 `Secure=true`
- 默认有效期 30 天

### user_feed_subscriptions

字段：

- `user_id uuid not null references users(id) on delete cascade`
- `feed_id uuid not null references feeds(id) on delete cascade`
- `created_at datetime not null`
- primary key: `(user_id, feed_id)`

同一个用户不能重复订阅同一个 Feed。多个用户可以订阅同一个 Feed。

### user_article_states

字段：

- `user_id uuid not null references users(id) on delete cascade`
- `article_id uuid not null references articles(id) on delete cascade`
- `is_read boolean not null default false`
- `updated_at datetime not null`
- primary key: `(user_id, article_id)`

没有状态行时等价于未读。标记已读或未读时 upsert 当前用户和文章的状态行。

`articles.is_read` 不再作为业务状态来源。迁移会把历史 `articles.is_read` 值复制到初始默认用户的 `user_article_states`，之后业务代码不再读取或写入该字段。

## API Design

公开端点：

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /health`

业务端点需要登录：

- `GET /feeds`
- `POST /feeds`
- `POST /feeds/{feed_id}/refresh`
- `DELETE /feeds/{feed_id}`
- `GET /articles`
- `GET /articles/{article_id}`
- `POST /articles/{article_id}/read`
- `POST /articles/{article_id}/unread`
- `POST /articles/{article_id}/reanalyze`

### Auth

`POST /auth/register`

请求：

```json
{
  "email": "user@example.com",
  "password": "correct horse battery staple"
}
```

行为：

- 邮箱格式必须合法。
- 密码最少 8 个字符。
- 邮箱已存在时返回 409。
- 注册成功后直接创建 session，并返回当前用户。

`POST /auth/login`

行为：

- 邮箱或密码错误时统一返回 401。
- 登录成功后创建 session，并覆盖旧 cookie。

`POST /auth/logout`

行为：

- 如果当前 cookie 对应有效 session，删除该 session。
- 无论是否已登录，都清除 cookie 并返回 204。

`GET /auth/me`

行为：

- 有有效 session 时返回当前用户。
- 无有效 session 时返回 401。

### Feeds

`GET /feeds` 只返回当前用户已订阅的 Feed。

`POST /feeds`：

- 如果全站已有相同 URL 的 Feed，只创建当前用户订阅。
- 如果全站没有该 URL，创建 Feed、抓取文章、创建当前用户订阅。
- 如果当前用户已经订阅该 Feed，返回现有订阅对应的 Feed 信息。

`POST /feeds/{feed_id}/refresh` 只允许刷新当前用户已订阅的 Feed。刷新任务仍对共享 Feed 生效。

`DELETE /feeds/{feed_id}` 只删除当前用户订阅，不删除共享 Feed、文章、正文或 AI 分析。

### Articles

`GET /articles`：

- 只展示当前用户已订阅 Feed 下的文章。
- `status_filter=read` 按当前用户已读状态过滤。
- `status_filter=unread` 展示没有状态行或状态行为未读的文章。
- 响应字段中的 `is_read` 来自 `user_article_states`。

`GET /articles/{article_id}`：

- 只有文章所属 Feed 已被当前用户订阅时才返回。
- 未订阅时返回 404，避免泄漏文章存在性。

`POST /articles/{article_id}/read` 和 `POST /articles/{article_id}/unread`：

- 只有订阅了文章所属 Feed 的用户可以操作。
- 只影响当前用户。

`POST /articles/{article_id}/reanalyze`：

- 只有订阅了文章所属 Feed 的用户可以触发。
- AI 分析结果仍是全站共享结果。

## Historical Data Migration

迁移新增认证表和用户关系表。

如果数据库中已有 Feed 或文章，迁移需要把它们挂到一个初始默认用户下：

- 初始用户邮箱来自 `INITIAL_USER_EMAIL`。
- 初始用户密码来自 `INITIAL_USER_PASSWORD`。
- 当存在历史 Feed 且缺少任一变量时，迁移失败并提示配置环境变量后重试。

迁移行为：

- 创建初始用户。
- 为所有现有 Feed 创建初始用户订阅。
- 为所有现有 Article 创建初始用户阅读状态，`is_read` 取历史 `articles.is_read`。

空数据库迁移时不强制创建初始用户。

## Frontend Design

新增页面：

- `/login`：邮箱密码登录，成功后进入 `/articles`。
- `/register`：邮箱密码注册，成功后进入 `/articles`。

新增状态：

- 当前用户由 `GET /auth/me` 读取。
- 未登录时业务页面不发起业务数据请求。
- 退出登录会调用 `POST /auth/logout`，然后清理查询缓存并跳转 `/login`。

请求行为：

- 所有 API 请求使用 `credentials: "include"`。
- API 错误为 401 时，前端清理当前用户状态并跳转登录页。

界面行为：

- 顶部导航显示当前用户邮箱。
- 顶部导航提供退出登录按钮。
- 登录和注册页不显示业务页面内容。

## Security

- 密码永不明文保存。
- Session 数据库存储 token 哈希，不存原始 token。
- Cookie 使用 HTTP-only，前端 JavaScript 不能读取 session token。
- 生产环境 Cookie 使用 Secure。
- 业务 API 默认需要登录。
- 订阅外文章详情返回 404，不返回 403。
- CORS 继续使用 allowlist，不开放任意 Origin。

第一版不实现：

- 邮箱验证。
- 密码重置。
- 多因素认证。
- 管理员角色。
- OAuth 登录。
- 细粒度权限管理。
- 自动清理无人订阅 Feed。
- CSRF token。第一版依赖 SameSite=Lax、CORS allowlist 和 JSON API 请求边界。

## Testing Strategy

后端测试：

- 注册成功会创建用户、设置 cookie、返回当前用户。
- 重复邮箱注册返回 409。
- 登录成功设置 cookie，错误密码返回 401。
- 退出登录删除 session 并清除 cookie。
- 未登录访问业务 API 返回 401。
- Feed 列表只返回当前用户订阅。
- 添加已存在共享 Feed 时只新增订阅，不重复抓取不重复建 Feed。
- 删除 Feed 只取消当前用户订阅。
- 文章列表只返回当前用户订阅 Feed 下的文章。
- 已读/未读状态按用户隔离。
- 未订阅文章详情、标记已读、重新分析返回 404。

前端验证：

- 未登录访问业务页面跳转登录。
- 注册后进入文章页。
- 登录后可以加载 Feed 和文章。
- 退出登录后回到登录页，旧数据缓存被清理。
- 前端构建通过。

## Acceptance Criteria

- 新用户可以通过邮箱密码注册并直接登录。
- 已注册用户可以登录和退出登录。
- Session Cookie 为 HTTP-only。
- 未登录用户不能访问 Feed 和文章业务 API。
- 用户只能看到自己订阅的 Feed。
- 用户只能看到自己订阅 Feed 下的文章。
- 已读/未读状态在用户之间独立。
- 同一个 Feed URL 被多个用户添加时，全站只保留一条 Feed。
- 同一篇文章的正文抽取和 AI 分析结果全站共享。
- 删除 Feed 只取消当前用户订阅，不删除共享内容。
- 历史数据迁移到初始默认用户订阅下。
- 后端测试和前端构建通过。
