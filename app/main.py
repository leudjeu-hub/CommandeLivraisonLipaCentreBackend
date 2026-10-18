import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.core.config import get_settings
from app.core.db import Base, async_session_maker, engine
from app.core.exceptions import AppError
from app.routers import orders, products
from app.services.catalogue_seed import seed_products_if_empty

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.seed_products:
        try:
            async with async_session_maker() as session:
                await seed_products_if_empty(session)
        except (OSError, SQLAlchemyError):
            # Keep serving (e.g. the healthcheck) when the database is unreachable at startup.
            logger.warning("Skipping product seeding: database unavailable", exc_info=True)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])


@app.get("/", tags=["Status"])
async def status() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
