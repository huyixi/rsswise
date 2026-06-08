import pytest

from app.services.ai_service import parse_ai_result


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
