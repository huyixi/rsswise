from app.models import (
    Article,
    ArticleAIAnalysis,
    ArticleAIAnalysisLog,
    ArticleContent,
    Feed,
    Session,
    User,
    UserArticleState,
    UserFeedSubscription,
)


def test_models_match_design_entities():
    assert Feed.__tablename__ == "feeds"
    assert Article.__tablename__ == "articles"
    assert ArticleContent.__tablename__ == "article_contents"
    assert ArticleAIAnalysis.__tablename__ == "article_ai_analyses"
    assert ArticleAIAnalysisLog.__tablename__ == "article_ai_analysis_logs"


def test_multi_user_tables_are_declared():
    assert User.__tablename__ == "users"
    assert Session.__tablename__ == "sessions"
    assert UserFeedSubscription.__tablename__ == "user_feed_subscriptions"
    assert UserArticleState.__tablename__ == "user_article_states"
