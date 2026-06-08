from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EmailDigestSetting
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
from app.services.email_service import (
    SMTPConfigError,
    send_email,
    translate_smtp_config_error,
    translate_smtp_error,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def serialize_email_digest_setting(setting: EmailDigestSetting) -> EmailDigestSettingsRead:
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
def get_email_digest_settings(db: Session = Depends(get_db)) -> EmailDigestSettingsRead:
    return serialize_email_digest_setting(get_or_create_email_digest_setting(db))


@router.put("/email-digest", response_model=EmailDigestSettingsRead)
def put_email_digest_settings(
    payload: EmailDigestSettingsUpdate,
    db: Session = Depends(get_db),
) -> EmailDigestSettingsRead:
    return serialize_email_digest_setting(update_email_digest_setting(db, payload))


@router.post("/email-digest/test", response_model=EmailDigestTestResponse)
def send_test_email(db: Session = Depends(get_db)) -> EmailDigestTestResponse:
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
    except SMTPConfigError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate_smtp_config_error(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=translate_smtp_error(exc),
        ) from exc

    return EmailDigestTestResponse()
