# AI RSS Reader — MVP Design

## 1. 产品定位

一个基于 RSS 的 AI 辅助阅读系统。

系统自动抓取 RSS 文章，抽取正文，并生成 AI 阅读建议，帮助用户快速判断：

* 是否值得阅读
* 应该如何阅读

产品本质仍然是 RSS 阅读器。AI 仅作为“阅读前辅助层”。

---

## 2. 核心流程

```text
添加 RSS
→ 自动抓取文章
→ 抽取正文
→ 保存 markdown 正文
→ AI 分析
→ 用户浏览文章列表
→ 进入详情阅读正文
```

---

## 3. 功能范围

### 3.1 RSS 源管理

支持：

* 添加 RSS 源
* 删除 RSS 源
* 查看 RSS 源列表
* 手动刷新 RSS 源

系统行为：

* 添加 RSS 后立即抓取一次
* 每 1 小时自动抓取所有 Feed

不支持：

* 启用 / 禁用 RSS 源
* 自定义抓取频率
* 面向用户展示抓取失败原因

---

### 3.2 文章聚合

系统从 RSS 中保存：

* 标题
* 链接
* 作者
* 发布时间
* RSS 摘要
* 封面图，如果存在

系统需要：

* 文章去重
* 永久保存文章

---

### 3.3 正文抽取

系统自动：

* 抓取文章网页
* 抽取正文
* 转换为 markdown
* 清洗无关内容

说明：

* 不保存 raw html
* markdown 是系统内部正文标准格式
* 正文 markdown 在详情页完整展示

---

### 3.4 AI 分析

系统对正文 markdown 执行 AI 分析。

AI 输出：

* 一句话摘要
* 阅读建议
* 阅读理由

阅读建议枚举：

```text
deep_read
skim
skip
```

前端映射：

```text
值得精读
适合略读
可以跳过
```

说明：

* 一个文章只保留一份 AI 分析结果
* 支持“重新 AI 分析”
* 重新分析会覆盖旧结果
* 不做 AI 长摘要
* 不做 AI 打分
* 不做 target readers
* 不做 keyword filtering

---

### 3.5 阅读状态

支持：

* 已读
* 未读

系统行为：

* 进入详情页自动标记已读
* 支持手动标记未读

不支持：

* 收藏
* 稍后读
* 阅读进度
* 最后阅读时间

---

## 4. 页面设计

### 4.1 文章列表页

展示：

* 标题
* 来源
* 发布时间
* 一句话摘要
* 阅读建议
* 已读状态

排序：

* 按发布时间倒序

筛选：

* 全部
* 已读
* 未读

不支持：

* 搜索
* AI 分数排序
* feed filter
* recommendation filter

---

### 4.2 文章详情页

展示：

* 标题
* 来源
* 发布时间
* 原文链接
* 一句话摘要
* 阅读建议
* 阅读理由
* markdown 完整正文

展示顺序：

```text
AI 信息
→ 正文
```

---

### 4.3 Feed 管理页

展示：

* Feed 标题
* Feed URL
* 站点链接
* Favicon
* 最后抓取时间

操作：

* 添加 Feed
* 删除 Feed
* 手动刷新 Feed

---

## 5. 系统处理流程

### 5.1 Feed 抓取流程

```text
用户添加 Feed
→ 保存 Feed
→ 立即抓取 Feed
→ 创建文章
→ 新文章进入正文抽取流程
```

定时任务：

```text
每 1 小时抓取所有 Feed
```

---

### 5.2 文章处理流程

```text
文章创建
→ 正文抽取
→ markdown 保存
→ AI 分析
→ 可阅读
```

---

### 5.3 重新 AI 分析流程

```text
用户点击“重新 AI 分析”
→ 创建 AI 分析任务
→ 使用当前 markdown 正文重新分析
→ 覆盖旧 AI 结果
```

说明：

* 不重新抓 RSS
* 不重新抽取正文
* 只重新执行 AI Analysis

---

## 6. 数据模型

### 6.1 Feed

```text
Feed
- id
- title
- url
- site_url
- favicon_url
- last_fetched_at
- created_at
```

---

### 6.2 Article

```text
Article
- id
- feed_id
- title
- url
- author
- published_at
- summary_from_feed
- cover_image_url
- guid
- is_read
- created_at
```

---

### 6.3 ArticleContent

```text
ArticleContent
- article_id
- content_markdown
- extraction_status
- extracted_at
```

---

### 6.4 ArticleAIAnalysis

```text
ArticleAIAnalysis
- article_id
- one_sentence_summary
- reading_recommendation
- reading_reason
- analysis_status
- created_at
- updated_at
```

---

## 7. 状态定义

### 7.1 正文抽取状态

```text
pending
processing
success
failed
```

---

### 7.2 AI 分析状态

```text
pending
processing
success
failed
```

---

## 8. 技术栈

### 8.1 Frontend

* Next.js
* TypeScript
* Tailwind CSS
* cossui
* react-markdown
* remark-gfm
* rehype-sanitize

### 8.2 Backend

* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* structlog

### 8.3 Database

* PostgreSQL

### 8.4 Worker

* Celery
* Celery Beat
* Redis

### 8.5 RSS / Extraction

* feedparser
* trafilatura

### 8.6 AI

* DeepSeek API

### 8.7 Deploy

* Docker
* Docker Compose

