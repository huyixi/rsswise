from datetime import date, datetime
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models import AnalysisStatus, ExtractionStatus, ReadingRecommendation


class FeedCreate(BaseModel):
    url: HttpUrl


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_auth_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("invalid email")
        return email


class UserRead(BaseModel):
    id: UUID
    email: str

    model_config = ConfigDict(from_attributes=True)


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


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SEND_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class EmailDigestSettingsUpdate(BaseModel):
    recipient_email: str | None = None
    enabled: bool
    send_interval_days: int = 1
    send_time: str

    @field_validator("recipient_email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("recipient_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and not EMAIL_RE.match(value):
            raise ValueError("recipient_email must be a valid email address")
        return value

    @field_validator("send_time")
    @classmethod
    def validate_send_time(cls, value: str) -> str:
        if not SEND_TIME_RE.match(value):
            raise ValueError("send_time must use HH:MM format")
        return value

    @field_validator("send_interval_days")
    @classmethod
    def validate_send_interval_days(cls, value: int) -> int:
        if value < 1 or value > 30:
            raise ValueError("send_interval_days must be between 1 and 30")
        return value

    @model_validator(mode="after")
    def validate_enabled_email(self) -> "EmailDigestSettingsUpdate":
        if self.enabled and self.recipient_email is None:
            raise ValueError("recipient_email is required when email digest is enabled")
        return self


class EmailDigestSettingsRead(BaseModel):
    recipient_email: str | None
    enabled: bool
    send_interval_days: int
    send_time: str
    timezone: str = "Asia/Shanghai"
    last_run_date: date | None
    last_sent_at: datetime | None
    last_attempted_at: datetime | None
    last_send_status: str | None
    last_send_error: str | None
    last_sent_article_count: int

    model_config = ConfigDict(from_attributes=True)


class EmailDigestTestResponse(BaseModel):
    status: str = "sent"
