# AI 摘要流式生成设计

## 背景

RSSWise 当前的 AI 分析流程是后台 Celery 任务在正文抽取成功后调用 DeepSeek 兼容接口，一次性拿到 JSON，校验后写入 `article_ai_analyses`。前端详情页通过 `/articles/{id}` 获取最终结果，并在 `extraction_status` 或 `analysis_status` 为 `processing` 时每 3 秒轮询。

本次改动要删除面向用户的“重新 AI 分析”能力，并让用户打开新文章详情页时，如果 AI 分析仍在等待或生成中，可以看到自动分析任务的流式生成过程。用户打开详情页还应能让尚未开始的文章分析插队；插队只影响尚未开始的任务，不中断已经在分析中的其它文章。

## 目标

- 删除用户可见的“重新 AI 分析”功能和对应 API。
- 新文章自动分析仍由 worker 负责执行，不由浏览器请求直接执行。
- 用户打开文章详情页时，如果 AI 分析处于 `pending`，该文章以高优先级进入待分析任务。
- 如果 AI 分析处于 `processing`，详情页订阅当前生成流，不重复投递任务，不抢占其它任务。
- 前端在桌面详情侧栏和移动端详情页都能显示流式生成内容。
- 数据库只保存最终通过结构化校验的 AI 分析结果，不保存半成品。
- 断开浏览器连接不影响后台 AI 任务。

## 非目标

- 不做用户手动重新分析。
- 不做取消、暂停或抢占已经开始的 AI 请求。
- 不引入 WebSocket。
- 不新增长摘要、评分、关键词或 target readers。
- 不改变一篇文章只保留一份共享 AI 分析结果的产品约束。

## 推荐架构

使用 Celery task priority、Redis Streams 和 SSE。

- Celery worker 继续负责 AI 分析。
- 普通自动分析以后台优先级投递。
- 用户打开详情页时，后端将 `pending` 文章以高优先级投递。
- worker 调用 DeepSeek streaming 接口，把生成片段写入 Redis Stream。
- FastAPI SSE 端点从 Redis Stream 读取事件并转发给浏览器。
- AI 响应完整结束后，worker 使用现有 `parse_ai_result` 校验 JSON，并把最终结构化结果写入数据库。

选择 Redis Streams 而不是纯 Pub/Sub，是因为 Streams 可以支持短期回放。浏览器刷新、SSE 断线重连或移动端切换页面后，可以根据 `Last-Event-ID` 继续读取最近事件。

## 后端接口

### `GET /articles/{article_id}/analysis/events`

认证要求与 `/articles/{article_id}` 相同：只有订阅了该文章 Feed 的当前用户可以访问。

连接建立时：

1. 读取文章、正文和 AI 分析记录。
2. 如果文章不存在或不属于当前用户，返回 `404`。
3. 如果正文尚未抽取成功，返回一个 `waiting_content` SSE 事件，然后结束或保持短轮询等待。第一版采用结束连接，让前端继续依赖现有详情轮询等待正文成功。
4. 如果 `analysis_status` 是 `pending`，投递高优先级分析任务，然后开始监听 Redis Stream。
5. 如果 `analysis_status` 是 `processing`，直接监听 Redis Stream。
6. 如果 `analysis_status` 是 `success`，返回 `done` 事件，前端刷新详情数据。
7. 如果 `analysis_status` 是 `failed`，返回 `error` 事件，前端显示失败状态。

SSE 事件类型：

```text
event: started
data: {"article_id":"..."}

event: chunk
data: {"text":"..."}

event: done
data: {"article_id":"..."}

event: error
data: {"message":"AI 分析失败"}
```

SSE 连接应支持 `Last-Event-ID`。服务端用 Redis Stream entry id 作为 SSE id。

## Redis 事件模型

每篇文章使用一个短期 Stream：

```text
article-analysis:{article_id}:events
```

事件字段：

```text
type=started|chunk|done|error
data=<json string>
```

worker 在任务开始时删除旧的同名 Stream，写入新的 `started` 事件，并设置 TTL。每次 chunk 写入 `chunk` 事件。完成后写入 `done`，失败后写入 `error`。TTL 建议为 30 分钟，避免 Redis 长期积累事件。

如果 SSE 端点发现数据库已经是 `success`，不要求 Redis Stream 仍存在；直接返回 `done` 即可。

## Celery 优先级与插队

AI 分析任务使用 Celery 的 task priority，而不是依赖多队列轮询顺序。Redis broker 需要开启优先级队列排序：

```python
celery_app.conf.task_queue_max_priority = 10
celery_app.conf.broker_transport_options = {
    "queue_order_strategy": "priority",
}
```

Redis broker 的优先级排序是反向的，`0` 表示最高优先级。定义两个常量：

```python
AI_PRIORITY_USER_OPENED = 0
AI_PRIORITY_BACKGROUND = 5
```

普通自动分析使用后台优先级：

```python
analyze_article_task.apply_async(args=[article_id], priority=AI_PRIORITY_BACKGROUND)
```

详情页插队使用最高优先级：

```python
analyze_article_task.apply_async(args=[article_id], priority=AI_PRIORITY_USER_OPENED)
```

worker 启动命令可以保持不变，但必须使用包含上述 Celery 配置的 `app.tasks.celery_app`：

```text
celery -A app.tasks.celery_app worker --loglevel=INFO
```

任务开始前必须重新检查数据库状态：

- `success`：直接跳过。
- `processing`：直接跳过，避免重复任务。
- `pending` 且正文存在：设置为 `processing` 后开始流式分析。
- 正文不存在或抽取未成功：失败或跳过由现有正文抽取流程决定；第一版保持现有行为，分析任务缺少 markdown 时抛错并标记失败。

由于插队只对 `pending` 生效，已经在运行的 AI 请求不会被取消或抢占。

如果后续实测 Redis priority 在当前部署中不能满足插队延迟要求，再增加一个只消费高优先级任务的独立 worker。第一版不引入该额外服务。

## AI 服务改造

保留现有结构化模型：

- `one_sentence_summary`
- `reading_recommendation`
- `reading_reason`

新增流式分析函数，例如：

```python
def stream_analyze_markdown_with_deepseek(markdown: str) -> Iterator[str]:
    ...
```

该函数只负责逐步产出原始文本片段。worker 负责把片段累积为完整字符串，结束后调用 `parse_ai_result`。最终结果仍必须是合法 JSON，且必须符合现有字段和枚举约束。

系统 prompt 继续要求只返回 JSON。由于 JSON 流式输出在中间阶段不可解析，前端流式区只展示“正在生成的文本”，不把中间内容当作最终结构化结果。

## 前端行为

删除手动入口：

- 删除文章详情中任何“重新 AI 分析”按钮。
- 删除调用 `/articles/{id}/reanalyze` 的 mutation。
- 删除前端类型或测试中依赖手动重分析的断言。

新增流式订阅：

- 当详情数据中 `analysis_status` 为 `pending` 或 `processing`，建立 SSE 连接。
- 收到 `started` 后显示生成中状态。
- 收到 `chunk` 后把文本追加到本地流式状态。
- 收到 `done` 后关闭连接，刷新当前文章详情 query，并刷新文章列表 query。
- 收到 `error` 后关闭连接，显示失败状态，并刷新详情 query。
- 组件卸载、切换文章或路由离开时关闭 SSE。

展示规则：

- 如果有最终 `one_sentence_summary / reading_reason / reading_recommendation`，优先展示最终结构化结果。
- 如果没有最终结果但有流式文本，展示流式文本，并保持“AI 总结生成中”的状态。
- 如果没有最终结果且没有流式文本，展示现有“AI 总结处理中”状态。
- 桌面 `AISummaryPanel` 和移动端 `ArticleDetailPage` 复用同一套 `ArticleAiSummary` 或新 hook。

## 数据一致性

数据库仍是最终事实来源。Redis Stream 只用于临时用户体验。

分析成功时：

1. worker 收集完整 AI 响应文本。
2. `parse_ai_result` 校验 JSON。
3. 写入 `ArticleAIAnalysis` 的三个结果字段。
4. 设置 `analysis_status = success`。
5. 写入 Redis `done` 事件。

分析失败时：

1. 设置 `analysis_status = failed`。
2. 更新 `updated_at`。
3. 写入 Redis `error` 事件。
4. 让 Celery 任务按现有方式失败，保留日志。

如果浏览器断线，worker 继续运行。用户重开详情页时，如果分析已成功，直接看到最终数据库结果；如果仍在处理中，通过 Redis Stream 继续读取近期事件。

## 错误处理

- AI 配置缺失：任务失败，状态为 `failed`，SSE 返回 `error`。
- AI 返回空内容：任务失败，状态为 `failed`，SSE 返回 `error`。
- AI 返回非法 JSON：任务失败，状态为 `failed`，SSE 返回 `error`。
- Redis 暂时不可用：任务仍应尽量完成数据库写入；SSE 体验失败但最终结果可通过详情刷新获得。
- 用户无权限订阅文章：SSE 端点返回 `404`，不暴露文章是否存在。

## 测试计划

后端单元测试：

- 流式 AI 服务能累积 chunk，并在最终内容合法时返回现有 `AIAnalysisResult`。
- 非法 JSON 仍会标记分析失败。
- `pending` 文章访问 SSE 时会投递高优先级任务。
- `processing` 文章访问 SSE 时不会重复投递任务。
- `success` 文章访问 SSE 时直接返回 `done`。
- 未订阅用户无法访问 SSE。
- `/articles/{id}/reanalyze` 被移除或返回 404。

前端测试：

- 详情页 `pending/processing` 时连接 SSE。
- 收到 chunk 后展示流式文本。
- 收到 done 后刷新详情和列表。
- 切换文章时关闭旧连接。
- 移动端详情页同样显示流式文本。
- 不再出现“重新 AI 分析”入口。

集成验证：

- `make test`
- `pnpm lint`
- `pnpm build`
- 如修改 E2E 覆盖行为，运行 `pnpm test:e2e`

## 迁移与部署

不需要数据库迁移。

需要更新 Celery 配置以启用 Redis task priority。现有 worker 启动命令可以保持不变。

Redis 已是现有依赖，不新增基础设施。

## 风险

- JSON 流式中间态不可结构化展示，第一版只展示原始生成文本。
- 如果当前只有一个 Celery worker 进程，高优先级任务只会影响“下一篇”任务，不能缩短正在执行的文章分析。
- Redis Stream 丢失不会影响最终数据库结果，但会影响流式体验。
- 如果 DeepSeek 兼容接口的 streaming chunk 格式变化，需要在 AI 服务层集中适配。

## 验收标准

- 用户界面没有“重新 AI 分析”功能。
- 新文章正文抽取成功后仍会自动进入 AI 分析。
- 用户打开一篇 `pending` AI 分析文章时，该文章会以高优先级进入待分析任务。
- 用户打开一篇 `processing` AI 分析文章时，可以看到流式生成文本。
- 已经开始分析的其它文章不会被取消或抢占。
- AI 分析完成后，详情页和列表展示最终结构化摘要与推荐。
- 浏览器断开不会中断后台 AI 分析任务。
