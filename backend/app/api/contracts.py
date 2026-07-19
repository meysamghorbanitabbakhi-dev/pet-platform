"""Named customer-facing API contracts shared by the versioned API routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MoneyIRR(BaseModel):
    """Canonical integer Iranian rial monetary value."""

    amount_irr: int
    currency: Literal["IRR"] = "IRR"


class OffsetPageMetadata(BaseModel):
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    has_more: bool


class CursorPageMetadata(BaseModel):
    next_cursor: str | None = None
    has_more: bool


class OffsetPage[T](BaseModel):
    """K8-compatible typed offset page."""

    items: list[T]
    page: OffsetPageMetadata


class CursorPage[T](BaseModel):
    """K8-compatible typed cursor page."""

    items: list[T]
    page: CursorPageMetadata


class IdResponse(BaseModel):
    id: UUID


class PolicyResponse(BaseModel):
    currency_code: Literal["IRR"]
    customer_display_currency_code: Literal["IRR"]
    customer_display_unit: Literal["TOMAN"]
    irr_per_customer_display_unit: int = Field(ge=1)
    delivery_commitment_hours: int
    late_credit_enabled: bool
    late_credit_customer_visible: bool
    late_credit_basis_points: int
    late_credit_expiry_months: int
    wallet_consumption_order: Literal["earliest_expiry_first"]
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
    reorder_safety_buffer_days: int | None = None
    reorder_snooze_early_break_worsening_days: int
    customer_request_acknowledgement_fa: str
    pet_health_consent_policy_version: str
    storage_backend: Literal["filesystem"]
    sourcing_start_rule: Literal["supplier_financial_commitment_with_timestamp_and_evidence"]


class AddressResponse(BaseModel):
    id: UUID
    label: str
    recipient_name: str
    recipient_mobile: str
    province: str
    city: str
    address_line: str
    postal_code: str | None = None


class OfferListItem(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    title_fa: str
    unit_label_fa: str
    price_irr: int
    reference_price_irr: int | None = None
    supplier_country: str
    stock_posture: str
    authenticity: Literal["supplier_verified"]
    minimum_shelf_life_months: int
    reference_price_reviewed_at: str | None = None
    available_until: str | None = None


class ProductAlternativeResponse(BaseModel):
    """An approved, operator-curated alternative with its current offer.

    Platform-curated, not a guaranteed clinical/nutritional substitute --
    see the customer-facing label the frontend renders alongside this.
    """

    id: UUID
    rank: int
    rationale_fa: str
    compatibility_notes_fa: str | None = None
    offer: OfferListItem


class OrderListItem(BaseModel):
    id: UUID
    household_id: UUID
    status: str
    total_irr: int
    currency: Literal["IRR"]
    paid_at: datetime | None = None
    delivery_commitment_at: datetime | None = None
    delivered_at: datetime | None = None


class PaymentRedirectResponse(BaseModel):
    attempt_id: UUID
    redirect_url: str


class PaymentCallbackResponse(BaseModel):
    state: str
    order_id: UUID | None = None
    delivery_commitment_at: str | None = None


class FulfillmentTimelineItem(BaseModel):
    type: str
    occurred_at: datetime


class SourcedUnitResponse(BaseModel):
    order_line_id: UUID
    exact_expiry_date: date | None = None
    supplier_country: str | None = None
    authenticity: str
    confirmed_at: datetime


class OrderJourneyResponse(BaseModel):
    order_id: UUID
    status: str
    delivery_commitment_at: datetime | None = None
    original_delivery_commitment_at: datetime | None = None
    revised_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    timeline: list[FulfillmentTimelineItem]
    sourced_units: list[SourcedUnitResponse]


class FoodEstimateProvenanceRow(BaseModel):
    key: str
    source: str = "server"
    value: str | int | float | None = None


class FoodEstimateResponse(BaseModel):
    id: UUID
    inventory_unit_id: UUID | None = None
    scope: Literal["household", "pet"] = "household"
    pet_id: UUID | None = None
    low_days: int | None = None
    high_days: int | None = None
    min_days: int | None = None
    max_days: int | None = None
    confidence: Literal["high", "mid", "unknown"]
    basis: dict[str, Any]
    calculated_at: datetime | None = None
    last_confirmed_at: datetime | None = None
    provenance: list[FoodEstimateProvenanceRow] = Field(default_factory=list)


class InventoryListItem(BaseModel):
    id: UUID
    label: str
    source: str
    state: str
    exact_expiry_date: date | None = None
    supplier_country: str | None = None
    authenticity: str | None = None


class InventoryAssignmentResponse(BaseModel):
    pet: PetSummary
    share_basis_points: int | None = None
    daily_portion_grams: int | None = None


class InventoryDetailResponse(InventoryListItem):
    household_id: UUID
    product_id: UUID | None = None
    initial_quantity_grams: int | None = None
    remaining_quantity_grams: int | None = None
    remaining_low_grams: int | None = None
    remaining_high_grams: int | None = None
    delivered_at: datetime | None = None
    opened_at: datetime | None = None
    sourcing_confirmed_at: datetime | None = None
    assignments: list[InventoryAssignmentResponse]
    shares_known: bool
    active_estimate: FoodEstimateResponse | None = None


class DiaryListItem(BaseModel):
    id: UUID
    entry_type: str
    title_fa: str
    happened_at: datetime


class GardenObjectResponse(BaseModel):
    id: UUID
    object_key: str
    state: str
    diary_entry_id: UUID
    quadrant: int | None = None
    position_x: int | None = None
    position_y: int | None = None


class DiaryEntryDetailResponse(DiaryListItem):
    note_fa: str | None = None
    source_type: str
    source_reference: str
    linked_garden_object: GardenObjectResponse | None = None


class GardenStateResponse(BaseModel):
    pet_id: UUID
    layout_version: int = 1
    unlocked_quadrants: list[int]
    visible_slot_count: int
    slot_rules: dict[str, Any]
    objects: list[GardenObjectResponse]
    next_eligibility: dict[str, Any] | None = None


class JourneyCompletionResponse(BaseModel):
    diary_entry_id: UUID
    garden_reward_id: UUID


class JourneyAnswerOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label_fa: str


class JourneyStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title_fa: str
    body_fa: str
    allowed_answers: list[JourneyAnswerOptionResponse]


class JourneyCompletionRequirementsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_step_keys: list[str]


class JourneyEligibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible_species: list[Literal["dog", "cat"]] | None = None


class JourneyActiveWindowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_from: datetime | None = None
    active_until: datetime | None = None


class JourneyExceptionBehaviorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    behavior: Literal["non_diagnostic"]
    message_fa: str | None = None


class JourneyContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_fa: str | None = None
    steps: list[JourneyStepResponse]
    completion_requirements: JourneyCompletionRequirementsResponse
    eligibility: JourneyEligibilityResponse
    duration_days: int | None = None
    active_window: JourneyActiveWindowResponse
    exception_behavior: JourneyExceptionBehaviorResponse
    garden_object_key: str
    professional_approval_ref: str


class JourneyOfferResponse(BaseModel):
    definition_id: UUID
    key: str
    version: int
    title_fa: str
    summary_fa: str | None = None
    duration_days: int | None = None


class JourneyDefinitionResponse(BaseModel):
    id: UUID
    key: str
    version: int
    title_fa: str
    summary_fa: str | None = None
    content: JourneyContentResponse
    approved_at: datetime


class JourneyCheckInResponse(BaseModel):
    id: UUID
    journey_id: UUID
    check_in_key: str
    answer_key: str
    submitted_at: datetime
    completed: bool = False
    diary_entry_id: UUID | None = None
    garden_reward_id: UUID | None = None


class JourneyDetailResponse(BaseModel):
    id: UUID
    pet_id: UUID
    definition_id: UUID
    definition_version: int
    status: Literal["active", "paused", "stopped", "completed"]
    started_at: datetime
    ended_at: datetime | None = None
    title_fa: str
    steps: list[JourneyStepResponse]
    check_ins: list[JourneyCheckInResponse]
    diary_entry_id: UUID | None = None
    garden_reward_id: UUID | None = None


class ReorderOptionResponse(BaseModel):
    offer_id: UUID
    sku: str
    available: bool
    reason_key: str | None = None


class ReorderAssessmentResponse(BaseModel):
    recommendation: str
    outcome: Literal["order_now", "not_yet", "snoozed", "policy_blocked", "insufficient_facts"]
    risk_gap_days: int | None = None
    remaining_low_days: int | None = None
    remaining_high_days: int | None = None
    latest_delivery_days: int | None = None
    safety_buffer_days: int | None = None
    snoozed_until: datetime | None = None
    provenance: list[FoodEstimateProvenanceRow] = Field(default_factory=list)
    options: list[ReorderOptionResponse] = Field(default_factory=list)


class WalletSummaryResponse(BaseModel):
    available_balance_irr: int


class NotificationDestinationResponse(BaseModel):
    kind: Literal["order", "inventory_unit", "journey", "customer_request", "offer", "none"]
    id: UUID | None = None


class NotificationListItem(BaseModel):
    id: UUID
    event_key: str
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None = None
    destination: NotificationDestinationResponse


class AvailabilitySubscriptionResponse(BaseModel):
    id: UUID
    offer_id: UUID
    status: Literal["active", "notified", "cancelled"]
    order_created: Literal[False] = False
    created_at: datetime
    notified_at: datetime | None = None
    cancelled_at: datetime | None = None


class CustomerRequestResponse(BaseModel):
    id: UUID
    household_id: UUID
    request_type: Literal["support", "concierge_sourcing"]
    order_id: UUID | None = None
    offer_id: UUID | None = None
    product_query_fa: str | None = None
    message_fa: str
    contact_preference: Literal["in_app", "sms"]
    status: Literal["submitted", "in_review", "resolved", "closed"]
    created_at: datetime
    updated_at: datetime
    promises: dict[str, bool]
    acknowledgement_fa: str


class DelayAcknowledgementResponse(BaseModel):
    id: UUID
    order_id: UUID
    delay_event_version: int
    acknowledged_at: datetime
    compensation_implied: Literal[False] = False
    cancellation_implied: Literal[False] = False
    waiver_implied: Literal[False] = False


class OrderCancellationResponse(BaseModel):
    order_id: UUID
    status: Literal["cancelled"]
    cancelled_at: datetime
    reason: str
    refund_amount_irr: int
    refund_status: Literal["owed", "operator_attested"]
    refund_auto_processed: Literal[False] = False


class PetSummary(BaseModel):
    id: UUID
    name: str
    species: Literal["dog", "cat"]


class MeIdentityResponse(BaseModel):
    id: UUID
    mobile_e164: str
    identity_type: Literal["customer"]


class HouseholdSummary(BaseModel):
    id: UUID
    name: str
    role: str
    pet_count: int = Field(ge=0)
    active_address_count: int = Field(ge=0)


class ContextPetSummary(PetSummary):
    household_id: UUID
    avatar_reference: str | None = None


class OnboardingRequirementsResponse(BaseModel):
    needs_household: bool
    needs_pet: bool
    needs_address: bool


class CustomerCapabilitiesResponse(BaseModel):
    availability_subscriptions_enabled: bool
    concierge_requests_enabled: bool
    care_journey_delivery_enabled: bool


class MeContextResponse(BaseModel):
    identity: MeIdentityResponse
    households: list[HouseholdSummary]
    default_household_id: UUID | None = None
    pets: list[ContextPetSummary]
    onboarding: OnboardingRequirementsResponse
    capabilities: CustomerCapabilitiesResponse


class ProductMediaResponse(BaseModel):
    media_type: Literal["image", "video"]
    public_reference: str
    alt_text_fa: str
    sort_order: int = Field(ge=0)


class OfferDetailResponse(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    title_fa: str
    description_fa: str | None = None
    unit_label_fa: str
    nominal_quantity_grams: int | None = Field(default=None, gt=0)
    media: list[ProductMediaResponse]
    availability: Literal["available", "temporarily_unavailable"]
    availability_reason_key: str | None = None
    price_irr: int
    reference_price_irr: int | None = None
    saving_percent: int | None = Field(default=None, ge=0)
    reference_price_reviewed_at: datetime | None = None
    supplier_country_code: str
    authenticity: Literal["supplier_verified"]
    minimum_shelf_life_months_at_delivery: int = Field(gt=0)
    available_from: datetime | None = None
    available_until: datetime | None = None


class SafePaymentSummaryResponse(BaseModel):
    status: str
    paid_at: datetime | None = None
    amount_irr: int
    currency: Literal["IRR"]
    masked_card: str | None = None


class OrderAddressSnapshotResponse(BaseModel):
    label: str
    recipient_name: str
    recipient_mobile: str
    province: str
    city: str
    address_line: str
    postal_code: str | None = None


class OrderLineResponse(BaseModel):
    id: UUID
    offer_id: UUID
    sku: str
    title_fa: str
    unit_label_fa: str
    quantity: int = Field(gt=0)
    unit_price_irr: int
    line_total_irr: int
    planned_pet_ids: list[UUID]
    sourced_unit: SourcedUnitResponse | None = None


class OrderPolicyFieldsResponse(BaseModel):
    delivery_commitment_hours: int = Field(gt=0)
    late_credit_customer_visible: bool


class OrderDetailResponse(BaseModel):
    id: UUID
    household_id: UUID
    status: str
    currency: Literal["IRR"]
    merchandise_total_irr: int
    created_at: datetime
    paid_at: datetime | None = None
    delivery_commitment_at: datetime | None = None
    original_delivery_commitment_at: datetime | None = None
    revised_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    payment: SafePaymentSummaryResponse | None = None
    delivery_address: OrderAddressSnapshotResponse
    lines: list[OrderLineResponse]
    policies: OrderPolicyFieldsResponse
    cancellation_eligible: bool
    cancellation: OrderCancellationResponse | None = None


class TodayFoodNone(BaseModel):
    state: Literal["none"]


class TodayFoodIncoming(BaseModel):
    state: Literal["incoming"]
    order_id: UUID
    label: str


class TodayFoodUnopened(BaseModel):
    state: Literal["unopened"]
    inventory_unit_id: UUID
    label: str


class TodayFoodUnknownEstimate(BaseModel):
    state: Literal["unknown_estimate"]
    inventory_unit_id: UUID
    label: str


class TodayFoodEstimated(BaseModel):
    state: Literal["estimated"]
    inventory_unit_id: UUID
    label: str
    remaining_low_days: int
    remaining_high_days: int | None = None
    confidence: str


class TodayFoodUnavailable(BaseModel):
    state: Literal["unavailable"]
    reason_key: str


TodayFoodResponse = Annotated[
    TodayFoodNone
    | TodayFoodIncoming
    | TodayFoodUnopened
    | TodayFoodUnknownEstimate
    | TodayFoodEstimated
    | TodayFoodUnavailable,
    Field(discriminator="state"),
]


class TodaySourcingFailedAttention(BaseModel):
    type: Literal["sourcing_failed"]
    order_id: UUID


class TodayDeliveryOverdueAttention(BaseModel):
    type: Literal["delivery_overdue"]
    order_id: UUID


class TodayDeliveryDelayedAttention(BaseModel):
    type: Literal["delivery_delayed"]
    order_id: UUID


class TodayActionAttention(BaseModel):
    type: Literal["confirm_opening", "improve_food_estimate"]


class TodayActiveJourneyAttention(BaseModel):
    type: Literal["active_journey"]
    journey_id: UUID


TodayAttentionResponse = Annotated[
    TodaySourcingFailedAttention
    | TodayDeliveryOverdueAttention
    | TodayDeliveryDelayedAttention
    | TodayActionAttention
    | TodayActiveJourneyAttention,
    Field(discriminator="type"),
]


class TodayActiveJourneyResponse(BaseModel):
    id: UUID
    status: str


class TodayGardenResponse(BaseModel):
    object_count: int


class TodayResponse(BaseModel):
    pet: PetSummary
    household_id: UUID
    generated_at: datetime
    food: TodayFoodResponse
    next_action: Literal["confirm_opening", "improve_food_estimate"] | None = None
    primary_attention: TodayAttentionResponse | None = None
    active_journey: TodayActiveJourneyResponse | None = None
    garden: TodayGardenResponse
    care_guidance: dict[str, Any]


class PetProfileResponse(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    species: Literal["dog", "cat"]
    birth_date: date | None = None
    birth_date_precision: str | None = None
    sex: str | None = None
    neuter_status: str | None = None
    expected_adult_size: str | None = None
    breed_reference_id: str | None = None
    breed_variety_id: str | None = None
    breed_identification_source: str | None = None
    mixed_breed: bool | None = None
    breed_selection_mode: str | None = None
    reproductive_state: str | None = None
    status: str


class AssetResponse(BaseModel):
    id: UUID
    category: str
    purpose: str
    filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    captured_at: datetime | None = None
    created_at: datetime


class BodyAssessmentResponse(BaseModel):
    id: UUID
    bcs_score: int
    bcs_scale: int
    muscle_condition: str
    assessment_source: str
    answers: dict[str, Any]
    assessed_at: datetime
    veterinarian_name: str | None = None
    veterinarian_confirmed_at: datetime | None = None


class MeasurementResponse(BaseModel):
    id: UUID
    measurement_type: str
    value: float
    unit: str
    measured_at: datetime
    source: str
    measurement_method: str | None = None
    confidence: str
    notes: str | None = None
    status: str
    supersedes_measurement_id: UUID | None = None
    correction_reason: str | None = None


class MutationStatusResponse(IdResponse):
    status: str
