from uuid import UUID

from app.services.analysis_events import (
    ANALYSIS_EVENT_TTL_SECONDS,
    analysis_events_key,
    format_sse_event,
    read_analysis_events,
    reset_analysis_events,
    write_analysis_event,
)


class FakeRedis:
    def __init__(self) -> None:
        self.messages: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.expirations: dict[str, int] = {}
        self.deleted: list[str] = []

    def xadd(self, key: str, fields: dict[str, str]) -> str:
        event_id = f"{len(self.messages.get(key, [])) + 1}-0"
        self.messages.setdefault(key, []).append((event_id, fields))
        return event_id

    def expire(self, key: str, ttl_seconds: int) -> bool:
        self.expirations[key] = ttl_seconds
        return True

    def delete(self, key: str) -> int:
        self.deleted.append(key)
        self.messages.pop(key, None)
        return 1

    def xread(
        self,
        streams: dict[str, str],
        block: int,
        count: int,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        key, last_event_id = next(iter(streams.items()))
        rows = self.messages.get(key, [])
        unread = [row for row in rows if row[0] > last_event_id]
        if not unread:
            return []
        return [(key, unread[:count])]


def test_analysis_events_key_is_article_scoped():
    article_id = UUID("11111111-1111-1111-1111-111111111111")

    assert analysis_events_key(article_id) == (
        "article-analysis:11111111-1111-1111-1111-111111111111:events"
    )


def test_write_analysis_event_stores_json_and_refreshes_ttl():
    redis_client = FakeRedis()
    article_id = UUID("11111111-1111-1111-1111-111111111111")

    event_id = write_analysis_event(
        redis_client,
        article_id,
        "chunk",
        {"text": "流式摘要"},
    )

    key = analysis_events_key(article_id)
    assert event_id == "1-0"
    assert redis_client.messages[key] == [
        ("1-0", {"type": "chunk", "data": '{"text": "流式摘要"}'})
    ]
    assert redis_client.expirations[key] == ANALYSIS_EVENT_TTL_SECONDS


def test_reset_analysis_events_deletes_article_stream():
    redis_client = FakeRedis()
    article_id = UUID("11111111-1111-1111-1111-111111111111")

    reset_analysis_events(redis_client, article_id)

    assert redis_client.deleted == [analysis_events_key(article_id)]


def test_format_sse_event_outputs_id_event_and_json_data():
    payload = {"text": "流式摘要"}

    assert format_sse_event("2-0", "chunk", payload) == (
        'id: 2-0\n'
        'event: chunk\n'
        'data: {"text": "流式摘要"}\n\n'
    )


def test_read_analysis_events_yields_until_terminal_event():
    redis_client = FakeRedis()
    article_id = UUID("11111111-1111-1111-1111-111111111111")
    write_analysis_event(redis_client, article_id, "started", {"article_id": str(article_id)})
    write_analysis_event(redis_client, article_id, "chunk", {"text": "A"})
    write_analysis_event(redis_client, article_id, "done", {"article_id": str(article_id)})

    events = list(
        read_analysis_events(
            redis_client,
            article_id,
            last_event_id="0-0",
            block_ms=1,
            keepalive=False,
        )
    )

    assert events == [
        ("1-0", "started", {"article_id": str(article_id)}),
        ("2-0", "chunk", {"text": "A"}),
        ("3-0", "done", {"article_id": str(article_id)}),
    ]
