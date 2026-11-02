"""Application settings, loaded from environment variables and apps/api/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = API_DIR.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # Storage
    database_url: str = f"sqlite:///{(API_DIR / 'culpa.db').as_posix()}"
    redis_url: str = ""

    # Queue: "auto" uses Redis when REDIS_URL is reachable, otherwise processes the outbox in-process.
    queue_mode: str = "auto"
    run_workers_in_process: bool = True
    reconcile_interval_s: int = 900

    # PayPal
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_env: str = "sandbox"
    allow_unverified_webhooks: bool = False

    # Google Gemini (aistudio.google.com > Get API key). Both models must be ones the key can use.
    gemini_api_key: str = ""
    llm_judge_model: str = "gemini-3.5-flash"
    llm_fast_model: str = "gemini-3.5-flash-lite"
    llm_timeout_s: float = 60.0
    # Fixed sampling temperature for repeatable answers.
    llm_temperature: float = 0.0

    # Security
    mandate_signing_secret: str = "dev-only-change-me"
    # The single dispute-console account, created (or its password updated) in the database at startup.
    # Leave both empty in local development to keep the console open without a login.
    analyst_username: str = ""
    analyst_password: str = ""
    session_ttl_hours: int = 12
    web_origin: str = "http://127.0.0.1:3000,http://localhost:3000"

    # URLs used to build PayPal return links
    public_api_url: str = "http://127.0.0.1:8000"
    public_web_url: str = "http://127.0.0.1:3000"

    # Settlement policy
    auto_settle: bool = False
    confidence_threshold: float = 0.8
    agent_provider_name: str = "Culpa Demo Agent"

    bench_dir: str = str(REPO_DIR / "bench")

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def paypal_base_url(self) -> str:
        if self.paypal_env == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
