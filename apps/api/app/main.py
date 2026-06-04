from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.routers import articles, auth, feeds, settings as settings_router

configure_logging()

app = FastAPI(title="RSSWise API")

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(feeds.router)
app.include_router(articles.router)
app.include_router(settings_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
