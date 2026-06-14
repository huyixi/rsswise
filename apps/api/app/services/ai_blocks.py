from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

RecommendationValue = Literal["deep_read", "skim", "skip"]

AiBlock = dict[str, Any]

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
BRACKET_NUM_RE = re.compile(r"^【[^】]*】\s*")
REQUIRED_SECTIONS = {"问题", "Highlights", "一句话摘要", "阅读建议", "阅读理由"}
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

    reading_question = _single_text(sections["问题"], "reading question")
    highlights = [
        _normalize_quote_text(item)
        for item in _bullet_items(sections["Highlights"])
    ]
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
            "title": "问题",
            "content": reading_question,
            "order": 10,
        },
        {
            "type": "summary",
            "title": "一句话摘要",
            "content": summary,
            "order": 20,
        },
        {
            "type": "reading_reason",
            "title": "阅读理由",
            "content": reading_reason,
            "order": 30,
        },
        {
            "type": "highlights",
            "title": "Highlights",
            "content": [
                {"text": item, "quote_verified": False}
                for item in highlights
            ],
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
            item = _normalize_quote_text(item)
            if item:
                items.append(item)
    return items


def _normalize_quote_text(value: str) -> str:
    text = value.strip()
    while text.startswith(">"):
        text = text[1:].strip()

    text = BRACKET_NUM_RE.sub("", text)
    while BRACKET_NUM_RE.match(text):
        text = BRACKET_NUM_RE.sub("", text)

    quote_pairs = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
    changed = True
    while changed:
        changed = False
        for opening, closing in quote_pairs:
            if text.startswith(opening) and text.endswith(closing) and len(text) >= 2:
                text = text[len(opening) : len(text) - len(closing)].strip()
                changed = True
                break
    return text


def _derive_text_block(ai_blocks: list[AiBlock] | None, block_type: str) -> str | None:
    if not ai_blocks:
        return None
    for block in sorted(ai_blocks, key=lambda item: item.get("order", 0)):
        if block.get("type") == block_type and isinstance(block.get("content"), str):
            return block["content"]
    return None
