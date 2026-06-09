# Article Reading Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store AI detail content as ordered `AiBlock[]`, stream readable Markdown during analysis, and render a reading guide with question, quote highlights, summary, reason, and optional chapters.

**Architecture:** Keep the existing Celery + Redis Stream + SSE analysis flow. Change the model output from JSON chunks to Markdown chunks, parse the completed Markdown into `ai_blocks` plus independent `reading_recommendation`, and derive legacy summary fields for list, detail compatibility, and EPUB. Add `ai_blocks` without removing legacy columns in the first migration so old articles keep rendering while new successful analyses stop treating legacy columns as canonical.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic v2, Celery, Redis Streams, OpenAI-compatible DeepSeek streaming, React 18, TanStack Query, React Markdown, Playwright.

**Source Spec:** `docs/article-reading-guide/spec.md`

---

## File Map

- Create: `apps/api/app/services/ai_blocks.py`
  Responsibility: define backend `AiBlock` shapes, parse completed AI Markdown, enforce highlight and chapter validation, and derive summary/reason values from blocks.

- Create: `apps/api/tests/test_ai_blocks.py`
  Responsibility: unit test Markdown parsing, required sections, recommendation validation, highlight counts, quote verification default, chapter thresholds, and summary derivation.

- Modify: `apps/api/app/services/ai_service.py`
  Responsibility: change prompt and streaming call from JSON response format to fixed-section Markdown response.

- Modify: `apps/api/tests/test_ai_service.py`
  Responsibility: verify streaming no longer requests JSON response format and prompt requests Markdown sections.

- Modify: `apps/api/app/models.py`
  Responsibility: add `ArticleAIAnalysis.ai_blocks` JSON column while keeping legacy columns for migration-period fallback.

- Create: `apps/api/alembic/versions/0003_article_ai_blocks.py`
  Responsibility: add nullable `ai_blocks` JSON column to `article_ai_analyses`.

- Modify: `apps/api/app/schemas.py`
  Responsibility: add Pydantic API schemas for `AiBlock` variants and expose `ai_blocks` on article detail.

- Modify: `apps/api/app/routers/articles.py`
  Responsibility: serialize list/detail summaries from `ai_blocks` when available, falling back to legacy columns for old rows.

- Modify: `apps/api/tests/test_articles_api.py`
  Responsibility: verify list summary derivation, detail `ai_blocks` response, and old-row fallback.

- Modify: `apps/api/app/tasks.py`
  Responsibility: accumulate Markdown chunks, parse to `ai_blocks`, persist `reading_recommendation`, stop writing new canonical summary/reason legacy values, and fail analysis on parser errors.

- Modify: `apps/api/tests/test_tasks.py`
  Responsibility: verify worker stream persistence to `ai_blocks`, parser failure handling, and Redis event text remains Markdown.

- Modify: `apps/api/app/services/epub_service.py`
  Responsibility: derive EPUB summary and reason from `ai_blocks` when available, with old-column fallback.

- Modify: `apps/api/tests/test_epub_service.py`
  Responsibility: verify EPUB includes summary/reason derived from blocks.

- Modify: `apps/web/src/lib/api.ts`
  Responsibility: add frontend `AiBlock` types and include `ai_blocks` in `ArticleDetail`.

- Modify: `apps/web/src/routes/articles/components.tsx`
  Responsibility: render structured blocks in order, render streaming Markdown, hide empty chapters and missing old fields.

- Modify: `apps/web/tests/e2e/articles.spec.ts`
  Responsibility: update fixtures and verify final block order, hidden empty chapters, old article fallback, and streaming Markdown.

---

### Task 1: Backend AiBlock Parser

**Files:**
- Create: `apps/api/tests/test_ai_blocks.py`
- Create: `apps/api/app/services/ai_blocks.py`

- [ ] **Step 1: Add parser tests for valid Markdown, derivation, and chapters**

Create `apps/api/tests/test_ai_blocks.py` with tests covering these exact cases:

```python
import pytest

from app.services.ai_blocks import (
    AiBlockParseError,
    derive_reading_reason,
    derive_summary,
    parse_ai_markdown,
)


LONG_MARKDOWN = "\n\n".join(
    [
        "第一段介绍背景和冲突。" * 20,
        "第二段解释关键变化。" * 20,
        "第三段说明影响范围。" * 20,
        "第四段分析读者需要注意的地方。" * 20,
        "第五段补充行业背景。" * 20,
        "第六段给出案例。" * 20,
        "第七段讨论限制。" * 20,
        "第八段收束全文。" * 20,
    ]
)


VALID_RESPONSE = """## 带读问题
这篇文章要回答 AI 产品如何在成本和体验之间取舍？

## Highlights
- 原文中的第一句亮点。
- 原文中的第二句亮点。
- 原文中的第三句亮点。

## 一句话摘要
文章解释了 AI 产品在体验、成本和可靠性之间的权衡。

## 阅读建议
deep_read

## 阅读理由
它能帮助读者判断类似产品决策背后的真实约束。

## 章节
- 背景变化
- 产品取舍
- 未来影响
"""


def test_parse_ai_markdown_builds_ordered_blocks():
    result = parse_ai_markdown(VALID_RESPONSE, source_markdown=LONG_MARKDOWN)

    assert result.reading_recommendation == "deep_read"
    assert [block["type"] for block in result.ai_blocks] == [
        "reading_question",
        "highlights",
        "summary",
        "reading_reason",
        "chapters",
    ]
    assert result.ai_blocks[0] == {
        "type": "reading_question",
        "title": "带读问题",
        "content": "这篇文章要回答 AI 产品如何在成本和体验之间取舍？",
        "order": 10,
    }
    assert result.ai_blocks[1]["content"] == [
        {"text": "原文中的第一句亮点。", "quote_verified": False},
        {"text": "原文中的第二句亮点。", "quote_verified": False},
        {"text": "原文中的第三句亮点。", "quote_verified": False},
    ]
    assert result.ai_blocks[-1]["content"] == [
        {"title": "背景变化"},
        {"title": "产品取舍"},
        {"title": "未来影响"},
    ]
    assert derive_summary(result.ai_blocks) == (
        "文章解释了 AI 产品在体验、成本和可靠性之间的权衡。"
    )
    assert derive_reading_reason(result.ai_blocks) == (
        "它能帮助读者判断类似产品决策背后的真实约束。"
    )


def test_parse_ai_markdown_discards_chapters_for_short_article():
    result = parse_ai_markdown(VALID_RESPONSE, source_markdown="短文第一段。\n\n短文第二段。")

    chapters = [block for block in result.ai_blocks if block["type"] == "chapters"]
    assert chapters == []
```

- [ ] **Step 2: Add parser tests for validation failures**

Append these tests to `apps/api/tests/test_ai_blocks.py`:

```python
def test_parse_ai_markdown_rejects_missing_required_section():
    response = VALID_RESPONSE.replace("## 阅读理由\n它能帮助读者判断类似产品决策背后的真实约束。\n", "")

    with pytest.raises(AiBlockParseError, match="missing required section"):
        parse_ai_markdown(response, source_markdown=LONG_MARKDOWN)


def test_parse_ai_markdown_rejects_invalid_recommendation():
    response = VALID_RESPONSE.replace("deep_read", "must_read")

    with pytest.raises(AiBlockParseError, match="invalid reading recommendation"):
        parse_ai_markdown(response, source_markdown=LONG_MARKDOWN)


def test_parse_ai_markdown_rejects_too_few_highlights():
    response = VALID_RESPONSE.replace(
        "- 原文中的第二句亮点。\n- 原文中的第三句亮点。\n",
        "",
    )

    with pytest.raises(AiBlockParseError, match="highlights must contain 3-5 items"):
        parse_ai_markdown(response, source_markdown=LONG_MARKDOWN)


def test_parse_ai_markdown_rejects_too_many_highlights():
    response = VALID_RESPONSE.replace(
        "- 原文中的第三句亮点。\n",
        "- 原文中的第三句亮点。\n- 原文中的第四句亮点。\n- 原文中的第五句亮点。\n- 原文中的第六句亮点。\n",
    )

    with pytest.raises(AiBlockParseError, match="highlights must contain 3-5 items"):
        parse_ai_markdown(response, source_markdown=LONG_MARKDOWN)


def test_derive_helpers_return_none_when_blocks_missing():
    assert derive_summary(None) is None
    assert derive_reading_reason([]) is None
```

- [ ] **Step 3: Run parser tests and verify they fail**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_blocks.py -q
```

Expected: FAIL because `app.services.ai_blocks` does not exist yet.

- [ ] **Step 4: Implement `apps/api/app/services/ai_blocks.py`**

Create the module with these public names and behavior:

```python
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

RecommendationValue = Literal["deep_read", "skim", "skip"]

AiBlock = dict[str, Any]

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
REQUIRED_SECTIONS = {"带读问题", "Highlights", "一句话摘要", "阅读建议", "阅读理由"}
RECOMMENDATIONS = {"deep_read", "skim", "skip"}
CHAPTER_MIN_NON_WHITESPACE_CHARS = 1200
CHAPTER_MIN_PARAGRAPHS = 8


class AiBlockParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedAiMarkdown:
    ai_blocks: list[AiBlock]
    reading_recommendation: RecommendationValue


def markdown_allows_chapters(markdown: str) -> bool:
    compact_length = len(re.sub(r"\s+", "", markdown))
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", markdown) if part.strip()]
    return (
        compact_length >= CHAPTER_MIN_NON_WHITESPACE_CHARS
        and len(paragraphs) >= CHAPTER_MIN_PARAGRAPHS
    )


def parse_ai_markdown(markdown: str, *, source_markdown: str) -> ParsedAiMarkdown:
    sections = _split_sections(markdown)
    missing = sorted(REQUIRED_SECTIONS - sections.keys())
    if missing:
        raise AiBlockParseError(f"missing required section: {', '.join(missing)}")

    reading_question = _single_text(sections["带读问题"], "reading question")
    highlights = _bullet_items(sections["Highlights"])
    if len(highlights) < 3 or len(highlights) > 5:
        raise AiBlockParseError("highlights must contain 3-5 items")

    summary = _single_text(sections["一句话摘要"], "summary")
    recommendation = _single_text(sections["阅读建议"], "reading recommendation")
    if recommendation not in RECOMMENDATIONS:
        raise AiBlockParseError("invalid reading recommendation")
    reading_reason = _single_text(sections["阅读理由"], "reading reason")

    blocks: list[AiBlock] = [
        {
            "type": "reading_question",
            "title": "带读问题",
            "content": reading_question,
            "order": 10,
        },
        {
            "type": "highlights",
            "title": "Highlights",
            "content": [
                {"text": item, "quote_verified": False}
                for item in highlights
            ],
            "order": 20,
        },
        {
            "type": "summary",
            "title": "一句话摘要",
            "content": summary,
            "order": 30,
        },
        {
            "type": "reading_reason",
            "title": "阅读理由",
            "content": reading_reason,
            "order": 40,
        },
    ]

    chapters = _bullet_items(sections.get("章节", ""))
    if chapters and markdown_allows_chapters(source_markdown):
        blocks.append(
            {
                "type": "chapters",
                "title": "章节",
                "content": [{"title": title} for title in chapters],
                "order": 50,
            }
        )

    return ParsedAiMarkdown(
        ai_blocks=blocks,
        reading_recommendation=recommendation,  # type: ignore[arg-type]
    )


def derive_summary(ai_blocks: list[AiBlock] | None) -> str | None:
    return _derive_text_block(ai_blocks, "summary")


def derive_reading_reason(ai_blocks: list[AiBlock] | None) -> str | None:
    return _derive_text_block(ai_blocks, "reading_reason")


def _split_sections(markdown: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[title] = markdown[start:end].strip()
    return sections


def _single_text(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise AiBlockParseError(f"{field_name} is required")
    return text


def _bullet_items(value: str) -> list[str]:
    items: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    return items


def _derive_text_block(ai_blocks: list[AiBlock] | None, block_type: str) -> str | None:
    if not ai_blocks:
        return None
    for block in sorted(ai_blocks, key=lambda item: item.get("order", 0)):
        if block.get("type") == block_type and isinstance(block.get("content"), str):
            return block["content"]
    return None
```

- [ ] **Step 5: Run parser tests and verify they pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_blocks.py -q
```

Expected: PASS.

---

### Task 2: Database And API Schema

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/alembic/versions/0003_article_ai_blocks.py`
- Modify: `apps/api/app/schemas.py`

- [ ] **Step 1: Add `ai_blocks` model field**

In `apps/api/app/models.py`, add `JSON` to the SQLAlchemy imports and add this column to `ArticleAIAnalysis`:

```python
from sqlalchemy import JSON
```

```python
ai_blocks: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

Keep `one_sentence_summary` and `reading_reason` columns in the model for old-row fallback during this migration.

- [ ] **Step 2: Add Alembic migration**

Create `apps/api/alembic/versions/0003_article_ai_blocks.py`:

```python
"""article ai blocks

Revision ID: 0003_article_ai_blocks
Revises: 0002_email_digest_settings
Create Date: 2026-06-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_article_ai_blocks"
down_revision: str | None = "0002_email_digest_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("article_ai_analyses", sa.Column("ai_blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("article_ai_analyses", "ai_blocks")
```

- [ ] **Step 3: Add API block schemas**

In `apps/api/app/schemas.py`, add these Pydantic models before `ArticleListItem`:

```python
from typing import Literal
```

```python
class HighlightBlockItem(BaseModel):
    text: str
    quote_verified: bool


class ChapterBlockItem(BaseModel):
    title: str


class ReadingQuestionBlock(BaseModel):
    type: Literal["reading_question"]
    title: Literal["带读问题"]
    content: str
    order: int


class HighlightsBlock(BaseModel):
    type: Literal["highlights"]
    title: Literal["Highlights"]
    content: list[HighlightBlockItem]
    order: int


class SummaryBlock(BaseModel):
    type: Literal["summary"]
    title: Literal["一句话摘要"]
    content: str
    order: int


class ReadingReasonBlock(BaseModel):
    type: Literal["reading_reason"]
    title: Literal["阅读理由"]
    content: str
    order: int


class ChaptersBlock(BaseModel):
    type: Literal["chapters"]
    title: Literal["章节"]
    content: list[ChapterBlockItem]
    order: int


AiBlock = (
    ReadingQuestionBlock
    | HighlightsBlock
    | SummaryBlock
    | ReadingReasonBlock
    | ChaptersBlock
)
```

Add this field to `ArticleDetail`:

```python
ai_blocks: list[AiBlock] | None
```

- [ ] **Step 4: Run backend import and model tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_models.py -q
```

Expected: PASS.

---

### Task 3: AI Service Markdown Streaming

**Files:**
- Modify: `apps/api/tests/test_ai_service.py`
- Modify: `apps/api/app/services/ai_service.py`

- [ ] **Step 1: Update AI service tests for Markdown streaming**

In `apps/api/tests/test_ai_service.py`, replace JSON parser tests with parser tests that live in `test_ai_blocks.py`. Keep the streaming client test but change expected chunks to Markdown:

```python
def test_stream_analyze_markdown_yields_delta_content(monkeypatch: pytest.MonkeyPatch):
    fake_client = FakeClient()
    monkeypatch.setattr(
        "app.services.ai_service.OpenAI",
        lambda api_key, base_url: fake_client,
    )
    monkeypatch.setattr("app.services.ai_service.settings.deepseek_api_key", "key")

    chunks = list(stream_analyze_markdown_with_deepseek("# Title"))

    assert chunks == [
        "## 带读问题\n",
        "这篇文章要回答什么？\n",
    ]
    assert fake_client.chat.completions.kwargs is not None
    assert fake_client.chat.completions.kwargs["stream"] is True
    assert "response_format" not in fake_client.chat.completions.kwargs
    messages = fake_client.chat.completions.kwargs["messages"]
    assert "## 带读问题" in messages[0]["content"]
    assert "## Highlights" in messages[0]["content"]
    assert "逐字摘录" in messages[0]["content"]
```

Update `FakeCompletions.create` to return:

```python
return [
    FakeChunk("## 带读问题\n"),
    FakeChunk(None),
    FakeChunk("这篇文章要回答什么？\n"),
]
```

- [ ] **Step 2: Run AI service tests and verify they fail**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_service.py -q
```

Expected: FAIL because `response_format` is still sent and prompt still asks for JSON.

- [ ] **Step 3: Update AI prompt and streaming call**

In `apps/api/app/services/ai_service.py`:

- Remove `AIAnalysisResult`, `parse_ai_result`, and non-streaming JSON analysis if no other code uses them after Task 5.
- Update `build_ai_messages` so the system message requires fixed Markdown sections.
- Remove `response_format={"type": "json_object"}` from the streaming request.

Use this system prompt content:

```python
"你是 RSS 阅读前分析助手。请只输出 Markdown，不要输出 JSON。"
"必须按顺序输出以下二级标题：## 带读问题、## Highlights、## 一句话摘要、## 阅读建议、## 阅读理由、## 章节。"
"带读问题必须是一句中文问题。"
"Highlights 必须是 3-5 条项目符号，每条都必须逐字摘录原文，不要翻译、改写或编造。"
"一句话摘要必须是一句中文。"
"阅读建议只能输出 deep_read、skim 或 skip。"
"阅读理由必须用中文说明为什么适合读、略读或跳过。"
"章节只在文章确实有明显结构时输出项目符号标题；短讯、公告或结构单一文章可留空。"
```

- [ ] **Step 4: Run AI service tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_service.py -q
```

Expected: PASS.

---

### Task 4: Worker Persistence

**Files:**
- Modify: `apps/api/tests/test_tasks.py`
- Modify: `apps/api/app/tasks.py`

- [ ] **Step 1: Update worker success test to expect Markdown chunks and `ai_blocks`**

In `apps/api/tests/test_tasks.py`, update `test_analyze_article_streams_chunks_and_persists_final_result` so the fake stream yields a valid Markdown response and assertions check `analysis.ai_blocks`:

```python
valid_markdown_chunks = [
    "## 带读问题\n这篇文章要回答什么？\n\n",
    "## Highlights\n- 原文第一句。\n- 原文第二句。\n- 原文第三句。\n\n",
    "## 一句话摘要\n这是一句话摘要。\n\n",
    "## 阅读建议\nskim\n\n",
    "## 阅读理由\n这篇文章适合快速了解背景。\n",
]
```

Expected persisted assertions:

```python
assert analysis.analysis_status == AnalysisStatus.success
assert analysis.ai_blocks is not None
assert [block["type"] for block in analysis.ai_blocks] == [
    "reading_question",
    "highlights",
    "summary",
    "reading_reason",
]
assert analysis.reading_recommendation == ReadingRecommendation.skim
assert analysis.one_sentence_summary in (None, "Existing summary")
assert analysis.reading_reason in (None, "Existing reason")
```

Keep Redis write assertions, but expect chunk payload text to be Markdown chunks.

- [ ] **Step 2: Add worker parser failure test**

Add this test:

```python
def test_analyze_article_marks_failed_when_ai_markdown_is_invalid(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        article_id = seed_article(db)

    monkeypatch.setattr("app.tasks.get_redis_client", lambda: object())
    monkeypatch.setattr("app.tasks.reset_analysis_events", lambda client, article_id: None)
    monkeypatch.setattr("app.tasks.write_analysis_event", lambda client, article_id, event_type, payload: None)
    monkeypatch.setattr(
        "app.tasks.stream_analyze_markdown_with_deepseek",
        lambda markdown: iter(["## 带读问题\n缺少其它字段"]),
    )

    with pytest.raises(Exception):
        analyze_article_task(str(article_id))

    with session_local() as db:
        analysis = db.get(ArticleAIAnalysis, article_id)
        assert analysis is not None
        assert analysis.analysis_status == AnalysisStatus.failed
        assert analysis.ai_blocks is None
```

- [ ] **Step 3: Run worker tests and verify they fail**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_tasks.py -q
```

Expected: FAIL because worker still calls JSON parsing and writes legacy fields.

- [ ] **Step 4: Update worker to parse Markdown into blocks**

In `apps/api/app/tasks.py`:

- Replace `parse_ai_result` import with `parse_ai_markdown`.
- After accumulating `raw_chunks`, call:

```python
parsed = parse_ai_markdown("".join(raw_chunks), source_markdown=content.content_markdown)
analysis.ai_blocks = parsed.ai_blocks
analysis.reading_recommendation = ReadingRecommendation(parsed.reading_recommendation)
analysis.analysis_status = AnalysisStatus.success
analysis.updated_at = datetime.now(UTC).replace(tzinfo=None)
```

- Do not write new values into `analysis.one_sentence_summary` or `analysis.reading_reason`.
- Keep `error` event and failed status behavior unchanged.

- [ ] **Step 5: Run worker tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_tasks.py -q
```

Expected: PASS.

---

### Task 5: API Serialization And EPUB Derivation

**Files:**
- Modify: `apps/api/app/routers/articles.py`
- Modify: `apps/api/tests/test_articles_api.py`
- Modify: `apps/api/app/services/epub_service.py`
- Modify: `apps/api/tests/test_epub_service.py`

- [ ] **Step 1: Add article API tests for derived summary and detail blocks**

Update `seed_article` in `apps/api/tests/test_articles_api.py` to accept `ai_blocks` and seed a new success article with:

```python
ai_blocks=[
    {
        "type": "reading_question",
        "title": "带读问题",
        "content": "这篇文章要回答什么？",
        "order": 10,
    },
    {
        "type": "summary",
        "title": "一句话摘要",
        "content": "来自 block 的摘要。",
        "order": 30,
    },
    {
        "type": "reading_reason",
        "title": "阅读理由",
        "content": "来自 block 的理由。",
        "order": 40,
    },
]
```

Assert:

```python
assert unread_articles[0]["one_sentence_summary"] == "来自 block 的摘要。"
assert detail["ai_blocks"][0]["type"] == "reading_question"
assert detail["one_sentence_summary"] == "来自 block 的摘要。"
assert detail["reading_reason"] == "来自 block 的理由。"
```

Keep one old-row fallback assertion where `ai_blocks=None` and legacy columns still produce the old summary/reason.

- [ ] **Step 2: Update EPUB tests for block-derived summary**

In `apps/api/tests/test_epub_service.py`, set `article.ai_analysis.ai_blocks` on the fixture:

```python
article.ai_analysis = ArticleAIAnalysis(
    ai_blocks=[
        {
            "type": "summary",
            "title": "一句话摘要",
            "content": "来自 block 的 EPUB 摘要",
            "order": 30,
        },
        {
            "type": "reading_reason",
            "title": "阅读理由",
            "content": "来自 block 的 EPUB 理由",
            "order": 40,
        },
    ],
    one_sentence_summary="旧摘要",
    reading_reason="旧理由",
)
```

Assert the chapter contains block-derived text, not legacy text:

```python
assert "来自 block 的 EPUB 摘要" in chapter
assert "来自 block 的 EPUB 理由" in chapter
assert "旧摘要" not in chapter
assert "旧理由" not in chapter
```

- [ ] **Step 3: Run API and EPUB tests and verify they fail**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py tests/test_epub_service.py -q
```

Expected: FAIL because serializers still read legacy fields directly and detail does not return `ai_blocks`.

- [ ] **Step 4: Add derivation helpers to serializers**

In `apps/api/app/routers/articles.py`, import:

```python
from app.services.ai_blocks import derive_reading_reason, derive_summary
```

Use these rules when building list and detail dicts:

```python
summary = derive_summary(article.ai_analysis.ai_blocks) if article.ai_analysis else None
if summary is None and article.ai_analysis:
    summary = article.ai_analysis.one_sentence_summary

reason = derive_reading_reason(article.ai_analysis.ai_blocks) if article.ai_analysis else None
if reason is None and article.ai_analysis:
    reason = article.ai_analysis.reading_reason
```

Add to detail response:

```python
"ai_blocks": article.ai_analysis.ai_blocks if article.ai_analysis else None,
```

- [ ] **Step 5: Add derivation to EPUB**

In `apps/api/app/services/epub_service.py`, import derivation helpers and choose summary/reason this way:

```python
summary = derive_summary(article.ai_analysis.ai_blocks) or article.ai_analysis.one_sentence_summary or ""
reason = derive_reading_reason(article.ai_analysis.ai_blocks) or article.ai_analysis.reading_reason or ""
```

- [ ] **Step 6: Run API and EPUB tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py tests/test_epub_service.py -q
```

Expected: PASS.

---

### Task 6: Frontend Types And Rendering

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/routes/articles/components.tsx`
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Add frontend `AiBlock` types**

In `apps/web/src/lib/api.ts`, add:

```ts
export type AiBlock =
  | {
      type: "reading_question"
      title: "带读问题"
      content: string
      order: number
    }
  | {
      type: "highlights"
      title: "Highlights"
      content: Array<{
        text: string
        quote_verified: boolean
      }>
      order: number
    }
  | {
      type: "summary"
      title: "一句话摘要"
      content: string
      order: number
    }
  | {
      type: "reading_reason"
      title: "阅读理由"
      content: string
      order: number
    }
  | {
      type: "chapters"
      title: "章节"
      content: Array<{
        title: string
      }>
      order: number
    }
```

Add to `ArticleDetail`:

```ts
ai_blocks: AiBlock[] | null
```

- [ ] **Step 2: Update E2E fixtures with final blocks and streaming Markdown**

In `apps/web/tests/e2e/articles.spec.ts`, add `ai_blocks` to successful details. For `articleDetail`, use blocks ordered out of sequence to prove sorting:

```ts
ai_blocks: [
  {
    type: "summary",
    title: "一句话摘要",
    content: "来自 block 的一句话摘要",
    order: 30,
  },
  {
    type: "reading_question",
    title: "带读问题",
    content: "这篇文章要回答什么问题？",
    order: 10,
  },
  {
    type: "highlights",
    title: "Highlights",
    content: [
      { text: "原文第一句亮点。", quote_verified: false },
      { text: "原文第二句亮点。", quote_verified: false },
      { text: "原文第三句亮点。", quote_verified: false },
    ],
    order: 20,
  },
  {
    type: "reading_reason",
    title: "阅读理由",
    content: "来自 block 的阅读理由。",
    order: 40,
  },
  {
    type: "chapters",
    title: "章节",
    content: [],
    order: 50,
  },
],
```

Set old fallback fixtures with `ai_blocks: null`.

Change the stream route body chunk to Markdown:

```ts
`data: {"text":"## 带读问题\\n这篇文章正在生成什么问题？\\n\\n"}\n\n`
```

- [ ] **Step 3: Add E2E expectations**

Update or add tests asserting:

```ts
await expect(page.getByText("这篇文章要回答什么问题？")).toBeVisible()
await expect(page.getByText("原文第一句亮点。")).toBeVisible()
await expect(page.getByText("来自 block 的一句话摘要")).toBeVisible()
await expect(page.getByText("来自 block 的阅读理由。")).toBeVisible()
await expect(page.getByRole("heading", { name: "章节" })).toHaveCount(0)
```

For order, compare bounding boxes for question, highlight, summary, and reason:

```ts
const questionTop = await page.getByText("这篇文章要回答什么问题？").evaluate((node) => node.getBoundingClientRect().top)
const highlightTop = await page.getByText("原文第一句亮点。").evaluate((node) => node.getBoundingClientRect().top)
const summaryTop = await page.getByText("来自 block 的一句话摘要").evaluate((node) => node.getBoundingClientRect().top)
const reasonTop = await page.getByText("来自 block 的阅读理由。").evaluate((node) => node.getBoundingClientRect().top)
expect(questionTop).toBeLessThan(highlightTop)
expect(highlightTop).toBeLessThan(summaryTop)
expect(summaryTop).toBeLessThan(reasonTop)
```

- [ ] **Step 4: Run frontend tests and verify they fail**

Run:

```bash
cd apps/web && pnpm test:e2e -- articles.spec.ts
```

Expected: FAIL because `ArticleAiSummary` still renders legacy fields only.

- [ ] **Step 5: Render structured blocks and Markdown stream**

In `apps/web/src/routes/articles/components.tsx`:

- Import `AiBlock`.
- Import and reuse `MarkdownContent` for streaming Markdown.
- Sort `article.ai_blocks ?? []` by `order`.
- Render each block by type.
- Hide `chapters` when `content.length === 0`.
- If `ai_blocks` is empty and `streamText` exists, render `MarkdownContent markdown={streamText}`.
- If `ai_blocks` is null, fall back to existing `one_sentence_summary` and `reading_reason`.

Use helper structure like:

```tsx
function visibleAiBlocks(blocks: AiBlock[] | null) {
  return [...(blocks ?? [])]
    .sort((a, b) => a.order - b.order)
    .filter((block) => block.type !== "chapters" || block.content.length > 0)
}
```

Keep the recommendation badge driven by `article.reading_recommendation`.

- [ ] **Step 6: Run frontend build and article E2E**

Run:

```bash
cd apps/web && pnpm build
cd apps/web && pnpm test:e2e -- articles.spec.ts
```

Expected: PASS.

---

### Task 7: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_ai_blocks.py tests/test_ai_service.py tests/test_tasks.py tests/test_articles_api.py tests/test_epub_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run all backend tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd apps/web && pnpm build
```

Expected: PASS.

- [ ] **Step 4: Run article E2E**

Run:

```bash
cd apps/web && pnpm test:e2e -- articles.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Inspect changed files**

Run:

```bash
git status --short
git diff -- docs/article-reading-guide/spec.md docs/article-reading-guide/plan.md
```

Expected: docs are present and source changes match the feature scope. Do not revert unrelated user changes.

---

## Self-Review Checklist

- Spec coverage: parser, storage, streaming Markdown, API derivation, EPUB derivation, frontend block order, hidden empty chapters, and old-row fallback are each mapped to a task.
- Type consistency: backend and frontend use the same block type names, titles, content shapes, and order values.
- Scope control: quote verification, old-article AI backfill, chapter anchors, and list-page guide display stay out of scope.
- Migration choice: keep legacy columns as fallback in this migration, but treat `ai_blocks` as the new canonical detail content for all new successful analyses.
