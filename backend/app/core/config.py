from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "pet-platform-backend"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    max_request_body_bytes: int = Field(default=12_000_000, ge=1024, le=20_000_000)
    pet_asset_max_bytes: int = Field(default=10_485_760, ge=1024, le=15_000_000)
    metrics_bearer_token: str | None = None
    security_hsts_enabled: bool = False

    database_url: str = "postgresql+asyncpg://pet_platform:pet_platform@localhost:5432/pet_platform"
    redis_url: str = "redis://localhost:6379/0"
    media_root: Path = Path("./media")

    jwt_secret: str = Field(default="development-only-change-me-please-32-chars")
    webhook_secret: str = Field(default="development-only-change-me-please-32-chars")

    # Policy boundaries. Defaults retain K8 runtime behavior; product decisions remain external.
    currency_code: Literal["IRR"] = "IRR"
    customer_display_currency_code: Literal["IRR"] = "IRR"
    customer_display_unit: Literal["TOMAN"] = "TOMAN"
    irr_per_customer_display_unit: int = Field(default=10, ge=1, le=10_000)
    delivery_commitment_hours: int = Field(default=366, ge=1, le=720)
    late_credit_enabled: bool = False
    late_credit_customer_visible: bool = False
    late_credit_basis_points: int = Field(default=500, ge=0, le=10_000)
    late_credit_expiry_months: int = Field(default=3, ge=1, le=60)
    full_payment_only: bool = True
    reserve_now_enabled: bool = False
    cancel_after_sourcing_enabled: bool = False
    refund_self_service_enabled: bool = False
    replacement_self_service_enabled: bool = False
    substitution_self_service_enabled: bool = False
    delay_compensation_customer_visible: bool = False
    availability_subscriptions_enabled: bool = True
    concierge_requests_enabled: bool = True
    care_journey_delivery_enabled: bool = True
    push_notifications_enabled: bool = False
    semantic_level_estimation_enabled: bool = True
    reorder_safety_buffer_days: int | None = Field(default=3, ge=0, le=30)
    reorder_snooze_early_break_worsening_days: int = Field(default=2, ge=1, le=30)
    customer_request_acknowledgement_fa: str = (
        "درخواست شما ثبت شد. نتیجه بررسی از طریق پیامک یا داخل برنامه اطلاع‌رسانی می‌شود. "
        "ثبت درخواست به‌معنای تضمین موجودی، قیمت، زمان پاسخ یا تأمین نیست."
    )
    pet_health_consent_policy_version: str = Field(default="1.0", min_length=1, max_length=50)
    storage_backend: Literal["filesystem"] = "filesystem"

    zarinpal_sandbox: bool = True
    zarinpal_merchant_id: str | None = None
    zarinpal_timeout_seconds: float = Field(default=15, gt=0, le=60)

    payamak_panel_username: str | None = None
    payamak_panel_password: str | None = None
    payamak_panel_sender_number: str | None = None
    payamak_panel_timeout_seconds: float = Field(default=15, gt=0, le=60)
    # Local/CI convenience only: when no SMS provider is configured and this is
    # enabled, OTP codes are logged to the server console instead of failing
    # closed with otp_provider_not_configured. The OTP itself, its hash, TTL,
    # attempt-locking, and consumption are entirely unchanged -- only the
    # delivery channel is swapped for a log line. Refused outright in
    # production (see validate_production_secrets below).
    otp_dev_console_fallback_enabled: bool = False
    otp_pepper: str = Field(default="development-only-otp-pepper-change-me")
    otp_ttl_seconds: int = Field(default=120, ge=60, le=600)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=30, le=300)
    otp_max_attempts: int = Field(default=5, ge=3, le=10)
    access_token_ttl_seconds: int = Field(default=900, ge=300, le=3600)
    refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=86_400, le=7_776_000)
    otp_ip_limit_per_10_minutes: int = Field(default=10, ge=1, le=100)
    otp_mobile_limit_per_10_minutes: int = Field(default=5, ge=1, le=50)
    otp_device_limit_per_10_minutes: int = Field(default=5, ge=1, le=50)

    outbox_batch_size: int = Field(default=50, ge=1, le=500)
    outbox_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    scheduler_poll_seconds: float = Field(default=5.0, gt=0, le=60)

    # Petmall Armenia price intelligence
    price_intelligence_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (compatible; PetPlatformBot/1.0; +https://petplatform.ir/bot)"
        )
    )
    price_intelligence_request_delay_seconds: float = Field(default=2.0, ge=0.5, le=10.0)
    price_intelligence_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    price_intelligence_max_retries: int = Field(default=3, ge=1, le=10)
    price_intelligence_max_pages: int = Field(default=50, ge=1, le=500)
    price_intelligence_max_products_per_run: int = Field(default=500, ge=1, le=5000)
    price_intelligence_max_response_bytes: int = Field(default=1_000_000, ge=10_000, le=5_000_000)
    price_intelligence_robots_required: bool = True
    price_intelligence_terms_required: bool = True
    price_intelligence_collection_enabled: bool = False

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.app_env == "production":
            secrets = (self.jwt_secret, self.webhook_secret, self.otp_pepper)
            weak = any(
                marker in secret
                for secret in secrets
                for marker in ("development-only", "replace-with")
            )
            if weak or any(len(secret) < 32 for secret in secrets):
                raise ValueError("production secrets must be unique and at least 32 characters")
            if not self.metrics_bearer_token or len(self.metrics_bearer_token) < 32:
                raise ValueError("production metrics bearer token must be at least 32 characters")
            if self.otp_dev_console_fallback_enabled:
                raise ValueError(
                    "otp_dev_console_fallback_enabled must never be set in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
