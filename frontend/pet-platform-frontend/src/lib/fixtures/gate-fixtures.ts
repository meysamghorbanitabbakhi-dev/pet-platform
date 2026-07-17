import type {
  FoodEstimateResponse,
  InventoryDetailResponse,
  JourneyOfferResponse,
  MeContextResponse,
  OfferListItem,
  PolicyResponse,
  TodayResponse,
} from "@/lib/api-types";

export const ids = {
  household: "11111111-1111-4111-8111-111111111111",
  petBishi: "22222222-2222-4222-8222-222222222222",
  petRex: "33333333-3333-4333-8333-333333333333",
  orderIncoming: "44444444-4444-4444-8444-444444444444",
  inventoryUnit: "55555555-5555-4555-8555-555555555555",
  journey: "66666666-6666-4666-8666-666666666666",
  journeyDefinition: "77777777-7777-4777-8777-777777777777",
  estimate: "88888888-8888-4888-8888-888888888888",
};

export const policyFixture: PolicyResponse = {
  availability_subscriptions_enabled: true,
  cancel_after_sourcing_enabled: false,
  care_journey_delivery_enabled: true,
  concierge_requests_enabled: true,
  currency_code: "IRR",
  customer_display_currency_code: "IRR",
  customer_display_unit: "TOMAN",
  customer_request_acknowledgement_fa:
    "درخواست شما ثبت شد. نتیجه بررسی از طریق پیامک یا داخل برنامه اطلاع‌رسانی می‌شود. ثبت درخواست به‌معنای تضمین موجودی، قیمت، زمان پاسخ یا تأمین نیست.",
  delay_compensation_customer_visible: false,
  delivery_commitment_hours: 366,
  full_payment_only: true,
  irr_per_customer_display_unit: 10,
  late_credit_basis_points: 500,
  late_credit_customer_visible: false,
  late_credit_enabled: false,
  late_credit_expiry_months: 3,
  push_notifications_enabled: false,
  refund_self_service_enabled: false,
  reorder_safety_buffer_days: 3,
  reorder_snooze_early_break_worsening_days: 2,
  replacement_self_service_enabled: false,
  reserve_now_enabled: false,
  semantic_level_estimation_enabled: true,
  sourcing_start_rule:
    "supplier_financial_commitment_with_timestamp_and_evidence",
  storage_backend: "filesystem",
  substitution_self_service_enabled: false,
  wallet_consumption_order: "earliest_expiry_first",
};

export const policyDisabledFixture: PolicyResponse = {
  ...policyFixture,
  availability_subscriptions_enabled: false,
  care_journey_delivery_enabled: false,
  concierge_requests_enabled: false,
  semantic_level_estimation_enabled: false,
};

export const meContextFixture: MeContextResponse = {
  capabilities: {
    availability_subscriptions_enabled: true,
    concierge_requests_enabled: true,
    care_journey_delivery_enabled: true,
  },
  default_household_id: ids.household,
  households: [
    {
      active_address_count: 1,
      id: ids.household,
      name: "خانه بیشی",
      pet_count: 2,
      role: "owner",
    },
  ],
  identity: {
    id: "99999999-9999-4999-8999-999999999999",
    identity_type: "customer",
    mobile_e164: "+989121234567",
  },
  onboarding: {
    needs_address: false,
    needs_household: false,
    needs_pet: false,
  },
  pets: [
    {
      id: ids.petBishi,
      household_id: ids.household,
      name: "بیشی",
      species: "dog",
      avatar_reference: null,
    },
    {
      id: ids.petRex,
      household_id: ids.household,
      name: "رکس",
      species: "cat",
      avatar_reference: null,
    },
  ],
};

export const offersFixture: OfferListItem[] = [
  {
    authenticity: "supplier_verified",
    available_until: null,
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    minimum_shelf_life_months: 6,
    price_irr: 4_800_000,
    product_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    reference_price_irr: 7_500_000,
    reference_price_reviewed_at: "2026-05-01T08:00:00Z",
    sku: "RC-ADULT-3KG",
    stock_posture: "available",
    supplier_country: "فرانسه",
    title_fa: "رویال کنین ادالت - ۳ کیلوگرم",
    unit_label_fa: "کیسه",
  },
  {
    authenticity: "supplier_verified",
    available_until: null,
    id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    minimum_shelf_life_months: 6,
    price_irr: 5_200_000,
    product_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    reference_price_irr: null,
    reference_price_reviewed_at: null,
    sku: "RC-CAT-2KG",
    stock_posture: "available",
    supplier_country: "فرانسه",
    title_fa: "رویال کنین کت - ۲ کیلوگرم",
    unit_label_fa: "کیسه",
  },
];

export const incomingTodayFixture: TodayResponse = {
  active_journey: null,
  care_guidance: {},
  food: {
    label: "رویال کنین ادالت - ۳ کیلوگرم",
    order_id: ids.orderIncoming,
    state: "incoming",
  },
  garden: { object_count: 0 },
  generated_at: "2026-07-17T08:00:00Z",
  household_id: ids.household,
  next_action: null,
  pet: { id: ids.petBishi, name: "بیشی", species: "dog" },
  primary_attention: {
    order_id: ids.orderIncoming,
    type: "delivery_delayed",
  },
};

export const unopenedTodayFixture: TodayResponse = {
  ...incomingTodayFixture,
  food: {
    inventory_unit_id: ids.inventoryUnit,
    label: "رویال کنین ادالت - ۳ کیلوگرم",
    state: "unopened",
  },
  next_action: "confirm_opening",
  primary_attention: {
    type: "confirm_opening",
  },
};

export const returningTodayFixture: TodayResponse = {
  active_journey: {
    id: ids.journey,
    status: "active",
  },
  care_guidance: {},
  food: {
    confidence: "mid",
    inventory_unit_id: ids.inventoryUnit,
    label: "رویال کنین ادالت - ۳ کیلوگرم",
    remaining_high_days: 18,
    remaining_low_days: 12,
    state: "estimated",
  },
  garden: { object_count: 3 },
  generated_at: "2026-07-17T08:15:00Z",
  household_id: ids.household,
  next_action: "improve_food_estimate",
  pet: { id: ids.petBishi, name: "بیشی", species: "dog" },
  primary_attention: null,
};

export const rexTodayFixture: TodayResponse = {
  ...returningTodayFixture,
  active_journey: null,
  food: { state: "none" },
  garden: { object_count: 1 },
  next_action: null,
  pet: { id: ids.petRex, name: "رکس", species: "cat" },
};

export const inventoryDetailFixture: InventoryDetailResponse = {
  active_estimate: null,
  assignments: [
    {
      daily_portion_grams: null,
      pet: { id: ids.petBishi, name: "بیشی", species: "dog" },
      share_basis_points: null,
    },
  ],
  authenticity: "supplier_verified",
  delivered_at: "2026-07-17T06:00:00Z",
  exact_expiry_date: "2027-01-17",
  household_id: ids.household,
  id: ids.inventoryUnit,
  initial_quantity_grams: 3000,
  label: "رویال کنین ادالت - ۳ کیلوگرم",
  opened_at: null,
  product_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  remaining_high_grams: null,
  remaining_low_grams: null,
  remaining_quantity_grams: null,
  shares_known: false,
  source: "paid_order",
  sourcing_confirmed_at: "2026-07-16T14:00:00Z",
  state: "delivered_unopened",
  supplier_country: "فرانسه",
};

export const openedEstimateFixture: FoodEstimateResponse = {
  basis: { source: "confirmed_opening" },
  calculated_at: "2026-07-17T09:00:00Z",
  confidence: "unknown",
  high_days: null,
  id: ids.estimate,
  inventory_unit_id: ids.inventoryUnit,
  last_confirmed_at: "2026-07-17T09:00:00Z",
  low_days: null,
  max_days: null,
  min_days: null,
  pet_id: ids.petBishi,
  provenance: [],
  scope: "household",
};

export const journeyOffersFixture: JourneyOfferResponse[] = [
  {
    definition_id: ids.journeyDefinition,
    duration_days: 28,
    key: "weekly_weight_watch",
    summary_fa:
      "مسیر تأییدشده برای پیگیری منظم، بدون تشخیص یا درمان در کلاینت.",
    title_fa: "پایش هفتگی وزن",
    version: 1,
  },
];
