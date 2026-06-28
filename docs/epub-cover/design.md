# Design: EPUB 封面

## Summary

EPUB 摘要生成时新增封面页。封面页始终可用；当文章中存在可用封面图时，下载图片并合成为完整封面 JPEG：上方左对齐显示加粗的大号 `RSSWise` 和生成日期，下方以更大的间距放置文章封面图。

## Decisions From Requirement Discovery

- **封面图来源**：按文章顺序遍历，取第一个 `cover_image_url` 非空的文章。该字段在 RSS 抓取时从 `media:content` / `media:thumbnail` 解析得到，已存在于 `Article.cover_image_url` 列。
- **封面呈现**：始终生成一个 XHTML 封面页作为 spine 第一项。有图时 `cover.xhtml` 显示合成后的 `cover.jpeg`；无图或下载失败时显示 `RSSWise` + 日期文字 fallback。
- **封面图属性**：有封面图时，在 OPF manifest 中声明合成后的 `cover.jpeg` 为 `properties="cover-image"`，让阅读器书架封面也包含品牌、日期和文章图。
- **图片下载时机**：在 `build_digest_epub()` 中实时下载，不预缓存。
- **图片处理**：Pillow 创建 800×1200 白底画布，左对齐绘制加粗大号 `RSSWise` 和日期，标题与日期的 gap 为 32px，将文章图等比缩放后居中放在下方，图片与日期的 gap 为 96px，输出 JPEG（quality 85）。
- **下载工具**：使用生产依赖中的 `httpx`。
- **降级行为**：无论是否有封面图，封面页始终存在。无图或下载失败时，封面页仅显示 `RSSWise` + 日期，OPF manifest 不声明 `cover-image`。

## Current State

当前 EPUB 生成位于 `apps/api/app/services/epub_service.py:74`（`build_digest_epub`），纯 Python 标准库 + zipfile 构建，无外部 EPUB 库。输出 EPUB 3.0 + NCX 后备，包含 OPF / nav.xhtml / toc.ncx / 每篇文章一个章节 XHTML。

`Article.cover_image_url` 列已存在于数据库，EPUB 生成按文章顺序取第一个可用 URL 作为封面图来源。

## Implementation Notes

### 封面页布局

```
┌──────────────────────┐
│  RSSWise             │
│                      │
│  2026-06-14          │
│                      │
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
| 有 URL + 下载成功 | 合成后的 cover.jpeg | ✓（RSSWise + 日期 + 图） | ✓ |
| 有 URL + 下载失败 | RSSWise + 日期 | ✗ | ✗ |
| 所有文章无 URL | RSSWise + 日期 | ✗ | ✗ |

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
| COVER_TITLE_DATE_GAP | 32 px |
| COVER_IMAGE_GAP | 96 px |
