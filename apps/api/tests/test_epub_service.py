from datetime import datetime
from io import BytesIO
from uuid import uuid4
import zipfile

from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed
from app.services.epub_service import build_digest_epub


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
        one_sentence_summary="一句话摘要",
        reading_reason="值得阅读的理由",
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
    assert "一句话摘要" in chapter
    assert "值得阅读的理由" in chapter
    assert "第一段" in chapter
    assert "第二段" in chapter


def test_build_digest_epub_allows_missing_body() -> None:
    epub = build_digest_epub([make_article(content_markdown=None)], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "A useful article" in chapter
    assert "正文抽取未完成或失败" in chapter
