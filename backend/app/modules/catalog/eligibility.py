from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement

from app.modules.catalog.models import Offer, Product, Supplier

# The single source of truth for which offer.mode values an ordinary,
# customer-facing catalog surface (browse/search/checkout/
# availability-subscriptions) may ever expose. 'concierge_only' is never
# included here at any tier -- it is a one-off Offer/Product pair bound
# to one specific customer/request, reachable only through concierge's
# own ownership-checked routes (app.modules.concierge), never through a
# generic catalog surface regardless of state. 'reserve' is included only
# once the reserve-now workflow is actually enabled (see catalog_modes) --
# ordinary checkout must reject it even when reserve_now_enabled is true,
# since converting a reserve offer requires the operator
# price/availability reconfirmation workflow (app.modules.reservations),
# not a plain purchase.
ORDINARY_MODES = frozenset({"full_payment"})
ORDINARY_AND_RESERVE_MODES = frozenset({"full_payment", "reserve"})

# The offer detail page (GET /catalog/offers/{id}) is deliberately more
# permissive than list/search/subscribe: knowing a reserve-mode offer
# exists and seeing its price is not itself sensitive (only converting it
# through the ordinary checkout path is gated, and that already rejects
# 'reserve' regardless of allowed_modes) -- so its detail page stays
# viewable even while reserve_now_enabled is false and it is therefore
# absent from browse/search. 'concierge_only' is still excluded: it is
# bound to one specific customer/request, and its price is meaningful
# only to them.
DETAIL_VIEWABLE_MODES = frozenset({"full_payment", "reserve"})


def catalog_modes(*, reserve_now_enabled: bool) -> frozenset[str]:
    """The allowed_modes every ordinary catalog-facing read/write path
    (list, search, checkout, subscribe, reorder) should pass to
    evaluate_offer_eligibility/orderable_offer_filters -- one place
    deciding whether 'reserve' is in scope, instead of each call site
    independently guessing at reserve_now_enabled's effect. offer_detail
    uses DETAIL_VIEWABLE_MODES instead -- see its docstring."""
    return ORDINARY_AND_RESERVE_MODES if reserve_now_enabled else ORDINARY_MODES


@dataclass(frozen=True, slots=True)
class OfferEligibility:
    """Every fact a catalog-facing read/write path might need, computed
    once. Each property below is a named *tier*, not a single yes/no --
    different surfaces legitimately need different tiers (a detail page
    may show a sold-out offer with a "temporarily unavailable" state
    instead of a blank 404; a subscription exists specifically to wait
    out that same transient unavailability), but none of them may ever
    disagree about the facts that never change without a real workflow
    (product/supplier active, offer mode, retired status)."""

    product_active: bool
    supplier_active: bool
    orderable_status: bool
    viewable_status: bool
    stock_ready: bool
    capacity_open: bool
    within_sale_window: bool
    mode_allowed: bool

    @property
    def orderable(self) -> bool:
        """Listable in browse/search, purchasable at checkout, reservable
        -- everything must currently hold."""
        return (
            self.product_active
            and self.supplier_active
            and self.orderable_status
            and self.stock_ready
            and self.capacity_open
            and self.within_sale_window
            and self.mode_allowed
        )

    @property
    def viewable(self) -> bool:
        """Detail-page visible: a real, active-product/active-supplier
        offer of a mode this surface serves, in a status that isn't
        retired -- but capacity/stock/sale-window may be transiently
        unavailable (shown as a state, not a 404)."""
        return (
            self.product_active
            and self.supplier_active
            and self.viewable_status
            and self.mode_allowed
        )

    @property
    def subscribable(self) -> bool:
        """A subscription exists specifically to wait out capacity/stock/
        sale-window transient unavailability, so those never disqualify
        it here -- but product/supplier/mode/retired-status facts that a
        subscription could never wait out on its own must still reject,
        or subscribing becomes another way to discover (and be notified
        the instant it activates) an offer this surface was never meant
        to expose at all."""
        return (
            self.product_active
            and self.supplier_active
            and self.viewable_status
            and self.mode_allowed
        )


def evaluate_offer_eligibility(
    offer: Offer,
    product: Product,
    supplier: Supplier,
    *,
    now: datetime,
    allowed_modes: frozenset[str],
) -> OfferEligibility:
    return OfferEligibility(
        product_active=product.status == "active",
        supplier_active=supplier.active,
        orderable_status=offer.status == "active",
        viewable_status=offer.status in ("active", "unavailable"),
        stock_ready=offer.stock_posture == "sourced_after_payment",
        capacity_open=offer.sourcing_capacity_status == "open",
        within_sale_window=(
            (offer.available_from is None or offer.available_from <= now)
            and (offer.available_until is None or offer.available_until > now)
        ),
        mode_allowed=offer.mode in allowed_modes,
    )


def orderable_offer_filters(
    now: datetime, *, allowed_modes: frozenset[str]
) -> tuple[ColumnElement[bool], ...]:
    """The SQL-query equivalent of evaluate_offer_eligibility(...).orderable,
    for listing surfaces (browse/search/alternatives/reorder) that filter
    at the database rather than evaluating one already-loaded offer.
    Requires the caller's query to join both Product and Supplier (every
    call site either already does or has been updated to) -- filtering
    only Offer's own columns is exactly the drift this module exists to
    close, so this deliberately does not offer a Product/Supplier-free
    variant."""
    return (
        Offer.status == "active",
        Offer.stock_posture == "sourced_after_payment",
        Offer.sourcing_capacity_status == "open",
        (Offer.available_from.is_(None)) | (Offer.available_from <= now),
        (Offer.available_until.is_(None)) | (Offer.available_until > now),
        Offer.mode.in_(allowed_modes),
        Product.status == "active",
        Supplier.active.is_(True),
    )
