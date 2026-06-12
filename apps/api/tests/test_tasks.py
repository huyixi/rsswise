from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID
import hashlib

import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    AnalysisStatus,
    Article,
    ArticleAIAnalysis,
    ArticleAIAnalysisLog,
    ArticleContent,
    Base,
    ExtractionStatus,
    Feed,
    FeedImportJob,
    FeedImportSourceType,
    ReadingRecommendation,
    User,
)
from app.tasks import (
    AI_PRIORITY_BACKGROUND,
    AI_PRIORITY_USER_OPENED,
    analyze_article_task,
    celery_app,
    extract_article_task,
    import_feeds_task,
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


VALID_MARKDOWN_CHUNKS = [
    "## 带读问题\n这篇文章要回答什么？\n\n",
    "## Highlights\n- 原文第一句。\n- 原文第二句。\n- 原文第三句。\n\n",
    "## 一句话摘要\n这是一句话摘要。\n\n",
    "## 阅读建议\nskim\n\n",
    "## 阅读理由\n这篇文章适合快速了解背景。\n",
]


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
        lambda markdown: iter(VALID_MARKDOWN_CHUNKS),
    )

    analyze_article_task(str(article_id))

    assert writes == [
        ("reset", str(article_id), None),
        ("started", str(article_id), {"article_id": str(article_id)}),
        ("chunk", str(article_id), {"text": "## 带读问题\n这篇文章要回答什么？\n\n"}),
        ("chunk", str(article_id), {"text": "## Highlights\n- 原文第一句。\n- 原文第二句。\n- 原文第三句。\n\n"}),
        ("chunk", str(article_id), {"text": "## 一句话摘要\n这是一句话摘要。\n\n"}),
        ("chunk", str(article_id), {"text": "## 阅读建议\nskim\n\n"}),
        ("chunk", str(article_id), {"text": "## 阅读理由\n这篇文章适合快速了解背景。\n"}),
        ("done", str(article_id), {"article_id": str(article_id)}),
    ]

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.success
        assert analysis.ai_blocks is not None
        assert [block["type"] for block in analysis.ai_blocks] == [
            "summary",
            "reading_question",
            "reading_reason",
            "highlights",
        ]
        assert analysis.reading_recommendation == ReadingRecommendation.skim
        assert analysis.one_sentence_summary is None
        assert analysis.reading_reason is None
        log = db.execute(select(ArticleAIAnalysisLog)).scalar_one()
        assert log.article_id == article_id
        assert log.model == "deepseek-chat"
        assert log.input_content_sha256 == hashlib.sha256(
            "# Readable Post\n\nBody text.".encode("utf-8")
        ).hexdigest()
        assert log.input_content_length == len("# Readable Post\n\nBody text.")
        assert log.prompt_messages is not None
        assert log.prompt_messages[0]["role"] == "system"
        assert log.prompt_messages[1]["role"] == "user"
        assert log.raw_output == "".join(VALID_MARKDOWN_CHUNKS)
        assert log.parsed_output == analysis.ai_blocks
        assert log.status == "success"
        assert log.error_message is None
        assert log.started_at is not None
        assert log.finished_at is not None
        assert log.duration_ms is not None


def test_analyze_article_marks_failed_when_ai_markdown_is_invalid(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db)

    monkeypatch.setattr("app.tasks.get_redis_client", lambda: object())
    monkeypatch.setattr("app.tasks.reset_analysis_events", lambda client, article_id: None)
    monkeypatch.setattr("app.tasks.write_analysis_event", lambda client, article_id, event_type, payload: None)
    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: iter(["## 带读问题\n缺少其它字段"]),
    )

    with pytest.raises(Exception):
        analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.failed
        assert analysis.ai_blocks is None
        log = db.execute(select(ArticleAIAnalysisLog)).scalar_one()
        assert log.article_id == article_id
        assert log.raw_output == "## 带读问题\n缺少其它字段"
        assert log.parsed_output is None
        assert log.status == "failed"
        assert log.error_message is not None
        assert "missing required section" in log.error_message
        assert log.finished_at is not None
        assert log.duration_ms is not None


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
        lambda markdown: iter(VALID_MARKDOWN_CHUNKS),
    )

    analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.success
        assert analysis.ai_blocks is not None


def test_import_feeds_task_processes_job(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        user = User(email="import-task@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        job = FeedImportJob(
            user_id=user.id,
            source_type=FeedImportSourceType.urls,
            total_count=0,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    calls: list[UUID] = []

    def fake_process(db: Session, received_job_id: UUID) -> None:
        calls.append(received_job_id)

    monkeypatch.setattr("app.tasks.process_feed_import_job", fake_process)

    import_feeds_task(str(job_id))

    assert calls == [job_id]
