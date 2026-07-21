from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import and_, delete, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    AvailabilitySubscriptionResponse,
    CursorPage,
    DelayAcknowledgementResponse,
    FulfillmentTimelineItem,
    OfferDetailResponse,
    OfferListItem,
    OffsetPage,
    OrderAddressSnapshotResponse,
    OrderCancellationResponse,
    OrderDetailResponse,
    OrderJourneyResponse,
    OrderLineResponse,
    OrderListItem,
    OrderPolicyFieldsResponse,
    PaymentCallbackResponse,
    PaymentRedirectResponse,
    ProductAlternativeResponse,
    ProductMediaResponse,
    ReservationResponse,
    SafePaymentSummaryResponse,
    ShelfLifeExceptionResponse,
    SourcedUnitResponse,
)
from app.api.cursor import CursorError, CursorPosition, cursor_page, decode_cursor, encode_cursor
from app.api.dependencies import CurrentIdentity
from app.api.pagination import Pagination, page
from app.common.time import utc_now
from app.core.config import Settings, get_settings
from app.db.session import SessionFactory, get_db_session
from app.integrations.payment.factory import (
    PaymentProviderNotConfiguredError,
    build_payment_gateway,
)
from app.integrations.payment.zarinpal import ZarinpalError, callback_allows_verification
from app.modules.catalog.eligibility import (
    DETAIL_VIEWABLE_MODES,
    catalog_modes,
    evaluate_offer_eligibility,
    orderable_offer_filters,
)
from app.modules.catalog.models import (
    CatalogAvailabilitySubscription,
    Offer,
    Product,
    ProductAlternative,
    ProductMedia,
    Supplier,
)
from app.modules.checkout.service import CheckoutError, CheckoutItem, CheckoutService
from app.modules.households.access import HouseholdAccessError, require_household_membership
from app.modules.households.models import HouseholdAddress, HouseholdMembership
from app.modules.orders.cancellation import (
    CancellationError,
    OrderCancellation,
    cancel_order_by_customer,
    is_order_cancellation_eligible_now,
)
from app.modules.orders.fulfillment import FulfillmentEvent
from app.modules.orders.models import Order, OrderDelayAcknowledgement, OrderLine, OrderLinePetPlan
from app.modules.orders.shelf_life_exceptions import (
    ShelfLifeException,
    ShelfLifeExceptionError,
    accept_shelf_life_exception,
    decline_shelf_life_exception,
)
from app.modules.payments.models import PaymentAttempt
from app.modules.payments.service import PaymentService, PaymentWorkflowError
from app.modules.pet_knowledge.search import normalize_persian_search
from app.modules.pets.models import Pet
from app.modules.purchasing.service import PurchasingError
from app.modules.reservations.models import Reservation
from app.modules.reservations.service import (
    ReservationError,
    approve_and_convert_reservation,
    decline_reservation,
    request_reservation,
)
from app.modules.system.idempotency import canonical_request_hash
from app.modules.trust.models import SourcedUnitEvidence

router = APIRouter(tags=["commerce"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)]
PaginationDependency = Annotated[Pagination, Depends()]


class CheckoutItemBody(BaseModel):
    offer_id: UUID
    quantity: int = Field(ge=1, le=100)


class CheckoutBody(BaseModel):
    household_id: UUID
    address_id: UUID
    items: list[CheckoutItemBody] = Field(min_length=1, max_length=50)


class OrderResponse(BaseModel):
    id: UUID
    status: str
    merchandise_total_irr: int
    currency: str


class PaymentRequestBody(BaseModel):
    callback_url: HttpUrl


class OrderPetPlanLineBody(BaseModel):
    order_line_id: UUID
    pet_ids: list[UUID] = Field(max_length=20)


class OrderPetPlanBody(BaseModel):
    lines: list[OrderPetPlanLineBody] = Field(max_length=50)


def _order_item(order: Order) -> OrderListItem:
    return OrderListItem(
        id=order.id,
        household_id=order.household_id,
        status=order.status,
        total_irr=order.merchandise_total_irr,
        currency=order.currency,
        paid_at=order.paid_at,
        delivery_commitment_at=order.delivery_commitment_at,
        delivered_at=order.delivered_at,
    )


def _offer_list_item(offer: Offer, supplier: Supplier) -> OfferListItem:
    return OfferListItem(
        id=offer.id,
        product_id=offer.product_id,
        sku=offer.sku,
        title_fa=offer.title_fa,
        unit_label_fa=offer.unit_label_fa,
        price_irr=offer.price_irr,
        reference_price_irr=offer.reference_price_irr,
        supplier_country=supplier.country_code,
        stock_posture=offer.stock_posture,
        authenticity="supplier_verified",
        minimum_shelf_life_months=offer.minimum_shelf_life_months,
        reference_price_reviewed_at=(
            offer.reference_price_reviewed_at.date().isoformat()
            if offer.reference_price_reviewed_at
            else None
        ),
        available_until=(offer.available_until.isoformat() if offer.available_until else None),
    )


@router.get("/catalog/offers", response_model=list[OfferListItem])
async def list_offers(
    session: SessionDependency, settings: SettingsDependency
) -> list[OfferListItem]:
    now = utc_now()
    modes = catalog_modes(reserve_now_enabled=settings.reserve_now_enabled)
    rows = (
        await session.execute(
            select(Offer, Supplier)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .join(Product, Product.id == Offer.product_id)
            .where(*orderable_offer_filters(now, allowed_modes=modes))
            .order_by(Offer.title_fa)
            .limit(500)
        )
    ).all()
    return [_offer_list_item(offer, supplier) for offer, supplier in rows]


def _escape_like_term(normalized: str) -> str:
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/catalog/offers/search", response_model=OffsetPage[OfferListItem])
async def search_offers(
    session: SessionDependency,
    pagination: PaginationDependency,
    settings: SettingsDependency,
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> dict[str, object]:
    now = utc_now()
    normalized = normalize_persian_search(q)
    if not normalized:
        return page([], total=0, pagination=pagination)
    modes = catalog_modes(reserve_now_enabled=settings.reserve_now_enabled)
    availability = orderable_offer_filters(now, allowed_modes=modes)
    term = _escape_like_term(normalized)
    match = or_(
        Offer.title_fa_search.like(term, escape="\\"),
        Offer.sku_search.like(term, escape="\\"),
    )
    total = int(
        await session.scalar(
            select(func.count(Offer.id))
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .join(Product, Product.id == Offer.product_id)
            .where(*availability, match)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(Offer, Supplier)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .join(Product, Product.id == Offer.product_id)
            .where(*availability, match)
            .order_by(Offer.title_fa, Offer.id)
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
    ).all()
    items = [_offer_list_item(offer, supplier) for offer, supplier in rows]
    return page(items, total=total, pagination=pagination)


@router.get("/catalog/offers/{offer_id}", response_model=OfferDetailResponse)
async def offer_detail(offer_id: UUID, session: SessionDependency) -> OfferDetailResponse:
    # This route is fully public/unauthenticated -- reachable by anyone
    # who has or guesses the id, with no ownership check possible.
    # evaluate_offer_eligibility's `viewable` tier, with
    # DETAIL_VIEWABLE_MODES (see its docstring: unlike list/search, a
    # reserve-mode offer's detail page stays visible even when
    # reserve_now_enabled is false -- only 'concierge_only', bound to one
    # specific customer/request, is excluded) -- but, unlike list/search,
    # still shows a real detail page (not a 404) for an offer that's
    # merely transiently out of capacity or outside its sale window, as
    # "temporarily_unavailable".
    row = (
        await session.execute(
            select(Offer, Product, Supplier)
            .join(Product, Product.id == Offer.product_id)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .where(Offer.id == offer_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    offer, product, supplier = row
    eligibility = evaluate_offer_eligibility(
        offer, product, supplier, now=utc_now(), allowed_modes=DETAIL_VIEWABLE_MODES
    )
    if not eligibility.viewable:
        raise HTTPException(status_code=404, detail="offer_not_found")
    media = list(
        (
            await session.scalars(
                select(ProductMedia)
                .where(ProductMedia.product_id == product.id, ProductMedia.active.is_(True))
                .order_by(ProductMedia.sort_order, ProductMedia.id)
            )
        ).all()
    )
    unavailable = not (
        eligibility.orderable_status
        and eligibility.stock_ready
        and eligibility.capacity_open
        and eligibility.within_sale_window
    )
    saving_percent = None
    if offer.reference_price_irr is not None:
        saving_percent = max(
            0, ((offer.reference_price_irr - offer.price_irr) * 100) // offer.reference_price_irr
        )
    return OfferDetailResponse(
        id=offer.id,
        product_id=product.id,
        sku=offer.sku,
        title_fa=offer.title_fa,
        description_fa=product.description_fa,
        unit_label_fa=offer.unit_label_fa,
        nominal_quantity_grams=product.nominal_quantity_grams,
        media=[
            ProductMediaResponse(
                media_type=item.media_type,
                public_reference=item.public_reference,
                alt_text_fa=item.alt_text_fa,
                sort_order=item.sort_order,
            )
            for item in media
        ],
        availability="temporarily_unavailable" if unavailable else "available",
        availability_reason_key="temporarily_unavailable" if unavailable else None,
        price_irr=offer.price_irr,
        reference_price_irr=offer.reference_price_irr,
        saving_percent=saving_percent,
        reference_price_reviewed_at=offer.reference_price_reviewed_at,
        supplier_country_code=supplier.country_code,
        authenticity="supplier_verified",
        minimum_shelf_life_months_at_delivery=offer.minimum_shelf_life_months,
        available_from=offer.available_from,
        available_until=offer.available_until,
    )


@router.get(
    "/catalog/products/{product_id}/alternatives",
    response_model=list[ProductAlternativeResponse],
)
async def list_product_alternatives(
    product_id: UUID, session: SessionDependency, settings: SettingsDependency
) -> list[ProductAlternativeResponse]:
    now = utc_now()
    alternatives = list(
        (
            await session.scalars(
                select(ProductAlternative)
                .where(
                    ProductAlternative.source_product_id == product_id,
                    ProductAlternative.status == "approved",
                )
                .order_by(ProductAlternative.rank, ProductAlternative.id)
            )
        ).all()
    )
    if not alternatives:
        return []
    alternative_product_ids = {a.alternative_product_id for a in alternatives}
    modes = catalog_modes(reserve_now_enabled=settings.reserve_now_enabled)
    rows = (
        await session.execute(
            select(Offer, Supplier)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .join(Product, Product.id == Offer.product_id)
            .where(
                Offer.product_id.in_(alternative_product_ids),
                *orderable_offer_filters(now, allowed_modes=modes),
            )
            .order_by(Offer.product_id, Offer.price_irr, Offer.id)
        )
    ).all()
    # Revalidated at read time, not cached: one representative (cheapest
    # currently-available) offer per alternative product. An alternative
    # whose product currently has no available offer is silently omitted,
    # never shown as a substitute that cannot actually be bought.
    best_offer_by_product: dict[UUID, tuple[Offer, Supplier]] = {}
    for offer, supplier in rows:
        if offer.product_id not in best_offer_by_product:
            best_offer_by_product[offer.product_id] = (offer, supplier)
    items: list[ProductAlternativeResponse] = []
    for alternative in alternatives:
        found = best_offer_by_product.get(alternative.alternative_product_id)
        if found is None:
            continue
        offer, supplier = found
        items.append(
            ProductAlternativeResponse(
                id=alternative.id,
                rank=alternative.rank,
                rationale_fa=alternative.rationale_fa,
                compatibility_notes_fa=alternative.compatibility_notes_fa,
                offer=_offer_list_item(offer, supplier),
            )
        )
    return items


@router.post(
    "/catalog/offers/{offer_id}/availability-subscriptions",
    response_model=AvailabilitySubscriptionResponse,
)
async def subscribe_offer_availability(
    offer_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> AvailabilitySubscriptionResponse:
    if not settings.availability_subscriptions_enabled:
        raise HTTPException(status_code=409, detail="availability_subscriptions_disabled")
    row = (
        await session.execute(
            select(Offer, Product, Supplier)
            .join(Product, Product.id == Offer.product_id)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .where(Offer.id == offer_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    offer, product, supplier = row
    # A subscription is a promise to notify once this offer becomes
    # orderable -- so transient capacity/stock/sale-window unavailability
    # is exactly what it exists to wait out (subscribable, not orderable,
    # is the right tier here). But an offer this surface was never meant
    # to expose at all (concierge_only, reserve when disabled, an
    # inactive product/supplier, retired) must still be rejected here,
    # matching list/search/detail -- otherwise subscribing becomes an
    # alternate way to discover, and be notified the instant it
    # activates, an offer those surfaces correctly hide.
    eligibility = evaluate_offer_eligibility(
        offer,
        product,
        supplier,
        now=utc_now(),
        allowed_modes=catalog_modes(reserve_now_enabled=settings.reserve_now_enabled),
    )
    if not eligibility.subscribable:
        raise HTTPException(status_code=404, detail="offer_not_found")
    existing = await session.scalar(
        select(CatalogAvailabilitySubscription).where(
            CatalogAvailabilitySubscription.identity_id == identity.id,
            CatalogAvailabilitySubscription.offer_id == offer.id,
            CatalogAvailabilitySubscription.status == "active",
        )
    )
    if existing is None:
        latest = await session.scalar(
            select(CatalogAvailabilitySubscription)
            .where(
                CatalogAvailabilitySubscription.identity_id == identity.id,
                CatalogAvailabilitySubscription.offer_id == offer.id,
            )
            .order_by(CatalogAvailabilitySubscription.activation_cycle.desc())
            .limit(1)
        )
        household_id = await session.scalar(
            select(HouseholdMembership.household_id)
            .where(HouseholdMembership.identity_id == identity.id)
            .order_by(HouseholdMembership.created_at)
            .limit(1)
        )
        existing = CatalogAvailabilitySubscription(
            identity_id=identity.id,
            household_id=household_id,
            offer_id=offer.id,
            status="active",
            activation_cycle=(latest.activation_cycle + 1 if latest else 0),
        )
        session.add(existing)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(CatalogAvailabilitySubscription).where(
                    CatalogAvailabilitySubscription.identity_id == identity.id,
                    CatalogAvailabilitySubscription.offer_id == offer.id,
                    CatalogAvailabilitySubscription.status == "active",
                )
            )
            if existing is None:
                raise
    await session.commit()
    return _availability_subscription_response(existing)


@router.delete(
    "/catalog/offers/{offer_id}/availability-subscriptions",
    response_model=AvailabilitySubscriptionResponse,
)
async def cancel_offer_availability_subscription(
    offer_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> AvailabilitySubscriptionResponse:
    if not settings.availability_subscriptions_enabled:
        raise HTTPException(status_code=409, detail="availability_subscriptions_disabled")
    subscription = await session.scalar(
        select(CatalogAvailabilitySubscription)
        .where(
            CatalogAvailabilitySubscription.identity_id == identity.id,
            CatalogAvailabilitySubscription.offer_id == offer_id,
            CatalogAvailabilitySubscription.status == "active",
        )
        .with_for_update()
    )
    now = utc_now()
    if subscription is None:
        subscription = await session.scalar(
            select(CatalogAvailabilitySubscription)
            .where(
                CatalogAvailabilitySubscription.identity_id == identity.id,
                CatalogAvailabilitySubscription.offer_id == offer_id,
            )
            .order_by(CatalogAvailabilitySubscription.created_at.desc())
            .limit(1)
        )
        if subscription is None:
            offer = await session.get(Offer, offer_id)
            if offer is None or offer.status == "retired":
                raise HTTPException(status_code=404, detail="offer_not_found")
            subscription = CatalogAvailabilitySubscription(
                identity_id=identity.id,
                offer_id=offer_id,
                status="cancelled",
                activation_cycle=0,
                cancelled_at=now,
            )
            session.add(subscription)
    elif subscription.cancelled_at is None:
        subscription.status = "cancelled"
        subscription.cancelled_at = now
    await session.commit()
    return _availability_subscription_response(subscription)


@router.get(
    "/me/availability-subscriptions",
    response_model=OffsetPage[AvailabilitySubscriptionResponse],
)
async def list_availability_subscriptions(
    identity: CurrentIdentity,
    session: SessionDependency,
    pagination: PaginationDependency,
    settings: SettingsDependency,
) -> OffsetPage[AvailabilitySubscriptionResponse]:
    if not settings.availability_subscriptions_enabled:
        raise HTTPException(status_code=409, detail="availability_subscriptions_disabled")
    filters = (CatalogAvailabilitySubscription.identity_id == identity.id,)
    total = int(
        await session.scalar(select(func.count(CatalogAvailabilitySubscription.id)).where(*filters))
        or 0
    )
    rows = list(
        (
            await session.scalars(
                select(CatalogAvailabilitySubscription)
                .where(*filters)
                .order_by(CatalogAvailabilitySubscription.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    )
    return OffsetPage[AvailabilitySubscriptionResponse].model_validate(
        page(
            [_availability_subscription_response(item) for item in rows],
            total=total,
            pagination=pagination,
        )
    )


@router.post("/checkout/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: CheckoutBody,
    idempotency_key: IdempotencyKey,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> OrderResponse:
    try:
        await require_household_membership(
            session,
            identity_id=identity.id,
            household_id=body.household_id,
        )
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="household_not_found") from exc
    try:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=identity.id,
            household_id=body.household_id,
            address_id=body.address_id,
            items=[CheckoutItem(item.offer_id, item.quantity) for item in body.items],
            idempotency_key=idempotency_key,
        )
    except CheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _order_response(order)


class ReservationCreateBody(BaseModel):
    household_id: UUID
    offer_id: UUID
    quantity: int = Field(ge=1, le=100)


class ReservationApproveBody(BaseModel):
    address_id: UUID


class ReservationDeclineBody(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


def _reservation_response(reservation: Reservation) -> ReservationResponse:
    return ReservationResponse(
        id=reservation.id,
        offer_id=reservation.offer_id,
        quantity=reservation.quantity,
        requested_price_irr=reservation.requested_price_irr,
        status=reservation.status,
        operator_review_by=reservation.operator_review_by,
        reconfirmed_price_irr=reservation.reconfirmed_price_irr,
        reconfirmed_available=reservation.reconfirmed_available,
        proposal_reason=reservation.proposal_reason,
        customer_respond_by=reservation.customer_respond_by,
        responded_at=reservation.responded_at,
        order_id=reservation.order_id,
    )


@router.post(
    "/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED
)
async def create_reservation(
    body: ReservationCreateBody,
    idempotency_key: IdempotencyKey,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReservationResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    try:
        await require_household_membership(
            session, identity_id=identity.id, household_id=body.household_id
        )
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="household_not_found") from exc
    offer = await session.scalar(select(Offer).where(Offer.id == body.offer_id).with_for_update())
    if offer is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    try:
        reservation = await request_reservation(
            session,
            offer=offer,
            customer_identity_id=identity.id,
            household_id=body.household_id,
            quantity=body.quantity,
            idempotency_key=idempotency_key,
        )
    except ReservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _reservation_response(reservation)


@router.get("/reservations", response_model=list[ReservationResponse])
async def list_reservations(
    identity: CurrentIdentity, session: SessionDependency, settings: SettingsDependency
) -> list[ReservationResponse]:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    rows = list(
        (
            await session.scalars(
                select(Reservation)
                .where(Reservation.customer_identity_id == identity.id)
                .order_by(Reservation.requested_at.desc())
                .limit(200)
            )
        ).all()
    )
    return [_reservation_response(row) for row in rows]


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReservationResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    reservation = await session.get(Reservation, reservation_id)
    if reservation is None or reservation.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    return _reservation_response(reservation)


@router.post("/reservations/{reservation_id}/approve", response_model=OrderResponse)
async def approve_reservation(
    reservation_id: UUID,
    body: ReservationApproveBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OrderResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    reservation = await session.scalar(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    )
    if reservation is None or reservation.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    row = (
        await session.execute(
            select(Offer, Supplier)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .where(Offer.id == reservation.offer_id)
            .with_for_update(of=Offer)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    offer, supplier = row
    address = await session.get(HouseholdAddress, body.address_id)
    if address is None:
        raise HTTPException(status_code=404, detail="address_not_found")
    try:
        _, order = await approve_and_convert_reservation(
            session,
            reservation=reservation,
            offer=offer,
            supplier=supplier,
            address=address,
            customer_identity_id=identity.id,
        )
    except ReservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _order_response(order)


@router.post("/reservations/{reservation_id}/decline", response_model=ReservationResponse)
async def decline_reservation_endpoint(
    reservation_id: UUID,
    body: ReservationDeclineBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReservationResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    reservation = await session.scalar(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    )
    if reservation is None or reservation.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    try:
        reservation = await decline_reservation(
            session,
            reservation=reservation,
            customer_identity_id=identity.id,
            reason=body.reason,
        )
    except ReservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _reservation_response(reservation)


@router.post("/orders/{order_id}/payments/zarinpal", response_model=PaymentRedirectResponse)
async def initiate_payment(
    order_id: UUID,
    body: PaymentRequestBody,
    idempotency_key: IdempotencyKey,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> PaymentRedirectResponse:
    try:
        gateway = build_payment_gateway(settings)
    except PaymentProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="payment_provider_not_configured") from exc
    try:
        result = await PaymentService(
            delivery_commitment_hours=settings.delivery_commitment_hours
        ).initiate(
            session,
            gateway,
            order_id=order_id,
            customer_identity_id=identity.id,
            customer_mobile_e164=identity.mobile_e164,
            callback_url=str(body.callback_url),
            idempotency_key=idempotency_key,
        )
    except PaymentWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ZarinpalError as exc:
        raise HTTPException(status_code=502, detail="payment_provider_failed") from exc
    finally:
        await gateway.aclose()
    return PaymentRedirectResponse(attempt_id=result.attempt_id, redirect_url=result.redirect_url)


@router.get("/payments/zarinpal/callback", response_model=PaymentCallbackResponse)
async def payment_callback(
    settings: SettingsDependency,
    authority: Annotated[str, Query(alias="Authority", min_length=1, max_length=255)],
    callback_status: Annotated[str | None, Query(alias="Status")] = None,
) -> PaymentCallbackResponse:
    """Deliberately does not take SessionDependency (the RLS-scoped app-role
    session): the payment gateway calls this endpoint directly, with no
    logged-in customer session to derive RLS context from, so a query
    against orders_orders/payments_attempts here would have
    app.identity_id unset -- the row-level-security policies on those
    tables require customer_identity_id = app_identity_id(), which is
    NULL in that case, so the finalize step's own row-locking SELECT
    would find nothing and every real payment verification would
    silently fail (confirmed directly: a raw UPDATE through the app-role
    session with no RLS context set affects 0 rows). This is the same
    "trusted system code, not scoped to a single identity" case
    app/db/session.py already carves out for schedulers -- the gateway's
    own signed provider_reference is what authorizes this write, not a
    customer session, so it uses SessionFactory (the superuser role)
    directly rather than the per-request dependency.
    """
    if not callback_allows_verification(callback_status):
        return PaymentCallbackResponse(state="cancelled_or_failed")
    try:
        gateway = build_payment_gateway(settings)
    except PaymentProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="payment_provider_not_configured") from exc
    try:
        async with SessionFactory() as session:
            order = await PaymentService(
                delivery_commitment_hours=settings.delivery_commitment_hours
            ).verify(session, gateway, provider_reference=authority)
    except PaymentWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ZarinpalError as exc:
        raise HTTPException(status_code=502, detail="payment_verification_failed") from exc
    except PurchasingError as exc:
        # A misconfigured aggregated offer (no default_batch_threshold_quantity)
        # reaching payment -- an operator-fixable data problem, not a
        # customer error. The payment itself is not marked verified since
        # nothing in this transaction committed; retry (or the reconcile
        # route) succeeds once the offer is configured.
        raise HTTPException(status_code=500, detail="purchase_batch_configuration_error") from exc
    finally:
        await gateway.aclose()
    return PaymentCallbackResponse(
        state="verified",
        order_id=order.id,
        delivery_commitment_at=(
            order.delivery_commitment_at.isoformat() if order.delivery_commitment_at else None
        ),
    )


def _order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        status=order.status,
        merchandise_total_irr=order.merchandise_total_irr,
        currency=order.currency,
    )


def _availability_subscription_response(
    item: CatalogAvailabilitySubscription,
) -> AvailabilitySubscriptionResponse:
    return AvailabilitySubscriptionResponse(
        id=item.id,
        offer_id=item.offer_id,
        status=item.status,
        order_created=False,
        created_at=item.created_at,
        notified_at=item.notified_at,
        cancelled_at=item.cancelled_at,
    )


@router.get("/orders", response_model=OffsetPage[OrderListItem])
async def list_customer_orders(
    identity: CurrentIdentity, session: SessionDependency, pagination: PaginationDependency
) -> OffsetPage[OrderListItem]:
    total = int(
        await session.scalar(
            select(func.count(Order.id)).where(Order.customer_identity_id == identity.id)
        )
        or 0
    )
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.customer_identity_id == identity.id)
                .order_by(Order.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    )
    items = [_order_item(order) for order in orders]
    return OffsetPage[OrderListItem].model_validate(page(items, total=total, pagination=pagination))


@router.get("/orders/feed", response_model=CursorPage[OrderListItem])
async def customer_order_feed(
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> CursorPage[OrderListItem]:
    query = select(Order).where(Order.customer_identity_id == identity.id)
    if cursor is not None:
        try:
            position = decode_cursor(cursor, settings.jwt_secret)
        except CursorError as exc:
            raise HTTPException(status_code=422, detail="invalid_cursor") from exc
        query = query.where(
            or_(
                Order.created_at < position.created_at,
                and_(Order.created_at == position.created_at, Order.id < position.item_id),
            )
        )
    rows = list(
        (
            await session.scalars(
                query.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1)
            )
        ).all()
    )
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last = visible[-1]
        next_cursor = encode_cursor(CursorPosition(last.created_at, last.id), settings.jwt_secret)
    return CursorPage[OrderListItem].model_validate(
        cursor_page([_order_item(order) for order in visible], next_cursor=next_cursor)
    )


@router.get("/orders/{order_id}/journey", response_model=OrderJourneyResponse)
async def customer_order_journey(
    order_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> OrderJourneyResponse:
    order = await session.get(Order, order_id)
    if order is None or order.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="order_not_found")
    payment = await session.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order.id, PaymentAttempt.status == "verified")
        .order_by(PaymentAttempt.verified_at.desc())
        .limit(1)
    )
    events = list(
        (
            await session.scalars(
                select(FulfillmentEvent)
                .where(FulfillmentEvent.order_id == order.id)
                .order_by(FulfillmentEvent.occurred_at)
            )
        ).all()
    )
    sourced_units = list(
        (
            await session.scalars(
                select(SourcedUnitEvidence)
                .join(OrderLine, OrderLine.id == SourcedUnitEvidence.order_line_id)
                .where(OrderLine.order_id == order.id)
                .order_by(SourcedUnitEvidence.confirmed_at)
            )
        ).all()
    )
    timeline: list[FulfillmentTimelineItem] = []
    if payment is not None:
        timeline.append(
            FulfillmentTimelineItem(type="payment_confirmed", occurred_at=payment.verified_at)
        )
    timeline.extend(
        FulfillmentTimelineItem(type=event.event_type, occurred_at=event.occurred_at)
        for event in events
    )
    return OrderJourneyResponse(
        order_id=order.id,
        status=order.status,
        delivery_commitment_at=order.delivery_commitment_at,
        original_delivery_commitment_at=order.delivery_commitment_at,
        delivered_at=order.delivered_at,
        timeline=timeline,
        sourced_units=[
            SourcedUnitResponse(
                order_line_id=item.order_line_id,
                exact_expiry_date=item.exact_expiry_date,
                supplier_country=item.supplier_country_snapshot,
                authenticity=item.authenticity_basis,
                confirmed_at=item.confirmed_at,
            )
            for item in sourced_units
        ],
    )


@router.post(
    "/orders/{order_id}/delay-acknowledgements",
    response_model=DelayAcknowledgementResponse,
)
async def acknowledge_order_delay(
    order_id: UUID,
    idempotency_key: IdempotencyKey,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> DelayAcknowledgementResponse:
    order = await session.get(Order, order_id)
    if order is None or order.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="order_not_found")
    delayed_events = list(
        (
            await session.scalars(
                select(FulfillmentEvent)
                .where(
                    FulfillmentEvent.order_id == order.id,
                    FulfillmentEvent.event_type == "delayed",
                )
                .order_by(FulfillmentEvent.occurred_at, FulfillmentEvent.id)
            )
        ).all()
    )
    if not delayed_events:
        raise HTTPException(status_code=409, detail="no_visible_delay")
    version = len(delayed_events)
    request_hash = canonical_request_hash(
        {"order_id": str(order.id), "delay_event_version": version}
    )
    order_id_value = order.id
    identity_id_value = identity.id
    acknowledgement = await session.scalar(
        select(OrderDelayAcknowledgement).where(
            OrderDelayAcknowledgement.identity_id == identity.id,
            OrderDelayAcknowledgement.order_id == order.id,
            OrderDelayAcknowledgement.idempotency_key == idempotency_key,
        )
    )
    if acknowledgement is not None and acknowledgement.request_hash not in (None, request_hash):
        raise HTTPException(status_code=409, detail="idempotency_key_conflict")
    if acknowledgement is None:
        existing_version = await session.scalar(
            select(OrderDelayAcknowledgement).where(
                OrderDelayAcknowledgement.identity_id == identity.id,
                OrderDelayAcknowledgement.order_id == order.id,
                OrderDelayAcknowledgement.delay_event_version == version,
            )
        )
        acknowledgement = existing_version or OrderDelayAcknowledgement(
            identity_id=identity.id,
            order_id=order.id,
            delay_event_version=version,
            acknowledged_at=utc_now(),
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        session.add(acknowledgement)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            acknowledgement = await session.scalar(
                select(OrderDelayAcknowledgement).where(
                    OrderDelayAcknowledgement.identity_id == identity_id_value,
                    OrderDelayAcknowledgement.order_id == order_id_value,
                    OrderDelayAcknowledgement.idempotency_key == idempotency_key,
                )
            )
            if acknowledgement is None or acknowledgement.request_hash not in (
                None,
                request_hash,
            ):
                raise HTTPException(status_code=409, detail="idempotency_key_conflict") from exc
    return DelayAcknowledgementResponse(
        id=acknowledgement.id,
        order_id=acknowledgement.order_id,
        delay_event_version=acknowledgement.delay_event_version,
        acknowledged_at=acknowledgement.acknowledged_at,
    )


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def customer_order_detail(
    order_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OrderDetailResponse:
    order = await session.get(Order, order_id)
    if order is None or order.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="order_not_found")
    lines = list(
        (
            await session.scalars(
                select(OrderLine)
                .where(OrderLine.order_id == order.id)
                .order_by(OrderLine.created_at, OrderLine.id)
            )
        ).all()
    )
    line_ids = [line.id for line in lines]
    plans_by_line: dict[UUID, list[UUID]] = {line_id: [] for line_id in line_ids}
    evidence_by_line: dict[UUID, SourcedUnitEvidence] = {}
    if line_ids:
        for line_id, pet_id in (
            await session.execute(
                select(OrderLinePetPlan.order_line_id, OrderLinePetPlan.pet_id).where(
                    OrderLinePetPlan.order_line_id.in_(line_ids)
                )
            )
        ).all():
            plans_by_line[line_id].append(pet_id)
        evidence_by_line = {
            item.order_line_id: item
            for item in (
                await session.scalars(
                    select(SourcedUnitEvidence).where(
                        SourcedUnitEvidence.order_line_id.in_(line_ids)
                    )
                )
            ).all()
        }
    payment = await session.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order.id, PaymentAttempt.status == "verified")
        .order_by(PaymentAttempt.verified_at.desc())
        .limit(1)
    )
    cancellation = await session.scalar(
        select(OrderCancellation).where(OrderCancellation.order_id == order.id)
    )
    cancellation_eligible = cancellation is None and await is_order_cancellation_eligible_now(
        session, order=order
    )
    snapshot = order.delivery_address_snapshot
    return OrderDetailResponse(
        id=order.id,
        household_id=order.household_id,
        status=order.status,
        currency="IRR",
        merchandise_total_irr=order.merchandise_total_irr,
        created_at=order.created_at,
        paid_at=order.paid_at,
        delivery_commitment_at=order.delivery_commitment_at,
        original_delivery_commitment_at=order.delivery_commitment_at,
        delivered_at=order.delivered_at,
        payment=(
            SafePaymentSummaryResponse(
                status=payment.status,
                paid_at=payment.verified_at,
                amount_irr=payment.amount_irr,
                currency="IRR",
                masked_card=payment.masked_card,
            )
            if payment is not None
            else None
        ),
        delivery_address=OrderAddressSnapshotResponse(
            label=str(snapshot["label"]),
            recipient_name=str(snapshot["recipient_name"]),
            recipient_mobile=str(snapshot["recipient_mobile_e164"]),
            province=str(snapshot["province"]),
            city=str(snapshot["city"]),
            address_line=str(snapshot["address_line"]),
            postal_code=(str(snapshot["postal_code"]) if snapshot.get("postal_code") else None),
        ),
        lines=[
            OrderLineResponse(
                id=line.id,
                offer_id=line.offer_id,
                sku=line.sku_snapshot,
                title_fa=line.title_fa_snapshot,
                unit_label_fa=line.unit_label_fa_snapshot,
                quantity=line.quantity,
                unit_price_irr=line.unit_price_irr,
                line_total_irr=line.line_total_irr,
                planned_pet_ids=plans_by_line[line.id],
                sourced_unit=(
                    SourcedUnitResponse(
                        order_line_id=evidence_by_line[line.id].order_line_id,
                        exact_expiry_date=evidence_by_line[line.id].exact_expiry_date,
                        supplier_country=evidence_by_line[line.id].supplier_country_snapshot,
                        authenticity=evidence_by_line[line.id].authenticity_basis,
                        confirmed_at=evidence_by_line[line.id].confirmed_at,
                    )
                    if line.id in evidence_by_line
                    else None
                ),
            )
            for line in lines
        ],
        policies=OrderPolicyFieldsResponse(
            delivery_commitment_hours=settings.delivery_commitment_hours,
            late_credit_customer_visible=settings.late_credit_customer_visible,
        ),
        cancellation_eligible=cancellation_eligible,
        cancellation=(
            OrderCancellationResponse(
                order_id=cancellation.order_id,
                status="cancelled",
                cancelled_at=cancellation.created_at,
                reason=cancellation.reason,
                refund_amount_irr=cancellation.refund_amount_irr,
                refund_status=cancellation.refund_status,
            )
            if cancellation is not None
            else None
        ),
    )


class OrderCancellationBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/orders/{order_id}/cancel", response_model=OrderCancellationResponse)
async def cancel_order(
    order_id: UUID,
    body: OrderCancellationBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> OrderCancellationResponse:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="order_not_found")
    try:
        cancellation = await cancel_order_by_customer(
            session, order=order, customer_identity_id=identity.id, reason=body.reason
        )
    except CancellationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return OrderCancellationResponse(
        order_id=cancellation.order_id,
        status="cancelled",
        cancelled_at=cancellation.created_at,
        reason=cancellation.reason,
        refund_amount_irr=cancellation.refund_amount_irr,
        refund_status=cancellation.refund_status,
    )


def _shelf_life_exception_response(
    exception: ShelfLifeException,
) -> ShelfLifeExceptionResponse:
    return ShelfLifeExceptionResponse(
        id=exception.id,
        order_line_id=exception.order_line_id,
        proposed_exact_expiry_date=exception.proposed_exact_expiry_date,
        additional_discount_irr=exception.additional_discount_irr,
        reason=exception.reason,
        status=exception.status,
        respond_by=exception.respond_by,
        responded_at=exception.responded_at,
        refund_status=exception.refund_status,
        refund_amount_irr=exception.refund_amount_irr,
    )


async def _owned_shelf_life_exception(
    session: AsyncSession, *, order_id: UUID, exception_id: UUID, customer_identity_id: UUID
) -> tuple[ShelfLifeException, OrderLine]:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.customer_identity_id != customer_identity_id:
        raise HTTPException(status_code=404, detail="order_not_found")
    row = (
        await session.execute(
            select(ShelfLifeException, OrderLine)
            .join(OrderLine, OrderLine.id == ShelfLifeException.order_line_id)
            .where(ShelfLifeException.id == exception_id, OrderLine.order_id == order.id)
            .with_for_update(of=ShelfLifeException)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="shelf_life_exception_not_found")
    exception, order_line = row
    return exception, order_line


@router.get(
    "/orders/{order_id}/shelf-life-exceptions",
    response_model=list[ShelfLifeExceptionResponse],
)
async def list_order_shelf_life_exceptions(
    order_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[ShelfLifeExceptionResponse]:
    order = await session.get(Order, order_id)
    if order is None or order.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="order_not_found")
    rows = list(
        (
            await session.scalars(
                select(ShelfLifeException)
                .join(OrderLine, OrderLine.id == ShelfLifeException.order_line_id)
                .where(OrderLine.order_id == order.id)
                .order_by(ShelfLifeException.proposed_at.desc())
            )
        ).all()
    )
    return [_shelf_life_exception_response(item) for item in rows]


@router.post(
    "/orders/{order_id}/shelf-life-exceptions/{exception_id}/accept",
    response_model=ShelfLifeExceptionResponse,
)
async def accept_order_shelf_life_exception(
    order_id: UUID,
    exception_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> ShelfLifeExceptionResponse:
    exception, order_line = await _owned_shelf_life_exception(
        session, order_id=order_id, exception_id=exception_id, customer_identity_id=identity.id
    )
    offer = await session.get(Offer, order_line.offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    try:
        exception = await accept_shelf_life_exception(
            session,
            exception=exception,
            order_line=order_line,
            supplier_id=offer.supplier_id,
            customer_identity_id=identity.id,
        )
    except ShelfLifeExceptionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _shelf_life_exception_response(exception)


@router.post(
    "/orders/{order_id}/shelf-life-exceptions/{exception_id}/decline",
    response_model=ShelfLifeExceptionResponse,
)
async def decline_order_shelf_life_exception(
    order_id: UUID,
    exception_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> ShelfLifeExceptionResponse:
    exception, order_line = await _owned_shelf_life_exception(
        session, order_id=order_id, exception_id=exception_id, customer_identity_id=identity.id
    )
    try:
        exception = await decline_shelf_life_exception(
            session, exception=exception, order_line=order_line, customer_identity_id=identity.id
        )
    except ShelfLifeExceptionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _shelf_life_exception_response(exception)


@router.put("/orders/{order_id}/pet-plan", status_code=status.HTTP_204_NO_CONTENT)
async def replace_order_pet_plan(
    order_id: UUID,
    body: OrderPetPlanBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="order_not_found")
    if order.status not in ("paid", "sourcing", "in_transit"):
        raise HTTPException(status_code=409, detail="order_pet_plan_not_editable")
    submitted_line_ids = [line.order_line_id for line in body.lines]
    if len(submitted_line_ids) != len(set(submitted_line_ids)):
        raise HTTPException(status_code=422, detail="duplicate_order_line_in_plan")
    order_lines = list(
        (await session.scalars(select(OrderLine).where(OrderLine.order_id == order.id))).all()
    )
    order_line_ids = {line.id for line in order_lines}
    if not set(submitted_line_ids).issubset(order_line_ids):
        raise HTTPException(status_code=404, detail="order_line_not_found")
    requested_pet_ids = {pet_id for line in body.lines for pet_id in line.pet_ids}
    pets = (
        list(
            (
                await session.scalars(
                    select(Pet).where(
                        Pet.id.in_(requested_pet_ids),
                        Pet.household_id == order.household_id,
                        Pet.status == "active",
                    )
                )
            ).all()
        )
        if requested_pet_ids
        else []
    )
    if {pet.id for pet in pets} != requested_pet_ids:
        raise HTTPException(status_code=404, detail="pet_not_found")
    desired = {(line.order_line_id, pet_id) for line in body.lines for pet_id in line.pet_ids}
    existing = set(
        (
            await session.execute(
                select(OrderLinePetPlan.order_line_id, OrderLinePetPlan.pet_id).where(
                    OrderLinePetPlan.order_line_id.in_(order_line_ids)
                )
            )
        ).all()
    )
    stale = existing - desired
    if stale:
        await session.execute(
            delete(OrderLinePetPlan).where(
                tuple_(OrderLinePetPlan.order_line_id, OrderLinePetPlan.pet_id).in_(stale)
            )
        )
    for order_line_id, pet_id in desired - existing:
        session.add(OrderLinePetPlan(order_line_id=order_line_id, pet_id=pet_id))
    await session.commit()
