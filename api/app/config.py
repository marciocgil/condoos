"""Application settings. Every secret comes from environment variables only."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Database. The API connects as a non-superuser role subject to Row-Level Security;
    # migrations and seed run with the owner role; the worker uses a BYPASSRLS role.
    database_url: str = "postgresql+asyncpg://condoos_app:condoos_app@localhost:5432/condoos"
    database_admin_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/condoos"
    database_worker_url: str = (
        "postgresql+asyncpg://condoos_worker:condoos_worker@localhost:5432/condoos"
    )

    # Auth
    web_base_url: str = "http://localhost:3000"
    magic_link_ttl_minutes: int = 15
    magic_link_max_per_hour: int = 5
    session_ttl_days: int = 14
    session_cookie_name: str = "condoos_session"
    session_cookie_secure: bool = False

    # Mail
    mailer: Literal["smtp", "console", "memory"] = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    mail_from: str = "CondoOS <nao-responda@condoos.local>"

    # Object storage (S3-compatible)
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_public_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "condoos-documents"
    s3_access_key_id: SecretStr = SecretStr("condoos")
    s3_secret_access_key: SecretStr = SecretStr("condoos-secret")
    s3_presign_ttl_seconds: int = 300
    storage_backend: Literal["s3", "memory"] = "s3"
    max_upload_mb: int = 20

    # Inbound e-mail: <slug>@<ingest_email_domain>. The folder provider reads .eml files.
    ingest_email_domain: str = "ingest.condoos.local"
    inbound_email_dir: str | None = None
    inbound_email_poll_seconds: float = 30.0

    # LLM (used from milestone 2 on)
    anthropic_api_key: SecretStr | None = None
    claude_model_extraction: str = "claude-sonnet-5-5"
    claude_model_reasoning: str = "claude-opus-5-5"
    claude_model_fast: str = "claude-haiku-5-5"
    # live: call the API (needs a key) · replay: recorded responses only · record: live and
    # save responses · off: never call. Default (None): live with a key, replay without.
    llm_mode: Literal["live", "replay", "record", "off"] | None = None
    llm_cassette_dir: str = "tests/fixtures/llm"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3
    llm_monthly_budget_usd_per_condominium: float = 40.0

    # PDF/image -> text. auto: Docling when installed (OCR, tables), else pypdfium2 (text PDFs).
    document_converter: Literal["auto", "docling", "pdfium"] = "auto"
    # Max characters of document text sent to the model (larger documents go as files).
    llm_max_text_chars: int = 60000

    # Data retention (years) for fiscal documents.
    retention_years_fiscal: int = 5

    # Development helpers
    seed_on_start: bool = False
    worker_poll_interval_seconds: float = Field(default=1.0, ge=0.05)


@lru_cache
def get_settings() -> Settings:
    return Settings()
