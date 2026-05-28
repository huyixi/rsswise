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
