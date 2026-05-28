import trafilatura
from lxml import html as lxml_html


UNRELATED_SELECTORS = ("nav", "header", "footer", "aside", "script", "style", "noscript")


def extract_markdown_from_html(html: str, url: str) -> str:
    html = remove_unrelated_nodes(html)
    markdown = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
    )
    if not markdown:
        raise ValueError("article extraction returned no markdown")
    return "\n\n".join(block.strip() for block in markdown.split("\n\n") if block.strip())


def remove_unrelated_nodes(html: str) -> str:
    document = lxml_html.fromstring(html)
    for selector in UNRELATED_SELECTORS:
        for node in document.xpath(f"//{selector}"):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    return lxml_html.tostring(document, encoding="unicode")


def fetch_and_extract_markdown(url: str) -> str:
    html = trafilatura.fetch_url(url)
    if not html:
        raise ValueError("article fetch returned no html")
    return extract_markdown_from_html(html, url)
