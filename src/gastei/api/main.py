"""FastAPI app entry point.

Minimal composition: mount routers, configure CORS for localhost
(ARCHITECTURE.md §9). No heavyweight middleware in the MVP.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gastei.api.routers import (
    accounts as accounts_router,
)
from gastei.api.routers import (
    categories as categories_router,
)
from gastei.api.routers import (
    chat as chat_router,
)
from gastei.api.routers import (
    debug as debug_router,
)
from gastei.api.routers import (
    imports as imports_router,
)
from gastei.api.routers import (
    insights as insights_router,
)
from gastei.api.routers import (
    items as items_router,
)
from gastei.api.routers import (
    sync as sync_router,
)
from gastei.api.routers import (
    transactions as transactions_router,
)
from gastei.jobs.sync_job import scheduler_lifespan
from gastei.utils.logging import install_redaction


def create_app() -> FastAPI:
    install_redaction()

    app = FastAPI(
        title="Gastei API",
        description="Personal finance assistant — backend",
        version="0.4.0",
        lifespan=scheduler_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",  # Streamlit dev
            "http://127.0.0.1:8501",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(imports_router.router)
    app.include_router(accounts_router.router)
    app.include_router(items_router.router)
    app.include_router(transactions_router.router)
    app.include_router(categories_router.router)
    app.include_router(insights_router.router)
    app.include_router(chat_router.router)
    app.include_router(sync_router.router)
    app.include_router(debug_router.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
