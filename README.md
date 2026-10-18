# Papeterie API

Async FastAPI + SQLAlchemy 2.0 order-management API for *Librairie Papeterie du Centre*.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg (PostgreSQL) / aiosqlite (tests)
- Pydantic v2 + pydantic-settings
- Alembic migrations
- pytest + pytest-asyncio + httpx
- ruff + mypy
- uv for dependency management

## Project layout

```
app/
  core/       config, async engine/session, DI, domain errors
  models/     SQLAlchemy 2.0 models (Product, Order, OrderItem)
  schemas/    Pydantic request/response models
  services/   business logic + DB access
  routers/    thin HTTP layer
  utils/      WhatsApp deep-link builder
alembic/      migrations
tests/        pytest suite (SQLite)
```

## Getting started

Works on **Windows** and **macOS**. All commands use `uv` — no platform-specific scripts.

```bash
uv sync
cp .env.example .env   # adjust DATABASE_URL / SHOP_WHATSAPP
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

Import the products from the frontend catalogue (upsert by `id`, stock is left untouched):

```bash
uv run python -m app.scripts.import_catalogue ../CommandeLivraisonLipaCentre/catalogue/catalogue.csv
```

For a quick start without migrations, set `CREATE_TABLES=true` and the app creates the
tables on startup.

## Tests / lint / types

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | / | Health check |
| GET | /admin | Admin page: list, create, edit, delete products (administrator login) |
| GET | /products/ | List products (sorted by name) |
| GET | /products/{id} | Get one product |
| POST | /products/ | Create product — **admin** |
| PUT | /products/{id} | Update product — **admin** |
| DELETE | /products/{id} | Delete product (409 if it appears in an order) — **admin** |
| POST | /orders/ | Create order (no account needed; decrements stock, returns `whatsapp_url`) |
| GET | /orders/ | List orders (newest first) — **admin** |
| GET | /orders/{id} | Get one order — **admin** |
| PATCH | /orders/{id}/status | Set status: new, confirmed, delivered, cancelled — **admin** |
| POST | /auth/register | Create a customer account (`user` role) and log in → `{token, user}` |
| POST | /auth/login | Log in with e-mail + password → `{token, user}` |
| POST | /auth/logout | Revoke the current token — logged in |
| GET | /auth/me | Current account — logged in |
| GET | /users/ | List accounts — **admin** |
| PATCH | /users/{id}/role | Promote to `admin` / demote to `user` (409 for the last admin) — **admin** |

### Accounts and roles

Send the token as `Authorization: Bearer <token>`. Missing or invalid token → 401, a customer on
an admin route → 403. Passwords are hashed with scrypt (standard library); the database only keeps
the SHA-256 of each token, valid for `TOKEN_TTL_DAYS`.

Create the first administrator (asks for the password; `ADMIN_PASSWORD` for non-interactive use).
For an existing account it only grants the admin role:

```bash
uv run python -m app.scripts.create_admin admin@example.com
```

On a server without shell access (Render), set `ADMIN_EMAIL` and `ADMIN_PASSWORD` instead: on
startup the app creates that administrator if **no admin exists yet** (an existing account with
that e-mail is promoted and keeps its password). Once any admin exists it does nothing, so
`ADMIN_PASSWORD` can be removed afterwards.

Further administrators can then be promoted by an admin (`PATCH /users/{id}/role`, or the site's
`/gestion` page in development).

## Configuration

| Env var | Default | Description |
|---|---|---|
| DATABASE_URL | postgresql+asyncpg://postgres:postgres@localhost:5432/papeterie | Async DB URL |
| SHOP_WHATSAPP | 2376XXXXXXXX | WhatsApp number (no `+`) |
| CREATE_TABLES | false | Create tables on startup instead of Alembic |
| SEED_PRODUCTS | true | Fill an empty products table with the 8 catalogue products on startup |
| CORS_ORIGINS | * | Comma-separated allowed origins |
| ADMIN_EMAIL / ADMIN_PASSWORD | – | Create this first administrator on startup if no admin exists |
| TOKEN_TTL_DAYS | 30 | Lifetime of a login session |

## Render

`render.yaml` is a Render Blueprint. `DATABASE_URL` (Neon) and `SHOP_WHATSAPP` come from the
`CommandeLivraisonLipaCentreGroup` environment group. On every start, `python -m app.scripts.migrate`
applies the Alembic migrations (and stamps databases that were created by `create_all`), then the
app fills an empty `products` table with the 8 catalogue products. Neon URLs with
`?sslmode=require&channel_binding=require` work as-is.

## CI/CD

- `.github/workflows/ci.yaml` — ruff check/format, mypy, pytest on every push/PR.
- `.github/workflows/cd.yaml` — builds and pushes a Docker image to GHCR on tags, and
  deploys to Render on `main`/tags.

### Render

Connect the repo via Render Blueprint (`render.yaml`). Set `DATABASE_URL` and
`SHOP_WHATSAPP` in the Render dashboard. Add `RENDER_SERVICE_ID` and `RENDER_API_KEY` as
GitHub secrets to enable the deploy job.

### Docker

```bash
docker build -t papeterie-api .
docker run -p 8000:8000 --env DATABASE_URL=... papeterie-api
```

## Migrations

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```
