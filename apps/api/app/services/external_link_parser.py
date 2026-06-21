from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from lxml import html as lxml_html
from lxml.etree import ParserError
from markdown_it import MarkdownIt
from markdown_it.token import Token

from app.models import ExternalLinkSourceMode

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
FILTERED_EXTENSIONS = {
    ".7z",
    ".atom",
    ".avi",
    ".doc",
    ".docx",
    ".epub",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".odp",
    ".ods",
    ".odt",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".rss",
    ".tar",
    ".tgz",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
FEED_PATH_SEGMENTS = {"atom", "feed", "feeds", "rss"}
FEED_PATH_FILENAMES = {"atom.xml", "feed.xml", "rss.xml"}

MARKDOWN_PARSER = MarkdownIt("commonmark", {"html": False})


@dataclass(frozen=True)
class ParsedExternalLink:
    position: int
    anchor_text: str
    original_url: str
    normalized_url: str


@dataclass(frozen=True)
class ExternalLinkParseResult:
    links: list[ParsedExternalLink]
    filtered_count: int
    duplicate_count: int


@dataclass(frozen=True)
class CandidateLink:
    url: str
    anchor_text: str


def normalize_external_url(url: str, *, base_url: str) -> str | None:
    url = url.strip()
    if not url:
        return None

    resolved_url = urljoin(base_url, url)
    parsed = urlsplit(resolved_url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.netloc:
        return None

    path = parsed.path or "/"
    if _is_filtered_path(path):
        return None

    query_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_query_key(key)
    ]
    query = urlencode(query_params, doseq=True)

    return urlunsplit((scheme, parsed.netloc.lower(), path, query, ""))


def extract_html_links(html: str | None) -> list[CandidateLink]:
    if not html or not html.strip():
        return []

    try:
        document = lxml_html.fragment_fromstring(html, create_parent="div")
    except (ParserError, ValueError):
        return []

    links: list[CandidateLink] = []
    for anchor in document.xpath(".//a[@href]"):
        href = anchor.get("href")
        if not href:
            continue
        links.append(
            CandidateLink(
                url=href,
                anchor_text=_normalize_anchor_text(anchor.text_content()),
            )
        )
    return links


def extract_markdown_links(markdown: str | None) -> list[CandidateLink]:
    if not markdown or not markdown.strip():
        return []

    links: list[CandidateLink] = []
    for block_token in MARKDOWN_PARSER.parse(markdown):
        if block_token.type != "inline" or not block_token.children:
            continue
        links.extend(_extract_inline_markdown_links(block_token.children))
    return links


def parse_external_links(
    *,
    source_url: str,
    summary_from_feed: str | None,
    content_markdown: str | None,
    mode: ExternalLinkSourceMode,
) -> ExternalLinkParseResult:
    candidates = _candidate_links_for_mode(
        summary_from_feed=summary_from_feed,
        content_markdown=content_markdown,
        mode=mode,
    )
    normalized_source_url = normalize_external_url(source_url, base_url=source_url)

    links: list[ParsedExternalLink] = []
    seen_urls: set[str] = set()
    filtered_count = 0
    duplicate_count = 0

    for candidate in candidates:
        normalized_url = normalize_external_url(candidate.url, base_url=source_url)
        if normalized_url is None or normalized_url == normalized_source_url:
            filtered_count += 1
            continue

        if normalized_url in seen_urls:
            duplicate_count += 1
            continue

        seen_urls.add(normalized_url)
        links.append(
            ParsedExternalLink(
                position=len(links) + 1,
                anchor_text=candidate.anchor_text,
                original_url=candidate.url,
                normalized_url=normalized_url,
            )
        )

    return ExternalLinkParseResult(
        links=links,
        filtered_count=filtered_count,
        duplicate_count=duplicate_count,
    )


def _candidate_links_for_mode(
    *,
    summary_from_feed: str | None,
    content_markdown: str | None,
    mode: ExternalLinkSourceMode,
) -> list[CandidateLink]:
    if mode == ExternalLinkSourceMode.summary_from_feed:
        return extract_html_links(summary_from_feed)
    if mode == ExternalLinkSourceMode.content_markdown:
        return extract_markdown_links(content_markdown)
    return extract_html_links(summary_from_feed) + extract_markdown_links(content_markdown)


def _extract_inline_markdown_links(children: list[Token]) -> list[CandidateLink]:
    links: list[CandidateLink] = []
    active_href: str | None = None
    anchor_parts: list[str] = []

    for token in children:
        if token.type == "link_open":
            active_href = token.attrGet("href")
            anchor_parts = []
            continue

        if token.type == "link_close":
            if active_href:
                links.append(
                    CandidateLink(
                        url=active_href,
                        anchor_text=_normalize_anchor_text("".join(anchor_parts)),
                    )
                )
            active_href = None
            anchor_parts = []
            continue

        if active_href and token.type in {"text", "code_inline"}:
            anchor_parts.append(token.content)
        elif active_href and token.type in {"softbreak", "hardbreak"}:
            anchor_parts.append(" ")

    return links


def _normalize_anchor_text(text: str) -> str:
    return " ".join(text.split())


def _is_tracking_query_key(key: str) -> bool:
    normalized_key = key.lower()
    return normalized_key.startswith("utm_") or normalized_key in TRACKING_QUERY_KEYS


def _is_filtered_path(path: str) -> bool:
    lower_path = path.lower().rstrip("/")
    path_segments = [segment for segment in lower_path.split("/") if segment]
    path_name = path_segments[-1] if path_segments else ""
    if any(segment in FEED_PATH_SEGMENTS for segment in path_segments):
        return True
    if path_name in FEED_PATH_FILENAMES:
        return True
    return any(path_name.endswith(extension) for extension in FILTERED_EXTENSIONS)
