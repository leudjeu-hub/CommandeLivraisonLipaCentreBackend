from app.core.config import Settings


def test_neon_url_is_converted_for_asyncpg() -> None:
    settings = Settings(
        database_url=(
            "postgresql://user:p%40ss@ep-x.eu-central-1.aws.neon.tech/neondb"
            "?sslmode=require&channel_binding=require"
        )
    )
    assert settings.async_database_url == (
        "postgresql+asyncpg://user:p%40ss@ep-x.eu-central-1.aws.neon.tech/neondb?ssl=require"
    )


def test_postgres_scheme_is_rewritten() -> None:
    settings = Settings(database_url="postgres://u:p@localhost:5432/db")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@localhost:5432/db"


def test_sqlite_url_is_untouched() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
    assert settings.async_database_url == "sqlite+aiosqlite:///./test.db"
