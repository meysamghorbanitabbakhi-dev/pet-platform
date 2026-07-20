"""Versioned KPI definitions (Workstream 6).

Each entry is metadata only -- what the number means, not how it is
computed (see service.py for the actual queries). Definitions are
versioned so a future change to a KPI's methodology (e.g. redefining
"conversion") ships as a new version rather than silently changing the
meaning of historical values under the same key.

window/timezone: every window-bound KPI here is computed against a
caller-supplied [window_start, window_end) UTC range -- this codebase
has no timezone-conversion utility anywhere (app.common.time.utc_now
is the only clock primitive) and does not fabricate one here. If a
future team wants Tehran-local day boundaries for reporting, that is a
distinct, separate decision requiring its own conversion utility.

currency: all monetary KPIs are integer IRR, matching every other
monetary value in this codebase (see ADR-002).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KPIDefinition:
    key: str
    name: str
    description: str
    numerator: str
    denominator: str
    window: str
    timezone: str
    currency: str | None
    status_inclusion: str
    late_event_handling: str
    version: int
    validation_query: str
    computable: bool = True
    data_limitation: str | None = None


KPI_REGISTRY: dict[str, KPIDefinition] = {
    "conversion": KPIDefinition(
        key="conversion",
        name="Checkout-to-payment conversion",
        description="Share of created orders that reach payment.",
        numerator="Orders with paid_at IS NOT NULL, created_at in window",
        denominator="All orders, created_at in window",
        window="[window_start, window_end) on Order.created_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Denominator includes every order status; numerator requires paid_at set",
        late_event_handling=(
            "Point-in-time snapshot: an order created near window_end that pays after "
            "the report is generated is undercounted until the report is re-run -- this "
            "KPI does not retroactively freeze or backfill past values"
        ),
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE paid_at IS NOT NULL) AS numerator, count(*) AS "
            "denominator FROM orders_orders WHERE created_at >= :window_start AND "
            "created_at < :window_end"
        ),
    ),
    "payment_success": KPIDefinition(
        key="payment_success",
        name="Payment attempt success rate",
        description="Share of payment attempts that verify successfully.",
        numerator="PaymentAttempt.status = 'verified', created_at in window",
        denominator="All payment attempts, created_at in window",
        window="[window_start, window_end) on PaymentAttempt.created_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Denominator includes every attempt status (created/redirect_ready/"
        "verified/failed)",
        late_event_handling=(
            "Attempt is bucketed by creation time, not verification time -- an attempt "
            "created in-window but verified via callback after window_end still counts "
            "in the numerator once verified, as of query time"
        ),
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE status = 'verified') AS numerator, count(*) AS "
            "denominator FROM payments_attempts WHERE created_at >= :window_start AND "
            "created_at < :window_end"
        ),
    ),
    "sourcing_failure": KPIDefinition(
        key="sourcing_failure",
        name="Sourcing job failure rate",
        description="Share of sourcing jobs that fail rather than commit.",
        numerator="SourcingJob.status = 'failed', created_at in window",
        denominator="All sourcing jobs, created_at in window",
        window="[window_start, window_end) on SourcingJob.created_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Denominator includes pending/committed/failed/cancelled",
        late_event_handling=(
            "Bucketed by job creation time; a job still pending at query time counts in "
            "the denominator but not the numerator until it actually fails"
        ),
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE status = 'failed') AS numerator, count(*) AS "
            "denominator FROM sourcing_jobs WHERE created_at >= :window_start AND "
            "created_at < :window_end"
        ),
    ),
    "delivery_within_commitment": KPIDefinition(
        key="delivery_within_commitment",
        name="Delivery within commitment",
        description="Share of delivered orders delivered at or before their commitment time.",
        numerator="Order.delivered_at <= delivery_commitment_at, delivered_at in window",
        denominator="Order.delivered_at IS NOT NULL, delivered_at in window",
        window="[window_start, window_end) on Order.delivered_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Only delivered orders; undelivered/cancelled/failed orders excluded "
        "from both numerator and denominator (see delivery_commitment_hours in system policies "
        "for the commitment definition)",
        late_event_handling="Anchored on delivery time, which is final once set -- not revised "
        "after the fact",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE delivered_at <= delivery_commitment_at) AS "
            "numerator, count(*) AS denominator FROM orders_orders WHERE delivered_at >= "
            ":window_start AND delivered_at < :window_end"
        ),
    ),
    "late_credit_issuance": KPIDefinition(
        key="late_credit_issuance",
        name="Late-delivery credit issuance",
        description="Wallet credits issued for late delivery.",
        numerator="sum(WalletCredit.original_amount_irr) WHERE source_type = "
        "'late_delivery_credit', created_at in window",
        denominator="count of the same rows",
        window="[window_start, window_end) on WalletCredit.created_at",
        timezone="UTC",
        currency="IRR",
        status_inclusion="Only source_type = 'late_delivery_credit' rows; other credit sources "
        "excluded",
        late_event_handling="Credits are issued once and never revised; no late-arrival concern",
        version=1,
        validation_query=(
            "SELECT count(*) AS denominator, coalesce(sum(original_amount_irr), 0) AS "
            "numerator FROM wallet_credits WHERE source_type = 'late_delivery_credit' AND "
            "created_at >= :window_start AND created_at < :window_end"
        ),
    ),
    "late_credit_redemption": KPIDefinition(
        key="late_credit_redemption",
        name="Late-delivery credit redemption",
        description="Late-delivery wallet credit actually spent via a debit allocation.",
        numerator="sum(WalletDebitAllocation.amount_irr) joined to WalletCredit where "
        "source_type = 'late_delivery_credit', joined to the owning WalletDebit for its "
        "created_at (WalletDebitAllocation has no timestamp of its own)",
        denominator="sum(WalletCredit.original_amount_irr) for the same source_type, "
        "created_at in window (issuance in the same window, for a same-cohort redemption rate)",
        window="[window_start, window_end) on WalletDebit.created_at for the numerator; "
        "WalletCredit.created_at for the denominator",
        timezone="UTC",
        currency="IRR",
        status_inclusion="Only source_type = 'late_delivery_credit' credits and their "
        "allocations",
        late_event_handling=(
            "Numerator and denominator use different windowed columns (allocation vs. "
            "issuance) -- a credit issued in-window may be redeemed after window_end, which "
            "this ratio does not capture; it measures same-window issuance vs. same-window "
            "redemption activity, not cohort lifetime redemption"
        ),
        version=1,
        validation_query=(
            "SELECT coalesce((SELECT sum(a.amount_irr) FROM wallet_debit_allocations a JOIN "
            "wallet_credits c ON c.id = a.wallet_credit_id JOIN wallet_debits d ON d.id = "
            "a.wallet_debit_id WHERE c.source_type = 'late_delivery_credit' AND "
            "d.created_at >= :window_start AND d.created_at < :window_end), 0) AS numerator, "
            "coalesce((SELECT sum(original_amount_irr) FROM wallet_credits WHERE source_type "
            "= 'late_delivery_credit' AND created_at >= :window_start AND created_at < "
            ":window_end), 0) AS denominator"
        ),
    ),
    "repeat_purchase": KPIDefinition(
        key="repeat_purchase",
        name="Repeat purchase rate",
        description="Share of paying customers in the window who had already paid for an "
        "earlier order before this one.",
        numerator="Distinct customers with a paid order in window who have an earlier paid "
        "order (paid_at strictly before the in-window order's paid_at)",
        denominator="Distinct customers with at least one paid order in window",
        window="[window_start, window_end) on Order.paid_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Only orders with paid_at set (any current status)",
        late_event_handling="A customer's first-ever paid order always counts as non-repeat "
        "even if an earlier order of theirs is still pending as of query time",
        version=1,
        validation_query=(
            "SELECT count(DISTINCT customer_identity_id) FILTER (WHERE prior_count > 0) AS "
            "numerator, count(DISTINCT customer_identity_id) AS denominator FROM (SELECT "
            "o.customer_identity_id, o.paid_at, (SELECT count(*) FROM orders_orders p WHERE "
            "p.customer_identity_id = o.customer_identity_id AND p.paid_at IS NOT NULL AND "
            "p.paid_at < o.paid_at) AS prior_count FROM orders_orders o WHERE o.paid_at >= "
            ":window_start AND o.paid_at < :window_end) sub"
        ),
    ),
    "gmv": KPIDefinition(
        key="gmv",
        name="Gross merchandise value",
        description="Total merchandise value of orders that reached payment in the window.",
        numerator="sum(Order.merchandise_total_irr) WHERE paid_at in window",
        denominator="count of the same rows",
        window="[window_start, window_end) on Order.paid_at",
        timezone="UTC",
        currency="IRR",
        status_inclusion="Any order with paid_at set, regardless of later status (delivered, "
        "cancelled, etc.) -- GMV is a payment-moment metric, not a delivery-moment metric",
        late_event_handling="Anchored on paid_at, which is set once and never revised",
        version=1,
        validation_query=(
            "SELECT count(*) AS denominator, coalesce(sum(merchandise_total_irr), 0) AS "
            "numerator FROM orders_orders WHERE paid_at >= :window_start AND paid_at < "
            ":window_end"
        ),
    ),
    "margin": KPIDefinition(
        key="margin",
        name="Gross margin",
        description="Revenue minus cost of goods for orders in the window.",
        numerator="Not computable",
        denominator="Not computable",
        window="n/a",
        timezone="UTC",
        currency="IRR",
        status_inclusion="n/a",
        late_event_handling="n/a",
        version=1,
        validation_query="n/a",
        computable=False,
        data_limitation=(
            "No supplier cost field exists anywhere in the regular commerce schema: Offer "
            "stores only price_irr (sale price) and reference_price_irr (market reference, "
            "not cost), and PurchaseBatch stores commitment metadata but no cost amount. "
            "Only concierge_offers (a small, currently flag-gated slice of volume) records "
            "supplier_cost_irr. Computing a platform-wide margin figure would require adding "
            "a cost field to the sourcing/purchasing schema -- not fabricated here from "
            "reference_price_irr, which is a market comparison price, not a cost"
        ),
    ),
    "reference_price_savings": KPIDefinition(
        key="reference_price_savings",
        name="Reference-price savings",
        description="Customer savings versus each offer's tracked market reference price.",
        numerator="sum((Offer.reference_price_irr - OrderLine.unit_price_irr) * quantity) for "
        "lines whose order paid_at is in window and the offer has a reference_price_irr",
        denominator="sum(Offer.reference_price_irr * quantity) for the same lines",
        window="[window_start, window_end) on Order.paid_at",
        timezone="UTC",
        currency="IRR",
        status_inclusion="Only order lines on orders with paid_at set, and only offers with a "
        "non-null reference_price_irr",
        late_event_handling=(
            "Uses the offer's CURRENT reference_price_irr, not a point-in-time snapshot "
            "(OrderLine does not snapshot it) -- accuracy for older orders degrades if the "
            "reference price has since been updated by price-intelligence collection"
        ),
        version=1,
        validation_query=(
            "SELECT coalesce(sum((f.reference_price_irr - l.unit_price_irr) * l.quantity), 0) "
            "AS numerator, coalesce(sum(f.reference_price_irr * l.quantity), 0) AS denominator "
            "FROM orders_order_lines l JOIN orders_orders o ON o.id = l.order_id JOIN "
            "catalog_offers f ON f.id = l.offer_id WHERE o.paid_at >= :window_start AND "
            "o.paid_at < :window_end AND f.reference_price_irr IS NOT NULL"
        ),
    ),
    "reorder_recommendation_coverage": KPIDefinition(
        key="reorder_recommendation_coverage",
        name="Reorder recommendation coverage",
        description="Share of opened inventory units for which the system ever generated a "
        "replenishment reservation (its persisted form of a reorder recommendation).",
        numerator="Distinct InventoryUnit.id opened in window with >=1 ReplenishmentReservation "
        "ever created for it",
        denominator="InventoryUnit.state = 'opened', opened_at in window",
        window="[window_start, window_end) on InventoryUnit.opened_at",
        timezone="UTC",
        currency=None,
        status_inclusion="All opened units regardless of current estimate status",
        late_event_handling="A unit opened near window_end may not yet have crossed the "
        "depletion threshold that triggers a reservation -- undercounted until it does",
        version=1,
        validation_query=(
            "SELECT count(DISTINCT u.id) FILTER (WHERE r.inventory_unit_id IS NOT NULL) AS "
            "numerator, count(DISTINCT u.id) AS denominator FROM inventory_units u LEFT JOIN "
            "replenishment_reservations r ON r.inventory_unit_id = u.id WHERE u.state = "
            "'opened' AND u.opened_at >= :window_start AND u.opened_at < :window_end"
        ),
    ),
    "reorder_approval_rate": KPIDefinition(
        key="reorder_approval_rate",
        name="Reorder approval rate",
        description="Of replenishment reservations resolved in the window, the share the "
        "customer approved.",
        numerator="ReplenishmentReservation.status = 'approved', created_at in window",
        denominator="ReplenishmentReservation.status IN ('approved','declined','expired',"
        "'invalidated'), created_at in window",
        window="[window_start, window_end) on ReplenishmentReservation.created_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Only terminal-status reservations; still pending_approval rows "
        "excluded from the denominator until resolved",
        late_event_handling="A reservation created near window_end that is still "
        "pending_approval at query time is excluded entirely until it resolves",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE status = 'approved') AS numerator, count(*) AS "
            "denominator FROM replenishment_reservations WHERE status IN ('approved',"
            "'declined','expired','invalidated') AND created_at >= :window_start AND "
            "created_at < :window_end"
        ),
    ),
    "replenishment_conversion": KPIDefinition(
        key="replenishment_conversion",
        name="Replenishment conversion",
        description="Of approved replenishment reservations, the share whose resulting order "
        "was actually delivered.",
        numerator="ReplenishmentReservation.status = 'approved' AND resulting_order_id's Order."
        "status = 'delivered', approved_at in window",
        denominator="ReplenishmentReservation.status = 'approved', approved_at in window",
        window="[window_start, window_end) on ReplenishmentReservation.approved_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Only approved reservations",
        late_event_handling="An order not yet delivered as of query time is excluded from the "
        "numerator until it is; the KPI is a point-in-time snapshot, not a final funnel value",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE o.status = 'delivered') AS numerator, count(*) AS "
            "denominator FROM replenishment_reservations r LEFT JOIN orders_orders o ON o.id = "
            "r.resulting_order_id WHERE r.status = 'approved' AND r.approved_at >= "
            ":window_start AND r.approved_at < :window_end"
        ),
    ),
    "concierge_conversion": KPIDefinition(
        key="concierge_conversion",
        name="Concierge offer conversion",
        description="Of presented concierge offers resolved in the window, the share the "
        "customer accepted.",
        numerator="ConciergeOffer.status = 'accepted', presented_at in window",
        denominator="ConciergeOffer.status IN ('accepted','declined','expired'), presented_at "
        "in window",
        window="[window_start, window_end) on ConciergeOffer.presented_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Only offers that reached offer_presented and then a terminal "
        "customer-facing outcome; 'reviewing'/'unavailable'/'refresh_requested' rows excluded",
        late_event_handling="An offer presented near window_end still awaiting customer "
        "response at query time is excluded until it resolves",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE status = 'accepted') AS numerator, count(*) AS "
            "denominator FROM concierge_offers WHERE status IN ('accepted','declined',"
            "'expired') AND presented_at >= :window_start AND presented_at < :window_end"
        ),
    ),
    "care_journey_start": KPIDefinition(
        key="care_journey_start",
        name="Care journey start rate",
        description="Share of active pets that started at least one care journey in the "
        "window.",
        numerator="Distinct Pet.id with a PetJourney started_at in window",
        denominator="Pet.status = 'active' as of query time",
        window="[window_start, window_end) on PetJourney.started_at for the numerator; "
        "denominator is a current-state snapshot, not window-bound",
        timezone="UTC",
        currency=None,
        status_inclusion="Denominator counts every active pet regardless of tenure -- not "
        "restricted to pets that existed for the whole window",
        late_event_handling="n/a (count-based, not a rate that revises after the fact)",
        version=1,
        validation_query=(
            "SELECT count(DISTINCT pet_id) FILTER (WHERE started_at >= :window_start AND "
            "started_at < :window_end) AS numerator, (SELECT count(*) FROM pets_pets WHERE "
            "status = 'active') AS denominator FROM journeys_pet_journeys"
        ),
    ),
    "care_journey_completion": KPIDefinition(
        key="care_journey_completion",
        name="Care journey completion rate",
        description="Of care journeys that reached a terminal state in the window, the share "
        "completed rather than stopped.",
        numerator="PetJourney.status = 'completed', started_at in window",
        denominator="PetJourney.status IN ('completed','stopped'), started_at in window",
        window="[window_start, window_end) on PetJourney.started_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Still-active/paused journeys excluded from the denominator until "
        "they reach a terminal state",
        late_event_handling="A journey started near window_end still active at query time is "
        "excluded until it resolves",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE status = 'completed') AS numerator, count(*) AS "
            "denominator FROM journeys_pet_journeys WHERE status IN ('completed','stopped') "
            "AND started_at >= :window_start AND started_at < :window_end"
        ),
    ),
    "inventory_estimate_completeness": KPIDefinition(
        key="inventory_estimate_completeness",
        name="Inventory estimate completeness",
        description="Share of opened inventory units with a resolvable (non-unknown-share) "
        "active food estimate.",
        numerator="InventoryUnit.state = 'opened', opened_at in window, with an active "
        "FoodEstimate having low_days/high_days both set",
        denominator="InventoryUnit.state = 'opened', opened_at in window",
        window="[window_start, window_end) on InventoryUnit.opened_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Only currently-opened units; exhausted/discarded units excluded",
        late_event_handling="A unit's estimate can change (correction) after opening -- this "
        "reflects the CURRENT active estimate as of query time, not the estimate at opening",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE e.low_days IS NOT NULL AND e.high_days IS NOT "
            "NULL) AS numerator, count(*) AS denominator FROM inventory_units u LEFT JOIN "
            "food_estimation_estimates e ON e.inventory_unit_id = u.id AND e.status = "
            "'active' WHERE u.state = 'opened' AND u.opened_at >= :window_start AND "
            "u.opened_at < :window_end"
        ),
    ),
    "knowledge_release_health": KPIDefinition(
        key="knowledge_release_health",
        name="Knowledge release health",
        description="Share of the currently published knowledge release's care guidance that "
        "is veterinary-approved and app-eligible.",
        numerator="KnowledgeGuidance.review_status = 'veterinary_approved' AND app_eligible = "
        "true, for the currently published release",
        denominator="All KnowledgeGuidance rows for the currently published release",
        window="Current-state snapshot of the single published KnowledgeRelease -- not a "
        "date-range window (a knowledge release does not have a meaningful per-day rate)",
        timezone="UTC",
        currency=None,
        status_inclusion="Only the release with status = 'published' (at most one, by "
        "constraint); returns not-computable if none is published",
        late_event_handling="n/a (snapshot, not a windowed rate)",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE g.review_status = 'veterinary_approved' AND "
            "g.app_eligible) AS numerator, count(*) AS denominator FROM "
            "pet_knowledge_guidance g JOIN pet_knowledge_releases r ON r.id = g.release_id "
            "WHERE r.status = 'published'"
        ),
    ),
    "pi_collection_quality": KPIDefinition(
        key="pi_collection_quality",
        name="Price-intelligence collection quality",
        description="Share of external product match attempts confidently approved rather "
        "than left unmatched/needing review.",
        numerator="ExternalProductMatch.match_status = 'approved', created_at in window",
        denominator="All external product matches, created_at in window",
        window="[window_start, window_end) on ExternalProductMatch.created_at",
        timezone="UTC",
        currency=None,
        status_inclusion="Denominator includes unmatched/suggested/needs_review/approved/"
        "rejected",
        late_event_handling="A match created near window_end still awaiting operator review "
        "at query time counts in the denominator but not the numerator until reviewed",
        version=1,
        validation_query=(
            "SELECT count(*) FILTER (WHERE match_status = 'approved') AS numerator, count(*) "
            "AS denominator FROM price_intelligence_external_product_matches WHERE "
            "created_at >= :window_start AND created_at < :window_end"
        ),
    ),
}
