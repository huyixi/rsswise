# AI Summary Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream automatic AI analysis progress to article detail pages, let opened pending articles jump ahead in the analysis queue, and remove user-facing manual reanalysis.

**Architecture:** Keep Celery as the only executor for AI analysis. Workers publish temporary stream events to Redis Streams while accumulating the final JSON response for existing Pydantic validation and database persistence. Article detail pages subscribe to a FastAPI SSE endpoint when analysis is pending or processing, while opening a pending article queues the task with higher Celery Redis priority.

**Tech Stack:** FastAPI, SQLAlchemy, Celery with Redis broker priority, Redis Streams, OpenAI-compatible DeepSeek client, React 18, TanStack Query, EventSource, Playwright.

**Source Spec:** `docs/superpowers/specs/2026-06-08-ai-summary-streaming-design.md`

---

## File Map

- Create: `apps/api/app/services/analysis_events.py`  
  Responsibility: Redis Stream key naming, event writing, event reading, and SSE event formatting.

- Create: `apps/api/tests/test_analysis_events.py`  
  Responsibility: unit test Redis event serialization, TTL handling, SSE formatting, and terminal event reading.

- Modify: `apps/api/app/services/ai_service.py`  
  Responsibility: share prompt construction between non-streaming and streaming AI analysis functions.

- Modify: `apps/api/tests/test_ai_service.py`  
  Responsibility: test OpenAI-compatible streaming chunk handling and existing JSON validation.

- Modify: `apps/api/app/tasks.py`  
  Responsibility: configure Celery Redis priority, queue automatic analysis with background priority, stream worker chunks to Redis, persist final validated AI results, and skip duplicate tasks.

- Create: `apps/api/tests/test_tasks.py`  
  Responsibility: test Celery priority configuration, background queue priority, streaming persistence, and duplicate-task skipping.

- Modify: `apps/api/app/routers/articles.py`  
  Responsibility: add the article analysis SSE endpoint, enqueue opened pending articles with high priority, and remove `/articles/{id}/reanalyze`.

- Modify: `apps/api/tests/test_articles_api.py`  
  Responsibility: test SSE authorization, pending-priority enqueue, processing subscription behavior, success terminal response, waiting-content response, and removed reanalysis route.

- Modify: `apps/web/src/lib/api.ts`  
  Responsibility: expose an API URL builder and an EventSource factory that keeps cookies enabled.

- Create: `apps/web/src/routes/articles/use-article-analysis-events.ts`  
  Responsibility: subscribe to article analysis SSE events and expose local streaming UI state.

- Modify: `apps/web/src/routes/articles/components.tsx`  
  Responsibility: render stream text and streaming/error states in the shared AI summary component.

- Modify: `apps/web/tests/e2e/articles.spec.ts`  
  Responsibility: add a processing article fixture and verify desktop/mobile streaming text display; assert manual reanalysis UI is absent.

---

### Task 1: Redis Analysis Event Service

**Files:**
- Create: `apps/api/tests/test_analysis_events.py`
- Create: `apps/api/app/services/analysis_events.py`

- [ ] **Step 1: Confirm the working tree before adding backend event tests**

Run:

```bash
git status --short
```

Expected: existing unrelated changes may be present. Do not stage or revert unrelated files.

- [ ] **Step 2: Add failing unit tests for analysis event serialization**

Create `apps/api/tests/test_analysis_events.py` with this complete file:

```python
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
```

- [ ] **Step 3: Run the new tests and verify they fail for the missing module**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_analysis_events.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.analysis_events'`.

- [ ] **Step 4: Implement the Redis event service**

Create `apps/api/app/services/analysis_events.py` with this complete file:

```python
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
```

- [ ] **Step 5: Run the event tests and verify they pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_analysis_events.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the event service**

Run:

```bash
git add apps/api/tests/test_analysis_events.py apps/api/app/services/analysis_events.py
git commit -m "feat(api): 添加 AI 分析流事件服务"
```

Expected: commit contains only the new event service and its tests.

---

### Task 2: OpenAI-Compatible Streaming AI Service

**Files:**
- Modify: `apps/api/tests/test_ai_service.py`
- Modify: `apps/api/app/services/ai_service.py`

- [ ] **Step 1: Add failing streaming tests**

Append this code to `apps/api/tests/test_ai_service.py`:

```python
from app.services.ai_service import stream_analyze_markdown_with_deepseek


class FakeDelta:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.delta = FakeDelta(content)


class FakeChunk:
    def __init__(self, content: str | None) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict | None = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return [
            FakeChunk('{"one_sentence_summary":"Short'),
            FakeChunk(None),
            FakeChunk(' summary.","reading_recommendation":"skim","reading_reason":"Useful."}'),
        ]


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self) -> None:
        self.chat = FakeChat()


def test_stream_analyze_markdown_yields_delta_content(monkeypatch: pytest.MonkeyPatch):
    fake_client = FakeClient()
    monkeypatch.setattr(
        "app.services.ai_service.OpenAI",
        lambda api_key, base_url: fake_client,
    )
    monkeypatch.setattr("app.services.ai_service.settings.deepseek_api_key", "key")

    chunks = list(stream_analyze_markdown_with_deepseek("# Title"))

    assert chunks == [
        '{"one_sentence_summary":"Short',
        ' summary.","reading_recommendation":"skim","reading_reason":"Useful."}',
    ]
    assert fake_client.chat.completions.kwargs is not None
    assert fake_client.chat.completions.kwargs["stream"] is True
    assert fake_client.chat.completions.kwargs["response_format"] == {
        "type": "json_object"
    }
```

- [ ] **Step 2: Run the AI service tests and verify the missing function failure**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_service.py -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `stream_analyze_markdown_with_deepseek`.

- [ ] **Step 3: Refactor prompt construction and add streaming function**

Replace the contents of `apps/api/app/services/ai_service.py` with this complete file:

```python
from collections.abc import Iterator
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

RecommendationValue = Literal["deep_read", "skim", "skip"]


class AIAnalysisResult(BaseModel):
    one_sentence_summary: str = Field(min_length=1, max_length=160)
    reading_recommendation: RecommendationValue
    reading_reason: str = Field(min_length=1, max_length=500)


def parse_ai_result(content: str) -> AIAnalysisResult:
    try:
        return AIAnalysisResult.model_validate_json(content)
    except ValidationError as exc:
        raise ValueError("invalid ai analysis json") from exc


def build_ai_messages(markdown: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是 RSS 阅读前分析助手。只返回 JSON。"
                "字段必须是 one_sentence_summary, reading_recommendation, reading_reason。"
                "reading_recommendation 只能是 deep_read, skim, skip。"
                "不要输出长摘要、分数、target readers 或 keywords。"
            ),
        },
        {"role": "user", "content": markdown[:40000]},
    ]


def create_deepseek_client() -> OpenAI:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required")
    return OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def analyze_markdown_with_deepseek(markdown: str) -> AIAnalysisResult:
    client = create_deepseek_client()
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        response_format={"type": "json_object"},
        messages=build_ai_messages(markdown),
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty ai response")
    return parse_ai_result(content)


def stream_analyze_markdown_with_deepseek(markdown: str) -> Iterator[str]:
    client = create_deepseek_client()
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        response_format={"type": "json_object"},
        messages=build_ai_messages(markdown),
        stream=True,
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content
```

- [ ] **Step 4: Run the AI service tests and verify they pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the streaming AI service**

Run:

```bash
git add apps/api/tests/test_ai_service.py apps/api/app/services/ai_service.py
git commit -m "feat(api): 支持 AI 分析流式响应"
```

Expected: commit contains only AI service tests and implementation.

---

### Task 3: Worker Priority And Streaming Persistence

**Files:**
- Create: `apps/api/tests/test_tasks.py`
- Modify: `apps/api/app/tasks.py`

- [ ] **Step 1: Add failing worker tests**

Create `apps/api/tests/test_tasks.py` with this complete file:

```python
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    AnalysisStatus,
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    Base,
    ExtractionStatus,
    Feed,
    ReadingRecommendation,
)
from app.tasks import (
    AI_PRIORITY_BACKGROUND,
    AI_PRIORITY_USER_OPENED,
    analyze_article_task,
    celery_app,
    extract_article_task,
)


@pytest.fixture
def session_local(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.tasks.SessionLocal", testing_session_local)
    yield testing_session_local
    Base.metadata.drop_all(bind=engine)


def seed_article(
    db: Session,
    *,
    analysis_status: AnalysisStatus = AnalysisStatus.pending,
    extraction_status: ExtractionStatus = ExtractionStatus.success,
) -> UUID:
    feed = Feed(
        title="Example Feed",
        url=f"https://example.com/{analysis_status.value}.xml",
        site_url="https://example.com",
    )
    article = Article(
        feed=feed,
        title="Readable Post",
        url=f"https://example.com/{analysis_status.value}",
        author="Ada",
        published_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        summary_from_feed="Feed summary",
        guid=f"post-{analysis_status.value}",
    )
    db.add(article)
    db.flush()
    db.add(
        ArticleContent(
            article_id=article.id,
            content_markdown="# Readable Post\n\nBody text."
            if extraction_status == ExtractionStatus.success
            else None,
            extraction_status=extraction_status,
        )
    )
    db.add(
        ArticleAIAnalysis(
            article_id=article.id,
            one_sentence_summary="Existing summary"
            if analysis_status == AnalysisStatus.success
            else None,
            reading_recommendation=ReadingRecommendation.deep_read
            if analysis_status == AnalysisStatus.success
            else None,
            reading_reason="Existing reason"
            if analysis_status == AnalysisStatus.success
            else None,
            analysis_status=analysis_status,
        )
    )
    db.commit()
    return article.id


def test_celery_redis_priority_is_configured():
    assert AI_PRIORITY_USER_OPENED == 0
    assert AI_PRIORITY_BACKGROUND == 5
    assert celery_app.conf.task_queue_max_priority == 10
    assert celery_app.conf.broker_transport_options["queue_order_strategy"] == "priority"


def test_extract_article_queues_background_ai_priority(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(
            db,
            analysis_status=AnalysisStatus.pending,
            extraction_status=ExtractionStatus.pending,
        )

    queued: list[tuple[list[str], int]] = []
    monkeypatch.setattr(
        "app.tasks.fetch_and_extract_markdown",
        lambda url: "# Extracted\n\nBody.",
    )
    monkeypatch.setattr(
        "app.tasks.analyze_article_task.apply_async",
        lambda args, priority: queued.append((args, priority)),
    )

    extract_article_task(str(article_id))

    assert queued == [([str(article_id)], AI_PRIORITY_BACKGROUND)]


def test_analyze_article_streams_chunks_and_persists_final_result(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db)

    writes: list[tuple[str, str, dict | None]] = []
    redis_client = object()
    monkeypatch.setattr("app.tasks.get_redis_client", lambda: redis_client)
    monkeypatch.setattr(
        "app.tasks.reset_analysis_events",
        lambda client, article_id: writes.append(("reset", str(article_id), None)),
    )
    monkeypatch.setattr(
        "app.tasks.write_analysis_event",
        lambda client, article_id, event_type, payload: writes.append(
            (event_type, str(article_id), payload)
        ),
    )
    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: iter(
            [
                '{"one_sentence_summary":"Short summary.",',
                '"reading_recommendation":"skim",',
                '"reading_reason":"Useful context."}',
            ]
        ),
    )

    analyze_article_task(str(article_id))

    assert writes == [
        ("reset", str(article_id), None),
        ("started", str(article_id), {"article_id": str(article_id)}),
        (
            "chunk",
            str(article_id),
            {"text": '{"one_sentence_summary":"Short summary.",'},
        ),
        (
            "chunk",
            str(article_id),
            {"text": '"reading_recommendation":"skim",'},
        ),
        (
            "chunk",
            str(article_id),
            {"text": '"reading_reason":"Useful context."}'},
        ),
        ("done", str(article_id), {"article_id": str(article_id)}),
    ]

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.success
        assert analysis.one_sentence_summary == "Short summary."
        assert analysis.reading_recommendation == ReadingRecommendation.skim
        assert analysis.reading_reason == "Useful context."


def test_analyze_article_skips_already_processing_article(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db, analysis_status=AnalysisStatus.processing)

    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: pytest.fail("processing article should not stream again"),
    )

    analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.processing


def test_analyze_article_persists_result_when_redis_events_fail(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db)

    monkeypatch.setattr("app.tasks.get_redis_client", lambda: object())
    monkeypatch.setattr(
        "app.tasks.reset_analysis_events",
        lambda client, article_id: (_ for _ in ()).throw(
            RedisError("redis unavailable")
        ),
    )
    monkeypatch.setattr(
        "app.tasks.write_analysis_event",
        lambda client, article_id, event_type, payload: (_ for _ in ()).throw(
            RedisError("redis unavailable")
        ),
    )
    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: iter(
            [
                '{"one_sentence_summary":"Short summary.",',
                '"reading_recommendation":"skim",',
                '"reading_reason":"Useful context."}',
            ]
        ),
    )

    analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.success
        assert analysis.one_sentence_summary == "Short summary."
```

- [ ] **Step 2: Run the worker tests and verify the missing constants/import failures**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_tasks.py -q
```

Expected: FAIL because `AI_PRIORITY_BACKGROUND` and `AI_PRIORITY_USER_OPENED` are not defined.

- [ ] **Step 3: Update Celery configuration and worker task logic**

In `apps/api/app/tasks.py`, make these edits:

1. Add these imports:

```python
from redis.exceptions import RedisError
```

2. Replace the AI service import with:

```python
from app.services.ai_service import parse_ai_result, stream_analyze_markdown_with_deepseek
from app.services.analysis_events import (
    get_redis_client,
    reset_analysis_events,
    write_analysis_event,
)
```

3. Add these constants and Celery config immediately after `celery_app.conf.beat_schedule = beat_schedule`:

```python
AI_PRIORITY_USER_OPENED = 0
AI_PRIORITY_BACKGROUND = 5

celery_app.conf.task_queue_max_priority = 10
celery_app.conf.broker_transport_options = {
    "queue_order_strategy": "priority",
}
```

4. Add this helper below the config:

```python
def reset_analysis_event_stream(redis_client, article_id: str) -> None:
    try:
        reset_analysis_events(redis_client, article_id)
    except RedisError:
        return


def publish_analysis_event(redis_client, article_id: str, event_type: str, payload: dict) -> None:
    try:
        write_analysis_event(redis_client, article_id, event_type, payload)
    except RedisError:
        return
```

5. In `extract_article_task`, replace:

```python
analyze_article_task.delay(article_id)
```

with:

```python
analyze_article_task.apply_async(
    args=[article_id],
    priority=AI_PRIORITY_BACKGROUND,
)
```

6. Replace `analyze_article_task` with this complete function body:

```python
@celery_app.task(name="articles.analyze")
def analyze_article_task(article_id: str) -> None:
    redis_client = get_redis_client()

    with SessionLocal() as db:
        analysis = db.get(ArticleAIAnalysis, UUID(article_id))
        content = db.get(ArticleContent, UUID(article_id))
        if analysis is None or content is None or not content.content_markdown:
            raise ValueError("article requires markdown before analysis")

        if analysis.analysis_status in {
            AnalysisStatus.processing,
            AnalysisStatus.success,
        }:
            return

        analysis.analysis_status = AnalysisStatus.processing
        analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        reset_analysis_event_stream(redis_client, article_id)
        publish_analysis_event(
            redis_client,
            article_id,
            "started",
            {"article_id": article_id},
        )

        raw_chunks: list[str] = []
        try:
            for chunk in stream_analyze_markdown_with_deepseek(content.content_markdown):
                raw_chunks.append(chunk)
                publish_analysis_event(
                    redis_client,
                    article_id,
                    "chunk",
                    {"text": chunk},
                )

            result = parse_ai_result("".join(raw_chunks))
            analysis.one_sentence_summary = result.one_sentence_summary
            analysis.reading_recommendation = ReadingRecommendation(result.reading_recommendation)
            analysis.reading_reason = result.reading_reason
            analysis.analysis_status = AnalysisStatus.success
            analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            publish_analysis_event(
                redis_client,
                article_id,
                "done",
                {"article_id": article_id},
            )
        except Exception:
            analysis.analysis_status = AnalysisStatus.failed
            analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            publish_analysis_event(
                redis_client,
                article_id,
                "error",
                {"message": "AI 分析失败"},
            )
            raise
```

- [ ] **Step 4: Run worker and AI tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_tasks.py tests/test_ai_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit worker streaming and priority changes**

Run:

```bash
git add apps/api/tests/test_tasks.py apps/api/app/tasks.py
git commit -m "feat(worker): 流式发布 AI 分析进度"
```

Expected: commit contains only worker tests and worker implementation changes.

---

### Task 4: Article Analysis SSE Endpoint And Removed Reanalysis API

**Files:**
- Modify: `apps/api/tests/test_articles_api.py`
- Modify: `apps/api/app/routers/articles.py`

- [ ] **Step 1: Update article API tests for removed reanalysis and SSE**

In `apps/api/tests/test_articles_api.py`, replace `test_detail_read_state_and_reanalysis_use_existing_markdown` with this test:

```python
def test_detail_read_state_and_reanalysis_route_is_removed(client: TestClient):
    user = register(client)
    article_id = seed_article(client, user_id=user["id"], is_read=False)

    detail_response = client.get(f"/articles/{article_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["content_markdown"] == "# Readable Post\n\nBody text."
    assert detail["extraction_status"] == "success"
    assert detail["analysis_status"] == "success"
    assert detail["reading_reason"] == "The article has durable insight."

    read_response = client.post(f"/articles/{article_id}/read")
    assert read_response.status_code == 204
    assert client.get("/articles?status_filter=read").json()[0]["id"] == str(article_id)

    unread_response = client.post(f"/articles/{article_id}/unread")
    assert unread_response.status_code == 204
    assert client.get("/articles?status_filter=unread").json()[0]["id"] == str(article_id)

    assert client.post(f"/articles/{article_id}/reanalyze").status_code == 404
```

Then add this helper below `seed_article`:

```python
def seed_pending_article(client: TestClient, *, user_id: str) -> UUID:
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        feed = Feed(
            title="Pending Feed",
            url="https://example.com/pending-feed.xml",
            site_url="https://example.com",
        )
        article = Article(
            feed=feed,
            title="Pending Post",
            url="https://example.com/pending-post",
            author="Ada",
            published_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            summary_from_feed="Feed summary",
            guid="pending-post-1",
        )
        db.add(article)
        db.flush()
        db.add(UserFeedSubscription(user_id=UUID(user_id), feed_id=feed.id))
        db.add(
            ArticleContent(
                article_id=article.id,
                content_markdown="# Pending Post\n\nBody text.",
                extraction_status=ExtractionStatus.success,
            )
        )
        db.add(
            ArticleAIAnalysis(
                article_id=article.id,
                analysis_status=AnalysisStatus.pending,
            )
        )
        db.commit()
        return article.id
```

Append these SSE tests:

```python
def test_analysis_events_pending_article_enqueues_priority_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    user = register(client)
    article_id = seed_pending_article(client, user_id=user["id"])
    queued: list[tuple[list[str], int]] = []
    redis_client = object()

    monkeypatch.setattr("app.routers.articles.get_redis_client", lambda: redis_client)
    monkeypatch.setattr(
        "app.routers.articles.analyze_article_task.apply_async",
        lambda args, priority: queued.append((args, priority)),
    )
    monkeypatch.setattr(
        "app.routers.articles.read_analysis_events",
        lambda client, article_id, last_event_id=None: iter(
            [
                ("1-0", "started", {"article_id": str(article_id)}),
                ("2-0", "done", {"article_id": str(article_id)}),
            ]
        ),
    )

    response = client.get(f"/articles/{article_id}/analysis/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: started" in response.text
    assert "event: done" in response.text
    assert queued == [([str(article_id)], 0)]


def test_analysis_events_success_article_returns_done_without_queue(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    user = register(client)
    article_id = seed_article(client, user_id=user["id"])

    monkeypatch.setattr(
        "app.routers.articles.analyze_article_task.apply_async",
        lambda args, priority: pytest.fail("success article should not be queued"),
    )

    response = client.get(f"/articles/{article_id}/analysis/events")

    assert response.status_code == 200
    assert "event: done" in response.text
    assert str(article_id) in response.text


def test_analysis_events_require_subscription(client: TestClient):
    first_user = register(client, "first@example.com")
    article_id = seed_article(client, user_id=first_user["id"])

    second_client = TestClient(app)
    register(second_client, "second@example.com")

    assert second_client.get(f"/articles/{article_id}/analysis/events").status_code == 404
```

- [ ] **Step 2: Run article API tests and verify SSE route failures**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py -q
```

Expected: FAIL because `/articles/{article_id}/analysis/events` does not exist and `/reanalyze` still returns 202.

- [ ] **Step 3: Implement the SSE endpoint and remove reanalysis**

In `apps/api/app/routers/articles.py`, make these edits:

1. Replace the FastAPI import with:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
```

2. Add model imports:

```python
from app.models import (
    AnalysisStatus,
    Article,
    ExtractionStatus,
    User,
    UserArticleState,
    UserFeedSubscription,
)
```

3. Add service/task imports:

```python
from app.services.analysis_events import (
    format_sse_event,
    get_redis_client,
    read_analysis_events,
)
from app.tasks import AI_PRIORITY_USER_OPENED, analyze_article_task
```

4. Add this helper above the route functions:

```python
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def single_sse_response(event_type: str, payload: dict, event_id: str = "0-0"):
    return StreamingResponse(
        iter([format_sse_event(event_id, event_type, payload)]),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
```

5. Add this route before `mark_read`:

```python
@router.get("/{article_id}/analysis/events")
def stream_analysis_events(
    article_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = get_subscribed_article_or_404(article_id, current_user, db)
    analysis = article.ai_analysis

    if article.content is None or article.content.extraction_status != ExtractionStatus.success:
        return single_sse_response(
            "waiting_content",
            {"article_id": str(article_id)},
        )

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="article analysis not found",
        )

    if analysis.analysis_status == AnalysisStatus.success:
        return single_sse_response("done", {"article_id": str(article_id)})

    if analysis.analysis_status == AnalysisStatus.failed:
        return single_sse_response("error", {"message": "AI 分析失败"})

    if analysis.analysis_status == AnalysisStatus.pending:
        analyze_article_task.apply_async(
            args=[str(article_id)],
            priority=AI_PRIORITY_USER_OPENED,
        )

    redis_client = get_redis_client()
    last_event_id = request.headers.get("last-event-id")

    def body():
        for event_id, event_type, payload in read_analysis_events(
            redis_client,
            article_id,
            last_event_id=last_event_id,
        ):
            yield format_sse_event(event_id, event_type, payload)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
```

6. Delete the complete `reanalyze` route:

```python
@router.post("/{article_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    analyze_article_task.delay(str(article_id))
    return {"status": "queued"}
```

- [ ] **Step 4: Run article API tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all backend tests touched so far**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_analysis_events.py tests/test_ai_service.py tests/test_tasks.py tests/test_articles_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit API streaming endpoint changes**

Run:

```bash
git add apps/api/tests/test_articles_api.py apps/api/app/routers/articles.py
git commit -m "feat(api): 添加文章 AI 分析事件流接口"
```

Expected: commit contains only article API tests and router changes.

---

### Task 5: Frontend EventSource Hook

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/routes/articles/use-article-analysis-events.ts`

- [ ] **Step 1: Expose API URL and EventSource helpers**

In `apps/web/src/lib/api.ts`, replace the top `API_BASE_URL` declaration with:

```ts
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || "/api"
).replace(/\/+$/, "");

export function buildApiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}
```

Then add this function after `apiDelete`:

```ts
export function openApiEventSource(path: string) {
  return new EventSource(buildApiUrl(path), { withCredentials: true });
}
```

Update each existing fetch call in the same file to use `buildApiUrl(path)` instead of duplicating `` `${API_BASE_URL}${path}` ``.

- [ ] **Step 2: Create the article analysis events hook**

Create `apps/web/src/routes/articles/use-article-analysis-events.ts` with this complete file:

```ts
import { useEffect, useState } from "react"

import { openApiEventSource, type ArticleDetail } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

type AnalysisStreamState = {
  streamText: string
  isStreaming: boolean
  streamError: string | null
}

function parseEventData<T>(event: MessageEvent<string>): T | null {
  try {
    return JSON.parse(event.data) as T
  } catch {
    return null
  }
}

export function useArticleAnalysisEvents(article: ArticleDetail | undefined) {
  const [state, setState] = useState<AnalysisStreamState>({
    streamText: "",
    isStreaming: false,
    streamError: null,
  })

  useEffect(() => {
    if (!article) {
      setState({ streamText: "", isStreaming: false, streamError: null })
      return
    }

    if (
      article.analysis_status !== "pending" &&
      article.analysis_status !== "processing"
    ) {
      setState({ streamText: "", isStreaming: false, streamError: null })
      return
    }

    let hasReceivedChunk = false
    const source = openApiEventSource(
      `/articles/${encodeURIComponent(article.id)}/analysis/events`,
    )

    setState({ streamText: "", isStreaming: true, streamError: null })

    source.addEventListener("started", () => {
      setState((current) => ({
        ...current,
        isStreaming: true,
        streamError: null,
      }))
    })

    source.addEventListener("chunk", (event) => {
      const data = parseEventData<{ text?: string }>(
        event as MessageEvent<string>,
      )
      if (!data?.text) return
      hasReceivedChunk = true
      setState((current) => ({
        streamText: `${current.streamText}${data.text}`,
        isStreaming: true,
        streamError: null,
      }))
    })

    source.addEventListener("done", () => {
      source.close()
      setState((current) => ({
        ...current,
        isStreaming: false,
        streamError: null,
      }))
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.detail(article.id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.all,
      })
    })

    source.addEventListener("waiting_content", () => {
      source.close()
      setState({ streamText: "", isStreaming: false, streamError: null })
    })

    source.addEventListener("error", (event) => {
      if ("data" in event && typeof event.data === "string") {
        const data = parseEventData<{ message?: string }>(
          event as MessageEvent<string>,
        )
        source.close()
        setState({
          streamText: "",
          isStreaming: false,
          streamError: data?.message ?? "AI 分析失败",
        })
        queryClient.invalidateQueries({
          queryKey: queryKeys.articles.detail(article.id),
        })
        return
      }

      if (!hasReceivedChunk) {
        setState((current) => ({
          ...current,
          isStreaming: false,
          streamError: "AI 分析连接中断",
        }))
      }
    })

    return () => {
      source.close()
    }
  }, [article?.analysis_status, article?.id])

  return state
}
```

- [ ] **Step 3: Build the frontend to catch TypeScript mistakes**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS. If TypeScript reports that `EventSourceInit.withCredentials` is missing in the active DOM lib, replace the EventSource call with:

```ts
return new EventSource(buildApiUrl(path));
```

and rerun the build.

- [ ] **Step 4: Commit the frontend EventSource hook**

Run:

```bash
git add apps/web/src/lib/api.ts apps/web/src/routes/articles/use-article-analysis-events.ts
git commit -m "feat(web): 添加文章 AI 分析事件订阅"
```

Expected: commit contains only API helper and hook changes.

---

### Task 6: Streaming UI And E2E Coverage

**Files:**
- Modify: `apps/web/src/routes/articles/components.tsx`
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Wire streaming state into the shared AI summary component**

In `apps/web/src/routes/articles/components.tsx`, add this import:

```ts
import { useArticleAnalysisEvents } from "./use-article-analysis-events"
```

Then inside `ArticleAiSummary`, immediately after the function starts, add:

```ts
  const { streamText, isStreaming, streamError } = useArticleAnalysisEvents(article)
```

Replace the `hasAiContent` declaration with:

```ts
  const hasAiContent =
    article.reading_recommendation ||
    article.one_sentence_summary ||
    article.reading_reason ||
    streamText ||
    streamError
```

Inside the existing content block, after the `reading_reason` paragraph block, add:

```tsx
          {!article.one_sentence_summary && streamText ? (
            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
              {streamText}
            </p>
          ) : null}

          {streamError ? (
            <p className="text-sm leading-6 text-destructive-foreground">
              {streamError}
            </p>
          ) : null}
```

Replace the empty-state paragraph:

```tsx
        <p className="text-sm text-muted-foreground">AI 总结处理中</p>
```

with:

```tsx
        <p className="text-sm text-muted-foreground">
          {isStreaming ? "AI 总结生成中" : "AI 总结处理中"}
        </p>
```

- [ ] **Step 2: Add an E2E streaming fixture**

In `apps/web/tests/e2e/articles.spec.ts`, add this constant after `secondArticleId`:

```ts
const streamingArticleId = "33333333-3333-3333-3333-333333333333"
```

Append this object to `articleList`:

```ts
  {
    id: streamingArticleId,
    title: "流式 AI 摘要测试",
    source_title: "RSSWise 测试源",
    published_at: "2026-06-06T08:00:00Z",
    one_sentence_summary: null,
    reading_recommendation: null,
    is_read: false,
  },
```

Add this detail fixture after `secondArticleDetail`:

```ts
const streamingArticleDetail = {
  id: streamingArticleId,
  title: "流式 AI 摘要测试",
  source_title: "RSSWise 测试源",
  published_at: "2026-06-06T08:00:00Z",
  url: "https://example.com/streaming-ai-article",
  one_sentence_summary: null,
  reading_recommendation: null,
  reading_reason: null,
  content_markdown: "## 流式正文\n\n这是流式测试正文。",
  extraction_status: "success",
  analysis_status: "processing",
}
```

Update the `articleDetails` type and object to include the streaming fixture:

```ts
const articleDetails: Record<
  string,
  typeof articleDetail | typeof secondArticleDetail | typeof streamingArticleDetail
> = {
  [firstArticleId]: articleDetail,
  [secondArticleId]: secondArticleDetail,
  [streamingArticleId]: streamingArticleDetail,
}
```

Add this helper after `mockReadRoute`:

```ts
async function mockAnalysisStreamRoute(page: Page) {
  await page.route(
    `**/api/articles/${streamingArticleId}/analysis/events`,
    async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
        },
        body:
          `id: 1-0\n` +
          `event: started\n` +
          `data: {"article_id":"${streamingArticleId}"}\n\n` +
          `id: 2-0\n` +
          `event: chunk\n` +
          `data: {"text":"流式摘要正在生成"}\n\n`,
      })
    },
  )
}
```

- [ ] **Step 3: Add desktop and mobile streaming tests**

Append these tests near the other article detail tests:

```ts
test("desktop workbench shows streaming AI summary text", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)
  await mockAnalysisStreamRoute(page)

  await page.goto(`/articles?id=${streamingArticleId}`)

  await expect(page.getByRole("heading", { name: "流式 AI 摘要测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "AI 总结" })).toBeVisible()
  await expect(page.getByText("流式摘要正在生成")).toBeVisible()
  await expect(page.getByText("重新 AI 分析")).toHaveCount(0)
})

test("mobile detail shows streaming AI summary text", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)
  await mockAnalysisStreamRoute(page)

  await page.goto(`/articles/${streamingArticleId}`)

  await expect(page.getByRole("heading", { name: "流式 AI 摘要测试" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "AI 总结" })).toBeVisible()
  await expect(page.getByText("流式摘要正在生成")).toBeVisible()
  await expect(page.getByText("重新 AI 分析")).toHaveCount(0)
})
```

- [ ] **Step 4: Run the focused E2E tests**

Run:

```bash
pnpm --dir apps/web test:e2e --grep "streaming AI summary text"
```

Expected: PASS.

- [ ] **Step 5: Run lint and build**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both commands PASS.

- [ ] **Step 6: Commit streaming UI changes**

Run:

```bash
git add apps/web/src/routes/articles/components.tsx apps/web/tests/e2e/articles.spec.ts
git commit -m "feat(web): 展示 AI 摘要流式生成"
```

Expected: commit contains only shared article component and E2E fixture/test changes.

---

### Task 7: Final Integration Verification

**Files:**
- Verify only; no planned file edits.

- [ ] **Step 1: Search for removed manual reanalysis references**

Run:

```bash
rg -n "reanalyze|重新 AI 分析" apps/api apps/web
```

Expected: no matches.

- [ ] **Step 2: Run the backend test suite**

Run:

```bash
make test
```

Expected: PASS.

- [ ] **Step 3: Run frontend lint and production build**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both commands PASS.

- [ ] **Step 4: Run article E2E tests**

Run:

```bash
pnpm --dir apps/web test:e2e --grep "article|AI summary"
```

Expected: PASS.

- [ ] **Step 5: Inspect final diff before merge or PR**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: working tree is clean except user-owned unrelated changes that were present before execution. Recent commits should match the task commits in this plan.
