# Design: EPUB 封面

## Summary

EPUB 摘要生成时新增封面页。封面页始终包含 RSSWISE 品牌标识和生成日期；当文章中存在可用的封面图时，下载、缩放到合适尺寸并嵌入封面页。

## Decisions From Requirement Discovery

- **封面图来源**：按文章顺序遍历，取第一个 `cover_image_url` 非空的文章。该字段在 RSS 抓取时从 `media:content` / `media:thumbnail` 解析得到，已存在于 `Article.cover_image_url` 列。
- **封面呈现**：始终生成一个 XHTML 封面页作为 spine 第一项。页面布局：左上角 `RSSWISE` → 下方日期（小字）→ 下方封面图居中显示。
- **封面图属性**：有封面图时，在 OPF manifest 中声明 `properties="cover-image"`，让阅读器识别为书架封面。
- **图片下载时机**：在 `build_digest_epub()` 中实时下载，不预缓存。
- **图片处理**：Pillow 等比缩放至 ≤800×1200px，转为 JPEG（quality 85）。
- **下载工具**：使用 `httpx`（已存在于 dev 依赖，需迁至生产依赖）。
- **降级行为**：无论是否有封面图，封面页始终存在。无图或下载失败时，封面页仅显示 RSSWISE + 日期，OPF manifest 不声明 `cover-image`。

## Current State

当前 EPUB 生成位于 `apps/api/app/services/epub_service.py:74`（`build_digest_epub`），纯 Python 标准库 + zipfile 构建，无外部 EPUB 库。输出 EPUB 3.0 + NCX 后备，包含 OPF / nav.xhtml / toc.ncx / 每篇文章一个章节 XHTML。

`Article.cover_image_url` 列已存在于数据库，但 EPUB 生成流程完全未使用。

## Implementation Notes

### 封面页布局

```
┌──────────────────────┐
│ RSSWISE              │  ← font-size: 1.5em, font-weight: bold
│ 2026-06-14           │  ← font-size: 0.9em, color: #555
│                      │
│    ┌──────────┐      │
│    │          │      │  ← max-width: 100%, max-height: 80vh
│    │  封面图   │      │     object-fit: contain
│    └──────────┘      │
└──────────────────────┘
```

### EPUB 结构变更

```
mimetype
META-INF/container.xml
OEBPS/content.opf          ← manifest/spine 新增 cover-page + cover-image
OEBPS/cover.xhtml           ← 新增：封面页
OEBPS/cover.jpeg            ← 新增：封面图（有图时）
OEBPS/nav.xhtml
OEBPS/toc.ncx
OEBPS/chapters/article-001.xhtml
...
```

### 降级矩阵

| 条件 | cover.xhtml 内容 | cover.jpeg | OPF cover-image |
|---|---|---|---|
| 有 URL + 下载成功 | RSSWISE + 日期 + 图 | ✓ | ✓ |
| 有 URL + 下载失败 | RSSWISE + 日期 | ✗ | ✗ |
| 所有文章无 URL | RSSWISE + 日期 | ✗ | ✗ |

### 依赖变更

- `httpx` 从 `optional-dependencies.dev` 移至 `dependencies`（生产依赖）
- 新增 `Pillow>=11.0` 到 `dependencies`

### 关键常量

| 常量 | 值 |
|---|---|
| COVER_MAX_WIDTH | 800 px |
| COVER_MAX_HEIGHT | 1200 px |
| COVER_JPEG_QUALITY | 85 |
| COVER_DOWNLOAD_TIMEOUT | 10 s |
