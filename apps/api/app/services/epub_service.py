from __future__ import annotations

from dataclasses import dataclass
from html import escape
from io import BytesIO
from textwrap import dedent
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import httpx
from markdown_it import MarkdownIt
from PIL import Image as PILImage
from PIL import ImageDraw as PILImageDraw
from PIL import ImageFont as PILImageFont

from app.models import AnalysisStatus, Article
from app.services.ai_summary_formatter import AiSummarySection, format_ai_summary

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
COVER_MAX_W = 800
COVER_MAX_H = 1000
COVER_JPEG_Q = 85
COVER_TIMEOUT = 10.0
COVER_MARGIN_X = 72
COVER_MARGIN_TOP = 88
COVER_IMAGE_BOTTOM = 72
COVER_TITLE_DATE_GAP = 32
COVER_IMAGE_GAP = 96
COVER_BRAND_FONT_SIZE = 88
COVER_BRAND_STROKE_WIDTH = 1
COVER_BRAND_LETTER_SPACING = 6
COVER_DATE_FONT_SIZE = 40
COVER_DATE_LETTER_SPACING = 3
COVER_BACKGROUND = (255, 255, 255)
COVER_TEXT = (24, 24, 24)
COVER_MUTED_TEXT = (86, 86, 86)
ARTICLE_IMAGE_TIMEOUT = 10.0
ARTICLE_IMAGE_JPEG_Q = 90


@dataclass(frozen=True)
class EpubImageAsset:
    item_id: str
    href: str
    chapter_src: str
    archive_path: str
    media_type: str
    content: bytes


def _is_epub_internal_href(href: str | None) -> bool:
    if not href:
        return False

    parsed = urlsplit(href.strip())
    return not parsed.scheme and not parsed.netloc


def _markdown_link_open(tokens, idx, options, env) -> str:
    href = tokens[idx].attrGet("href")
    is_internal = _is_epub_internal_href(href)
    env.setdefault("rsswise_link_stack", []).append(
        {
            "href": href.strip() if href else "",
            "is_internal": is_internal,
            "has_image": False,
        }
    )
    if not is_internal:
        return ""
    return MARKDOWN_RENDERER.renderer.renderToken(tokens, idx, options, env)


def _markdown_link_close(tokens, idx, options, env) -> str:
    stack = env.setdefault("rsswise_link_stack", [])
    link = stack.pop() if stack else {"href": "", "is_internal": False}
    if not link["is_internal"]:
        if link.get("has_image"):
            return ""
        href = link["href"]
        return f" ({escape(href)})" if href else ""
    return MARKDOWN_RENDERER.renderer.renderToken(tokens, idx, options, env)


def _is_remote_image_src(src: str | None) -> bool:
    if not src:
        return False

    parsed = urlsplit(src.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _download_article_image(url: str) -> bytes | None:
    try:
        response = httpx.get(url, timeout=ARTICLE_IMAGE_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return None

    try:
        with PILImage.open(BytesIO(response.content)) as img:
            rgb_image = img.convert("RGB")
            buf = BytesIO()
            rgb_image.save(buf, format="JPEG", quality=ARTICLE_IMAGE_JPEG_Q)
            return buf.getvalue()
    except Exception:
        return None


def _next_article_image_asset(src: str, env) -> EpubImageAsset | None:
    if "rsswise_article_index" not in env or "rsswise_image_assets" not in env:
        return None

    if not _is_remote_image_src(src):
        return None

    image_bytes = _download_article_image(src.strip())
    if image_bytes is None:
        return None

    article_index = int(env.get("rsswise_article_index", 0))
    image_index = int(env.get("rsswise_article_image_index", 0)) + 1
    env["rsswise_article_image_index"] = image_index

    filename = f"article-{article_index:03d}-{image_index:03d}.jpg"
    asset = EpubImageAsset(
        item_id=f"image-{article_index:03d}-{image_index:03d}",
        href=f"images/{filename}",
        chapter_src=f"../images/{filename}",
        archive_path=f"OEBPS/images/{filename}",
        media_type="image/jpeg",
        content=image_bytes,
    )
    env.setdefault("rsswise_image_assets", []).append(asset)
    return asset


def _markdown_image(tokens, idx, options, env) -> str:
    stack = env.setdefault("rsswise_link_stack", [])
    if stack:
        stack[-1]["has_image"] = True

    token = tokens[idx]
    src = token.attrGet("src") or ""
    alt = token.content
    asset = _next_article_image_asset(src, env)
    if asset is None:
        return escape(alt) if alt else ""

    return f'<img src="{escape(asset.chapter_src)}" alt="{escape(alt)}" />'


MARKDOWN_RENDERER = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "xhtmlOut": True,
    },
).enable("table")
MARKDOWN_RENDERER.renderer.rules["link_open"] = _markdown_link_open
MARKDOWN_RENDERER.renderer.rules["link_close"] = _markdown_link_close
MARKDOWN_RENDERER.renderer.rules["image"] = _markdown_image


def markdown_to_xhtml(
    markdown: str | None,
    *,
    article_index: int | None = None,
    image_assets: list[EpubImageAsset] | None = None,
) -> str:
    if not markdown or not markdown.strip():
        return "<p>正文抽取未完成或失败。</p>"

    env = {}
    if article_index is not None:
        env["rsswise_article_index"] = article_index
    if image_assets is not None:
        env["rsswise_image_assets"] = image_assets
    return MARKDOWN_RENDERER.render(markdown, env)


def _ai_section_xhtml(section: AiSummarySection, *, label: str | None = None) -> str:
    label = escape(label or section.label)
    if section.type in {"highlights", "chapters"}:
        items = "\n".join(f"<li>{escape(item)}</li>" for item in section.items)
        return f"<section><h2>{label}</h2><ul>{items}</ul></section>"

    text = escape(section.items[0]) if section.items else ""
    return f"<section><h2>{label}</h2><p>{text}</p></section>"


def _ai_sections_xhtml(
    sections: list[AiSummarySection],
    *,
    type_order: tuple[str, ...],
    labels: dict[str, str],
) -> str:
    rendered_sections = []
    for section_type in type_order:
        rendered_sections.extend(
            _ai_section_xhtml(section, label=labels[section_type])
            for section in sections
            if section.type == section_type
        )
    return "\n".join(rendered_sections)


def article_ai_xhtml(article: Article) -> tuple[str, str]:
    if (
        article.ai_analysis is not None
        and article.ai_analysis.analysis_status == AnalysisStatus.failed
    ):
        return "", ""

    summary = format_ai_summary(article.ai_analysis)
    if not summary.sections:
        return "", ""

    preface = _ai_sections_xhtml(
        summary.sections,
        type_order=("summary", "reading_question"),
        labels={
            "summary": "文章摘要",
            "reading_question": "问题导读",
        },
    )
    afterword = _ai_sections_xhtml(
        summary.sections,
        type_order=("reading_reason", "chapters", "highlights"),
        labels={
            "reading_reason": "AI 评注",
            "chapters": "章节结构",
            "highlights": "摘录",
        },
    )
    return preface, afterword


def article_chapter_xhtml(
    article: Article,
    index: int,
    *,
    image_assets: list[EpubImageAsset] | None = None,
) -> str:
    source_title = article.feed.title if article.feed else ""
    ai_preface, ai_afterword = article_ai_xhtml(article)
    preface_body_divider = "<hr />" if ai_preface else ""
    body_afterword_divider = "<hr />" if ai_afterword else ""
    article_body = markdown_to_xhtml(
        article.content.content_markdown if article.content else None,
        article_index=index,
        image_assets=image_assets,
    )

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
            {ai_preface}
            {preface_body_divider}
            {article_body}
            {body_afterword_divider}
            {ai_afterword}
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


def _digest_summary_items_xhtml(articles: list[Article]) -> str:
    if not articles:
        return "<p>本期没有文章。</p>"

    items = []
    for index, article in enumerate(articles, start=2):
        summary = _summary_fragment(_digest_article_summary(article))
        summary_html = f"<p>{escape(summary)}。</p>" if summary else ""
        items.append(
            dedent(
                f"""\
                <li>
                  <a href="article-{index:03d}.xhtml">{escape(article.title)}</a>
                  {summary_html}
                </li>
                """
            ).strip()
        )

    item_html = "\n".join(items)
    return f"<ul>\n{item_html}\n</ul>"


def digest_summary_chapter_xhtml(articles: list[Article], digest_date: str) -> str:
    summary_items = _digest_summary_items_xhtml(articles)

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
            <p>本期共 {len(articles)} 篇文章。</p>
            {summary_items}
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


def _download_cover_image(url: str) -> PILImage.Image | None:
    try:
        response = httpx.get(url, timeout=COVER_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return None

    try:
        with PILImage.open(BytesIO(response.content)) as img:
            return img.convert("RGB")
    except Exception:
        return None


def _cover_font(size: int) -> PILImageFont.ImageFont:
    return PILImageFont.load_default(size=size)


def _draw_left_text(
    draw: PILImageDraw.ImageDraw,
    text: str,
    y: int,
    *,
    font: PILImageFont.ImageFont,
    fill: tuple[int, int, int],
    stroke_width: int = 0,
    letter_spacing: int = 0,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    height = bbox[3] - bbox[1]
    x = COVER_MARGIN_X - bbox[0]

    for index, character in enumerate(text):
        character_bbox = draw.textbbox(
            (0, 0),
            character,
            font=font,
            stroke_width=stroke_width,
        )
        draw.text(
            (x - character_bbox[0], y - bbox[1]),
            character,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=fill,
        )
        x += character_bbox[2] - character_bbox[0]
        if index < len(text) - 1:
            x += letter_spacing

    return y + height


def _compose_cover_jpeg(image: PILImage.Image, digest_date: str) -> bytes:
    canvas = PILImage.new("RGB", (COVER_MAX_W, COVER_MAX_H), COVER_BACKGROUND)
    draw = PILImageDraw.Draw(canvas)

    y = COVER_MARGIN_TOP
    y = _draw_left_text(
        draw,
        "RSSWise",
        y,
        font=_cover_font(COVER_BRAND_FONT_SIZE),
        fill=COVER_TEXT,
        stroke_width=COVER_BRAND_STROKE_WIDTH,
        letter_spacing=COVER_BRAND_LETTER_SPACING,
    )
    y += COVER_TITLE_DATE_GAP
    y = _draw_left_text(
        draw,
        digest_date,
        y,
        font=_cover_font(COVER_DATE_FONT_SIZE),
        fill=COVER_MUTED_TEXT,
        letter_spacing=COVER_DATE_LETTER_SPACING,
    )
    y += COVER_IMAGE_GAP

    cover_image = image.copy()
    cover_image.thumbnail(
        (
            COVER_MAX_W - COVER_MARGIN_X * 2,
            COVER_MAX_H - y - COVER_IMAGE_BOTTOM,
        ),
        PILImage.LANCZOS,
    )
    canvas.paste(cover_image, ((COVER_MAX_W - cover_image.width) // 2, y))

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=COVER_JPEG_Q)
    return buf.getvalue()


def _cover_page_xhtml(digest_date: str, *, has_image: bool) -> str:
    body_html = (
        '<div class="cover-image"><img src="cover.jpeg" alt="封面" /></div>'
        if has_image
        else f'<div class="brand">RSSWise</div><div class="date">{digest_date}</div>'
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
              .cover-image {{ text-align: center; }}
              .cover-image img {{ max-width: 100%; max-height: 80vh; object-fit: contain; }}
            </style>
          </head>
          <body>
            {body_html}
          </body>
        </html>
        """)


def build_digest_epub(articles: list[Article], *, digest_date: str) -> bytes:
    identifier = _stable_identifier(articles, digest_date)

    cover_url = _first_cover_url(articles)
    cover_image = _download_cover_image(cover_url) if cover_url else None
    cover_bytes = _compose_cover_jpeg(cover_image, digest_date) if cover_image else None
    has_cover_image = cover_bytes is not None
    image_assets: list[EpubImageAsset] = []
    article_chapters = [
        (
            index,
            article_chapter_xhtml(article, index, image_assets=image_assets),
        )
        for index, article in enumerate(articles, start=2)
    ]

    cover_image_manifest = (
        '<item id="cover-image" href="cover.jpeg" media-type="image/jpeg" properties="cover-image" />'
        if has_cover_image
        else ""
    )
    article_image_manifest = "\n".join(
        f'<item id="{asset.item_id}" href="{asset.href}" media-type="{asset.media_type}" />'
        for asset in image_assets
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
            {article_image_manifest}
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
        for asset in image_assets:
            _write_file(
                archive,
                asset.archive_path,
                asset.content,
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
        for index, chapter_xhtml in article_chapters:
            _write_file(
                archive,
                f"OEBPS/chapters/article-{index:03d}.xhtml",
                chapter_xhtml,
                compress_type=ZIP_DEFLATED,
            )
    return output.getvalue()
