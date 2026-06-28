# Plan: EPUB 封面

## Files Changed

### `apps/api/pyproject.toml`
- `httpx` 从 dev 依赖移入 core `dependencies`
- 新增 `Pillow>=11.0` 到 `dependencies`

### `apps/api/app/services/epub_service.py`
- 新增 `import httpx`
- 新增 `from PIL import Image, ImageDraw, ImageFont`
- 新增常量 `COVER_MAX_W`, `COVER_MAX_H`, `COVER_JPEG_Q`, `COVER_TIMEOUT`, `COVER_TITLE_DATE_GAP`, `COVER_IMAGE_GAP`
- 新增 `_first_cover_url(articles) -> str | None`
- 新增 `_download_cover_image(url) -> Image | None`
- 新增 `_compose_cover_jpeg(image, digest_date) -> bytes`
- 新增 `_cover_page_xhtml(digest_date, has_image) -> str`
- 修改 `build_digest_epub()`：织入封面下载、合成封面图和封面页生成，更新 OPF manifest/spine，添加 ZIP 条目

### `apps/api/tests/test_epub_service.py`
- 新增 `test_cover_page_always_present` — 无封面图时封面页仍存在，含 RSSWise + 日期
- 新增 `test_cover_page_with_image` — mock 下载成功，验证左对齐合成后的 cover.jpeg + OPF cover-image
- 新增 `test_cover_takes_first_available_cover_url` — 多文章中取第一个有封面 URL
- 新增 `test_cover_download_failure_graceful` — 下载失败时降级为无图封面
- 引入 `from PIL import Image` 辅助生成 mock JPEG

### 不涉及的文件
- 数据库模型 (`models.py`) — `cover_image_url` 列已存在
- 邮件摘要服务 (`email_digest_service.py`) — `build_digest_epub` 接口不变
- 前端 — 无 UI 变更

## Steps

1. 在 `epub_service.py` 顶部新增 `httpx`、`PIL.Image`、`PIL.ImageDraw`、`PIL.ImageFont` 导入及常量
2. 实现 `_first_cover_url(articles)` — 遍历返回第一个非空 `cover_image_url`
3. 实现 `_download_cover_image(url)` — httpx GET 下载 → Pillow 打开 → `convert("RGB")`
4. 实现 `_compose_cover_jpeg(image, digest_date)` — 800×1200 白底画布 → 顶部左对齐绘制大号 RSSWise + 日期 → 使用较小标题日期 gap 和更大图片 gap → 下方居中放文章图 → JPEG 编码输出 `bytes`
5. 实现 `_cover_page_xhtml(digest_date, has_image)` — 生成 cover.xhtml 内容
6. 修改 `build_digest_epub`：
   - 开头调用 `_first_cover_url` + `_download_cover_image`
   - 下载成功后调用 `_compose_cover_jpeg`
   - 在 `content_opf` manifest 中插入 cover-page（始终）和 cover-image（有图时）
   - 在 spine 开头插入 cover-page `<itemref>`
   - 在 ZIP 中写入 `OEBPS/cover.xhtml`（始终）和 `OEBPS/cover.jpeg`（有图时）
7. 更新 `pyproject.toml` 依赖
8. 运行 `ruff check` + `pytest tests/test_epub_service.py` 验证
