from __future__ import annotations

from html import escape
from io import BytesIO
from textwrap import dedent
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import httpx
from markdown_it import MarkdownIt
from PIL import Image as PILImage

from app.models import AnalysisStatus, Article
from app.services.ai_summary_formatter import AiSummarySection, format_ai_summary

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
COVER_MAX_W = 800
COVER_MAX_H = 1200
COVER_JPEG_Q = 85
COVER_TIMEOUT = 10.0


def _is_epub_internal_href(href: str | None) -> bool:
    if not href:
        return False

    parsed = urlsplit(href.strip())
    return not parsed.scheme and not parsed.netloc


def _markdown_link_open(tokens, idx, options, env) -> str:
    href = tokens[idx].attrGet("href")
    is_internal = _is_epub_internal_href(href)
    env.setdefault("rsswise_internal_link_stack", []).append(is_internal)
    if not is_internal:
        return ""
    return MARKDOWN_RENDERER.renderer.renderToken(tokens, idx, options, env)


def _markdown_link_close(tokens, idx, options, env) -> str:
    stack = env.setdefault("rsswise_internal_link_stack", [])
    is_internal = stack.pop() if stack else False
    if not is_internal:
        return ""
    return MARKDOWN_RENDERER.renderer.renderToken(tokens, idx, options, env)


MARKDOWN_RENDERER = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "xhtmlOut": True,
    },
).enable("table")
MARKDOWN_RENDERER.renderer.rules["link_open"] = _markdown_link_open
MARKDOWN_RENDERER.renderer.rules["link_close"] = _markdown_link_close


def markdown_to_xhtml(markdown: str | None) -> str:
    if not markdown or not markdown.strip():
        return "<p>正文抽取未完成或失败。</p>"

    return MARKDOWN_RENDERER.render(markdown)


def _ai_section_xhtml(section: AiSummarySection) -> str:
    label = escape(section.label)
    if section.type in {"highlights", "chapters"}:
        items = "\n".join(f"<li>{escape(item)}</li>" for item in section.items)
        return f"<section><h3>{label}</h3><ul>{items}</ul></section>"

    text = escape(section.items[0]) if section.items else ""
    return f"<section><h3>{label}</h3><p>{text}</p></section>"


def ai_summary_xhtml(article: Article) -> str:
    if (
        article.ai_analysis is not None
        and article.ai_analysis.analysis_status == AnalysisStatus.failed
    ):
        return ""

    summary = format_ai_summary(article.ai_analysis)
    if not summary.sections:
        return "<section><h2>AI 总结</h2><p>暂无 AI 总结</p></section>"

    sections = "\n".join(_ai_section_xhtml(section) for section in summary.sections)
    return f"<section><h2>AI 总结</h2>{sections}</section>"


def article_chapter_xhtml(article: Article, index: int) -> str:
    source_title = article.feed.title if article.feed else ""
    ai_summary = ai_summary_xhtml(article)
    article_body = markdown_to_xhtml(article.content.content_markdown if article.content else None)

    return dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head>
            <title>{escape(article.title)}</title>
            <meta charset="utf-8" />
          </head>
          <body>
            <h1>{escape(article.title)}</h1>
            <p><strong>来源：</strong>{escape(source_title)}</p>
            <p><strong>链接：</strong>{escape(article.url)}</p>
            {ai_summary}
            {article_body}
          </body>
        </html>
        """
    )


def _digest_article_summary(article: Article) -> str:
    if (
        article.ai_analysis is not None
        and article.ai_analysis.analysis_status == AnalysisStatus.failed
    ):
        return article.title

    summary = format_ai_summary(article.ai_analysis).one_sentence_summary
    return summary or article.title


def _summary_fragment(value: str) -> str:
    return " ".join(value.split()).strip().rstrip("。！？.!?")


def _digest_summary_sentence(articles: list[Article]) -> str:
    if not articles:
        return "本期没有文章。"

    fragments = [
        fragment
        for article in articles
        if (fragment := _summary_fragment(_digest_article_summary(article)))
    ]
    if not fragments:
        return f"本期共 {len(articles)} 篇文章。"

    return f"本期共 {len(articles)} 篇文章，涵盖：{'；'.join(fragments)}。"


def digest_summary_chapter_xhtml(articles: list[Article], digest_date: str) -> str:
    summary = _digest_summary_sentence(articles)

    return dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head>
            <title>本期摘要</title>
            <meta charset="utf-8" />
          </head>
          <body>
            <h1>本期摘要</h1>
            <p><strong>日期：</strong>{escape(digest_date)}</p>
            <p>{escape(summary)}</p>
          </body>
        </html>
        """
    )


def _stable_identifier(articles: list[Article], digest_date: str) -> str:
    article_keys = "|".join(article.url for article in articles)
    return f"urn:uuid:{uuid5(NAMESPACE_URL, f'rsswise:{digest_date}:{article_keys}')}"


def _write_file(
    archive: ZipFile,
    path: str,
    content: str | bytes,
    *,
    compress_type: int,
) -> None:
    info = ZipInfo(path, date_time=ZIP_TIMESTAMP)
    info.compress_type = compress_type
    archive.writestr(info, content)


def _first_cover_url(articles: list[Article]) -> str | None:
    for article in articles:
        if article.cover_image_url:
            return article.cover_image_url
    return None


def _download_cover(url: str) -> bytes | None:
    try:
        response = httpx.get(url, timeout=COVER_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return None

    try:
        img = PILImage.open(BytesIO(response.content))
        img = img.convert("RGB")
        img.thumbnail((COVER_MAX_W, COVER_MAX_H), PILImage.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=COVER_JPEG_Q)
        return buf.getvalue()
    except Exception:
        return None


def _cover_page_xhtml(digest_date: str, *, has_image: bool) -> str:
    image_html = (
        '<div class="cover-image"><img src="cover.jpeg" alt="封面" /></div>'
        if has_image
        else ""
    )
    return dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head>
            <title>RSSWise Digest - {digest_date}</title>
            <meta charset="utf-8" />
            <style>
              body {{ margin: 2em; font-family: serif; }}
              .brand {{ font-size: 1.5em; font-weight: bold; }}
              .date {{ font-size: 0.9em; color: #555; margin-top: 0.5em; }}
              .cover-image {{ text-align: center; margin-top: 2em; }}
              .cover-image img {{ max-width: 100%; max-height: 80vh; object-fit: contain; }}
            </style>
          </head>
          <body>
            <div class="brand">RSSWISE</div>
            <div class="date">{digest_date}</div>
            {image_html}
          </body>
        </html>
        """)


def build_digest_epub(articles: list[Article], *, digest_date: str) -> bytes:
    identifier = _stable_identifier(articles, digest_date)

    cover_url = _first_cover_url(articles)
    cover_bytes = _download_cover(cover_url) if cover_url else None
    has_cover_image = cover_bytes is not None

    cover_image_manifest = (
        '<item id="cover-image" href="cover.jpeg" media-type="image/jpeg" properties="cover-image" />'
        if has_cover_image
        else ""
    )
    chapter_items = "\n".join(
        (
            f'<item id="article-{index:03d}" '
            f'href="chapters/article-{index:03d}.xhtml" '
            'media-type="application/xhtml+xml" />'
        )
        for index in range(1, len(articles) + 2)
    )
    spine_items = "\n".join(
        f'<itemref idref="article-{index:03d}" />'
        for index in range(1, len(articles) + 2)
    )
    nav_items = "\n".join(
        [
            '<li><a href="chapters/article-001.xhtml">本期摘要</a></li>',
            *(
                f'<li><a href="chapters/article-{index:03d}.xhtml">{escape(article.title)}</a></li>'
                for index, article in enumerate(articles, start=2)
            ),
        ]
    )

    content_opf = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:identifier id="book-id">{identifier}</dc:identifier>
            <dc:title>RSSWise Digest - {digest_date}</dc:title>
            <dc:language>zh-CN</dc:language>
            <dc:creator>RSSWise</dc:creator>
          </metadata>
          <manifest>
            <item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml" />
            {cover_image_manifest}
            <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
            {chapter_items}
          </manifest>
          <spine>
            <itemref idref="cover-page" />
            {spine_items}
          </spine>
        </package>
        """
    )

    nav_xhtml = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head><title>RSSWise Digest - {digest_date}</title></head>
          <body>
            <nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">
              <h1>RSSWise Digest - {digest_date}</h1>
              <ol>{nav_items}</ol>
            </nav>
          </body>
        </html>
        """
    )

    toc_ncx = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
          <head><meta name="dtb:uid" content="{identifier}" /></head>
          <docTitle><text>RSSWise Digest - {digest_date}</text></docTitle>
          <navMap></navMap>
        </ncx>
        """
    )

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        _write_file(archive, "mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        _write_file(
            archive,
            "META-INF/container.xml",
            dedent(
                """\
                <?xml version="1.0" encoding="utf-8"?>
                <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" />
                  </rootfiles>
                </container>
                """
            ),
            compress_type=ZIP_DEFLATED,
        )
        _write_file(archive, "OEBPS/content.opf", content_opf, compress_type=ZIP_DEFLATED)
        _write_file(
            archive,
            "OEBPS/cover.xhtml",
            _cover_page_xhtml(digest_date, has_image=has_cover_image),
            compress_type=ZIP_DEFLATED,
        )
        if has_cover_image:
            _write_file(
                archive,
                "OEBPS/cover.jpeg",
                cover_bytes,
                compress_type=ZIP_DEFLATED,
            )
        _write_file(archive, "OEBPS/nav.xhtml", nav_xhtml, compress_type=ZIP_DEFLATED)
        _write_file(archive, "OEBPS/toc.ncx", toc_ncx, compress_type=ZIP_DEFLATED)
        _write_file(
            archive,
            "OEBPS/chapters/article-001.xhtml",
            digest_summary_chapter_xhtml(articles, digest_date),
            compress_type=ZIP_DEFLATED,
        )
        for index, article in enumerate(articles, start=2):
            _write_file(
                archive,
                f"OEBPS/chapters/article-{index:03d}.xhtml",
                article_chapter_xhtml(article, index),
                compress_type=ZIP_DEFLATED,
            )
    return output.getvalue()
