from collections.abc import Iterator
import json
from typing import Any
from uuid import UUID

from redis import Redis

from app.core.config import settings

ANALYSIS_EVENT_TTL_SECONDS = 30 * 60
ANALYSIS_STREAM_BLOCK_MS = 5_000
TERMINAL_ANALYSIS_EVENT_TYPES = {"done", "error", "waiting_content"}


def analysis_events_key(article_id: UUID | str) -> str:
    return f"article-analysis:{article_id}:events"


def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def reset_analysis_events(redis_client: Redis, article_id: UUID | str) -> None:
    redis_client.delete(analysis_events_key(article_id))


def write_analysis_event(
    redis_client: Redis,
    article_id: UUID | str,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    key = analysis_events_key(article_id)
    event_id = redis_client.xadd(
        key,
        {
            "type": event_type,
            "data": json.dumps(payload, ensure_ascii=False),
        },
    )
    redis_client.expire(key, ANALYSIS_EVENT_TTL_SECONDS)
    return str(event_id)


def format_sse_event(event_id: str, event_type: str, payload: dict[str, Any]) -> str:
    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def read_analysis_events(
    redis_client: Redis,
    article_id: UUID | str,
    *,
    last_event_id: str | None = None,
    block_ms: int = ANALYSIS_STREAM_BLOCK_MS,
    keepalive: bool = True,
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    key = analysis_events_key(article_id)
    current_event_id = last_event_id or "0-0"

    while True:
        rows = redis_client.xread({key: current_event_id}, block=block_ms, count=20)
        if not rows:
            if keepalive:
                yield ("", "ping", {})
                continue
            return

        for _stream_key, messages in rows:
            for event_id, fields in messages:
                event_type = str(fields.get("type", "chunk"))
                raw_data = fields.get("data") or "{}"
                payload = json.loads(raw_data)
                current_event_id = str(event_id)
                yield (current_event_id, event_type, payload)
                if event_type in TERMINAL_ANALYSIS_EVENT_TYPES:
                    return
