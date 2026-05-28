from fastapi import FastAPI

from app.core.logging import configure_logging
from app.routers import articles, feeds

configure_logging()

app = FastAPI(title="RSSWise API")
app.include_router(feeds.router)
app.include_router(articles.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
