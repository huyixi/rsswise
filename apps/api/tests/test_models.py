from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed


def test_models_match_design_entities():
    assert Feed.__tablename__ == "feeds"
    assert Article.__tablename__ == "articles"
    assert ArticleContent.__tablename__ == "article_contents"
    assert ArticleAIAnalysis.__tablename__ == "article_ai_analyses"
