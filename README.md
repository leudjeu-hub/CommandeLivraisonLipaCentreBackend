# Papeterie API

Async FastAPI backend for *Librairie Papeterie du Centre*. It provides a product catalogue,
order management, and customer accounts with administrator roles.

## Stack

- Python, FastAPI, and Uvicorn
- SQLAlchemy 2 async with PostgreSQL (`asyncpg`) or SQLite (`aiosqlite`)
- Pydantic v2 and pydantic-settings
- Alembic database migrations
- pytest, pytest-asyncio, and httpx
- Ruff and mypy
- uv for dependency and virtual-environment management

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL for a shared or production database; SQLite is suitable for local development

## Local development on Windows

Run these commands from the repository root in PowerShell:

```powershell
uv sync
Copy-Item .env.example .env
```

Open `.env` and configure the database. For a local SQLite database, use:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./dev.db
CREATE_TABLES=true
```

`CREATE_TABLES=true` creates missing tables at application startup. Alternatively, leave it
`false` and use Alembic migrations as described below. Do not enable `CREATE_TABLES` in
production; apply migrations instead.

Set `SHOP_WHATSAPP` to the shop's WhatsApp number without a leading `+`, then start the API:

```powershell
uv run uvicorn app.main:app --reload
```

The API listens at <http://localhost:8000>. Interactive API documentation is at
<http://localhost:8000/docs>.

### Product catalogue seeding

When `SEED_PRODUCTS=true` (the default), startup adds the eight built-in catalogue products only
if the `products` table is empty. It does not overwrite or update existing products.

If startup logs `Skipping product seeding: database unavailable`, the app could not query the
database while attempting to seed. Check that `DATABASE_URL` points to the intended database,
that the database is running and reachable, and that its schema has been created. With
`CREATE_TABLES=false`, apply migrations before starting the app:

```powershell
uv run alembic upgrade head
```

The app logs the underlying database exception and continues starting, so the health endpoint
may still respond even when database-backed routes are unavailable.

## Database migrations

For a new or existing database with `CREATE_TABLES=false`, apply the schema:

```powershell
uv run alembic upgrade head
```

After changing SQLAlchemy models, generate and review a migration before applying it:

```powershell
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

For databases initially created using `CREATE_TABLES=true`, the deployment migration script
stamps the existing schema before applying any newer migrations.

## Importing the full catalogue

To import or update products from the companion frontend repository's catalogue CSV, run from
this repository's root:

```powershell
uv run python -m app.scripts.import_catalogue ..\CommandeLivraisonLipaCentre\catalogue\catalogue.csv
```

The import upserts by product ID and leaves stock unchanged.

## First administrator

Create an administrator interactively from a machine that can connect to the database:

```powershell
uv run python -m app.scripts.create_admin admin@example.com
```

For a deployment without shell access, set `ADMIN_EMAIL` and `ADMIN_PASSWORD`. At startup, the
app creates that administrator only if no administrator exists; if an account with that email
already exists, it promotes the account without changing its password. Remove
`ADMIN_PASSWORD` after the administrator has been created.

## API endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/` | Public | Health check |
| GET | `/admin` | Page | Serve the admin page |
| GET | `/products/` | Public | List products |
| GET | `/products/{product_id}` | Public | Get a product |
| POST | `/products/` | Admin | Create a product |
| PUT | `/products/{product_id}` | Admin | Update a product |
| DELETE | `/products/{product_id}` | Admin | Delete a product |
| POST | `/orders/` | Public | Place an order; response includes a WhatsApp link |
| GET | `/orders/` | Admin | List orders |
| GET | `/orders/{order_id}` | Admin | Get an order |
| PATCH | `/orders/{order_id}/status` | Admin | Update an order status |
| POST | `/auth/register` | Public | Create a customer account and sign in |
| POST | `/auth/login` | Public | Sign in |
| POST | `/auth/logout` | Signed in | Revoke the current token |
| GET | `/auth/me` | Signed in | Get the current account |
| GET | `/users/` | Admin | List accounts |
| PATCH | `/users/{user_id}/role` | Admin | Promote or demote an account |

Send the login token in the `Authorization: Bearer <token>` header. Missing or invalid tokens
receive `401`; a signed-in customer attempting an admin-only operation receives `403`. Order
creation is public and does not require an account. Order listing and retrieval are admin-only
because order records contain customer contact details.

## Configuration

Settings are read from environment variables or the repository-root `.env` file.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | Local PostgreSQL URL | Database connection URL. Use `sqlite+aiosqlite:///./dev.db` for local SQLite. |
| `SHOP_WHATSAPP` | `2376XXXXXXXX` | Shop WhatsApp number, without `+`, used to build order links |
| `CREATE_TABLES` | `false` | Create tables at startup; intended for development, not production |
| `SEED_PRODUCTS` | `true` | Seed the built-in products if the products table is empty |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `TOKEN_TTL_DAYS` | `30` | Lifetime of a login token |
| `ADMIN_EMAIL` | Unset | Optional first administrator's email |
| `ADMIN_PASSWORD` | Unset | Optional first administrator's password; remove after bootstrap |

Keep `.env` and production credentials out of version control.

## Tests, lint, and type checking

Tests use SQLite and do not require an external database:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## Deployment

`render.yaml` defines a Render Blueprint. The Render startup command runs
`python -m app.scripts.migrate` to apply Alembic migrations, then the app seeds an empty product
table. Configure `DATABASE_URL` and `SHOP_WHATSAPP` in the Render environment. PostgreSQL URLs
with `sslmode` and `channel_binding` parameters are supported.

For GitHub Actions deployment to Render, configure `RENDER_SERVICE_ID` and `RENDER_API_KEY` as
GitHub Actions secrets.

Build and run the Docker image with:

```powershell
docker build -t papeterie-api .
$env:DATABASE_URL = "your-database-url"
docker run -p 8000:8000 --env "DATABASE_URL=$env:DATABASE_URL" papeterie-api
```

The CI workflow runs Ruff, mypy, and pytest. The CD workflow builds and publishes Docker images
to GHCR and deploys to Render on its configured branches and tags.
