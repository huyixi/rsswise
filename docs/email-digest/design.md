# Design: Email Digest

## Summary

RSSWise 新增邮件摘要功能。用户在设置 dialog 中配置一个收件邮箱、启用状态、发送间隔天数和发送时间。系统按 `Asia/Shanghai` 时区巡检是否到达下一次应发送时间；如果有自上次成功发送后新增的文章，则生成一个 EPUB 附件，并通过后端统一 SMTP 发件账号发送。

本轮采用全局单例设置，不引入认证、多用户或多个收件邮箱。发送频率使用 `send_interval_days` 表示，范围为 1 到 30 天，默认 1 天。表结构和 API 命名保留向未来用户级偏好迁移的空间。

## Decisions From Requirement Discovery

- 邮件类型：按用户配置间隔定时发送的摘要。
- 收件邮箱：前端设置 dialog 配置一个邮箱，后端落库。
- 发件账号：系统统一 SMTP 发件，用户不提供发件邮箱或 SMTP 密钥。
- 启用控制：设置 dialog 包含“启用邮件摘要”开关。
- 发送频率：用户可配置发送间隔天数，范围 1 到 30 天，默认 1 天。
- 发送时间：用户可配置每次到点检查的发送时间，默认 `08:00`。
- 时区：固定 `Asia/Shanghai`，本轮不提供时区设置。
- 文章范围：默认发送所有新增文章，即 `last_sent_at` 之后进入系统的文章；首次成功发送前发送当前已有全部文章。
- 邮件内容：每次发送时，将所有新增文章打包成一个 EPUB 附件。
- EPUB 每篇文章包含标题、来源、原文链接、AI 一句话总结、阅读理由和正文全文。
- 正文抽取失败或未完成的文章仍进入 EPUB，但只放标题、来源、链接、AI 摘要和阅读理由。
- AI 内容缺失不阻塞发送。
- 没有新增文章时不发送邮件，只记录本次检查结果。
- 设置 dialog 提供发送测试邮件按钮，用于验证 SMTP 配置和收件地址。

## Current State

后端是 FastAPI + SQLAlchemy + Alembic + Celery + Redis：

```text
apps/api/app/core/config.py        # Pydantic settings
apps/api/app/models.py             # SQLAlchemy models
apps/api/app/schemas.py            # Pydantic API schemas
apps/api/app/routers/*.py          # API routes
apps/api/app/tasks.py              # Celery tasks
apps/api/app/beat.py               # Celery beat schedule
apps/api/app/services/*.py         # Feed, extraction, AI services
apps/api/alembic/versions/*.py     # DB migrations
```

现有 `feeds.refresh_all` 每小时刷新所有 Feed；文章创建后会异步抽取正文并做 AI 分析。

前端是 React + Vite + TanStack Query + coss UI：

```text
apps/web/src/App.tsx
apps/web/src/lib/api.ts
apps/web/src/lib/query-keys.ts
apps/web/src/components/ui/dialog.tsx
apps/web/src/components/ui/input.tsx
apps/web/src/components/ui/switch.tsx
apps/web/src/components/ui/field.tsx
```

当前没有用户、认证、设置页或邮件发送实现。旧环境变量规划中预留了 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`，但尚未接入代码。

## Target Behavior

### Settings Dialog

应用导航区新增设置入口，打开“邮件摘要” dialog。

dialog 展示：

- 收件邮箱输入框。
- 发送间隔天数输入，默认 `1`，范围 1 到 30。
- 发送时间输入，默认 `08:00`。
- 固定时区说明：`Asia/Shanghai`。
- 启用邮件摘要开关。
- 保存按钮。
- 发送测试邮件按钮。
- 最近一次摘要状态：成功、失败、无新增文章、跳过未配置等。

保存行为：

- 收件邮箱为空时允许保存，但启用状态必须自动变为关闭，或后端拒绝 `enabled=true` 且邮箱为空的请求。
- `send_interval_days` 必须是 1 到 30 之间的整数。
- `send_time` 必须是 `HH:MM` 24 小时格式。
- 前端不暴露 SMTP 主机、用户名、密码或发件邮箱。

测试邮件行为：

- 使用当前已保存的收件邮箱发送测试邮件。
- 测试邮件不生成 EPUB，不更新 `last_sent_at`，不影响摘要发送状态。
- SMTP 未配置或邮箱为空时返回明确错误。

### Digest Schedule

Celery beat 增加一个轻量巡检任务，例如每 5 分钟运行一次。任务读取全局邮件摘要设置，并按 `Asia/Shanghai` 计算当前本地日期和时间。发送间隔由 `send_interval_days` 决定，不通过动态重写 Celery beat schedule 实现。

发送判断：

1. 设置不存在时创建默认设置。
2. `enabled=false` 时跳过。
3. 收件邮箱为空时跳过。
4. 当前上海时间早于 `send_time` 时跳过。
5. 当天已经运行过摘要检查时跳过。
6. 如果 `last_run_date` 存在，且当前日期距离 `last_run_date` 小于 `send_interval_days`，则跳过。
7. 查询 `Article.created_at > last_sent_at` 的文章；如果 `last_sent_at` 为空，则查询所有文章。
8. 没有新增文章时不发邮件，记录当天已检查和状态 `skipped_no_articles`。
9. 有新增文章时生成 EPUB 并发送邮件。
10. SMTP 发送成功后更新 `last_sent_at`、`last_run_date`、`last_send_status=success` 和发送统计。
11. SMTP 发送失败时记录 `last_run_date`、`last_send_status=failed` 和错误摘要，但不更新 `last_sent_at`。下一次满足发送间隔时会重新尝试发送仍未成功发送的文章。

这种巡检式调度避免用户修改发送时间或发送间隔后动态重写 Celery beat schedule。

## Data Model

新增 `EmailDigestSetting`，当前作为全局单例使用：

```text
email_digest_settings
- id                       integer primary key, fixed to 1
- recipient_email          string(320), nullable
- enabled                  boolean, default false
- send_interval_days       integer, default 1
- send_time                time, default 08:00
- last_run_date            date, nullable
- last_sent_at             datetime(timezone=True), nullable
- last_attempted_at        datetime(timezone=True), nullable
- last_send_status         string(50), nullable
- last_send_error          text, nullable
- last_sent_article_count  integer, default 0
- created_at               datetime(timezone=True)
- updated_at               datetime(timezone=True)
```

`timezone` 不落库，API 固定返回 `Asia/Shanghai`。

状态值：

```text
success
failed
skipped_disabled
skipped_missing_recipient
skipped_before_send_time
skipped_already_ran_today
skipped_interval_not_due
skipped_no_articles
```

未来多用户迁移时有两条可选路径：

- 在当前表增加 `user_id`，把唯一全局行迁移为用户级偏好行。
- 新建用户级偏好表，将当前全局设置迁移给默认用户。

## API Design

新增 router：`app.routers.settings`。

### `GET /settings/email-digest`

返回当前全局设置。如果不存在，创建默认设置并返回。

响应字段：

```json
{
  "recipient_email": "reader@example.com",
  "enabled": true,
  "send_interval_days": 1,
  "send_time": "08:00",
  "timezone": "Asia/Shanghai",
  "last_run_date": "2026-06-04",
  "last_sent_at": "2026-06-04T00:00:00Z",
  "last_attempted_at": "2026-06-04T00:00:00Z",
  "last_send_status": "success",
  "last_send_error": null,
  "last_sent_article_count": 12
}
```

### `PUT /settings/email-digest`

请求：

```json
{
  "recipient_email": "reader@example.com",
  "enabled": true,
  "send_interval_days": 7,
  "send_time": "08:00"
}
```

校验：

- `recipient_email` 为空字符串时保存为 `null`。
- `enabled=true` 时必须有合法邮箱。
- `send_interval_days` 必须是 1 到 30 之间的整数。
- `send_time` 必须符合 `HH:MM`，小时 `00-23`，分钟 `00-59`。

### `POST /settings/email-digest/test`

发送测试邮件到已保存邮箱。

响应：

```json
{
  "status": "sent"
}
```

错误：

- `400`：未配置收件邮箱。
- `400`：SMTP 环境变量缺失。
- `502`：SMTP 服务连接或发送失败。

## SMTP Configuration

后端环境变量新增或启用：

```text
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=RSSWise
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=20
```

约束：

- 所有 SMTP 变量只属于 `apps/api/.env*`。
- `SMTP_PASSWORD` 不允许出现在前端环境变量或 Compose public build args 中。
- `SMTP_USE_TLS` 表示 STARTTLS，常用于 587 端口。
- `SMTP_USE_SSL` 表示 SSL/TLS socket，常用于 465 端口。
- `SMTP_USE_TLS` 和 `SMTP_USE_SSL` 不能同时为 true。

## EPUB Generation

不新增 EPUB 第三方依赖。本轮使用 Python 标准库生成固定结构 EPUB：

```text
mimetype
META-INF/container.xml
OEBPS/content.opf
OEBPS/nav.xhtml
OEBPS/toc.ncx
OEBPS/chapters/article-001.xhtml
OEBPS/chapters/article-002.xhtml
```

正文处理：

- `content_markdown` 存在时转换为安全 XHTML 段落内容。
- 本轮不引入 Markdown 解析依赖；先用基础转义和段落换行转换，确保 EPUB 可读和安全。
- 链接以可点击文本形式展示。
- AI 摘要和阅读理由为空时展示“暂无 AI 总结”或省略对应段落。

EPUB metadata：

- Title：`RSSWise Digest - YYYY-MM-DD`
- Language：`zh-CN`
- Creator：`RSSWise`
- Identifier：基于日期和生成时间的唯一 URN。

邮件附件名：

```text
RSSWise-YYYY-MM-DD.epub
```

## Email Content

摘要邮件正文保持简洁：

- 主题：`RSSWise 摘要 - YYYY-MM-DD`
- 正文说明本次包含多少篇文章。
- 附件为 EPUB。
- 邮件正文不内联所有文章，避免内容过长。

测试邮件：

- 主题：`RSSWise 测试邮件`
- 正文说明 SMTP 和收件邮箱配置已可用。
- 不包含附件。

## Error Handling

- SMTP 缺失配置：API 测试邮件返回 `400`，定时任务记录 `failed`。
- SMTP 发送失败：记录错误摘要，不更新 `last_sent_at`。
- EPUB 生成失败：记录 `failed`，不发送邮件，不更新 `last_sent_at`。
- 没有新增文章：记录 `skipped_no_articles`，不发送邮件。
- 未达到发送间隔：记录 `skipped_interval_not_due`，不发送邮件。
- 未启用或无邮箱：记录跳过状态，不发送邮件。
- 单篇文章正文或 AI 缺失不算失败。

## Testing And Acceptance

后端测试覆盖：

- Settings 读取 SMTP env、默认值和互斥 TLS/SSL 校验。
- Alembic 迁移创建 `email_digest_settings`。
- API 默认读取、保存、邮箱、发送间隔、时间校验、测试邮件错误路径。
- EPUB 生成包含标题、来源、链接、AI 摘要、阅读理由和正文；正文缺失时仍包含文章元信息。
- Digest 任务按 `send_interval_days`、`send_time` 和 `Asia/Shanghai` 判断是否应该发送。
- 成功发送更新 `last_sent_at`；失败不更新 `last_sent_at`。
- 无新增文章不调用 SMTP。

前端测试覆盖：

- 设置 dialog 能读取并展示邮箱、启用状态、发送间隔、发送时间和时区。
- 保存设置会调用 `PUT /settings/email-digest`。
- 发送测试邮件会调用 `POST /settings/email-digest/test`。
- 邮箱为空且启用时显示错误或保存失败反馈。

验收标准：

- 用户可以在 UI 中配置一个收件邮箱、启用开关、发送间隔天数和发送时间。
- 后端只通过 SMTP 环境变量发件。
- 到达配置的发送间隔和发送时间后，有新增文章才发送 EPUB 邮件。
- EPUB 包含所有新增文章；正文成功的文章包含全文，正文失败或未完成的文章包含元信息和摘要。
- 没有新增文章时不发送邮件。
- 测试邮件不影响正式摘要发送状态。

## Out Of Scope

- 不做登录、认证、多用户或用户级设置。
- 不做多个收件邮箱。
- 不做发件邮箱由用户配置。
- 不做时区配置，固定 `Asia/Shanghai`。
- 不做按 Feed、AI 推荐等级或已读状态筛选。
- 不做“今日无新增文章”通知邮件。
- 不做邮件打开追踪、退订链接、投递回执。
- 不做 EPUB 样式主题配置。
