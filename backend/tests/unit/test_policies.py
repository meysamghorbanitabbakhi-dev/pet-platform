import pytest
from app.core.config import Settings
from app.core.policies import LaunchPolicies
from pydantic import ValidationError


def test_policy_defaults_preserve_k8_behavior() -> None:
    policies = LaunchPolicies.from_settings(Settings(_env_file=None))

    assert policies.currency_code == "IRR"
    assert policies.customer_display_currency_code == "IRR"
    assert policies.customer_display_unit == "TOMAN"
    assert policies.irr_per_customer_display_unit == 10
    assert policies.delivery_commitment_hours == 366
    assert policies.late_credit_enabled is False
    assert policies.late_credit_customer_visible is False
    assert policies.late_credit_basis_points == 500
    assert policies.late_credit_expiry_months == 3
    assert policies.wallet_consumption_order == "earliest_expiry_first"
    assert policies.full_payment_only is True
    assert policies.reserve_now_enabled is False
    assert policies.cancel_after_sourcing_enabled is False
    assert policies.refund_self_service_enabled is False
    assert policies.replacement_self_service_enabled is False
    assert policies.substitution_self_service_enabled is False
    assert policies.delay_compensation_customer_visible is False
    assert policies.availability_subscriptions_enabled is True
    assert policies.concierge_requests_enabled is True
    assert policies.care_journey_delivery_enabled is True
    assert policies.push_notifications_enabled is False
    assert policies.semantic_level_estimation_enabled is True
    assert policies.reorder_safety_buffer_days == 3
    assert policies.reorder_snooze_early_break_worsening_days == 2
    assert policies.replenishment_reservation_enabled is False
    assert policies.replenishment_reservation_lead_days == 14
    assert policies.replenishment_reservation_approval_window_hours == 48
    assert policies.concierge_offers_enabled is False
    assert policies.concierge_offer_default_validity_hours == 24
    assert "تضمین موجودی" in policies.customer_request_acknowledgement_fa
    assert policies.storage_backend == "filesystem"


def test_policy_configuration_has_bounded_overrides() -> None:
    policies = LaunchPolicies.from_settings(
        Settings(
            _env_file=None,
            delivery_commitment_hours=336,
            late_credit_enabled=True,
            reserve_now_enabled=True,
        )
    )
    assert policies.delivery_commitment_hours == 336
    assert policies.late_credit_enabled is True
    assert policies.reserve_now_enabled is True

    with pytest.raises(ValidationError):
        Settings(_env_file=None, currency_code="IRT")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, delivery_commitment_hours=0)


def test_production_requires_protected_metrics() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="j" * 32,
            webhook_secret="w" * 32,
            otp_pepper="o" * 32,
            metrics_bearer_token=None,
        )


def test_production_requires_hsts_enabled() -> None:
    # otp_dev_console_fallback_enabled is pinned False here: it is read
    # from the ambient environment too, and this test must isolate the
    # HSTS check specifically regardless of what a dev container happens
    # to have set for that unrelated flag.
    with pytest.raises(ValidationError, match="security_hsts_enabled"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="j" * 32,
            webhook_secret="w" * 32,
            otp_pepper="o" * 32,
            metrics_bearer_token="m" * 32,
            otp_dev_console_fallback_enabled=False,
            security_hsts_enabled=False,
        )
    # Every other production-secrets requirement satisfied plus HSTS on
    # succeeds -- proves the new check is additive, not a blanket failure.
    Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="j" * 32,
        webhook_secret="w" * 32,
        otp_pepper="o" * 32,
        metrics_bearer_token="m" * 32,
        otp_dev_console_fallback_enabled=False,
        security_hsts_enabled=True,
    )
