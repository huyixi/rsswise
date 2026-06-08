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
