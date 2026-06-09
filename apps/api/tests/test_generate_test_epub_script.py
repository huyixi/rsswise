from pathlib import Path

from scripts import generate_test_epub


def test_default_epub_output_path_uses_digest_date() -> None:
    assert generate_test_epub.default_epub_output_path("2026-06-04") == Path(
        "RSSWise-2026-06-04.epub"
    )
