from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Papeterie API"
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    shop_whatsapp: str = "2376XXXXXXXX"
    create_tables: bool = False
    seed_products: bool = True
    cors_origins: str = "*"
    # Lifetime of a login session (bearer token).
    token_ttl_days: int = 30
    # First administrator, created on startup when both are set and no admin exists yet.
    admin_email: str | None = None
    admin_password: SecretStr | None = None
    # Forgotten password: the e-mailed link opens this site page (token in the URL fragment).
    site_url: str = "https://leudjeu-hub.github.io/CommandeLivraisonLipaCentre"
    password_reset_ttl_minutes: int = 30
    # E-mails go out through Brevo's HTTP API (Render's free plan blocks SMTP ports). Without a
    # key nothing is sent and a warning is logged.
    brevo_api_key: SecretStr | None = None
    mail_from: str = "Lipacentre237@gmail.com"
    mail_from_name: str = "LipaCentre"

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
