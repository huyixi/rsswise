import pytest

from app.services.feed_import_service import (
    MAX_FEED_IMPORT_URLS,
    FeedImportCandidate,
    normalize_feed_url,
    parse_opml_feeds,
    parse_urls_text,
    prepare_import_candidates,
)


def test_parse_urls_text_trims_blank_lines_and_keeps_titles_empty():
    candidates = parse_urls_text(
        """
        https://example.com/feed.xml

        https://example.org/rss
        """
    )

    assert candidates == [
        FeedImportCandidate(source_title=None, raw_url="https://example.com/feed.xml"),
        FeedImportCandidate(source_title=None, raw_url="https://example.org/rss"),
    ]


def test_parse_opml_feeds_reads_nested_outlines():
    candidates = parse_opml_feeds(
        """
        <opml version="2.0">
          <body>
            <outline text="Folder">
              <outline text="Example" title="Example Title" xmlUrl="https://example.com/feed.xml" />
              <outline text="Second" xmlUrl="https://example.org/rss" />
            </outline>
          </body>
        </opml>
        """
    )

    assert candidates == [
        FeedImportCandidate(source_title="Example Title", raw_url="https://example.com/feed.xml"),
        FeedImportCandidate(source_title="Second", raw_url="https://example.org/rss"),
    ]


def test_parse_opml_rejects_invalid_xml():
    with pytest.raises(ValueError, match="OPML 解析失败"):
        parse_opml_feeds("<opml><body>")


def test_prepare_import_candidates_preserves_duplicates_as_items():
    prepared = prepare_import_candidates(
        [
            FeedImportCandidate(source_title="A", raw_url=" https://example.com/feed.xml "),
            FeedImportCandidate(source_title="A duplicate", raw_url="https://example.com/feed.xml"),
        ]
    )

    assert prepared.unique_count == 1
    assert [item.dedupe_key for item in prepared.items] == [
        "https://example.com/feed.xml",
        "https://example.com/feed.xml",
    ]


def test_prepare_import_candidates_enforces_unique_limit():
    candidates = [
        FeedImportCandidate(source_title=None, raw_url=f"https://example.com/{index}.xml")
        for index in range(MAX_FEED_IMPORT_URLS + 1)
    ]

    with pytest.raises(ValueError, match="最多导入 200 个 Feed"):
        prepare_import_candidates(candidates)


def test_normalize_feed_url_is_conservative():
    assert normalize_feed_url(" https://example.com/feed/?a=1 ") == "https://example.com/feed/?a=1"
