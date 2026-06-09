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
