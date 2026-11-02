"""Local-only HTTP service; no network publishing or login functionality."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import projects, shots, assets, storyboards, sync
from .db import build_engine, init_database, make_session_factory


ALLOWED_LOCAL_ORIGINS = [
    "http://127.0.0.1:5173", "http://localhost:5173",
    "http://127.0.0.1:4173", "http://localhost:4173",
]


def create_app(database_url: str | None = None) -> FastAPI:
    engine = build_engine(database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_database(engine)
        yield
        engine.dispose()

    app = FastAPI(title="BLUEPRINT STUDIOS Local API", version="0.2.0", lifespan=lifespan)
    app.state.session_factory = make_session_factory(engine)
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_LOCAL_ORIGINS,
                       allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type"])
    app.include_router(projects.router)
    app.include_router(shots.router)
    app.include_router(assets.router)
    app.include_router(storyboards.router)
    app.include_router(sync.router)

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "blueprint-studios-bs-m2"}

    return app


app = create_app()
