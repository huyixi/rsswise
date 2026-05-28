from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models import AnalysisStatus, ExtractionStatus, ReadingRecommendation


class FeedCreate(BaseModel):
    url: HttpUrl


class FeedRead(BaseModel):
    id: UUID
    title: str
    url: str
    site_url: str | None
    favicon_url: str | None
    last_fetched_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleListItem(BaseModel):
    id: UUID
    title: str
    source_title: str
    published_at: datetime | None
    one_sentence_summary: str | None
    reading_recommendation: ReadingRecommendation | None
    is_read: bool


class ArticleDetail(BaseModel):
    id: UUID
    title: str
    source_title: str
    published_at: datetime | None
    url: str
    one_sentence_summary: str | None
    reading_recommendation: ReadingRecommendation | None
    reading_reason: str | None
    content_markdown: str | None
    extraction_status: ExtractionStatus | None
    analysis_status: AnalysisStatus | None


class QueuedResponse(BaseModel):
    status: str = "queued"
