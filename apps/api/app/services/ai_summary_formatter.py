from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.models import ArticleAIAnalysis

AiBlock = dict[str, Any]

BRACKET_NUM_RE = re.compile(r"^【[^】]*】\s*")


@dataclass(frozen=True)
class AiSummarySection:
    type: str
    label: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class FormattedAiSummary:
    one_sentence_summary: str | None
    reading_reason: str | None
    ai_blocks: list[AiBlock] | None
    sections: list[AiSummarySection]


def format_ai_summary(analysis: ArticleAIAnalysis | None) -> FormattedAiSummary:
    if analysis is None:
        return FormattedAiSummary(
            one_sentence_summary=None,
            reading_reason=None,
            ai_blocks=None,
            sections=[],
        )

    visible_blocks = visible_ai_blocks(analysis.ai_blocks)
    if visible_blocks:
        sections = sections_from_ai_blocks(visible_blocks)
        return FormattedAiSummary(
            one_sentence_summary=_first_section_item(sections, "summary"),
            reading_reason=_first_section_item(sections, "reading_reason"),
            ai_blocks=visible_blocks,
            sections=sections,
        )

    sections = legacy_sections(analysis)
    return FormattedAiSummary(
        one_sentence_summary=analysis.one_sentence_summary,
        reading_reason=analysis.reading_reason,
        ai_blocks=[] if analysis.ai_blocks is not None else None,
        sections=sections,
    )


def visible_ai_blocks(ai_blocks: list[AiBlock] | None) -> list[AiBlock]:
    return [
        block
        for block in sorted(ai_blocks or [], key=lambda item: item.get("order", 0))
        if not _is_empty_chapters_block(block)
    ]


def sections_from_ai_blocks(ai_blocks: list[AiBlock]) -> list[AiSummarySection]:
    sections: list[AiSummarySection] = []
    for block in ai_blocks:
        block_type = block.get("type")
        content = block.get("content")
        if block_type == "reading_question" and isinstance(content, str):
            section = _text_section("reading_question", "问题", content)
        elif block_type == "summary" and isinstance(content, str):
            section = _text_section("summary", "一句话摘要", content)
        elif block_type == "reading_reason" and isinstance(content, str):
            section = _text_section("reading_reason", "阅读理由", content)
        elif block_type == "highlights" and isinstance(content, list):
            section = _list_section(
                "highlights",
                "摘录",
                (_highlight_text(item) for item in content),
            )
        elif block_type == "chapters" and isinstance(content, list):
            section = _list_section(
                "chapters",
                "章节",
                (_chapter_title(item) for item in content),
            )
        else:
            section = None

        if section is not None and section.items:
            sections.append(section)
    return sections


def legacy_sections(analysis: ArticleAIAnalysis) -> list[AiSummarySection]:
    sections: list[AiSummarySection] = []
    if analysis.one_sentence_summary:
        sections.append(_text_section("summary", "一句话摘要", analysis.one_sentence_summary))
    if analysis.reading_reason:
        sections.append(_text_section("reading_reason", "阅读理由", analysis.reading_reason))
    return sections


def _text_section(block_type: str, label: str, content: str) -> AiSummarySection | None:
    text = content.strip()
    if not text:
        return None
    return AiSummarySection(type=block_type, label=label, items=(text,))


def _list_section(
    block_type: str,
    label: str,
    values: Any,
) -> AiSummarySection | None:
    items = tuple(item for item in values if item)
    if not items:
        return None
    return AiSummarySection(type=block_type, label=label, items=items)


def _first_section_item(sections: list[AiSummarySection], block_type: str) -> str | None:
    for section in sections:
        if section.type == block_type and section.items:
            return section.items[0]
    return None


def _is_empty_chapters_block(block: AiBlock) -> bool:
    return block.get("type") == "chapters" and len(block.get("content") or []) == 0


def _highlight_text(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    text = item.get("text")
    if not isinstance(text, str):
        return None
    return _normalize_quote_text(text)


def _chapter_title(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    if not isinstance(title, str):
        return None
    title = title.strip()
    return title or None


def _normalize_quote_text(value: str) -> str | None:
    text = value.strip()
    while text.startswith(">"):
        text = text[1:].strip()

    while BRACKET_NUM_RE.match(text):
        text = BRACKET_NUM_RE.sub("", text, count=1)

    quote_pairs = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
    changed = True
    while changed:
        changed = False
        for opening, closing in quote_pairs:
            if text.startswith(opening) and text.endswith(closing) and len(text) >= 2:
                text = text[len(opening) : len(text) - len(closing)].strip()
                changed = True
                break
    return text or None
