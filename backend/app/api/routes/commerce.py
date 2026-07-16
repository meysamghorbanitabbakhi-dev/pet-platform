from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import and_, delete, func, or_, select, tuple_
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
    OrderDetailResponse,
    OrderJourneyResponse,
    OrderLineResponse,
    OrderListItem,
    OrderPolicyFieldsResponse,
    PaymentCallbackResponse,
    PaymentRedirectResponse,
    ProductMediaResponse,
    SafePaymentSummaryResponse,
    SourcedUnitResponse,
)
from app.api.cursor import CursorError, CursorPosition, cursor_page, decode_cursor, encode_cursor
from app.api.dependencies import CurrentIdentity
from app.api.pagination import Pagination, page
from app.common.time import utc_now
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.integrations.payment.factory import (
    PaymentProviderNotConfiguredError,
    build_payment_gateway,
)
from app.integrations.payment.zarinpal import ZarinpalError, callback_allows_verification
from app.modules.catalog.models import (
    CatalogAvailabilitySubscription,
    Offer,
    Product,
    ProductMedia,
    Supplier,
)
from app.modules.checkout.service import CheckoutError, CheckoutItem, CheckoutService
from app.modules.households.access import HouseholdAccessError, require_household_membership
from app.modules.households.models import HouseholdMembership
from app.modules.orders.fulfillment import FulfillmentEvent
from app.modules.orders.models import Order, OrderDelayAcknowledgement, OrderLine, OrderLinePetPlan
from app.modules.payments.models import PaymentAttempt
from app.modules.payments.service import PaymentService, PaymentWorkflowError
from app.modules.pets.models import Pet
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


@router.get("/catalog/offers", response_model=list[OfferListItem])
async def list_offers(session: SessionDependency) -> list[OfferListItem]:
    now = utc_now()
    rows = (
        await session.execute(
            select(Offer, Supplier)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .where(
                Offer.status == "active",
                Offer.stock_posture == "sourced_after_payment",
                Offer.sourcing_capacity_status == "open",
                (Offer.available_from.is_(None)) | (Offer.available_from <= now),
                (Offer.available_until.is_(None)) | (Offer.available_until > now),
            )
            .order_by(Offer.title_fa)
        )
    ).all()
    return [
        OfferListItem(
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
        for offer, supplier in rows
    ]


@router.get("/catalog/offers/{offer_id}", response_model=OfferDetailResponse)
async def offer_detail(offer_id: UUID, session: SessionDependency) -> OfferDetailResponse:
    row = (
        await session.execute(
            select(Offer, Product, Supplier)
            .join(Product, Product.id == Offer.product_id)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .where(
                Offer.id == offer_id,
                Offer.status.in_(("active", "unavailable")),
                Product.status == "active",
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    offer, product, supplier = row
    media = list(
        (
            await session.scalars(
                select(ProductMedia)
                .where(ProductMedia.product_id == product.id, ProductMedia.active.is_(True))
                .order_by(ProductMedia.sort_order, ProductMedia.id)
            )
        ).all()
    )
    unavailable = offer.status == "unavailable" or offer.stock_posture == "unavailable"
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
    offer = await session.get(Offer, offer_id)
    if offer is None or offer.status == "retired":
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
        await session.flush()
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
    session: SessionDependency,
    settings: SettingsDependency,
    authority: Annotated[str, Query(alias="Authority", min_length=1, max_length=255)],
    callback_status: Annotated[str | None, Query(alias="Status")] = None,
) -> PaymentCallbackResponse:
    if not callback_allows_verification(callback_status):
        return PaymentCallbackResponse(state="cancelled_or_failed")
    try:
        gateway = build_payment_gateway(settings)
    except PaymentProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="payment_provider_not_configured") from exc
    try:
        order = await PaymentService(
            delivery_commitment_hours=settings.delivery_commitment_hours
        ).verify(session, gateway, provider_reference=authority)
    except PaymentWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ZarinpalError as exc:
        raise HTTPException(status_code=502, detail="payment_verification_failed") from exc
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
    acknowledgement = await session.scalar(
        select(OrderDelayAcknowledgement).where(
            OrderDelayAcknowledgement.identity_id == identity.id,
            OrderDelayAcknowledgement.order_id == order.id,
            OrderDelayAcknowledgement.idempotency_key == idempotency_key,
        )
    )
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
        )
        session.add(acknowledgement)
        await session.commit()
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
    )


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
