from app.services.extraction_service import extract_markdown_from_html


def test_extract_markdown_from_html_removes_unrelated_content():
    html = """
    <html><body>
      <nav>Navigation</nav>
      <article>
        <h1>Readable Title</h1>
        <p>First paragraph.</p>
        <p>Second paragraph.</p>
      </article>
    </body></html>
    """

    markdown = extract_markdown_from_html(html, "https://example.com/post")

    assert "Readable Title" in markdown
    assert "First paragraph." in markdown
    assert "Navigation" not in markdown
