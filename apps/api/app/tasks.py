from datetime import UTC, datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import select

from app.beat import beat_schedule
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    AnalysisStatus,
    ArticleAIAnalysis,
    ArticleContent,
    ExtractionStatus,
    Feed,
    ReadingRecommendation,
)
from redis.exceptions import RedisError

from app.services.ai_blocks import parse_ai_markdown
from app.services.ai_service import stream_analyze_markdown_with_deepseek
from app.services.analysis_events import (
    get_redis_client,
    reset_analysis_events,
    write_analysis_event,
)
from app.services.email_digest_service import run_due_email_digest
from app.services.extraction_service import fetch_and_extract_markdown
from app.services.feed_service import refresh_feed_by_id

celery_app = Celery("rsswise", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.beat_schedule = beat_schedule


AI_PRIORITY_USER_OPENED = 0
AI_PRIORITY_BACKGROUND = 5

celery_app.conf.task_queue_max_priority = 10
celery_app.conf.broker_transport_options = {
    "queue_order_strategy": "priority",
}


def reset_analysis_event_stream(redis_client, article_id: str) -> None:
    try:
        reset_analysis_events(redis_client, article_id)
    except RedisError:
        return


def publish_analysis_event(redis_client, article_id: str, event_type: str, payload: dict) -> None:
    try:
        write_analysis_event(redis_client, article_id, event_type, payload)
    except RedisError:
        return


@celery_app.task(name="articles.extract")
def extract_article_task(article_id: str) -> None:
    with SessionLocal() as db:
        content = db.execute(
            select(ArticleContent).where(ArticleContent.article_id == UUID(article_id))
        ).scalar_one()
        content.extraction_status = ExtractionStatus.processing
        db.commit()

        try:
            markdown = fetch_and_extract_markdown(content.article.url)
            content.content_markdown = markdown
            content.extraction_status = ExtractionStatus.success
            content.extracted_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            analyze_article_task.apply_async(
                args=[article_id],
                priority=AI_PRIORITY_BACKGROUND,
            )
        except Exception:
            content.extraction_status = ExtractionStatus.failed
            db.commit()
            raise


@celery_app.task(name="articles.analyze")
def analyze_article_task(article_id: str) -> None:
    redis_client = get_redis_client()

    with SessionLocal() as db:
        analysis = db.get(ArticleAIAnalysis, UUID(article_id))
        content = db.get(ArticleContent, UUID(article_id))
        if analysis is None or content is None or not content.content_markdown:
            raise ValueError("article requires markdown before analysis")

        if analysis.analysis_status in {
            AnalysisStatus.processing,
            AnalysisStatus.success,
        }:
            return

        analysis.analysis_status = AnalysisStatus.processing
        analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        reset_analysis_event_stream(redis_client, article_id)
        publish_analysis_event(
            redis_client,
            article_id,
            "started",
            {"article_id": article_id},
        )

        raw_chunks: list[str] = []
        try:
            for chunk in stream_analyze_markdown_with_deepseek(content.content_markdown):
                raw_chunks.append(chunk)
                publish_analysis_event(
                    redis_client,
                    article_id,
                    "chunk",
                    {"text": chunk},
                )

            parsed = parse_ai_markdown("".join(raw_chunks), source_markdown=content.content_markdown)
            analysis.ai_blocks = parsed.ai_blocks
            analysis.reading_recommendation = ReadingRecommendation(parsed.reading_recommendation)
            analysis.analysis_status = AnalysisStatus.success
            analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            publish_analysis_event(
                redis_client,
                article_id,
                "done",
                {"article_id": article_id},
            )
        except Exception:
            analysis.analysis_status = AnalysisStatus.failed
            analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            publish_analysis_event(
                redis_client,
                article_id,
                "error",
                {"message": "AI 分析失败"},
            )
            raise


@celery_app.task(name="feeds.refresh_all")
def refresh_all_feeds_task() -> None:
    with SessionLocal() as db:
        feed_ids = [str(row[0]) for row in db.execute(select(Feed.id)).all()]

    for feed_id in feed_ids:
        refresh_feed_task.delay(feed_id)


@celery_app.task(name="feeds.refresh")
def refresh_feed_task(feed_id: str) -> None:
    with SessionLocal() as db:
        refresh_feed_by_id(db, UUID(feed_id))


@celery_app.task(name="email_digest.run_due")
def run_due_email_digest_task() -> str:
    with SessionLocal() as db:
        return run_due_email_digest(db)
