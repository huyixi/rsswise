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


def analyze_markdown_with_deepseek(markdown: str) -> AIAnalysisResult:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required")

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        response_format={"type": "json_object"},
        messages=[
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
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty ai response")
    return parse_ai_result(content)
