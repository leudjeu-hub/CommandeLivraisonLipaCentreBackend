from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Papeterie API"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/papeterie"
    shop_whatsapp: str = "2376XXXXXXXX"
    create_tables: bool = False
    seed_products: bool = True
    cors_origins: str = "*"

    @property
    def async_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        if not url.startswith("postgresql+asyncpg://"):
            return url
        # libpq options (e.g. Neon's `?sslmode=require&channel_binding=require`) are not
        # understood by asyncpg: map sslmode to its `ssl` argument and drop the rest.
        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query):
            if key == "sslmode":
                query.append(("ssl", value))
            elif key != "channel_binding":
                query.append((key, value))
        return urlunsplit(parts._replace(query=urlencode(query)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
