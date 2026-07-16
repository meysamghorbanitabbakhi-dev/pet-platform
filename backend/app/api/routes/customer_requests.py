from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import CustomerRequestResponse, OffsetPage
from app.api.dependencies import CurrentIdentity, CurrentOperator
from app.api.pagination import Pagination, page
from app.common.time import utc_now
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.catalog.models import Offer
from app.modules.households.access import HouseholdAccessError, require_household_membership
from app.modules.orders.models import Order
from app.modules.support.models import CustomerRequest, CustomerRequestStatusAudit

router = APIRouter(tags=["customer-requests"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
PaginationDependency = Annotated[Pagination, Depends()]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)]


class CustomerRequestBody(BaseModel):
    household_id: UUID
    request_type: Literal["support", "concierge_sourcing"]
    order_id: UUID | None = None
    offer_id: UUID | None = None
    product_query_fa: str | None = Field(default=None, max_length=500)
    message_fa: str = Field(min_length=1, max_length=2000)
    contact_preference: Literal["in_app", "sms"]


class CustomerRequestStatusBody(BaseModel):
    status: Literal["submitted", "in_review", "resolved", "closed"]
    reason: str = Field(min_length=5, max_length=2000)


@router.post(
    "/customer-requests",
    response_model=CustomerRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_request(
    body: CustomerRequestBody,
    idempotency_key: IdempotencyKey,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> CustomerRequestResponse:
    if not settings.concierge_requests_enabled:
        raise HTTPException(status_code=409, detail="concierge_requests_disabled")
    await _household_access(session, identity.id, body.household_id)
    if body.order_id is not None:
        order = await session.get(Order, body.order_id)
        if order is None or order.customer_identity_id != identity.id:
            raise HTTPException(status_code=404, detail="order_not_found")
        if order.household_id != body.household_id:
            raise HTTPException(status_code=404, detail="order_not_found")
    if body.offer_id is not None:
        offer = await session.get(Offer, body.offer_id)
        if offer is None or offer.status == "retired":
            raise HTTPException(status_code=404, detail="offer_not_found")
    existing = await session.scalar(
        select(CustomerRequest).where(
            CustomerRequest.identity_id == identity.id,
            CustomerRequest.idempotency_key == idempotency_key,
        )
    )
    if existing is None:
        existing = CustomerRequest(
            identity_id=identity.id,
            household_id=body.household_id,
            request_type=body.request_type,
            order_id=body.order_id,
            offer_id=body.offer_id,
            product_query_fa=body.product_query_fa,
            message_fa=body.message_fa,
            contact_preference=body.contact_preference,
            status="submitted",
            idempotency_key=idempotency_key,
        )
        session.add(existing)
        await session.flush()
        session.add(
            CustomerRequestStatusAudit(
                request_id=existing.id,
                operator_identity_id=None,
                old_status=None,
                new_status="submitted",
                reason="customer submitted request",
                facts={"promises": _no_customer_request_promises()},
                changed_at=utc_now(),
            )
        )
        await session.commit()
    return _customer_request_response(existing)


@router.get("/customer-requests", response_model=OffsetPage[CustomerRequestResponse])
async def list_customer_requests(
    identity: CurrentIdentity,
    session: SessionDependency,
    pagination: PaginationDependency,
) -> OffsetPage[CustomerRequestResponse]:
    filters = (CustomerRequest.identity_id == identity.id,)
    total = int(await session.scalar(select(func.count(CustomerRequest.id)).where(*filters)) or 0)
    rows = list(
        (
            await session.scalars(
                select(CustomerRequest)
                .where(*filters)
                .order_by(CustomerRequest.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    )
    return OffsetPage[CustomerRequestResponse].model_validate(
        page(
            [_customer_request_response(item) for item in rows],
            total=total,
            pagination=pagination,
        )
    )


@router.get("/customer-requests/{request_id}", response_model=CustomerRequestResponse)
async def customer_request_detail(
    request_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> CustomerRequestResponse:
    item = await session.get(CustomerRequest, request_id)
    if item is None or item.identity_id != identity.id:
        raise HTTPException(status_code=404, detail="customer_request_not_found")
    return _customer_request_response(item)


@router.get("/operator/customer-requests", response_model=OffsetPage[CustomerRequestResponse])
async def operator_customer_requests(
    _: CurrentOperator,
    session: SessionDependency,
    pagination: PaginationDependency,
) -> OffsetPage[CustomerRequestResponse]:
    total = int(await session.scalar(select(func.count(CustomerRequest.id))) or 0)
    rows = list(
        (
            await session.scalars(
                select(CustomerRequest)
                .order_by(CustomerRequest.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    )
    return OffsetPage[CustomerRequestResponse].model_validate(
        page(
            [_customer_request_response(item) for item in rows],
            total=total,
            pagination=pagination,
        )
    )


@router.post(
    "/operator/customer-requests/{request_id}/status",
    response_model=CustomerRequestResponse,
)
async def operator_customer_request_status(
    request_id: UUID,
    body: CustomerRequestStatusBody,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CustomerRequestResponse:
    item = await session.get(CustomerRequest, request_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="customer_request_not_found")
    before = item.status
    item.status = body.status
    session.add(
        CustomerRequestStatusAudit(
            request_id=item.id,
            operator_identity_id=operator.id,
            old_status=before,
            new_status=body.status,
            reason=body.reason,
            facts={"promises": _no_customer_request_promises()},
            changed_at=utc_now(),
        )
    )
    await session.commit()
    return _customer_request_response(item)


async def _household_access(session: AsyncSession, identity_id: UUID, household_id: UUID) -> None:
    try:
        await require_household_membership(
            session, identity_id=identity_id, household_id=household_id
        )
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="household_not_found") from exc


def _no_customer_request_promises() -> dict[str, bool]:
    return {
        "availability": False,
        "refund": False,
        "replacement": False,
        "response_time": False,
        "sourcing_success": False,
    }


def _customer_request_response(item: CustomerRequest) -> CustomerRequestResponse:
    return CustomerRequestResponse(
        id=item.id,
        household_id=item.household_id,
        request_type=item.request_type,
        order_id=item.order_id,
        offer_id=item.offer_id,
        product_query_fa=item.product_query_fa,
        message_fa=item.message_fa,
        contact_preference=item.contact_preference,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
        promises=_no_customer_request_promises(),
        acknowledgement_fa=get_settings().customer_request_acknowledgement_fa,
    )
