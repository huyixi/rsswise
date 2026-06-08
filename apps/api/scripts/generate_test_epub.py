"""Generate an EPUB digest file from real DB data for local inspection.

Usage:
    cd apps/api && uv run python scripts/generate_test_epub.py [output_path]

Output path defaults to ./rsswise-test-digest.epub
"""

import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.services.email_digest_service import list_digest_articles, now_in_digest_timezone
from app.services.email_digest_settings_service import get_or_create_email_digest_setting
from app.services.epub_service import build_digest_epub


def main(output: Path) -> None:
    with SessionLocal() as db:
        setting = get_or_create_email_digest_setting(db)
        articles = list_digest_articles(db, setting)

        if not articles:
            print("No articles found in database. Run feed refresh + extraction first.")
            sys.exit(1)

        digest_date = now_in_digest_timezone().date().isoformat()
        epub_bytes = build_digest_epub(articles, digest_date=digest_date)

        output.write_bytes(epub_bytes)
        print(f"EPUB saved: {output} ({len(articles)} articles, {len(epub_bytes)} bytes)")


if __name__ == "__main__":
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("rsswise-test-digest.epub")
    main(output_path.resolve())
