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
                "你是 RSS 阅读前分析助手。请只输出 Markdown，不要输出 JSON。"
                "必须按顺序输出以下二级标题：## 问题、## 一句话摘要、## 阅读理由、## 阅读建议、## Highlights、## 章节。"
                "问题必须是一句中文问题。"
                "Highlights 必须是 3-5 条项目符号，每条都必须逐字摘录原文，不要翻译、改写或编造。"
                "一句话摘要必须是一句中文。"
                "阅读建议只能输出 deep_read、skim 或 skip。"
                "阅读理由必须用中文说明为什么适合读、略读或跳过。"
                "章节只在文章确实有明显结构时输出项目符号标题；短讯、公告或结构单一文章可留空。"
                "不要使用【1】【2】等中文括号编号格式。使用标准 Markdown 列表语法。"
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
