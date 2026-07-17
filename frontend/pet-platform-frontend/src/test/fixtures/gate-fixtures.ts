import type {
  AddressResponse,
  AvailabilitySubscriptionPage,
  AvailabilitySubscriptionResponse,
  CustomerRequestPage,
  CustomerRequestResponse,
  DiaryEntryDetailResponse,
  DiaryListItem,
  NotificationPage,
  PrivacyRequestResponse,
  WalletSummaryResponse,
} from "@/lib/api-types";
import type {
  BodyAssessmentItem,
  BreedDetailResponse,
  BreedListItem,
  BreedSearchItem,
  CareGuidanceResponse,
  MeasurementItem,
  PetAssetItem,
  PetKnowledgeResponse,
  WeightTrendResponse,
} from "@/lib/pet-health-types";
import type {
  FoodEstimateResponse,
  GardenStateResponse,
  InventoryDetailResponse,
  InventoryListItem,
  JourneyDefinitionResponse,
  JourneyDetailResponse,
  JourneyOfferResponse,
  MeContextResponse,
  OfferDetailResponse,
  OfferListItem,
  OrderDetailResponse,
  OrderJourneyResponse,
  OrderResponse,
  PaymentCallbackResponse,
  PaymentRedirectResponse,
  PolicyResponse,
  ReorderAssessmentResponse,
  TodayResponse,
} from "@/lib/api-types";

export const ids = {
  household: "11111111-1111-4111-8111-111111111111",
  petBishi: "22222222-2222-4222-8222-222222222222",
  petRex: "33333333-3333-4333-8333-333333333333",
  orderIncoming: "44444444-4444-4444-8444-444444444444",
  orderPaid: "45454545-4545-4545-8545-454545454545",
  inventoryUnit: "55555555-5555-4555-8555-555555555555",
  journey: "66666666-6666-4666-8666-666666666666",
  journeyDefinition: "77777777-7777-4777-8777-777777777777",
  estimate: "88888888-8888-4888-8888-888888888888",
  address: "abababab-abab-4aba-8aba-abababababab",
  paymentAttempt: "99999999-aaaa-4aaa-8aaa-999999999999",
  offerDog: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  offerCat: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  offerUnavailable: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
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
    id: ids.offerDog,
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
    id: ids.offerCat,
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

export const unavailableOfferFixture: OfferDetailResponse = {
  authenticity: "supplier_verified",
  availability: "temporarily_unavailable",
  availability_reason_key: "temporarily_unavailable",
  available_from: null,
  available_until: null,
  description_fa: "این محصول فعلا برای پرداخت کامل در دسترس نیست.",
  id: ids.offerUnavailable,
  media: [],
  minimum_shelf_life_months_at_delivery: 6,
  nominal_quantity_grams: 3000,
  price_irr: 4_800_000,
  product_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  reference_price_irr: 7_500_000,
  reference_price_reviewed_at: "2026-05-01T08:00:00Z",
  saving_percent: 36,
  sku: "RC-ADULT-3KG",
  supplier_country_code: "FR",
  title_fa: "رویال کنین ادالت - ۳ کیلوگرم",
  unit_label_fa: "کیسه",
};

export const offerDetailFixture: OfferDetailResponse = {
  ...unavailableOfferFixture,
  availability: "available",
  availability_reason_key: null,
  id: ids.offerDog,
  media: [
    {
      alt_text_fa: "تصویر بسته غذای خشک رویال کنین",
      media_type: "image",
      public_reference:
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='420' viewBox='0 0 640 420'%3E%3Crect width='640' height='420' fill='%23f7f1e6'/%3E%3Crect x='220' y='52' width='200' height='316' rx='22' fill='%23f9fafb' stroke='%232f3148' stroke-width='10'/%3E%3Crect x='242' y='88' width='156' height='86' rx='12' fill='%23d8a43e'/%3E%3Ctext x='320' y='134' text-anchor='middle' font-size='30' font-family='Arial' fill='%232f3148'%3ERC%3C/text%3E%3Crect x='260' y='210' width='120' height='86' rx='43' fill='%234a7c59'/%3E%3Ctext x='320' y='259' text-anchor='middle' font-size='26' font-family='Arial' fill='white'%3E3kg%3C/text%3E%3C/svg%3E",
      sort_order: 1,
    },
  ],
};

export const catOfferDetailFixture: OfferDetailResponse = {
  ...offerDetailFixture,
  id: ids.offerCat,
  price_irr: 5_200_000,
  product_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  reference_price_irr: null,
  reference_price_reviewed_at: null,
  saving_percent: null,
  sku: "RC-CAT-2KG",
  title_fa: "رویال کنین کت - ۲ کیلوگرم",
};

export const addressFixture: AddressResponse = {
  address_line: "خیابان ولیعصر پلاک ۱۲",
  city: "تهران",
  id: ids.address,
  label: "خانه",
  postal_code: "1234567890",
  province: "تهران",
  recipient_mobile: "+989121234567",
  recipient_name: "مالک خانه",
};

export const orderResponseFixture: OrderResponse = {
  currency: "IRR",
  id: ids.orderPaid,
  merchandise_total_irr: 4_800_000,
  status: "awaiting_payment",
};

export const paymentRedirectFixture: PaymentRedirectResponse = {
  attempt_id: ids.paymentAttempt,
  redirect_url:
    "/checkout/payment/return?Authority=fixture-authority&Status=OK",
};

export const paymentCallbackFixture: PaymentCallbackResponse = {
  delivery_commitment_at: "2026-08-01T15:00:00Z",
  order_id: ids.orderPaid,
  state: "verified",
};

export const orderDetailFixture: OrderDetailResponse = {
  created_at: "2026-07-17T09:00:00Z",
  currency: "IRR",
  delivered_at: null,
  delivery_address: {
    address_line: addressFixture.address_line,
    city: addressFixture.city,
    label: addressFixture.label,
    postal_code: addressFixture.postal_code,
    province: addressFixture.province,
    recipient_mobile: addressFixture.recipient_mobile,
    recipient_name: addressFixture.recipient_name,
  },
  delivery_commitment_at: "2026-08-01T15:00:00Z",
  household_id: ids.household,
  id: ids.orderPaid,
  lines: [
    {
      id: "12121212-1212-4121-8121-121212121212",
      line_total_irr: 4_800_000,
      offer_id: ids.offerDog,
      planned_pet_ids: [],
      quantity: 1,
      sku: "RC-ADULT-3KG",
      sourced_unit: null,
      title_fa: "رویال کنین ادالت - ۳ کیلوگرم",
      unit_label_fa: "کیسه",
      unit_price_irr: 4_800_000,
    },
  ],
  merchandise_total_irr: 4_800_000,
  original_delivery_commitment_at: "2026-08-01T15:00:00Z",
  paid_at: "2026-07-17T09:05:00Z",
  payment: {
    amount_irr: 4_800_000,
    currency: "IRR",
    masked_card: "۶۲۷۴ **** **** ۱۲۳۴",
    paid_at: "2026-07-17T09:05:00Z",
    status: "verified",
  },
  policies: {
    delivery_commitment_hours: 366,
    late_credit_customer_visible: false,
  },
  revised_delivery_at: null,
  status: "paid",
};

export const orderJourneyFixture: OrderJourneyResponse = {
  delivered_at: null,
  delivery_commitment_at: "2026-08-01T15:00:00Z",
  order_id: ids.orderPaid,
  original_delivery_commitment_at: "2026-08-01T15:00:00Z",
  revised_delivery_at: null,
  sourced_units: [],
  status: "paid",
  timeline: [
    {
      occurred_at: "2026-07-17T09:05:00Z",
      type: "payment_confirmed",
    },
  ],
};

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

export const inventoryListFixture: InventoryListItem[] = [
  {
    authenticity: "supplier_verified",
    exact_expiry_date: "2027-01-17",
    id: ids.inventoryUnit,
    label: "رویال کنین ادالت - ۳ کیلوگرم",
    source: "paid_order",
    state: "delivered_unopened",
    supplier_country: "فرانسه",
  },
];

export const reorderAssessmentFixture: ReorderAssessmentResponse = {
  latest_delivery_days: 15,
  options: [{ available: true, offer_id: ids.offerDog, sku: "royal-canin-3kg" }],
  outcome: "not_yet",
  provenance: [],
  recommendation: "موجودی فعلی برای روزهای پیش رو کافی است.",
  remaining_high_days: 18,
  remaining_low_days: 12,
  risk_gap_days: null,
  safety_buffer_days: 3,
  snoozed_until: null,
};

export const journeyDefinitionFixture: JourneyDefinitionResponse = {
  approved_at: "2026-06-01T00:00:00Z",
  content: {
    active_window: { active_from: null, active_until: null },
    completion_requirements: { required_step_keys: ["week1", "week2"] },
    duration_days: 28,
    eligibility: { eligible_species: ["dog", "cat"] },
    exception_behavior: {
      behavior: "non_diagnostic",
      message_fa:
        "این مسیر جایگزین مراجعه به دامپزشک نیست و تشخیص یا درمان ارائه نمی‌دهد.",
    },
    garden_object_key: "watering_can",
    professional_approval_ref: "vet-ref-001",
    steps: [
      {
        allowed_answers: [
          { key: "on_track", label_fa: "روند طبیعی است" },
          { key: "concerned", label_fa: "نگران هستم" },
        ],
        body_fa: "وزن پت خود را این هفته بررسی و ثبت کنید.",
        key: "week1",
        title_fa: "هفته اول: بررسی وزن",
      },
      {
        allowed_answers: [
          { key: "on_track", label_fa: "روند طبیعی است" },
          { key: "concerned", label_fa: "نگران هستم" },
        ],
        body_fa: "دوباره وزن پت را بررسی و مقایسه کنید.",
        key: "week2",
        title_fa: "هفته دوم: بررسی وزن",
      },
    ],
  },
  id: ids.journeyDefinition,
  key: "weekly_weight_watch",
  summary_fa: "مسیر تأییدشده برای پیگیری منظم، بدون تشخیص یا درمان در کلاینت.",
  title_fa: "پایش هفتگی وزن",
  version: 1,
};

export const journeyDetailFixture: JourneyDetailResponse = {
  check_ins: [],
  definition_id: ids.journeyDefinition,
  definition_version: 1,
  ended_at: null,
  id: ids.journey,
  pet_id: ids.petBishi,
  started_at: "2026-07-10T00:00:00Z",
  status: "active",
  steps: journeyDefinitionFixture.content.steps,
  title_fa: "پایش هفتگی وزن",
};

export const diaryListFixture: DiaryListItem[] = [
  {
    entry_type: "journey_completion",
    happened_at: "2026-07-10T12:00:00Z",
    id: ids.journey,
    title_fa: "هفته خوبی بود",
  },
];

export const diaryEntryDetailFixture: DiaryEntryDetailResponse = {
  entry_type: "journey_completion",
  happened_at: "2026-07-10T12:00:00Z",
  id: ids.journey,
  linked_garden_object: {
    diary_entry_id: ids.journey,
    id: ids.estimate,
    object_key: "watering_can",
    position_x: null,
    position_y: null,
    quadrant: null,
    state: "revealed",
  },
  note_fa: "پایش هفتگی وزن با موفقیت تکمیل شد.",
  source_reference: ids.journey,
  source_type: "journey_completion",
  title_fa: "هفته خوبی بود",
};

export const gardenStateFixture: GardenStateResponse = {
  layout_version: 1,
  next_eligibility: { reason_key: "server_derived_milestones_only" },
  objects: [
    {
      diary_entry_id: ids.journey,
      id: ids.estimate,
      object_key: "watering_can",
      position_x: null,
      position_y: null,
      quadrant: null,
      state: "revealed",
    },
  ],
  pet_id: ids.petBishi,
  slot_rules: { decay_enabled: false, source: "server_milestone_rules", xp_enabled: false },
  unlocked_quadrants: [1],
  visible_slot_count: 12,
};

export const availabilitySubscriptionFixture: AvailabilitySubscriptionResponse = {
  cancelled_at: null,
  created_at: "2026-07-17T08:00:00Z",
  id: "aaaa1111-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
  notified_at: null,
  offer_id: ids.offerUnavailable,
  order_created: false,
  status: "active",
};

export const availabilitySubscriptionPageFixture: AvailabilitySubscriptionPage = {
  items: [],
  page: { has_more: false, limit: 25, offset: 0, total: 0 },
};

export const customerRequestFixture: CustomerRequestResponse = {
  acknowledgement_fa:
    "درخواست شما ثبت شد. نتیجه بررسی از طریق پیامک یا داخل برنامه اطلاع‌رسانی می‌شود. ثبت درخواست به‌معنای تضمین موجودی، قیمت، زمان پاسخ یا تأمین نیست.",
  contact_preference: "in_app",
  created_at: "2026-07-17T08:00:00Z",
  household_id: ids.household,
  id: "bbbb2222-bbbb-4bbb-8bbb-bbbbbbbbbbb2",
  message_fa: "آیا این محصول برای نژاد پرشین مناسب است؟",
  offer_id: null,
  order_id: null,
  product_query_fa: null,
  promises: {
    availability: false,
    refund: false,
    replacement: false,
    response_time: false,
    sourcing_success: false,
  },
  request_type: "support",
  status: "submitted",
  updated_at: "2026-07-17T08:00:00Z",
};

export const customerRequestPageFixture: CustomerRequestPage = {
  items: [customerRequestFixture],
  page: { has_more: false, limit: 25, offset: 0, total: 1 },
};

export const walletFixture: WalletSummaryResponse = {
  available_balance_irr: 0,
};

export const notificationPageFixture: NotificationPage = {
  items: [
    {
      created_at: "2026-07-17T08:00:00Z",
      event_key: "catalog.offer_available",
      id: "cccc3333-cccc-4ccc-8ccc-ccccccccccc3",
      payload: { offer_id: ids.offerUnavailable },
      read_at: null,
    },
  ],
  page: { has_more: false, limit: 25, offset: 0, total: 1 },
};

export const privacyRequestFixture: PrivacyRequestResponse = {
  id: "dddd4444-dddd-4ddd-8ddd-ddddddddddd4",
  status: "pending",
};

export const privacyExportFixture: Record<string, unknown> = {
  generated_at: "2026-07-17T08:00:00Z",
  households: [],
  identity: { mobile_e164: "+989121234567" },
};

export const measurementFixture: MeasurementItem = {
  confidence: "high",
  id: "ffff5555-ffff-4fff-8fff-fffffffffff5",
  measured_at: "2026-07-15T08:00:00Z",
  measurement_method: null,
  measurement_type: "weight",
  notes: null,
  source: "owner_reported",
  unit: "kg",
  value: 12.4,
};

export const weightTrendFixture: WeightTrendResponse = {
  changes: {
    "7_days": null,
    "30_days": { baseline_weight_kg: 12.0, change_percent: 3.3 },
    "90_days": null,
  },
  current_weight_kg: 12.4,
  interpretation: "personal_trend_only",
  measured_at: "2026-07-15T08:00:00Z",
  state: "available",
};

export const petAssetFixture: PetAssetItem = {
  captured_at: "2026-07-10T08:00:00Z",
  category: "body_side",
  checksum_sha256: "abc123",
  created_at: "2026-07-10T08:05:00Z",
  filename: "photo.jpg",
  id: "aaaa6666-aaaa-4aaa-8aaa-aaaaaaaaaaa6",
  media_type: "image/jpeg",
  purpose: "body_photographs",
  size_bytes: 204800,
};

export const bodyAssessmentFixture: BodyAssessmentItem = {
  answers: {},
  assessed_at: "2026-07-10T08:10:00Z",
  assessment_source: "owner_reported",
  bcs_score: 5,
  bcs_scale: 9,
  id: "bbbb7777-bbbb-4bbb-8bbb-bbbbbbbbbbb7",
  muscle_condition: "normal",
  veterinarian_confirmed_at: null,
  veterinarian_name: null,
};

export const breedListFixture: { items: BreedListItem[] } = {
  items: [
    { id: "persian", name_en: "Persian", name_fa: "پرشین", species: "cat" },
  ],
};

export const breedSearchFixture: { items: BreedSearchItem[] } = {
  items: [
    {
      aliases_fa: [],
      id: "persian",
      matched_field: "name_fa",
      name_en: "Persian",
      name_fa: "پرشین",
      species: "cat",
    },
  ],
};

export const breedDetailFixture: BreedDetailResponse = {
  breed: { id: "persian", name_en: "Persian", name_fa: "پرشین", species: "cat" },
  claims: [
    {
      claim_type: "grooming",
      id: "claim-1",
      review_status: "veterinary_approved",
      reviewer_disclosure: "anonymous_external_veterinarian",
      sources: [{ id: "source-1", title: "منبع تاییدشده", type: "journal" }],
      text_fa: "نیاز به شانه‌کشی روزانه دارد.",
      variety_id: null,
    },
  ],
  guidance: [
    {
      domain: "grooming",
      id: "guidance-1",
      reviewer_disclosure: "anonymous_external_veterinarian",
      supporting_claim_ids: ["claim-1"],
      text_fa: "روزانه شانه بکشید.",
      variety_id: null,
    },
  ],
  release: {
    checksum_sha256: "def456",
    dataset_version: "2026.1",
    published_at: "2026-01-01T00:00:00Z",
  },
  varieties: [],
};

export const petKnowledgeFixture: PetKnowledgeResponse = {
  breed: { id: "persian", name_en: "Persian", name_fa: "پرشین", species: "cat" },
  breed_identification_source: "owner_reported",
  claims: breedDetailFixture.claims,
  disclaimer_fa: "این اطلاعات عمومی است و جایگزین نظر دامپزشک نیست.",
  guidance: breedDetailFixture.guidance,
  pet_id: ids.petBishi,
  release: breedDetailFixture.release,
  status: "available",
};

export const careGuidanceFixture: CareGuidanceResponse = {
  disclaimer_fa: "راهنماهای عمومی جایگزین توصیه اختصاصی دامپزشک نیستند.",
  items: [
    {
      domain: "grooming",
      emergency_classification: "not_emergency",
      external_id: "guidance-1",
      id: "cccc8888-cccc-4ccc-8ccc-ccccccccccc8",
      interpretation: "general_care_guidance_not_individual_medical_advice",
      population_level_explanation_fa: null,
      professional_discussion_fa: null,
      release: { checksum_sha256: "def456", dataset_version: "2026.1" },
      reviewer_disclosure: "anonymous_external_veterinarian",
      supporting_claim_ids: ["claim-1"],
      text_fa: "روزانه شانه بکشید.",
    },
  ],
  state: "available",
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
