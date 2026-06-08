from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    AnalysisStatus,
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    Base,
    ExtractionStatus,
    Feed,
    ReadingRecommendation,
)
from app.tasks import (
    AI_PRIORITY_BACKGROUND,
    AI_PRIORITY_USER_OPENED,
    analyze_article_task,
    celery_app,
    extract_article_task,
)


@pytest.fixture
def session_local(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.tasks.SessionLocal", testing_session_local)
    yield testing_session_local
    Base.metadata.drop_all(bind=engine)


def seed_article(
    db: Session,
    *,
    analysis_status: AnalysisStatus = AnalysisStatus.pending,
    extraction_status: ExtractionStatus = ExtractionStatus.success,
) -> UUID:
    feed = Feed(
        title="Example Feed",
        url=f"https://example.com/{analysis_status.value}.xml",
        site_url="https://example.com",
    )
    article = Article(
        feed=feed,
        title="Readable Post",
        url=f"https://example.com/{analysis_status.value}",
        author="Ada",
        published_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        summary_from_feed="Feed summary",
        guid=f"post-{analysis_status.value}",
    )
    db.add(article)
    db.flush()
    db.add(
        ArticleContent(
            article_id=article.id,
            content_markdown="# Readable Post\n\nBody text."
            if extraction_status == ExtractionStatus.success
            else None,
            extraction_status=extraction_status,
        )
    )
    db.add(
        ArticleAIAnalysis(
            article_id=article.id,
            one_sentence_summary="Existing summary"
            if analysis_status == AnalysisStatus.success
            else None,
            reading_recommendation=ReadingRecommendation.deep_read
            if analysis_status == AnalysisStatus.success
            else None,
            reading_reason="Existing reason"
            if analysis_status == AnalysisStatus.success
            else None,
            analysis_status=analysis_status,
        )
    )
    db.commit()
    return article.id


def test_celery_redis_priority_is_configured():
    assert AI_PRIORITY_USER_OPENED == 0
    assert AI_PRIORITY_BACKGROUND == 5
    assert celery_app.conf.task_queue_max_priority == 10
    assert celery_app.conf.broker_transport_options["queue_order_strategy"] == "priority"


def test_extract_article_queues_background_ai_priority(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(
            db,
            analysis_status=AnalysisStatus.pending,
            extraction_status=ExtractionStatus.pending,
        )

    queued: list[tuple[list[str], int]] = []
    monkeypatch.setattr(
        "app.tasks.fetch_and_extract_markdown",
        lambda url: "# Extracted\n\nBody.",
    )
    monkeypatch.setattr(
        "app.tasks.analyze_article_task.apply_async",
        lambda args, priority: queued.append((args, priority)),
    )

    extract_article_task(str(article_id))

    assert queued == [([str(article_id)], AI_PRIORITY_BACKGROUND)]


def test_analyze_article_streams_chunks_and_persists_final_result(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db)

    writes: list[tuple[str, str, dict | None]] = []
    redis_client = object()
    monkeypatch.setattr("app.tasks.get_redis_client", lambda: redis_client)
    monkeypatch.setattr(
        "app.tasks.reset_analysis_events",
        lambda client, article_id: writes.append(("reset", str(article_id), None)),
    )
    monkeypatch.setattr(
        "app.tasks.write_analysis_event",
        lambda client, article_id, event_type, payload: writes.append(
            (event_type, str(article_id), payload)
        ),
    )
    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: iter(
            [
                '{"one_sentence_summary":"Short summary.",',
                '"reading_recommendation":"skim",',
                '"reading_reason":"Useful context."}',
            ]
        ),
    )

    analyze_article_task(str(article_id))

    assert writes == [
        ("reset", str(article_id), None),
        ("started", str(article_id), {"article_id": str(article_id)}),
        (
            "chunk",
            str(article_id),
            {"text": '{"one_sentence_summary":"Short summary.",'},
        ),
        (
            "chunk",
            str(article_id),
            {"text": '"reading_recommendation":"skim",'},
        ),
        (
            "chunk",
            str(article_id),
            {"text": '"reading_reason":"Useful context."}'},
        ),
        ("done", str(article_id), {"article_id": str(article_id)}),
    ]

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.success
        assert analysis.one_sentence_summary == "Short summary."
        assert analysis.reading_recommendation == ReadingRecommendation.skim
        assert analysis.reading_reason == "Useful context."


def test_analyze_article_skips_already_processing_article(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db, analysis_status=AnalysisStatus.processing)

    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: pytest.fail("processing article should not stream again"),
    )

    analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.processing


def test_analyze_article_persists_result_when_redis_events_fail(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db)

    monkeypatch.setattr("app.tasks.get_redis_client", lambda: object())
    monkeypatch.setattr(
        "app.tasks.reset_analysis_events",
        lambda client, article_id: (_ for _ in ()).throw(
            RedisError("redis unavailable")
        ),
    )
    monkeypatch.setattr(
        "app.tasks.write_analysis_event",
        lambda client, article_id, event_type, payload: (_ for _ in ()).throw(
            RedisError("redis unavailable")
        ),
    )
    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: iter(
            [
                '{"one_sentence_summary":"Short summary.",',
                '"reading_recommendation":"skim",',
                '"reading_reason":"Useful context."}',
            ]
        ),
    )

    analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.success
        assert analysis.one_sentence_summary == "Short summary."
