"""Typed application settings with compatibility-safe lifecycle accessors.

Startup-stable infrastructure reads through cached :func:`get_settings`, while
historically runtime-observable boundaries use uncached :func:`load_settings`.
The absolute ``backend/.env`` location keeps both paths independent of the
process working directory, and business modules never read the environment
directly.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import socket

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'girlfriend_menu.db'}"
DEFAULT_CUSTOMER_SESSION_TTL_DAYS = 90
TRUE_VALUES = frozenset({"1", "true", "yes"})


class Settings(BaseSettings):
    """Model every existing backend environment variable without renaming it."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_default=True,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    database_url: SecretStr = Field(
        default=SecretStr(DEFAULT_DATABASE_URL),
        validation_alias="DATABASE_URL",
    )
    frontend_url: str = Field(default="", validation_alias="FRONTEND_URL")

    admin_password: SecretStr | None = Field(
        default=None,
        validation_alias="ADMIN_PASSWORD",
    )
    admin_invite_code: SecretStr | None = Field(
        default=None,
        validation_alias="ADMIN_INVITE_CODE",
    )
    admin_secret: SecretStr | None = Field(
        default=None,
        validation_alias="ADMIN_SECRET",
    )
    admin_token_version: str = Field(default="1", validation_alias="ADMIN_TOKEN_VERSION")

    customer_invite_code: SecretStr | None = Field(
        default=None,
        validation_alias="CUSTOMER_INVITE_CODE",
    )
    customer_session_ttl_days_raw: str = Field(
        default=str(DEFAULT_CUSTOMER_SESSION_TTL_DAYS),
        validation_alias="CUSTOMER_SESSION_TTL_DAYS",
        repr=False,
    )
    allow_legacy_customer_header_raw: str = Field(
        default="false",
        validation_alias="ALLOW_LEGACY_CUSTOMER_HEADER",
        repr=False,
    )

    upload_provider: str = Field(default="local", validation_alias="UPLOAD_PROVIDER")
    s3_endpoint: str = Field(default="", validation_alias="S3_ENDPOINT")
    s3_region: str = Field(default="", validation_alias="S3_REGION")
    s3_bucket: str = Field(default="", validation_alias="S3_BUCKET")
    s3_access_key_id: SecretStr | None = Field(
        default=None,
        validation_alias="S3_ACCESS_KEY_ID",
    )
    s3_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias="S3_SECRET_ACCESS_KEY",
    )
    s3_public_base_url: str = Field(default="", validation_alias="S3_PUBLIC_BASE_URL")

    redis_url: SecretStr | None = Field(default=None, validation_alias="REDIS_URL")
    game_room_lease_seconds_raw: str = Field(
        default="30",
        validation_alias="GAME_ROOM_LEASE_SECONDS",
        repr=False,
    )
    game_instance_id: str = Field(default="", validation_alias="GAME_INSTANCE_ID")
    render_instance_id: str = Field(default="", validation_alias="RENDER_INSTANCE_ID")

    loveos_tracing_enabled_raw: str = Field(
        default="false",
        validation_alias="LOVEOS_TRACING_ENABLED",
        repr=False,
    )
    loveos_tracing_console_raw: str = Field(
        default="false",
        validation_alias="LOVEOS_TRACING_CONSOLE",
        repr=False,
    )
    otel_sdk_disabled_raw: str = Field(
        default="false",
        validation_alias="OTEL_SDK_DISABLED",
        repr=False,
    )
    otel_service_name: str = Field(
        default="loveos-backend",
        validation_alias="OTEL_SERVICE_NAME",
    )

    db_pool_size_raw: str = Field(default="5", validation_alias="DB_POOL_SIZE", repr=False)
    db_max_overflow_raw: str = Field(
        default="10",
        validation_alias="DB_MAX_OVERFLOW",
        repr=False,
    )
    db_pool_timeout_raw: str = Field(
        default="30",
        validation_alias="DB_POOL_TIMEOUT",
        repr=False,
    )
    db_pool_recycle_raw: str = Field(
        default="1800",
        validation_alias="DB_POOL_RECYCLE",
        repr=False,
    )

    @staticmethod
    def _secret_value(value: SecretStr | None) -> str:
        """Return a secret only at the boundary that actually needs it."""
        return value.get_secret_value() if value is not None else ""

    @property
    def normalized_database_url(self) -> str:
        """Preserve the legacy PostgreSQL scheme normalization exactly."""
        value = self.database_url.get_secret_value()
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value

    @property
    def db_pool_size(self) -> int:
        """Parse the pool size only when a non-SQLite engine needs it."""
        return max(1, int(self.db_pool_size_raw))

    @property
    def db_max_overflow(self) -> int:
        """Preserve the existing non-negative overflow bound."""
        return max(0, int(self.db_max_overflow_raw))

    @property
    def db_pool_timeout(self) -> int:
        """Preserve the existing five-second minimum pool timeout."""
        return max(5, int(self.db_pool_timeout_raw))

    @property
    def db_pool_recycle(self) -> int:
        """Preserve the existing five-minute minimum recycle interval."""
        return max(300, int(self.db_pool_recycle_raw))

    @property
    def customer_session_ttl_days(self) -> int:
        """Keep invalid TTL fallback and the existing 1..365 day bounds."""
        try:
            days = int(self.customer_session_ttl_days_raw)
        except ValueError:
            days = DEFAULT_CUSTOMER_SESSION_TTL_DAYS
        return min(max(days, 1), 365)

    @property
    def game_room_lease_seconds(self) -> int:
        """Keep the existing lease minimum and invalid-value failure behavior."""
        return max(15, int(self.game_room_lease_seconds_raw))

    @property
    def allow_legacy_customer_header(self) -> bool:
        """Parse the same explicit true values as the legacy dependency."""
        return self.allow_legacy_customer_header_raw.lower() in TRUE_VALUES

    @property
    def is_production(self) -> bool:
        """Report whether the current environment uses production behavior."""
        return self.app_env.lower() == "production"

    @property
    def upload_provider_name(self) -> str:
        """Normalize the provider exactly where the old storage boundary did."""
        return self.upload_provider.strip().lower()

    @property
    def frontend_origins(self) -> list[str]:
        """Parse the optional browser allow-list without affecting mini programs."""
        return [
            url.strip().rstrip("/")
            for url in self.frontend_url.split(",")
            if url.strip()
        ]

    @property
    def tracing_enabled(self) -> bool:
        """Require an explicit app opt-in while honoring the standard SDK kill switch."""
        requested = self.loveos_tracing_enabled_raw.lower() == "true"
        sdk_disabled = self.otel_sdk_disabled_raw.lower() == "true"
        return requested and not sdk_disabled

    @property
    def tracing_console_enabled(self) -> bool:
        """Allow console export only through a second explicit development opt-in."""
        return self.loveos_tracing_console_raw.lower() == "true"

    @property
    def tracing_service_name(self) -> str:
        """Return a low-cardinality standard service name with a safe fallback."""
        return self.otel_service_name.strip()[:100] or "loveos-backend"

    @property
    def redis_url_value(self) -> str:
        """Expose the optional Redis URL only to cache/rate-limit adapters."""
        return self._secret_value(self.redis_url).strip()

    @property
    def admin_password_value(self) -> str:
        """Expose the admin password without making it startup-required."""
        return self._secret_value(self.admin_password)

    @property
    def admin_invite_code_value(self) -> str:
        """Expose the admin invite only at the login boundary."""
        return self._secret_value(self.admin_invite_code)

    @property
    def customer_invite_code_value(self) -> str:
        """Expose the customer invite only when a session is created/recovered."""
        return self._secret_value(self.customer_invite_code)

    @property
    def s3_access_key_id_value(self) -> str:
        """Expose the S3 access key only while constructing the storage client."""
        return self._secret_value(self.s3_access_key_id)

    @property
    def s3_secret_access_key_value(self) -> str:
        """Expose the S3 secret only while constructing the storage client."""
        return self._secret_value(self.s3_secret_access_key)

    def require_admin_secret(self) -> str:
        """Fail only when admin token signing/verification actually needs the secret."""
        secret = self._secret_value(self.admin_secret)
        if len(secret) < 16:
            raise RuntimeError("ADMIN_SECRET must contain at least 16 characters")
        return secret

    def resolved_game_instance_id(self) -> str:
        """Build the same explicit-or-host process identifier used by room leases."""
        return self.game_instance_id.strip() or (
            f"{self.render_instance_id or socket.gethostname()}:{os.getpid()}"
        )


def load_settings() -> Settings:
    """Load a fresh snapshot for values historically read at call/request time."""
    return Settings(_env_file=ENV_FILE)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached snapshot for startup-stable infrastructure settings."""
    return load_settings()


def reset_settings_cache() -> None:
    """Clear settings between tests or explicit environment reconfiguration."""
    get_settings.cache_clear()
