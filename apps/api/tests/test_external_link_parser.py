from app.models import ExternalLinkSourceMode
from app.services.external_link_parser import parse_external_links


def test_parse_summary_mode_strips_tracking_params_and_filters_non_article_links():
    result = parse_external_links(
        source_url="https://newsletter.example.com/issues/42?utm_source=email#top",
        summary_from_feed="""
        <p>
          <a href="/posts/a?utm_source=newsletter&id=1#comments">First</a>
          <a href="https://example.com/posts/a?id=1&utm_medium=rss">Duplicate</a>
          <a href="mailto:editor@example.com">Mail</a>
          <a href="https://example.com/image.jpg">Image</a>
        </p>
        """,
        content_markdown="[Markdown only](https://example.com/markdown)",
        mode=ExternalLinkSourceMode.summary_from_feed,
    )

    assert [(link.position, link.anchor_text, link.normalized_url) for link in result.links] == [
        (1, "First", "https://newsletter.example.com/posts/a?id=1"),
        (2, "Duplicate", "https://example.com/posts/a?id=1"),
    ]
    assert result.filtered_count == 2
    assert result.duplicate_count == 0


def test_parse_auto_combines_summary_then_markdown_and_dedupes_by_normalized_url():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed='<a href="https://target.example.com/read?utm_campaign=x">HTML Target</a>',
        content_markdown="[Markdown Target](https://target.example.com/read)",
        mode=ExternalLinkSourceMode.auto,
    )

    assert len(result.links) == 1
    assert result.links[0].anchor_text == "HTML Target"
    assert result.links[0].normalized_url == "https://target.example.com/read"
    assert result.duplicate_count == 1


def test_parse_markdown_links_keeps_source_order_and_excludes_source_url():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed=None,
        content_markdown=(
            "[Self](https://example.com/source#part)\n\n"
            "[First](https://a.example.com/post)\n\n"
            "[Second `code`](https://b.example.com/post?utm_source=rss&x=1)"
        ),
        mode=ExternalLinkSourceMode.content_markdown,
    )

    assert [(link.position, link.anchor_text, link.normalized_url) for link in result.links] == [
        (1, "First", "https://a.example.com/post"),
        (2, "Second code", "https://b.example.com/post?x=1"),
    ]
    assert result.filtered_count == 1


def test_parse_ignores_feed_and_document_urls():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed="""
        <a href="https://example.com/feed.xml">Feed</a>
        <a href="https://example.com/atom">Atom</a>
        <a href="https://example.com/report.pdf">PDF</a>
        <a href="https://example.com/readable">Readable</a>
        """,
        content_markdown=None,
        mode=ExternalLinkSourceMode.auto,
    )

    assert [link.normalized_url for link in result.links] == ["https://example.com/readable"]
    assert result.filtered_count == 3


def test_parse_ignores_nested_feed_rss_and_atom_urls():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed="""
        <a href="https://example.com/feed/posts">Nested Feed</a>
        <a href="https://example.com/rss/latest.xml">Nested RSS</a>
        <a href="https://example.com/feeds/posts/default">Blogger Feed</a>
        <a href="https://example.com/atom.xml">Atom File</a>
        <a href="https://example.com/posts/readable">Readable</a>
        """,
        content_markdown=None,
        mode=ExternalLinkSourceMode.auto,
    )

    assert [link.normalized_url for link in result.links] == [
        "https://example.com/posts/readable"
    ]
    assert result.filtered_count == 4


def test_parse_markdown_anchor_text_preserves_adjacent_inline_code_without_spaces():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed=None,
        content_markdown="[foo`bar`baz](https://example.com/post)",
        mode=ExternalLinkSourceMode.content_markdown,
    )

    assert result.links[0].anchor_text == "foobarbaz"
