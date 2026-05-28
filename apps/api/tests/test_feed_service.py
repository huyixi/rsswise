from app.services.feed_service import parse_feed_items


def test_parse_feed_items_keeps_design_fields():
    parsed = parse_feed_items(
        """
        <rss version="2.0"><channel>
          <title>Example Feed</title>
          <link>https://example.com</link>
          <item>
            <guid>post-1</guid>
            <title>First Post</title>
            <link>https://example.com/post-1</link>
            <author>Ada</author>
            <pubDate>Wed, 01 Jan 2026 00:00:00 GMT</pubDate>
            <description>Summary</description>
          </item>
        </channel></rss>
        """
    )

    assert parsed.feed_title == "Example Feed"
    assert parsed.site_url == "https://example.com"
    assert parsed.items[0].title == "First Post"
    assert parsed.items[0].guid == "post-1"
    assert parsed.items[0].summary_from_feed == "Summary"
