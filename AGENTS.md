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
  roles (`UserRole`: `user`, `employee`, `manager`, `admin`; the last active admin cannot be demoted,
  blocked or deleted). `User.is_active`: a blocked account gets 403 on login (after the password
  check) and its tokens stop working. `/users/{id}/active` blocks or unblocks; `DELETE /users/{id}`
  refuses an account with recorded hours (409) — block it instead. No one can block or delete themselves.
- `User.last_login_at` (naive UTC, nullable): set by `create_token` (login and sign-up, not token reuse);
  only `/users` returns it (`UserAdminRead`), `/auth/*` keeps `UserRead`.
- Forgotten password (`app/services/password_reset.py`): `POST /auth/password-reset/request {email}`
  always answers 202 and looks the account up in a background task (no enumeration by answer or
  timing); an active account gets a link `SITE_URL/mot-de-passe/nouveau#token=…` by e-mail
  (`app/services/mailer.py`, Brevo HTTP API: Render's free plan blocks SMTP). Only the token's SHA-256
  is stored (`password_reset_tokens`), valid `PASSWORD_RESET_TTL_MINUTES` (30), one per account (a new
  request replaces it). `POST /auth/password-reset/confirm {token, password}` → 204, deletes the token
  and every `AuthToken` of the account, clears its login lockout; bad/expired token → 400. Throttles:
  3/hour per e-mail (silently dropped), 50/hour site-wide (429). Tests use the `outbox` fixture.
- `app/core/deps.py` — `CurrentUserDep` (401) and `require_admin` (403). Product writes and `/users` are
  admin-only; order reads and status updates need `require_manager` (manager or admin); `GET /products` stays public. `POST /orders` is
  admin-only too (it takes stock). The site's form calls the public `POST /orders/submit`
  (`OrderService.submit`: catalogue prices, no stock taken, delivery details, `order_throttle`
  60/hour site-wide); the site's Gestion > Commandes tab lists them and changes their status. `status_changed_at` (naive UTC)
  is set on each status change; `OrderService.list` first deletes orders cancelled more than 30 days ago
  (`purge_cancelled`; no scheduler on Render's free plan).
- `app/core/rate_limit.py` — in-memory throttles: failed logins per e-mail (10 / 15 min → 429) and
  new accounts site-wide (30 / hour → 429),
  reset in `tests/conftest.py`. `GZipMiddleware` compresses responses over 1 KB (catalogue on 3G).
  `GET /products/` sends `Cache-Control: public, max-age=60, stale-while-revalidate=600` (clients
  refetch with `cache: "no-cache"` after an edit); CORS preflights are cached 24 h (`max_age`).
- Time clock (`/time`, `app/routers/time_entries.py`, `TimeService`): employees and admins
  (`require_staff`: employee, manager, admin) clock in/out at server time (`/time/me/clock-in`, `/clock-out`, `/current`,
  `/entries`); managers and admins (`require_manager`) list everyone's entries (`/time/staff` for the
  staff list) and correct (`PUT`, stamped `edited_at`/`edited_by_id`) or delete them; a manager cannot
  change their own entries. Times are stored naive UTC and returned with a zone; a break is the gap between
  two entries. A partial unique index allows one open entry per person.
- Catalogue import (`POST /products/import`, admin only, `app/services/catalogue_import.py`): JSON
  `{content, dry_run}` with the CSV text (French headers `id;categorie;prix;nom;famille;…`, `;` or `,`).
  `Product.family` is a free-text sub-category (≤ 60 chars) the site groups the catalogue by.
  A row with `id` updates that product (unknown id = error), without `id` it updates the product of
  the same name (case-insensitive) or creates one. Only columns in the file are written on update.
  Errors come back per line as codes (the site translates them) and then nothing is written.
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

- `ci.yaml` — ruff check/format, mypy, pytest on push/PR; job `postgres` reruns the whole suite on a
  PostgreSQL service whose schema comes from `python -m app.scripts.migrate` (`TEST_DATABASE_URL`,
  see `tests/conftest.py`; tables are truncated between tests, `sqlite_only` marks create_all tests),
  then `alembic check`. `tests/test_status.py` fails on more than one Alembic head.
- `sauvegarde-base.yml` — nightly encrypted `pg_dump` of Neon + test restore (`scripts/sauvegarde.sh`,
  `docs/SAUVEGARDE.md`); `restaurer-sauvegarde.yml` restores one into `RESTORE_DATABASE_URL`.
- `/` and `/health` never touch the database and answer HEAD (UptimeRobot free monitors use HEAD).
- `cd.yaml` — Docker build/push to GHCR on tags; Render deploy on `main`/tags
  (needs `RENDER_SERVICE_ID` + `RENDER_API_KEY` secrets).
