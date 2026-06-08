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


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return now_in_digest_timezone()
    if now.tzinfo is None:
        return now.replace(tzinfo=ZoneInfo(EMAIL_DIGEST_TIMEZONE))
    return now.astimezone(ZoneInfo(EMAIL_DIGEST_TIMEZONE))


def run_due_email_digest(db: Session, *, now: datetime | None = None) -> str:
    from app.services.email_digest_settings_service import get_or_create_email_digest_setting

    current_time = _normalize_now(now)
    setting = get_or_create_email_digest_setting(db)

    setting.last_attempted_at = current_time
    setting.last_send_error = None
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
            subject=f"RSSWise 文章推送 - {digest_date}",
            to_email=setting.recipient_email,
            text_body=f"本次推送包含 {len(articles)} 篇文章，见附件 EPUB。",
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
