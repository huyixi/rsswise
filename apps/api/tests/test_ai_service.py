import pytest

from app.services.ai_service import parse_ai_result, stream_analyze_markdown_with_deepseek


def test_parse_ai_result_accepts_design_enum():
    result = parse_ai_result(
        '{"one_sentence_summary":"Short summary.",'
        '"reading_recommendation":"skim",'
        '"reading_reason":"Useful context."}'
    )

    assert result.reading_recommendation == "skim"


def test_parse_ai_result_rejects_score_output():
    with pytest.raises(ValueError):
        parse_ai_result(
            '{"one_sentence_summary":"Short summary.",'
            '"reading_recommendation":"score_9",'
            '"reading_reason":"Useful."}'
        )



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
            FakeChunk("## 问题\n"),
            FakeChunk(None),
            FakeChunk("这篇文章要回答什么？\n"),
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
        "## 问题\n",
        "这篇文章要回答什么？\n",
    ]
    assert fake_client.chat.completions.kwargs is not None
    assert fake_client.chat.completions.kwargs["stream"] is True
    assert "response_format" not in fake_client.chat.completions.kwargs
    messages = fake_client.chat.completions.kwargs["messages"]
    assert "## 问题" in messages[0]["content"]
    assert "## Highlights" in messages[0]["content"]
    assert "最多 3 条" in messages[0]["content"]
    assert "逐字摘录" in messages[0]["content"]
