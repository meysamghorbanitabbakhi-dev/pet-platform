from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class LaunchPolicies:
    currency_code: str
    customer_display_currency_code: str
    customer_display_unit: str
    irr_per_customer_display_unit: int
    delivery_commitment_hours: int
    late_credit_enabled: bool
    late_credit_customer_visible: bool
    late_credit_basis_points: int
    late_credit_expiry_months: int
    wallet_consumption_order: str
    full_payment_only: bool
    reserve_now_enabled: bool
    cancel_after_sourcing_enabled: bool
    refund_self_service_enabled: bool
    replacement_self_service_enabled: bool
    substitution_self_service_enabled: bool
    delay_compensation_customer_visible: bool
    availability_subscriptions_enabled: bool
    concierge_requests_enabled: bool
    care_journey_delivery_enabled: bool
    push_notifications_enabled: bool
    semantic_level_estimation_enabled: bool
    reorder_safety_buffer_days: int | None
    reorder_snooze_early_break_worsening_days: int
    customer_request_acknowledgement_fa: str
    storage_backend: str
    sourcing_start_rule: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "LaunchPolicies":
        return cls(
            currency_code=settings.currency_code,
            customer_display_currency_code=settings.customer_display_currency_code,
            customer_display_unit=settings.customer_display_unit,
            irr_per_customer_display_unit=settings.irr_per_customer_display_unit,
            delivery_commitment_hours=settings.delivery_commitment_hours,
            late_credit_enabled=settings.late_credit_enabled,
            late_credit_customer_visible=settings.late_credit_customer_visible,
            late_credit_basis_points=settings.late_credit_basis_points,
            late_credit_expiry_months=settings.late_credit_expiry_months,
            wallet_consumption_order="earliest_expiry_first",
            full_payment_only=settings.full_payment_only,
            reserve_now_enabled=settings.reserve_now_enabled,
            cancel_after_sourcing_enabled=settings.cancel_after_sourcing_enabled,
            refund_self_service_enabled=settings.refund_self_service_enabled,
            replacement_self_service_enabled=settings.replacement_self_service_enabled,
            substitution_self_service_enabled=settings.substitution_self_service_enabled,
            delay_compensation_customer_visible=settings.delay_compensation_customer_visible,
            availability_subscriptions_enabled=settings.availability_subscriptions_enabled,
            concierge_requests_enabled=settings.concierge_requests_enabled,
            care_journey_delivery_enabled=settings.care_journey_delivery_enabled,
            push_notifications_enabled=settings.push_notifications_enabled,
            semantic_level_estimation_enabled=settings.semantic_level_estimation_enabled,
            reorder_safety_buffer_days=settings.reorder_safety_buffer_days,
            reorder_snooze_early_break_worsening_days=(
                settings.reorder_snooze_early_break_worsening_days
            ),
            customer_request_acknowledgement_fa=settings.customer_request_acknowledgement_fa,
            storage_backend=settings.storage_backend,
            sourcing_start_rule="supplier_financial_commitment_with_timestamp_and_evidence",
        )
