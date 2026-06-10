import pytest
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    FeedImportItem,
    FeedImportItemStatus,
    FeedImportJob,
    FeedImportJobStatus,
    FeedImportSourceType,
    User,
)
from app.services.feed_import_service import (
    MAX_FEED_IMPORT_URLS,
    FeedImportCandidate,
    create_feed_import_job,
    normalize_feed_url,
    parse_opml_feeds,
    parse_urls_text,
    prepare_import_candidates,
    process_feed_import_job,
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


def make_import_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def make_import_user(db):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    return user


def test_process_import_job_marks_duplicate_item_skipped(mocker):
    db = make_import_db()
    user = make_import_user(db)
    prepared = prepare_import_candidates(
        [
            FeedImportCandidate(source_title="A", raw_url="https://example.com/feed.xml"),
            FeedImportCandidate(source_title="A again", raw_url="https://example.com/feed.xml"),
        ]
    )
    job = create_feed_import_job(db, user, FeedImportSourceType.urls, prepared)
    add_or_subscribe = mocker.patch("app.services.feed_import_service.add_or_subscribe_feed_from_url")
    add_or_subscribe.return_value.status = "created"
    add_or_subscribe.return_value.feed.id = uuid4()

    process_feed_import_job(db, job.id)

    db.refresh(job)
    items = db.execute(select(FeedImportItem).order_by(FeedImportItem.created_at)).scalars().all()
    assert job.status == FeedImportJobStatus.completed
    assert job.processed_count == 2
    assert job.created_count == 1
    assert job.skipped_count == 1
    assert [item.status for item in items] == [
        FeedImportItemStatus.created,
        FeedImportItemStatus.skipped,
    ]
    add_or_subscribe.assert_called_once()


def test_process_import_job_records_item_failure_and_continues(mocker):
    db = make_import_db()
    user = make_import_user(db)
    prepared = prepare_import_candidates(
        [
            FeedImportCandidate(source_title="Broken", raw_url="https://broken.example.com/feed.xml"),
            FeedImportCandidate(source_title="Good", raw_url="https://good.example.com/feed.xml"),
        ]
    )
    job = create_feed_import_job(db, user, FeedImportSourceType.urls, prepared)

    good_feed_id = uuid4()

    def fake_add(db, url, user):
        if "broken" in url:
            raise TimeoutError("timed out while fetching private details")
        result = mocker.Mock()
        result.status = "subscribed"
        result.feed.id = good_feed_id
        return result

    mocker.patch("app.services.feed_import_service.add_or_subscribe_feed_from_url", side_effect=fake_add)

    process_feed_import_job(db, job.id)

    db.refresh(job)
    items = db.execute(select(FeedImportItem).order_by(FeedImportItem.created_at)).scalars().all()
    assert job.status == FeedImportJobStatus.completed
    assert job.failed_count == 1
    assert job.subscribed_count == 1
    assert items[0].status == FeedImportItemStatus.failed
    assert items[0].message == "Feed 导入失败"
    assert items[1].status == FeedImportItemStatus.subscribed
