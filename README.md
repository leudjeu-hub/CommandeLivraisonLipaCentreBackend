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
| GET | /products/ | List products (sorted by name) |
| GET | /products/{id} | Get one product |
| POST | /products/ | Create product |
| PUT | /products/{id} | Update product |
| DELETE | /products/{id} | Delete product |
| POST | /orders/ | Create order (decrements stock, returns `whatsapp_url`) |
| GET | /orders/ | List orders (newest first) |
| GET | /orders/{id} | Get one order |
| PATCH | /orders/{id}/status | Set status: new, confirmed, delivered, cancelled |

## Configuration

| Env var | Default | Description |
|---|---|---|
| DATABASE_URL | postgresql+asyncpg://postgres:postgres@localhost:5432/papeterie | Async DB URL |
| SHOP_WHATSAPP | 2376XXXXXXXX | WhatsApp number (no `+`) |
| CREATE_TABLES | false | Create tables on startup instead of Alembic |
| SEED_PRODUCTS | true | Fill an empty products table with the 8 catalogue products on startup |
| CORS_ORIGINS | * | Comma-separated allowed origins |

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
