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

    assert (
        should_run_digest(
            setting,
            now=datetime(2026, 6, 4, 7, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        is False
    )


def test_should_run_digest_runs_after_send_time() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=1,
        send_time=time(hour=8, minute=0),
    )

    assert (
        should_run_digest(
            setting,
            now=datetime(2026, 6, 4, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        is True
    )


def test_should_run_digest_skips_when_already_ran_today() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=1,
        send_time=time(hour=8, minute=0),
        last_run_date=date(2026, 6, 4),
    )

    assert (
        should_run_digest(
            setting,
            now=datetime(2026, 6, 4, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        is False
    )


def test_should_run_digest_skips_before_interval_elapses() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=7,
        send_time=time(hour=8, minute=0),
        last_run_date=date(2026, 6, 1),
    )

    assert (
        should_run_digest(
            setting,
            now=datetime(2026, 6, 4, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        is False
    )


def test_should_run_digest_runs_after_interval_elapses() -> None:
    setting = EmailDigestSetting(
        enabled=True,
        recipient_email="reader@example.com",
        send_interval_days=7,
        send_time=time(hour=8, minute=0),
        last_run_date=date(2026, 6, 1),
    )

    assert (
        should_run_digest(
            setting,
            now=datetime(2026, 6, 8, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        is True
    )


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
