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
