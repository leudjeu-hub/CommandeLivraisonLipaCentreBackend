# AGENTS.md

Papeterie API — async FastAPI + SQLAlchemy 2.0 backend for a stationery-shop order app.
Single Python package `app/` at the repo root, no frontend, no `backend/` subdir.

## Commands

Run from the repo root (there is no workspace/codegen step).

```bash
uv sync                                  # installs runtime + dev deps (dependency-groups)
uv run uvicorn app.main:app --reload     # :8000, DATABASE_URL defaults to local SQLite
uv run pytest                            # SQLite, no external DB
uv run ruff check . && uv run ruff format .
uv run mypy app
uv run alembic upgrade head              # apply migrations
```

## Architecture

Layered, one direction only: `routers/` → `services/` → `models/` + `schemas/`.

- `app/main.py` — app entrypoint. Lifespan runs `create_all` when `CREATE_TABLES=true`
  (and initializes an empty local SQLite database automatically); CORS from
  `CORS_ORIGINS`; registers the `AppError` handler; mounts
  `/products`, `/orders`, `/auth` and `/users`; serves `/` healthcheck and `/admin` (static
  `app/static/admin.html`, product CRUD UI behind an administrator login).
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

## Auth

- `app/core/security.py` — scrypt password hashes and random bearer tokens (stdlib only); only
  the token's SHA-256 is stored (`AuthToken`, `auth_tokens` table).
- `app/services/auth_service.py` — register, authenticate (same timing for unknown e-mails), tokens,
  roles (`UserRole`: `user`, `employee`, `admin`; the last admin cannot be demoted).
- `app/core/deps.py` — `CurrentUserDep` (401) and `require_admin` (403). Product writes, order reads
  and status updates, and `/users` are admin-only; `GET /products` and `POST /orders` stay public.
- Time clock (`/time`, `app/routers/time_entries.py`, `TimeService`): employees and admins
  (`require_staff`) clock in/out at server time (`/time/me/clock-in`, `/clock-out`, `/current`,
  `/entries`); admins list everyone's entries and correct (`PUT`, stamped `edited_at`/`edited_by_id`)
  or delete them. Times are stored naive UTC and returned with a zone; a break is the gap between
  two entries. A partial unique index allows one open entry per person.
- First admin: `uv run python -m app.scripts.create_admin <email>`, or `ADMIN_EMAIL` + `ADMIN_PASSWORD`
  env vars (created on startup by `app/services/admin_bootstrap.py` only while no admin exists).
- Tests: the `client` fixture is logged in as an admin; use `anon_client` for anonymous requests
  and `make_user()` for other accounts.

## Gotchas

**`app` must be top-level.** Imports are absolute (`from app.models.product import ...`), so
run uvicorn/pytest with cwd = repo root.

**`uv sync` installs dev deps by default** (`[dependency-groups]`). Use `uv sync --no-dev` for
production images (the Dockerfile does this).

**No tables are created at import time.** In lifespan, `create_all` runs when
`CREATE_TABLES=true`, and an empty SQLite database is initialized automatically
(`initialize_database_if_empty`). Otherwise use Alembic. Tests set `DATABASE_URL` to SQLite and
create tables in a `conftest.py` fixture.

**The engine is created eagerly at import time.** `DATABASE_URL` defaults to
`sqlite+aiosqlite:///./dev.db` for local development; a real deployment must set a PostgreSQL URL.

**`OrderStatus` uses `native_enum=False`**, so the column is `VARCHAR(20)` + CHECK — portable
across PostgreSQL and SQLite. Keep the Alembic migration in sync if you change the enum.

**Tests force `sqlite+aiosqlite:///./test.db`** in `tests/conftest.py` and drop/recreate tables
around every test. `test.db` is gitignored (`*.db`).

## CI/CD

- `ci.yaml` — ruff check/format, mypy, pytest on push/PR.
- `cd.yaml` — Docker build/push to GHCR on tags; Render deploy on `main`/tags
  (needs `RENDER_SERVICE_ID` + `RENDER_API_KEY` secrets).
