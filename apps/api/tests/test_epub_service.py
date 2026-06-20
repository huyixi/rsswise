from datetime import datetime
from io import BytesIO
from unittest.mock import Mock
from uuid import uuid4
import zipfile

from PIL import Image as PILImage

from app.models import AnalysisStatus, Article, ArticleAIAnalysis, ArticleContent, Feed
from app.services.epub_service import build_digest_epub


def chapter_xhtml_for(markdown: str | None) -> str:
    epub = build_digest_epub([make_article(content_markdown=markdown)], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        return archive.read("OEBPS/chapters/article-001.xhtml").decode()


def make_article(*, content_markdown: str | None) -> Article:
    feed = Feed(id=uuid4(), title="Example Feed", url="https://example.com/feed.xml")
    article = Article(
        id=uuid4(),
        feed=feed,
        title="A useful article",
        url="https://example.com/a-useful-article",
        created_at=datetime(2026, 6, 4, 1, 0, 0),
    )
    article.content = ArticleContent(content_markdown=content_markdown)
    article.ai_analysis = ArticleAIAnalysis(
        ai_blocks=[
            {
                "type": "summary",
                "title": "一句话摘要",
                "content": "来自 block 的 EPUB 摘要",
                "order": 10,
            },
            {
                "type": "reading_reason",
                "title": "阅读理由",
                "content": "来自 block 的 EPUB 理由",
                "order": 30,
            },
        ],
        one_sentence_summary="旧摘要",
        reading_reason="旧理由",
    )
    return article


def test_build_digest_epub_contains_article_metadata_and_body() -> None:
    epub = build_digest_epub(
        [make_article(content_markdown="第一段\n\n第二段")],
        digest_date="2026-06-04",
    )

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        names = set(archive.namelist())
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "mimetype" in names
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "A useful article" in chapter
    assert "Example Feed" in chapter
    assert "https://example.com/a-useful-article" in chapter
    assert "来自 block 的 EPUB 摘要" in chapter
    assert "来自 block 的 EPUB 理由" in chapter
    assert "旧摘要" not in chapter
    assert "旧理由" not in chapter
    assert "第一段" in chapter
    assert "第二段" in chapter


def test_build_digest_epub_renders_markdown_bold_text() -> None:
    chapter = chapter_xhtml_for("这是一段包含 **重点内容** 的正文。")

    assert "<strong>重点内容</strong>" in chapter
    assert "**重点内容**" not in chapter


def test_build_digest_epub_renders_markdown_heading() -> None:
    chapter = chapter_xhtml_for("# 小标题")

    assert "<h1>小标题</h1>" in chapter


def test_build_digest_epub_renders_markdown_unordered_list() -> None:
    chapter = chapter_xhtml_for("- 第一项\n- 第二项")

    assert "<ul>" in chapter
    assert "<li>第一项</li>" in chapter
    assert "<li>第二项</li>" in chapter


def test_build_digest_epub_renders_markdown_link() -> None:
    chapter = chapter_xhtml_for("[示例链接](https://example.com/docs)")

    assert '<a href="https://example.com/docs">示例链接</a>' in chapter


def test_build_digest_epub_renders_markdown_inline_and_fenced_code() -> None:
    chapter = chapter_xhtml_for("调用 `inline()`。\n\n```python\nprint('hi')\n```")

    assert "<code>inline()</code>" in chapter
    assert "<pre><code" in chapter
    assert "print('hi')" in chapter


def test_build_digest_epub_renders_markdown_blockquote() -> None:
    chapter = chapter_xhtml_for("> 引用内容")

    assert "<blockquote>" in chapter
    assert "<p>引用内容</p>" in chapter


def test_build_digest_epub_renders_markdown_table() -> None:
    chapter = chapter_xhtml_for("| 名称 | 数量 |\n| --- | ---: |\n| 苹果 | 3 |")

    assert "<table>" in chapter
    assert "<th>名称</th>" in chapter
    assert "<td>苹果</td>" in chapter


def test_build_digest_epub_escapes_raw_html() -> None:
    chapter = chapter_xhtml_for("<script>alert(1)</script>")

    assert "<script>" not in chapter
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in chapter


def test_build_digest_epub_renders_ai_blocks_like_web_summary() -> None:
    article = make_article(content_markdown="正文")
    article.ai_analysis.ai_blocks = [
        {
            "type": "reading_reason",
            "title": "阅读理由",
            "content": "因为它解释了决策背后的约束。",
            "order": 30,
        },
        {
            "type": "highlights",
            "title": "Highlights",
            "content": [
                {"text": "第一条原文摘录。", "quote_verified": False},
                {"text": "第二条原文摘录。", "quote_verified": False},
            ],
            "order": 40,
        },
        {
            "type": "chapters",
            "title": "章节",
            "content": [{"title": "背景"}, {"title": "影响"}],
            "order": 50,
        },
        {
            "type": "summary",
            "title": "一句话摘要",
            "content": "这是一句和 web 端一致的摘要。",
            "order": 20,
        },
        {
            "type": "reading_question",
            "title": "问题",
            "content": "这篇文章要回答什么？",
            "order": 10,
        },
        {
            "type": "chapters",
            "title": "章节",
            "content": [],
            "order": 60,
        },
    ]

    epub = build_digest_epub([article], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "这篇文章要回答什么？" in chapter
    assert "这是一句和 web 端一致的摘要。" in chapter
    assert "因为它解释了决策背后的约束。" in chapter
    assert "第一条原文摘录。" in chapter
    assert "第二条原文摘录。" in chapter
    assert "背景" in chapter
    assert "影响" in chapter
    assert "旧摘要" not in chapter
    assert "旧理由" not in chapter

    positions = [
        chapter.index("这篇文章要回答什么？"),
        chapter.index("这是一句和 web 端一致的摘要。"),
        chapter.index("因为它解释了决策背后的约束。"),
        chapter.index("第一条原文摘录。"),
        chapter.index("背景"),
    ]
    assert positions == sorted(positions)


def test_build_digest_epub_allows_missing_body() -> None:
    epub = build_digest_epub([make_article(content_markdown=None)], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "A useful article" in chapter
    assert "正文抽取未完成或失败" in chapter


def test_build_digest_epub_omits_ai_summary_when_analysis_failed() -> None:
    article = make_article(content_markdown="正文")
    article.ai_analysis.ai_blocks = None
    article.ai_analysis.one_sentence_summary = None
    article.ai_analysis.reading_reason = None
    article.ai_analysis.analysis_status = AnalysisStatus.failed

    epub = build_digest_epub([article], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "AI 总结" not in chapter
    assert "暂无 AI 总结" not in chapter
    assert "正文" in chapter


def _tiny_jpeg(width: int = 100, height: int = 150) -> bytes:
    img = PILImage.new("RGB", (width, height), color=(70, 130, 180))
    buf = BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _mock_httpx_get(mocker, jpeg_bytes: bytes) -> None:
    mock_response = Mock()
    mock_response.content = jpeg_bytes
    mock_response.raise_for_status = Mock()
    mocker.patch("app.services.epub_service.httpx.get", return_value=mock_response)


def test_cover_page_always_present() -> None:
    """无封面图时：封面页仍然存在，只含 RSSWISE 品牌和日期."""
    epub = build_digest_epub([make_article(content_markdown="正文")], digest_date="2026-06-14")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        names = set(archive.namelist())
        cover_xhtml = archive.read("OEBPS/cover.xhtml").decode()
        opf = archive.read("OEBPS/content.opf").decode()

    assert "OEBPS/cover.xhtml" in names
    assert "OEBPS/cover.jpeg" not in names
    assert "RSSWISE" in cover_xhtml
    assert "2026-06-14" in cover_xhtml
    assert 'properties="cover-image"' not in opf
    assert '<itemref idref="cover-page" />' in opf
    assert opf.index("cover-page") < opf.index("article-001")


def test_cover_page_with_image(mocker) -> None:
    """有封面图时：下载成功则嵌入 cover.jpeg 并声明 cover-image."""
    article = make_article(content_markdown="正文")
    article.cover_image_url = "https://example.com/cover.jpg"

    _mock_httpx_get(mocker, _tiny_jpeg(400, 600))

    epub = build_digest_epub([article], digest_date="2026-06-14")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        names = set(archive.namelist())
        cover_xhtml = archive.read("OEBPS/cover.xhtml").decode()
        cover_jpeg = archive.read("OEBPS/cover.jpeg")
        opf = archive.read("OEBPS/content.opf").decode()

    assert "OEBPS/cover.xhtml" in names
    assert "OEBPS/cover.jpeg" in names
    assert 'src="cover.jpeg"' in cover_xhtml
    assert 'id="cover-image"' in opf
    assert 'properties="cover-image"' in opf

    cover_img = PILImage.open(BytesIO(cover_jpeg))
    assert cover_img.format == "JPEG"
    assert cover_img.size[0] <= 800
    assert cover_img.size[1] <= 1200


def test_cover_takes_first_available_cover_url(mocker) -> None:
    """多篇文章：取第一个有 cover_image_url 的文章封面."""
    article1 = make_article(content_markdown="A")
    article2 = make_article(content_markdown="B")
    article2.cover_image_url = "https://example.com/second-cover.jpg"

    _mock_httpx_get(mocker, _tiny_jpeg(200, 300))

    epub = build_digest_epub([article1, article2], digest_date="2026-06-14")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        assert "OEBPS/cover.jpeg" in set(archive.namelist())


def test_cover_download_failure_graceful(mocker) -> None:
    """下载失败时降级：封面页仅含品牌文字，无 cover-image."""
    article = make_article(content_markdown="正文")
    article.cover_image_url = "https://example.com/broken.jpg"

    mocker.patch(
        "app.services.epub_service.httpx.get",
        side_effect=Exception("Network error"),
    )

    epub = build_digest_epub([article], digest_date="2026-06-14")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        names = set(archive.namelist())
        cover_xhtml = archive.read("OEBPS/cover.xhtml").decode()
        opf = archive.read("OEBPS/content.opf").decode()

    assert "OEBPS/cover.xhtml" in names
    assert "OEBPS/cover.jpeg" not in names
    assert "RSSWISE" in cover_xhtml
    assert "2026-06-14" in cover_xhtml
    assert 'src="cover.jpeg"' not in cover_xhtml
    assert 'properties="cover-image"' not in opf
