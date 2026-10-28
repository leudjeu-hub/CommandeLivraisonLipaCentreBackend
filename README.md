# Papeterie API

Async FastAPI backend for *Librairie Papeterie du Centre*. It provides a product catalogue with
stock tracking, public order placement with a WhatsApp link, and customer accounts with
administrator roles. A small admin dashboard is served at `/admin`.

## Stack

- Python 3.12+, FastAPI, and Uvicorn
- SQLAlchemy 2 async with PostgreSQL (`asyncpg`) or SQLite (`aiosqlite`)
- Pydantic v2 and pydantic-settings
- Alembic migrations
- Scrypt password hashing and hashed bearer tokens (standard library only)
- pytest, pytest-asyncio, and httpx
- Ruff and mypy
- uv for dependency and virtual-environment management

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL only for a shared or production database; SQLite is used for local development
- Docker, only if you want to build the container image

## Quick start

Run every command from the repository root. Imports are absolute (`from app...`), so the app must
be started from this directory.

### Windows (PowerShell)

```powershell
uv sync
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload
```

### macOS / Linux (bash or zsh)

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload
```

The API listens at <http://localhost:8000>. Interactive documentation is at
<http://localhost:8000/docs>, and the admin dashboard is at <http://localhost:8000/admin>.

On the first start with an empty SQLite database, the app creates the schema and seeds the eight
built-in catalogue products automatically. See [Database](#database) for the exact rules.

## Configuration

Settings are read from environment variables or the repository-root `.env` file. Environment
variables take precedence over `.env`. Keep `.env` and production credentials out of version
control.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | Database connection URL. Local development defaults to SQLite; set a PostgreSQL URL in production. |
| `SHOP_WHATSAPP` | `2376XXXXXXXX` | Shop WhatsApp number, without `+`, used to build order links |
| `CREATE_TABLES` | `false` | Create missing tables at startup via `metadata.create_all`; intended for development, not production |
| `SEED_PRODUCTS` | `true` | Seed the eight built-in products if the products table is empty |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed browser origins; `*` allows all |
| `TOKEN_TTL_DAYS` | `30` | Lifetime of a login token |
| `ADMIN_EMAIL` | Unset | Optional first administrator's email |
| `ADMIN_PASSWORD` | Unset | Optional first administrator's password; remove after bootstrap |

`SHOP_WHATSAPP` is not a secret but must be set for order responses to contain a usable
`whatsapp_url`.

## Database

### Local SQLite

SQLite is the default, so no database server is needed:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./dev.db
```

Startup behaviour for SQLite:

1. If the database has no tables, the schema is created automatically.
2. If `SEED_PRODUCTS=true` (the default) and the products table is empty, the catalogue is seeded.
3. If `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set and no administrator exists, that account is
   created.

`CREATE_TABLES=true` forces `metadata.create_all` on every start (it adds missing tables). Leave
it `false` in production and use migrations. To reset local data, stop the API and delete
`dev.db`; it is recreated and seeded on the next start.

### PostgreSQL

For a shared or production database, use the async driver URL:

```dotenv
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database
```

Plain `postgres://` and `postgresql://` URLs are rewritten to `postgresql+asyncpg://` at runtime.
Neon/libpq `sslmode` is translated to asyncpg's `ssl` argument and `channel_binding` is dropped.

### Migrations

Apply the schema to a new or existing database:

```bash
uv run alembic upgrade head
```

After changing SQLAlchemy models, generate and review a migration before applying it:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

For deployments, run the wrapper that stamps databases previously created with
`CREATE_TABLES=true` before upgrading:

```bash
uv run python -m app.scripts.migrate
```

Alembic reads `DATABASE_URL` through `app.core.config.get_settings()`, so the same `.env` or
environment variables apply to migrations.

## Product catalogue

When `SEED_PRODUCTS=true` (the default), startup inserts the eight built-in products only if the
`products` table is empty. Existing products are never overwritten.

To import or update the full catalogue from the companion frontend repository's CSV (upsert by
product ID; stock is left unchanged):

```powershell
# Windows
uv run python -m app.scripts.import_catalogue ..\CommandeLivraisonLipaCentre\catalogue\catalogue.csv
```

```bash
# macOS / Linux
uv run python -m app.scripts.import_catalogue ../CommandeLivraisonLipaCentre/catalogue/catalogue.csv
```

If startup logs `Skipping product seeding: database unavailable`, the app could not reach the
database. Check `DATABASE_URL`, make sure the database is running, and apply migrations (or set
`CREATE_TABLES=true` locally). The app logs the underlying exception and keeps starting, so the
health endpoint may still respond while database-backed routes fail.

## Administrators

Create an administrator interactively, or promote an existing account (the password is not
changed when the account already exists):

```bash
uv run python -m app.scripts.create_admin admin@example.com
```

The script prompts for a password of at least 8 characters. Set `ADMIN_PASSWORD` to skip the
prompt, for example on a server.

For deployments without shell access, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` and let startup create
the first administrator. It only runs while no administrator exists; if the email belongs to an
existing account, that account is promoted without a password change. Remove `ADMIN_PASSWORD`
once the account exists. Further administrators can be promoted from `/admin` or with
`PATCH /users/{user_id}/role`.

## API endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/` | Public | Health check |
| GET | `/docs` | Public | Interactive API documentation |
| GET | `/admin` | Public page | Admin dashboard (logs in through the API) |
| GET | `/products/` | Public | List products |
| GET | `/products/{product_id}` | Public | Get a product |
| POST | `/products/` | Manager, admin | Create a product |
| PUT | `/products/{product_id}` | Manager, admin | Update a product |
| DELETE | `/products/{product_id}` | Manager, admin | Delete a product |
| POST | `/orders/` | Admin | Place an order (takes stock); the response includes a WhatsApp link |
| POST | `/orders/submit` | Public | Record an order or quote from the site's form (no stock taken, 60/hour site-wide) |
| GET | `/orders/` | Manager, admin | List orders, newest first (`?status=new` to filter); first deletes orders cancelled more than 30 days ago or delivered more than 12 months ago |
| GET | `/orders/{order_id}` | Manager, admin | Get an order |
| PATCH | `/orders/{order_id}/status` | Manager, admin | Update an order status; once `delivered`, admin only (403 for a manager) |
| POST | `/auth/register` | Public | Create a customer account and sign in |
| POST | `/auth/login` | Public | Sign in |
| POST | `/auth/logout` | Signed in | Revoke the current token |
| GET | `/auth/me` | Signed in | Get the current account |
| GET | `/users/` | Admin | List accounts |
| PATCH | `/users/{user_id}/role` | Admin | Promote or demote an account |

Send the login token in the `Authorization: Bearer <token>` header. Missing or invalid tokens
receive `401`; a signed-in customer attempting an admin-only operation receives `403`.

Accounts have a `user` or `admin` role. The last administrator cannot be demoted. Orders contain
customer contact details: managers and administrators read them and change their status, and
only administrators use `POST /orders/`, which takes stock (left public,
anyone could empty it). The one exception is `POST /orders/submit`: the site's form records each
order or quote there (delivery area, address, slot, payment, notes, fee shown to the customer) and the
customer still sends it by WhatsApp or e-mail; it takes no stock, uses catalogue prices, and answers
`429` after 60 orders within an hour (site-wide). After 10 wrong
passwords for one e-mail within 15 minutes, `/auth/login` answers `429` for that e-mail; after 30
new accounts within an hour (site-wide), `/auth/register` answers `429`. Responses
over 1 KB are gzipped (the full catalogue drops from ~470 KB to ~40 KB). Order statuses are `new`, `confirmed`, `delivered`, and
`cancelled`.

Example order body:

```json
{
  "customer_name": "Awa",
  "phone": "2376XXXXXXXX",
  "items": [
    { "product_id": 1, "quantity": 2 },
    { "product_id": 6, "quantity": 1 }
  ]
}
```

Order creation decrements product stock and computes the total in the same transaction. If a
product is missing or has insufficient stock, the order is rejected.

## Project layout

```text
app/
  main.py            FastAPI app, lifespan, CORS, error handler, admin page
  core/              Settings, async engine/session, dependencies, errors, security
  models/            SQLAlchemy models: Product, Order, OrderItem, User, AuthToken
  schemas/           Pydantic v2 request/response models
  services/          Product, order, and auth services; seeding and admin bootstrap
  routers/           HTTP endpoints for products, orders, auth, and users
  scripts/           create_admin, import_catalogue, migrate
  static/admin.html  Admin dashboard
  utils/whatsapp.py  WhatsApp deep-link builder
alembic/             Migration environment and versions
tests/               pytest suite (SQLite, no external database)
```

## Tests, lint, and type checking

Tests use SQLite and do not require an external database:

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check .
uv run ruff format .
uv run mypy app
```

`uv sync` installs runtime and development dependencies by default. Use `uv sync --no-dev` for a
production-only environment.

## Deployment

### Render

`render.yaml` defines a Render Blueprint. The start command runs
`python -m app.scripts.migrate` before Uvicorn, so migrations are applied on every start, and the
app then seeds an empty products table. The blueprint expects a Render environment group named
`CommandeLivraisonLipaCentreGroup` containing `DATABASE_URL` and `SHOP_WHATSAPP`.

For GitHub Actions deployment, configure `RENDER_SERVICE_ID` and `RENDER_API_KEY` as GitHub
Actions secrets.

### Docker

The image installs production dependencies only and runs Uvicorn. It does not run migrations, so
apply them before or at container start.

Windows (PowerShell):

```powershell
docker build -t papeterie-api .
$env:DATABASE_URL = "your-database-url"
docker run -p 8000:8000 --env "DATABASE_URL=$env:DATABASE_URL" papeterie-api
```

macOS / Linux:

```bash
docker build -t papeterie-api .
export DATABASE_URL="your-database-url"
docker run -p 8000:8000 -e DATABASE_URL="$DATABASE_URL" papeterie-api
```

Add `SHOP_WHATSAPP` the same way. For a SQLite container without migrations, set
`CREATE_TABLES=true` and mount a volume if the database must survive container replacement.

### CI/CD

- CI (`.github/workflows/ci.yaml`) runs on pushes to `main` and pull requests: Ruff check and
  format check, mypy, then pytest with coverage.
- CD (`.github/workflows/cd.yaml`) runs on `v*` tags and manual dispatch: it builds and pushes an
  image to `ghcr.io/<owner>/<repository>`, then deploys to Render for tags or manual runs on
  `main` when the required secrets are set.
