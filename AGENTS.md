# AGENTS.md

Papeterie API — async FastAPI + SQLAlchemy 2.0 backend for a stationery-shop order app.
Single Python package `app/` at the repo root, no frontend, no `backend/` subdir.

## Commands

Run from the repo root (there is no workspace/codegen step).

```bash
uv sync                                  # installs runtime + dev deps (dependency-groups)
uv run uvicorn app.main:app --reload     # :8000, needs DATABASE_URL
uv run pytest                            # 24 tests, SQLite, no external DB
uv run ruff check . && uv run ruff format .
uv run mypy app
uv run alembic upgrade head              # apply migrations
```

## Architecture

Layered, one direction only: `routers/` → `services/` → `models/` + `schemas/`.

- `app/main.py` — app entrypoint. Lifespan optionally runs `create_all` when
  `CREATE_TABLES=true`; CORS from `CORS_ORIGINS`; registers the `AppError` handler; mounts
  `/products` and `/orders`; serves `/` healthcheck and `/admin` (static `app/static/admin.html`, product CRUD UI, no auth).
- `app/core/config.py` — pydantic-settings `Settings` (`get_settings()` is `lru_cache`d).
  `async_database_url` rewrites `postgres://` → `postgresql+asyncpg://`.
- `app/core/db.py` — async engine, `async_session_maker` (`expire_on_commit=False`),
  `get_async_session` dependency, `Base`.
- `app/core/deps.py` — `SessionDep`, `ProductServiceDep`, `OrderServiceDep`.
- `app/core/exceptions.py` — `AppError` base plus `ProductNotFoundError`,
  `InsufficientStockError` (handled in `main.py`).
- `app/models/` — `Product`, `Order`, `OrderItem`. `OrderStatus` is an `enum.StrEnum`.
  `Order.items` and `OrderItem.product` use `lazy="selectin"` so reads never lazy-load.
- `app/schemas/` — Pydantic v2 in/out models. `*Read` models use `from_attributes=True`.
- `app/services/` — `ProductService`, `OrderService`. `OrderService.create` decrements stock
  and computes the total in one transaction; `to_order_read` attaches `whatsapp_url`.
- `app/routers/` — thin HTTP layer; converts ORM models to `*Read` schemas.
- `app/utils/whatsapp.py` — builds the `wa.me` deep link from `SHOP_WHATSAPP`.

## Gotchas

**`app` must be top-level.** Imports are absolute (`from app.models.product import ...`), so
run uvicorn/pytest with cwd = repo root.

**`uv sync` installs dev deps by default** (`[dependency-groups]`). Use `uv sync --no-dev` for
production images (the Dockerfile does this).

**No tables are created at import time.** `create_all` only runs in lifespan when
`CREATE_TABLES=true`. Otherwise use Alembic. Tests set `DATABASE_URL` to SQLite and create
tables in a `conftest.py` fixture.

**`DATABASE_URL` is required at import time** (engine is created eagerly). There is a default,
but a real deployment must set it.

**`OrderStatus` uses `native_enum=False`**, so the column is `VARCHAR(20)` + CHECK — portable
across PostgreSQL and SQLite. Keep the Alembic migration in sync if you change the enum.

**Tests force `sqlite+aiosqlite:///./test.db`** in `tests/conftest.py` and drop/recreate tables
around every test. `test.db` is gitignored (`*.db`).

## CI/CD

- `ci.yaml` — ruff check/format, mypy, pytest on push/PR.
- `cd.yaml` — Docker build/push to GHCR on tags; Render deploy on `main`/tags
  (needs `RENDER_SERVICE_ID` + `RENDER_API_KEY` secrets).
