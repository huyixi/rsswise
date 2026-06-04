# Email Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable email digest that sends newly added RSSWise articles as one EPUB attachment through backend-managed SMTP at a user-defined day interval.

**Architecture:** Store a single global email digest setting in PostgreSQL, expose it through `/settings/email-digest`, and run a Celery beat polling task that checks the configured `send_interval_days` and `send_time` in `Asia/Shanghai`. Build EPUB files with Python standard library code and send messages through a focused SMTP service so scheduling, EPUB generation, and mail delivery remain independently testable.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, Celery, Python `zoneinfo`/`zipfile`/`smtplib`, React, Vite, TanStack Query, coss UI, Playwright.

**Source Spec:** `docs/email-digest/design.md`

---

## File Map

- Modify: `apps/api/app/core/config.py`  
  Responsibility: SMTP settings, default email digest interval/send time, and TLS/SSL validation.

- Modify: `apps/api/app/models.py`  
  Responsibility: `EmailDigestSetting` model and timestamp defaults.

- Modify: `apps/api/app/schemas.py`  
  Responsibility: request and response models for email digest settings.

- Create: `apps/api/alembic/versions/0002_email_digest_settings.py`  
  Responsibility: create and drop `email_digest_settings`.

- Create: `apps/api/app/services/email_digest_settings_service.py`  
  Responsibility: load/create the singleton setting and update it safely.

- Create: `apps/api/app/services/epub_service.py`  
  Responsibility: generate deterministic EPUB bytes from article records.

- Create: `apps/api/app/services/email_service.py`  
  Responsibility: validate SMTP configuration and send plain emails with optional attachments.

- Create: `apps/api/app/services/email_digest_service.py`  
  Responsibility: decide if the digest is due, select articles, build EPUB, send email, and update setting status.

- Create: `apps/api/app/routers/settings.py`  
  Responsibility: settings API endpoints and test email endpoint.

- Modify: `apps/api/app/main.py`  
  Responsibility: include settings router.

- Modify: `apps/api/app/tasks.py`  
  Responsibility: Celery task wrapper for email digest execution.

- Modify: `apps/api/app/beat.py`  
  Responsibility: add the 5-minute email digest polling schedule.

- Modify: `apps/api/.env.example`, `apps/api/.env.test.example`, `.env.compose.example`, `README.md`  
  Responsibility: document backend SMTP variables and local usage.

- Modify: `apps/web/src/lib/api.ts`  
  Responsibility: email digest setting types and `apiPut`.

- Modify: `apps/web/src/lib/query-keys.ts`  
  Responsibility: query keys for settings.

- Create: `apps/web/src/components/email-digest-settings-dialog.tsx`  
  Responsibility: coss dialog for email, enabled switch, send time, save, and test email.

- Modify: `apps/web/src/App.tsx`  
  Responsibility: add settings button/dialog in the app header.

- Test: `apps/api/tests/test_config.py`
- Test: `apps/api/tests/test_email_digest_settings_api.py`
- Test: `apps/api/tests/test_epub_service.py`
- Test: `apps/api/tests/test_email_service.py`
- Test: `apps/api/tests/test_email_digest_service.py`
- Test: `apps/api/tests/test_beat.py`
- Test: `apps/web/tests/e2e/articles.spec.ts` or `apps/web/tests/e2e/settings.spec.ts`

---

### Task 1: Baseline And Test Fixtures

**Files:**
- Read: `docs/email-digest/design.md`
- Read: `apps/api/app/core/config.py`
- Read: `apps/api/app/models.py`
- Read: `apps/api/app/tasks.py`
- Read: `apps/api/app/beat.py`
- Read: `apps/web/src/App.tsx`
- Read: `apps/web/src/components/ui/dialog.tsx`
- Read: `apps/web/src/components/ui/field.tsx`

- [ ] **Step 1: Confirm working tree**

Run:

```bash
git status --short
```

Expected: only intentional docs changes and unrelated user changes. Do not revert unrelated files.

- [ ] **Step 2: Run backend baseline tests**

Run:

```bash
make test
```

Expected: PASS. If it fails before edits, record the failing tests and decide whether the failure blocks email digest work.

- [ ] **Step 3: Run frontend baseline checks**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: PASS. If either command fails before edits, record the failure before changing code.

---

### Task 2: Add SMTP Settings

**Files:**
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/tests/test_config.py`

- [ ] **Step 1: Add failing config tests**

Append these tests to `apps/api/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError


def test_settings_reads_smtp_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="rsswise@example.com",
        smtp_password="secret",
        smtp_from_email="rsswise@example.com",
        smtp_from_name="RSSWise",
        smtp_use_tls=True,
        smtp_use_ssl=False,
        smtp_timeout_seconds=20,
        email_digest_default_interval_days=1,
        email_digest_default_send_time="08:00",
    )

    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 587
    assert settings.smtp_user == "rsswise@example.com"
    assert settings.smtp_password == "secret"
    assert settings.smtp_from_email == "rsswise@example.com"
    assert settings.smtp_from_name == "RSSWise"
    assert settings.smtp_use_tls is True
    assert settings.smtp_use_ssl is False
    assert settings.smtp_timeout_seconds == 20
    assert settings.email_digest_default_interval_days == 1
    assert settings.email_digest_default_send_time == "08:00"


def test_settings_rejects_simultaneous_smtp_tls_and_ssl() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
            redis_url="redis://127.0.0.1:6379/0",
            smtp_use_tls=True,
            smtp_use_ssl=True,
        )


def test_settings_rejects_invalid_default_digest_interval() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
            redis_url="redis://127.0.0.1:6379/0",
            email_digest_default_interval_days=0,
        )
```

- [ ] **Step 2: Run config tests and verify failure**

Run:

```bash
uv run --directory apps/api pytest tests/test_config.py -v
```

Expected: FAIL because SMTP settings are not defined.

- [ ] **Step 3: Implement SMTP settings**

Update `Settings` in `apps/api/app/core/config.py`:

```python
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str
    redis_url: str

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "RSSWise"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 20

    email_digest_default_interval_days: int = 1
    email_digest_default_send_time: str = "08:00"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_smtp_security(self) -> Self:
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be true")
        if (
            self.email_digest_default_interval_days < 1
            or self.email_digest_default_interval_days > 30
        ):
            raise ValueError("EMAIL_DIGEST_DEFAULT_INTERVAL_DAYS must be between 1 and 30")
        return self


settings = Settings()
```

- [ ] **Step 4: Run config tests and verify pass**

Run:

```bash
uv run --directory apps/api pytest tests/test_config.py -v
```

Expected: PASS.

---

### Task 3: Add Email Digest Setting Model And Migration

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/alembic/versions/0002_email_digest_settings.py`
- Create: `apps/api/tests/test_email_digest_settings_api.py`

- [ ] **Step 1: Add failing model/migration smoke test**

Create `apps/api/tests/test_email_digest_settings_api.py` with this initial test:

```python
from app.models import EmailDigestSetting


def test_email_digest_setting_model_exists() -> None:
    assert EmailDigestSetting.__tablename__ == "email_digest_settings"
```

- [ ] **Step 2: Run the new test and verify failure**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_settings_api.py -v
```

Expected: FAIL because `EmailDigestSetting` is not defined.

- [ ] **Step 3: Add the SQLAlchemy model**

In `apps/api/app/models.py`, add these imports:

```python
from datetime import date, datetime, time
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, UniqueConstraint
```

Then add the model after `ArticleAIAnalysis`:

```python
class EmailDigestSetting(Base):
    __tablename__ = "email_digest_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    send_interval_days: Mapped[int] = mapped_column(Integer, default=1)
    send_time: Mapped[time] = mapped_column(Time(), default=lambda: time(hour=8, minute=0))
    last_run_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_send_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sent_article_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
```

Keep the existing `utcnow()` helper. If the import line becomes too long, split it across multiple lines using the existing style.

- [ ] **Step 4: Add migration**

Create `apps/api/alembic/versions/0002_email_digest_settings.py`:

```python
"""email digest settings

Revision ID: 0002_email_digest_settings
Revises: 0001_initial
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_email_digest_settings"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_digest_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("send_interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("send_time", sa.Time(), nullable=False, server_default="08:00:00"),
        sa.Column("last_run_date", sa.Date(), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_send_status", sa.String(length=50), nullable=True),
        sa.Column("last_send_error", sa.Text(), nullable=True),
        sa.Column("last_sent_article_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_digest_settings")
```

- [ ] **Step 5: Run the model test**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_settings_api.py -v
```

Expected: PASS.

---

### Task 4: Add Schemas And Singleton Settings Service

**Files:**
- Modify: `apps/api/app/schemas.py`
- Create: `apps/api/app/services/email_digest_settings_service.py`
- Modify: `apps/api/tests/test_email_digest_settings_api.py`

- [ ] **Step 1: Add schema validation tests**

Append to `apps/api/tests/test_email_digest_settings_api.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas import EmailDigestSettingsUpdate


def test_email_digest_update_accepts_hh_mm_time() -> None:
    payload = EmailDigestSettingsUpdate(
        recipient_email="reader@example.com",
        enabled=True,
        send_interval_days=7,
        send_time="07:30",
    )

    assert payload.recipient_email == "reader@example.com"
    assert payload.enabled is True
    assert payload.send_interval_days == 7
    assert payload.send_time == "07:30"


def test_email_digest_update_rejects_enabled_without_email() -> None:
    with pytest.raises(ValidationError):
        EmailDigestSettingsUpdate(
            recipient_email="",
            enabled=True,
            send_interval_days=1,
            send_time="08:00",
        )


def test_email_digest_update_rejects_invalid_send_time() -> None:
    with pytest.raises(ValidationError):
        EmailDigestSettingsUpdate(
            recipient_email="reader@example.com",
            enabled=True,
            send_interval_days=1,
            send_time="24:00",
        )


def test_email_digest_update_rejects_invalid_send_interval() -> None:
    with pytest.raises(ValidationError):
        EmailDigestSettingsUpdate(
            recipient_email="reader@example.com",
            enabled=True,
            send_interval_days=0,
            send_time="08:00",
        )
```

- [ ] **Step 2: Run schema tests and verify failure**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_settings_api.py -v
```

Expected: FAIL because schemas are not defined.

- [ ] **Step 3: Add schemas**

In `apps/api/app/schemas.py`, add:

```python
import re
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

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
```

Merge these imports with the existing imports instead of duplicating `BaseModel`, `ConfigDict`, or `datetime`.

- [ ] **Step 4: Create settings service**

Create `apps/api/app/services/email_digest_settings_service.py`:

```python
from datetime import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import EmailDigestSetting
from app.schemas import EmailDigestSettingsUpdate

SINGLETON_SETTING_ID = 1
EMAIL_DIGEST_TIMEZONE = "Asia/Shanghai"


def parse_send_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(hour=int(hour), minute=int(minute))


def format_send_time(value: time) -> str:
    return value.strftime("%H:%M")


def default_send_time() -> time:
    return parse_send_time(settings.email_digest_default_send_time)


def default_send_interval_days() -> int:
    return settings.email_digest_default_interval_days


def get_or_create_email_digest_setting(db: Session) -> EmailDigestSetting:
    setting = db.get(EmailDigestSetting, SINGLETON_SETTING_ID)
    if setting is not None:
        return setting

    setting = EmailDigestSetting(
        id=SINGLETON_SETTING_ID,
        send_interval_days=default_send_interval_days(),
        send_time=default_send_time(),
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def update_email_digest_setting(
    db: Session,
    payload: EmailDigestSettingsUpdate,
) -> EmailDigestSetting:
    setting = get_or_create_email_digest_setting(db)
    setting.recipient_email = str(payload.recipient_email) if payload.recipient_email else None
    setting.enabled = payload.enabled
    setting.send_interval_days = payload.send_interval_days
    setting.send_time = parse_send_time(payload.send_time)
    db.commit()
    db.refresh(setting)
    return setting
```

- [ ] **Step 5: Run settings tests**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_settings_api.py -v
```

Expected: PASS.

---

### Task 5: Add Settings API And Test Email Endpoint

**Files:**
- Create: `apps/api/app/routers/settings.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/app/services/email_service.py`
- Modify: `apps/api/tests/test_email_digest_settings_api.py`
- Create: `apps/api/tests/test_email_service.py`

- [ ] **Step 1: Add API tests**

Append to `apps/api/tests/test_email_digest_settings_api.py`:

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_get_email_digest_settings_returns_default(client: TestClient) -> None:
    response = client.get("/settings/email-digest")

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_email"] is None
    assert data["enabled"] is False
    assert data["send_interval_days"] == 1
    assert data["send_time"] == "08:00"
    assert data["timezone"] == "Asia/Shanghai"


def test_put_email_digest_settings_updates_values(client: TestClient) -> None:
    response = client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 7,
            "send_time": "07:30",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_email"] == "reader@example.com"
    assert data["enabled"] is True
    assert data["send_interval_days"] == 7
    assert data["send_time"] == "07:30"


def test_put_email_digest_settings_rejects_enabled_without_email(client: TestClient) -> None:
    response = client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Add email service tests**

Create `apps/api/tests/test_email_service.py`:

```python
import pytest

from app.core.config import settings
from app.services.email_service import EmailAttachment, SMTPConfigError, build_email_message


def test_build_email_message_includes_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from_email", "rsswise@example.com")

    message = build_email_message(
        subject="RSSWise 摘要 - 2026-06-04",
        to_email="reader@example.com",
        text_body="本次摘要包含 1 篇文章。",
        attachments=[
            EmailAttachment(
                filename="rsswise-digest-2026-06-04.epub",
                content=b"epub-bytes",
                content_type="application/epub+zip",
            )
        ],
    )

    assert message["Subject"] == "RSSWise 摘要 - 2026-06-04"
    assert message["To"] == "reader@example.com"
    assert message.is_multipart()


def test_validate_smtp_config_rejects_missing_host() -> None:
    from app.services.email_service import validate_smtp_config

    with pytest.raises(SMTPConfigError):
        validate_smtp_config(
            smtp_host="",
            smtp_from_email="rsswise@example.com",
        )
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_settings_api.py tests/test_email_service.py -v
```

Expected: FAIL because the router and email service do not exist.

- [ ] **Step 4: Implement email service**

Create `apps/api/app/services/email_service.py`:

```python
from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from app.core.config import settings


class SMTPConfigError(ValueError):
    pass


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str


def validate_smtp_config(
    *,
    smtp_host: str | None = None,
    smtp_from_email: str | None = None,
) -> None:
    host = settings.smtp_host if smtp_host is None else smtp_host
    from_email = settings.smtp_from_email if smtp_from_email is None else smtp_from_email
    if not host:
        raise SMTPConfigError("SMTP_HOST is required")
    if not from_email:
        raise SMTPConfigError("SMTP_FROM_EMAIL is required")


def build_email_message(
    *,
    subject: str,
    to_email: str,
    text_body: str,
    attachments: list[EmailAttachment] | None = None,
) -> EmailMessage:
    validate_smtp_config()

    message = EmailMessage()
    from_display = settings.smtp_from_email
    if settings.smtp_from_name:
        from_display = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["From"] = from_display
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)

    for attachment in attachments or []:
        maintype, subtype = attachment.content_type.split("/", 1)
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    return message


def send_email(
    *,
    subject: str,
    to_email: str,
    text_body: str,
    attachments: list[EmailAttachment] | None = None,
) -> None:
    message = build_email_message(
        subject=subject,
        to_email=to_email,
        text_body=text_body,
        attachments=attachments,
    )

    smtp_cls = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_cls(
        settings.smtp_host,
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as smtp:
        smtp.ehlo()
        if settings.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
```

- [ ] **Step 5: Implement settings router**

Create `apps/api/app/routers/settings.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    EmailDigestSettingsRead,
    EmailDigestSettingsUpdate,
    EmailDigestTestResponse,
)
from app.services.email_digest_settings_service import (
    EMAIL_DIGEST_TIMEZONE,
    format_send_time,
    get_or_create_email_digest_setting,
    update_email_digest_setting,
)
from app.services.email_service import SMTPConfigError, send_email

router = APIRouter(prefix="/settings", tags=["settings"])


def serialize_email_digest_setting(setting) -> EmailDigestSettingsRead:
    return EmailDigestSettingsRead(
        recipient_email=setting.recipient_email,
        enabled=setting.enabled,
        send_interval_days=setting.send_interval_days,
        send_time=format_send_time(setting.send_time),
        timezone=EMAIL_DIGEST_TIMEZONE,
        last_run_date=setting.last_run_date,
        last_sent_at=setting.last_sent_at,
        last_attempted_at=setting.last_attempted_at,
        last_send_status=setting.last_send_status,
        last_send_error=setting.last_send_error,
        last_sent_article_count=setting.last_sent_article_count,
    )


@router.get("/email-digest", response_model=EmailDigestSettingsRead)
def get_email_digest_settings(db: Session = Depends(get_db)):
    return serialize_email_digest_setting(get_or_create_email_digest_setting(db))


@router.put("/email-digest", response_model=EmailDigestSettingsRead)
def put_email_digest_settings(
    payload: EmailDigestSettingsUpdate,
    db: Session = Depends(get_db),
):
    return serialize_email_digest_setting(update_email_digest_setting(db, payload))


@router.post("/email-digest/test", response_model=EmailDigestTestResponse)
def send_test_email(db: Session = Depends(get_db)):
    setting = get_or_create_email_digest_setting(db)
    if not setting.recipient_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="recipient email is not configured",
        )

    try:
        send_email(
            subject="RSSWise 测试邮件",
            to_email=setting.recipient_email,
            text_body="这是一封 RSSWise 测试邮件，用于验证 SMTP 和收件邮箱配置。",
        )
    except SMTPConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to send test email",
        ) from exc

    return EmailDigestTestResponse()
```

- [ ] **Step 6: Include router**

In `apps/api/app/main.py`, update imports and router registration:

```python
from app.routers import articles, feeds, settings

app.include_router(feeds.router)
app.include_router(articles.router)
app.include_router(settings.router)
```

- [ ] **Step 7: Run API and email service tests**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_settings_api.py tests/test_email_service.py -v
```

Expected: PASS.

---

### Task 6: Add EPUB Generation

**Files:**
- Create: `apps/api/app/services/epub_service.py`
- Create: `apps/api/tests/test_epub_service.py`

- [ ] **Step 1: Add EPUB tests**

Create `apps/api/tests/test_epub_service.py`:

```python
from datetime import datetime
from uuid import uuid4
import zipfile
from io import BytesIO

from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed
from app.services.epub_service import build_digest_epub


def make_article(*, content_markdown: str | None) -> Article:
    feed = Feed(id=uuid4(), title="Example Feed", url="https://example.com/feed.xml")
    article = Article(
        id=uuid4(),
        feed=feed,
        title="A useful article",
        url="https://example.com/a-useful-article",
        created_at=datetime(2026, 6, 4, 1, 0, 0),
    )
    article.content = ArticleContent(content_markdown=content_markdown)
    article.ai_analysis = ArticleAIAnalysis(
        one_sentence_summary="一句话摘要",
        reading_reason="值得阅读的理由",
    )
    return article


def test_build_digest_epub_contains_article_metadata_and_body() -> None:
    epub = build_digest_epub([make_article(content_markdown="第一段\n\n第二段")], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        names = set(archive.namelist())
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "mimetype" in names
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "A useful article" in chapter
    assert "Example Feed" in chapter
    assert "https://example.com/a-useful-article" in chapter
    assert "一句话摘要" in chapter
    assert "值得阅读的理由" in chapter
    assert "第一段" in chapter
    assert "第二段" in chapter


def test_build_digest_epub_allows_missing_body() -> None:
    epub = build_digest_epub([make_article(content_markdown=None)], digest_date="2026-06-04")

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        chapter = archive.read("OEBPS/chapters/article-001.xhtml").decode()

    assert "A useful article" in chapter
    assert "正文抽取未完成或失败" in chapter
```

- [ ] **Step 2: Run EPUB tests and verify failure**

Run:

```bash
uv run --directory apps/api pytest tests/test_epub_service.py -v
```

Expected: FAIL because `epub_service.py` does not exist.

- [ ] **Step 3: Implement EPUB service**

Create `apps/api/app/services/epub_service.py` with these public functions:

```python
from __future__ import annotations

from html import escape
from io import BytesIO
from textwrap import dedent
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from app.models import Article


def markdown_to_xhtml(markdown: str | None) -> str:
    if not markdown:
        return "<p>正文抽取未完成或失败。</p>"

    paragraphs = [part.strip() for part in markdown.split("\n\n") if part.strip()]
    if not paragraphs:
        return "<p>正文抽取未完成或失败。</p>"
    return "\n".join(f"<p>{escape(part).replace(chr(10), '<br />')}</p>" for part in paragraphs)


def article_chapter_xhtml(article: Article, index: int) -> str:
    summary = ""
    reason = ""
    if article.ai_analysis is not None:
        summary = article.ai_analysis.one_sentence_summary or ""
        reason = article.ai_analysis.reading_reason or ""

    return dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head>
            <title>{escape(article.title)}</title>
            <meta charset="utf-8" />
          </head>
          <body>
            <h1>{escape(article.title)}</h1>
            <p><strong>来源：</strong>{escape(article.feed.title)}</p>
            <p><strong>链接：</strong><a href="{escape(article.url)}">{escape(article.url)}</a></p>
            <p><strong>AI 摘要：</strong>{escape(summary) if summary else "暂无 AI 总结"}</p>
            <p><strong>阅读理由：</strong>{escape(reason) if reason else "暂无阅读理由"}</p>
            {markdown_to_xhtml(article.content.content_markdown if article.content else None)}
          </body>
        </html>
        """
    )


def build_digest_epub(articles: list[Article], *, digest_date: str) -> bytes:
    identifier = f"urn:uuid:{uuid4()}"
    chapter_items = "\n".join(
        f'<item id="article-{index:03d}" href="chapters/article-{index:03d}.xhtml" media-type="application/xhtml+xml" />'
        for index, _ in enumerate(articles, start=1)
    )
    spine_items = "\n".join(
        f'<itemref idref="article-{index:03d}" />'
        for index, _ in enumerate(articles, start=1)
    )
    nav_items = "\n".join(
        f'<li><a href="chapters/article-{index:03d}.xhtml">{escape(article.title)}</a></li>'
        for index, article in enumerate(articles, start=1)
    )

    content_opf = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:identifier id="book-id">{identifier}</dc:identifier>
            <dc:title>RSSWise Digest - {digest_date}</dc:title>
            <dc:language>zh-CN</dc:language>
            <dc:creator>RSSWise</dc:creator>
          </metadata>
          <manifest>
            <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
            {chapter_items}
          </manifest>
          <spine>
            {spine_items}
          </spine>
        </package>
        """
    )

    nav_xhtml = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head><title>RSSWise Digest - {digest_date}</title></head>
          <body>
            <nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">
              <h1>RSSWise Digest - {digest_date}</h1>
              <ol>{nav_items}</ol>
            </nav>
          </body>
        </html>
        """
    )

    toc_ncx = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
          <head><meta name="dtb:uid" content="{identifier}" /></head>
          <docTitle><text>RSSWise Digest - {digest_date}</text></docTitle>
          <navMap></navMap>
        </ncx>
        """
    )

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            dedent(
                """\
                <?xml version="1.0" encoding="utf-8"?>
                <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" />
                  </rootfiles>
                </container>
                """
            ),
            compress_type=ZIP_DEFLATED,
        )
        archive.writestr("OEBPS/content.opf", content_opf, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/nav.xhtml", nav_xhtml, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/toc.ncx", toc_ncx, compress_type=ZIP_DEFLATED)
        for index, article in enumerate(articles, start=1):
            archive.writestr(
                f"OEBPS/chapters/article-{index:03d}.xhtml",
                article_chapter_xhtml(article, index),
                compress_type=ZIP_DEFLATED,
            )
    return output.getvalue()
```

- [ ] **Step 4: Run EPUB tests**

Run:

```bash
uv run --directory apps/api pytest tests/test_epub_service.py -v
```

Expected: PASS.

---

### Task 7: Add Digest Service And Celery Scheduling

**Files:**
- Create: `apps/api/app/services/email_digest_service.py`
- Modify: `apps/api/app/tasks.py`
- Modify: `apps/api/app/beat.py`
- Create: `apps/api/tests/test_email_digest_service.py`
- Modify: `apps/api/tests/test_beat.py`

- [ ] **Step 1: Add digest service tests**

Create `apps/api/tests/test_email_digest_service.py`:

```python
from collections.abc import Iterator
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    Base,
    EmailDigestSetting,
    Feed,
)
from app.services.email_digest_service import run_due_email_digest, should_run_digest


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        yield db

    Base.metadata.drop_all(bind=engine)


def seed_digest_setting(db: Session) -> EmailDigestSetting:
    setting = EmailDigestSetting(
        id=1,
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=1,
        send_time=time(hour=8, minute=0),
    )
    db.add(setting)
    db.commit()
    return setting


def seed_digest_article(db: Session) -> Article:
    feed = Feed(
        title="Example Feed",
        url="https://example.com/feed.xml",
        site_url="https://example.com",
    )
    article = Article(
        feed=feed,
        title="Readable Post",
        url="https://example.com/readable-post",
        is_read=False,
        created_at=datetime(2026, 6, 4, 1, 0, 0),
    )
    article.content = ArticleContent(content_markdown="Readable body.")
    article.ai_analysis = ArticleAIAnalysis(
        one_sentence_summary="A concise summary.",
        reading_reason="A durable reason.",
    )
    db.add(article)
    db.commit()
    return article


def test_should_run_digest_waits_until_configured_send_time() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=1,
        send_time=time(hour=8, minute=0),
    )

    assert should_run_digest(
        setting,
        now=datetime(2026, 6, 4, 7, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
    ) is False


def test_should_run_digest_runs_after_send_time() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=1,
        send_time=time(hour=8, minute=0),
    )

    assert should_run_digest(
        setting,
        now=datetime(2026, 6, 4, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    ) is True


def test_should_run_digest_skips_when_already_ran_today() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=1,
        send_time=time(hour=8, minute=0),
        last_run_date=date(2026, 6, 4),
    )

    assert should_run_digest(
        setting,
        now=datetime(2026, 6, 4, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    ) is False


def test_should_run_digest_skips_before_interval_elapses() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=7,
        send_time=time(hour=8, minute=0),
        last_run_date=date(2026, 6, 1),
    )

    assert should_run_digest(
        setting,
        now=datetime(2026, 6, 4, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    ) is False


def test_should_run_digest_runs_after_interval_elapses() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=7,
        send_time=time(hour=8, minute=0),
        last_run_date=date(2026, 6, 1),
    )

    assert should_run_digest(
        setting,
        now=datetime(2026, 6, 8, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    ) is True


def test_run_due_email_digest_skips_without_articles(db_session: Session) -> None:
    setting = seed_digest_setting(db_session)

    status = run_due_email_digest(
        db_session,
        now=datetime(2026, 6, 4, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    db_session.refresh(setting)

    assert status == "skipped_no_articles"
    assert setting.last_run_date == date(2026, 6, 4)
    assert setting.last_sent_at is None
    assert setting.last_sent_article_count == 0


def test_run_due_email_digest_success_updates_last_sent_at(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setting = seed_digest_setting(db_session)
    seed_digest_article(db_session)
    sent_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.services.email_digest_service.send_email",
        lambda **kwargs: sent_messages.append(kwargs),
    )

    status = run_due_email_digest(
        db_session,
        now=datetime(2026, 6, 4, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    db_session.refresh(setting)

    assert status == "success"
    assert setting.last_sent_at is not None
    assert setting.last_run_date == date(2026, 6, 4)
    assert setting.last_sent_article_count == 1
    assert sent_messages[0]["to_email"] == "reader@example.com"


def test_run_due_email_digest_failure_does_not_update_last_sent_at(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setting = seed_digest_setting(db_session)
    seed_digest_article(db_session)

    def raise_smtp_error(**kwargs: object) -> None:
        raise RuntimeError("smtp failed")

    monkeypatch.setattr("app.services.email_digest_service.send_email", raise_smtp_error)

    with pytest.raises(RuntimeError):
        run_due_email_digest(
            db_session,
            now=datetime(2026, 6, 4, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    db_session.refresh(setting)

    assert setting.last_send_status == "failed"
    assert setting.last_sent_at is None
    assert setting.last_run_date == date(2026, 6, 4)
```

- [ ] **Step 2: Add beat schedule test**

Update `apps/api/tests/test_beat.py` to assert the new schedule exists:

```python
from app.beat import beat_schedule


def test_email_digest_schedule_registered() -> None:
    schedule = beat_schedule["email-digest-every-five-minutes"]

    assert schedule["task"] == "email_digest.run_due"
    assert schedule["schedule"] == 300.0
```

Keep existing beat tests intact.

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_service.py tests/test_beat.py -v
```

Expected: FAIL because the digest service and beat entry are missing.

- [ ] **Step 4: Implement digest service**

Create `apps/api/app/services/email_digest_service.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Article, EmailDigestSetting
from app.services.email_digest_settings_service import EMAIL_DIGEST_TIMEZONE
from app.services.email_service import EmailAttachment, send_email
from app.services.epub_service import build_digest_epub


def now_in_digest_timezone() -> datetime:
    return datetime.now(ZoneInfo(EMAIL_DIGEST_TIMEZONE))


def should_run_digest(setting: EmailDigestSetting, *, now: datetime) -> bool:
    if not setting.enabled:
        return False
    if not setting.recipient_email:
        return False
    if now.time().replace(second=0, microsecond=0) < setting.send_time:
        return False
    if setting.last_run_date == now.date():
        return False
    if setting.last_run_date is not None:
        days_since_last_run = (now.date() - setting.last_run_date).days
        if days_since_last_run < setting.send_interval_days:
            return False
    return True


def list_digest_articles(db: Session, setting: EmailDigestSetting) -> list[Article]:
    statement = (
        select(Article)
        .options(
            joinedload(Article.feed),
            joinedload(Article.content),
            joinedload(Article.ai_analysis),
        )
        .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
    )
    if setting.last_sent_at is not None:
        statement = statement.where(Article.created_at > setting.last_sent_at)
    return db.execute(statement).unique().scalars().all()


def run_due_email_digest(db: Session, *, now: datetime | None = None) -> str:
    from app.services.email_digest_settings_service import get_or_create_email_digest_setting

    current_time = now or now_in_digest_timezone()
    setting = get_or_create_email_digest_setting(db)

    setting.last_attempted_at = current_time
    if not setting.enabled:
        setting.last_send_status = "skipped_disabled"
        db.commit()
        return setting.last_send_status
    if not setting.recipient_email:
        setting.last_send_status = "skipped_missing_recipient"
        db.commit()
        return setting.last_send_status
    if current_time.time().replace(second=0, microsecond=0) < setting.send_time:
        setting.last_send_status = "skipped_before_send_time"
        db.commit()
        return setting.last_send_status
    if setting.last_run_date == current_time.date():
        setting.last_send_status = "skipped_already_ran_today"
        db.commit()
        return setting.last_send_status
    if setting.last_run_date is not None:
        days_since_last_run = (current_time.date() - setting.last_run_date).days
        if days_since_last_run < setting.send_interval_days:
            setting.last_send_status = "skipped_interval_not_due"
            db.commit()
            return setting.last_send_status

    articles = list_digest_articles(db, setting)
    setting.last_run_date = current_time.date()

    if not articles:
        setting.last_send_status = "skipped_no_articles"
        setting.last_send_error = None
        setting.last_sent_article_count = 0
        db.commit()
        return setting.last_send_status

    digest_date = current_time.date().isoformat()
    try:
        epub = build_digest_epub(articles, digest_date=digest_date)
        send_email(
            subject=f"RSSWise 摘要 - {digest_date}",
            to_email=setting.recipient_email,
            text_body=f"本次 RSSWise 摘要包含 {len(articles)} 篇文章，见附件 EPUB。",
            attachments=[
                EmailAttachment(
                    filename=f"rsswise-digest-{digest_date}.epub",
                    content=epub,
                    content_type="application/epub+zip",
                )
            ],
        )
    except Exception as exc:
        setting.last_send_status = "failed"
        setting.last_send_error = str(exc)[:1000]
        db.commit()
        raise

    setting.last_sent_at = current_time
    setting.last_send_status = "success"
    setting.last_send_error = None
    setting.last_sent_article_count = len(articles)
    db.commit()
    return setting.last_send_status
```

- [ ] **Step 5: Add Celery task**

In `apps/api/app/tasks.py`, add:

```python
from app.services.email_digest_service import run_due_email_digest


@celery_app.task(name="email_digest.run_due")
def run_due_email_digest_task() -> str:
    with SessionLocal() as db:
        return run_due_email_digest(db)
```

- [ ] **Step 6: Add beat schedule**

In `apps/api/app/beat.py`, add:

```python
"email-digest-every-five-minutes": {
    "task": "email_digest.run_due",
    "schedule": 300.0,
},
```

Keep the existing hourly feed refresh schedule.

- [ ] **Step 7: Run digest service tests**

Run:

```bash
uv run --directory apps/api pytest tests/test_email_digest_service.py tests/test_beat.py -v
```

Expected: PASS.

---

### Task 8: Add Frontend API Types And Query Keys

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/query-keys.ts`

- [ ] **Step 1: Add API types and PUT helper**

In `apps/web/src/lib/api.ts`, add:

```ts
export type EmailDigestSettings = {
  recipient_email: string | null
  enabled: boolean
  send_interval_days: number
  send_time: string
  timezone: "Asia/Shanghai"
  last_run_date: string | null
  last_sent_at: string | null
  last_attempted_at: string | null
  last_send_status: string | null
  last_send_error: string | null
  last_sent_article_count: number
}

export type EmailDigestSettingsUpdate = {
  recipient_email: string | null
  enabled: boolean
  send_interval_days: number
  send_time: string
}
```

Also add:

```ts
export async function apiPut<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  return parseResponse<T>(response)
}
```

- [ ] **Step 2: Add settings query keys**

In `apps/web/src/lib/query-keys.ts`, add:

```ts
settings: {
  all: ["settings"] as const,
  emailDigest: () => ["settings", "email-digest"] as const,
},
```

Keep existing `articles` and `feeds` keys unchanged.

- [ ] **Step 3: Run frontend lint**

Run:

```bash
pnpm --dir apps/web lint
```

Expected: PASS.

---

### Task 9: Add Email Digest Settings Dialog

**Files:**
- Create: `apps/web/src/components/email-digest-settings-dialog.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Create dialog component**

Create `apps/web/src/components/email-digest-settings-dialog.tsx`. Use this structure and keep `DialogHeader` outside the form:

```tsx
import { useEffect, useState, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { MailIcon, SettingsIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import {
  apiGet,
  apiPost,
  apiPut,
  type EmailDigestSettings,
  type EmailDigestSettingsUpdate,
} from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

function statusLabel(status: string | null) {
  switch (status) {
    case "success":
      return "最近一次发送成功"
    case "failed":
      return "最近一次发送失败"
    case "skipped_no_articles":
      return "最近一次检查没有新增文章"
    case "skipped_disabled":
      return "邮件摘要已停用"
    case "skipped_missing_recipient":
      return "未配置收件邮箱"
    case "skipped_interval_not_due":
      return "未到下次发送间隔"
    default:
      return "暂无发送记录"
  }
}

export function EmailDigestSettingsDialog() {
  const [email, setEmail] = useState("")
  const [enabled, setEnabled] = useState(false)
  const [sendIntervalDays, setSendIntervalDays] = useState(1)
  const [sendTime, setSendTime] = useState("08:00")
  const [localError, setLocalError] = useState<string | null>(null)

  const settingsQuery = useQuery({
    queryKey: queryKeys.settings.emailDigest(),
    queryFn: () => apiGet<EmailDigestSettings>("/settings/email-digest"),
  })

  useEffect(() => {
    if (!settingsQuery.data) return
    setEmail(settingsQuery.data.recipient_email ?? "")
    setEnabled(settingsQuery.data.enabled)
    setSendIntervalDays(settingsQuery.data.send_interval_days)
    setSendTime(settingsQuery.data.send_time)
  }, [settingsQuery.data])

  const saveMutation = useMutation({
    mutationFn: (payload: EmailDigestSettingsUpdate) =>
      apiPut<EmailDigestSettings>("/settings/email-digest", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.settings.emailDigest(),
      })
    },
  })

  const testMutation = useMutation({
    mutationFn: () => apiPost("/settings/email-digest/test"),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLocalError(null)
    const trimmedEmail = email.trim()
    if (enabled && !trimmedEmail) {
      setLocalError("启用邮件摘要前需要填写收件邮箱")
      return
    }
    if (sendIntervalDays < 1 || sendIntervalDays > 30) {
      setLocalError("发送间隔需要在 1 到 30 天之间")
      return
    }

    saveMutation.mutate({
      recipient_email: trimmedEmail || null,
      enabled,
      send_interval_days: sendIntervalDays,
      send_time: sendTime,
    })
  }

  const error =
    localError ??
    saveMutation.error?.message ??
    testMutation.error?.message ??
    null

  return (
    <Dialog>
      <DialogTrigger
        render={<Button aria-label="邮件摘要设置" size="icon" variant="ghost" />}
      >
        <SettingsIcon aria-hidden="true" />
      </DialogTrigger>
      <DialogPopup>
        <DialogHeader>
          <DialogTitle>邮件摘要</DialogTitle>
          <DialogDescription>
            设置收件邮箱、发送间隔和发送时间。
          </DialogDescription>
        </DialogHeader>
        <form className="contents" onSubmit={handleSubmit}>
          <DialogPanel className="flex flex-col gap-4">
            <Field>
              <FieldLabel htmlFor="email-digest-recipient">收件邮箱</FieldLabel>
              <Input
                id="email-digest-recipient"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="reader@example.com"
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="email-digest-interval">发送间隔天数</FieldLabel>
              <Input
                id="email-digest-interval"
                type="number"
                min={1}
                max={30}
                value={sendIntervalDays}
                onChange={(event) => setSendIntervalDays(Number(event.target.value))}
              />
              <FieldDescription>1 表示每天发送，7 表示每周发送。</FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="email-digest-send-time">发送时间</FieldLabel>
              <Input
                id="email-digest-send-time"
                type="time"
                value={sendTime}
                onChange={(event) => setSendTime(event.target.value)}
              />
              <FieldDescription>固定使用 Asia/Shanghai 时区。</FieldDescription>
            </Field>

            <div className="flex items-center justify-between gap-4 rounded-lg border bg-card p-3">
              <div>
                <p className="text-sm font-medium text-foreground">启用邮件摘要</p>
                <p className="text-xs text-muted-foreground">有新增文章时发送 EPUB 附件。</p>
              </div>
              <Switch
                aria-label="启用邮件摘要"
                checked={enabled}
                onCheckedChange={setEnabled}
              />
            </div>

            {settingsQuery.data ? (
              <div className="flex items-start gap-2 rounded-lg border bg-card p-3 text-sm text-muted-foreground">
                <MailIcon aria-hidden="true" className="mt-0.5 size-4" />
                <div>
                  <p>{statusLabel(settingsQuery.data.last_send_status)}</p>
                  {settingsQuery.data.last_send_error ? (
                    <p className="mt-1 text-destructive-foreground">
                      {settingsQuery.data.last_send_error}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {error ? (
              <p className="text-sm text-destructive-foreground">{error}</p>
            ) : null}
          </DialogPanel>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              loading={testMutation.isPending}
              disabled={testMutation.isPending || !settingsQuery.data?.recipient_email}
              onClick={() => testMutation.mutate()}
            >
              发送测试邮件
            </Button>
            <Button
              type="submit"
              loading={saveMutation.isPending}
              disabled={saveMutation.isPending}
            >
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogPopup>
    </Dialog>
  )
}
```

- [ ] **Step 2: Add header entry**

In `apps/web/src/App.tsx`, import and render the dialog:

```tsx
import { EmailDigestSettingsDialog } from "@/components/email-digest-settings-dialog"
```

Inside `<nav>`, add a right-aligned container:

```tsx
<div className="ml-auto">
  <EmailDigestSettingsDialog />
</div>
```

- [ ] **Step 3: Run frontend lint and build**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: PASS.

---

### Task 10: Add Frontend E2E Coverage

**Files:**
- Create: `apps/web/tests/e2e/settings.spec.ts` or modify `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Add settings dialog E2E test**

Create `apps/web/tests/e2e/settings.spec.ts`:

```ts
import { expect, test } from "@playwright/test"

test("email digest settings dialog saves settings and sends test email", async ({ page }) => {
  await page.route("**/api/settings/email-digest", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        contentType: "application/json",
        json: {
          recipient_email: null,
          enabled: false,
          send_interval_days: 1,
          send_time: "08:00",
          timezone: "Asia/Shanghai",
          last_run_date: null,
          last_sent_at: null,
          last_attempted_at: null,
          last_send_status: null,
          last_send_error: null,
          last_sent_article_count: 0,
        },
      })
      return
    }

    expect(route.request().method()).toBe("PUT")
    expect(route.request().postDataJSON()).toEqual({
      recipient_email: "reader@example.com",
      enabled: true,
      send_interval_days: 7,
      send_time: "07:30",
    })
    await route.fulfill({
      contentType: "application/json",
      json: {
        recipient_email: "reader@example.com",
        enabled: true,
        send_interval_days: 7,
        send_time: "07:30",
        timezone: "Asia/Shanghai",
        last_run_date: null,
        last_sent_at: null,
        last_attempted_at: null,
        last_send_status: null,
        last_send_error: null,
        last_sent_article_count: 0,
      },
    })
  })

  await page.route("**/api/settings/email-digest/test", async (route) => {
    expect(route.request().method()).toBe("POST")
    await route.fulfill({
      contentType: "application/json",
      json: { status: "sent" },
    })
  })

  await page.goto("/articles")
  await page.getByRole("button", { name: "邮件摘要设置" }).click()
  await page.getByLabel("收件邮箱").fill("reader@example.com")
  await page.getByLabel("发送间隔天数").fill("7")
  await page.getByLabel("发送时间").fill("07:30")
  await page.getByRole("switch", { name: /启用邮件摘要/ }).click()
  await page.getByRole("button", { name: "保存" }).click()
  await page.getByRole("button", { name: "发送测试邮件" }).click()
})
```

- [ ] **Step 2: Run E2E test**

Run:

```bash
pnpm --dir apps/web test:e2e -- settings.spec.ts
```

Expected: PASS.

---

### Task 11: Update Environment Docs

**Files:**
- Modify: `apps/api/.env.example`
- Modify: `apps/api/.env.test.example`
- Modify: `.env.compose.example`
- Modify: `README.md`

- [ ] **Step 1: Add backend env examples**

Append to `apps/api/.env.example` and `apps/api/.env.test.example`:

```text
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=RSSWise
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=20

EMAIL_DIGEST_DEFAULT_INTERVAL_DAYS=1
EMAIL_DIGEST_DEFAULT_SEND_TIME=08:00
```

- [ ] **Step 2: Confirm compose env ownership**

In `.env.compose.example`, do not add SMTP secrets unless production Compose interpolation explicitly needs them. SMTP runtime values belong in `apps/api/.env.production`.

- [ ] **Step 3: Update README production environment section**

Add:

````markdown
### Email Digest

Email digests are configured in the web settings dialog, including recipient, enabled state, send interval in days, and send time. The backend sends mail through SMTP values from `apps/api/.env` or `apps/api/.env.production`:

```text
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=rsswise@example.com
SMTP_PASSWORD=change-me
SMTP_FROM_EMAIL=rsswise@example.com
SMTP_FROM_NAME=RSSWise
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

The digest send interval and send time are stored in the database. Send time is interpreted as `Asia/Shanghai`.
````

- [ ] **Step 4: Run env safety check**

Run:

```bash
scripts/check-env-safety.sh
```

Expected: PASS.

---

### Task 12: Full Verification

**Files:**
- Read: all modified files

- [ ] **Step 1: Run backend tests**

Run:

```bash
make test
```

Expected: PASS.

- [ ] **Step 2: Run backend lint**

Run:

```bash
uv run --directory apps/api ruff check .
```

Expected: PASS.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
```

Expected: PASS.

- [ ] **Step 4: Run database migration locally**

Run:

```bash
make db-migrate
```

Expected: Alembic applies `0002_email_digest_settings` without errors.

- [ ] **Step 5: Manual smoke test**

Run the local stack:

```bash
make dev-up
make api
make worker
make beat
make web
```

In the web app:

- Open `/articles`.
- Open the email digest settings dialog.
- Save `reader@example.com`, enable the digest, set interval `7`, and set `07:30`.
- With valid SMTP env values, send a test email.
- Confirm API logs show a successful `POST /settings/email-digest/test`.

Expected: settings save successfully, test email succeeds when SMTP is valid, and no SMTP secrets appear in frontend code or browser network responses.

---

## Execution Notes

- Do not add a user table or authentication in this implementation.
- Do not add multiple recipients.
- Do not expose SMTP settings through frontend APIs.
- Do not update `last_sent_at` on failed digest sends.
- Do not send a digest when no new articles exist.
- Keep all user-facing times in `Asia/Shanghai`.
