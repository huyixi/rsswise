from datetime import datetime
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
from app.services.ai_service import analyze_markdown_with_deepseek
from app.services.extraction_service import fetch_and_extract_markdown
from app.services.feed_service import refresh_feed_by_id

celery_app = Celery("rsswise", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.beat_schedule = beat_schedule


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
            content.extracted_at = datetime.utcnow()
            db.commit()
            analyze_article_task.delay(article_id)
        except Exception:
            content.extraction_status = ExtractionStatus.failed
            db.commit()
            raise


@celery_app.task(name="articles.analyze")
def analyze_article_task(article_id: str) -> None:
    with SessionLocal() as db:
        analysis = db.get(ArticleAIAnalysis, UUID(article_id))
        content = db.get(ArticleContent, UUID(article_id))
        if analysis is None or content is None or not content.content_markdown:
            raise ValueError("article requires markdown before analysis")

        analysis.analysis_status = AnalysisStatus.processing
        db.commit()

        try:
            result = analyze_markdown_with_deepseek(content.content_markdown)
            analysis.one_sentence_summary = result.one_sentence_summary
            analysis.reading_recommendation = ReadingRecommendation(result.reading_recommendation)
            analysis.reading_reason = result.reading_reason
            analysis.analysis_status = AnalysisStatus.success
            analysis.updated_at = datetime.utcnow()
            db.commit()
        except Exception:
            analysis.analysis_status = AnalysisStatus.failed
            analysis.updated_at = datetime.utcnow()
            db.commit()
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
