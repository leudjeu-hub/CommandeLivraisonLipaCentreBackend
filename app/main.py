import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.core.config import get_settings
from app.core.db import Base, async_session_maker, engine, initialize_database_if_empty
from app.core.exceptions import AppError
from app.routers import auth, orders, products, time_entries, users
from app.services.admin_bootstrap import ensure_admin
from app.services.catalogue_seed import seed_products_if_empty

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    elif engine.dialect.name == "sqlite":
        try:
            if await initialize_database_if_empty():
                logger.info("Created schema in empty local SQLite database")
        except (OSError, SQLAlchemyError):
            logger.warning("Skipping database initialization", exc_info=True)
    if settings.seed_products:
        try:
            async with async_session_maker() as session:
                await seed_products_if_empty(session)
        except (OSError, SQLAlchemyError):
            # Keep serving (e.g. the healthcheck) when the database is unreachable at startup.
            logger.warning("Skipping product seeding: database unavailable", exc_info=True)
    if settings.admin_email and settings.admin_password:
        try:
            async with async_session_maker() as session:
                message = await ensure_admin(
                    session, settings.admin_email, settings.admin_password.get_secret_value()
                )
            if message:
                logger.warning(message)
        except (OSError, SQLAlchemyError, ValueError):
            logger.warning("Skipping admin bootstrap", exc_info=True)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers cache the OPTIONS preflight (writes, calls with a token): Chrome caps this at 2 h,
    # Firefox at 24 h; Starlette's default is 10 min, i.e. an extra round trip per visit on 3G.
    max_age=86400,
)
# The full catalogue (~1,500 products) is ~470 KB of JSON but ~40 KB gzipped: it matters on 3G.
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(time_entries.router, prefix="/time", tags=["Time clock"])


ADMIN_PAGE = Path(__file__).parent / "static" / "admin.html"


@app.get("/admin", include_in_schema=False)
async def admin() -> FileResponse:
    return FileResponse(ADMIN_PAGE)


# Status routes never touch the database: probes every few minutes (Render, UptimeRobot, the site's
# wake-up job) would otherwise keep Neon's free compute awake around the clock. HEAD is accepted
# because UptimeRobot's free monitors send HEAD (FastAPI answers 405 to HEAD on a GET-only route).
@app.api_route("/", methods=["GET", "HEAD"], tags=["Status"])
async def status() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Status"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
