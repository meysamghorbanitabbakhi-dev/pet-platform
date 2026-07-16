from datetime import date, time, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    AddressResponse,
    CursorPage,
    DiaryEntryDetailResponse,
    DiaryListItem,
    FoodEstimateProvenanceRow,
    FoodEstimateResponse,
    GardenObjectResponse,
    GardenStateResponse,
    InventoryAssignmentResponse,
    InventoryDetailResponse,
    InventoryListItem,
    JourneyCheckInResponse,
    JourneyCompletionResponse,
    JourneyDefinitionResponse,
    JourneyDetailResponse,
    JourneyOfferResponse,
    NotificationListItem,
    OffsetPage,
    PetSummary,
    ReorderAssessmentResponse,
    TodayResponse,
    WalletSummaryResponse,
)
from app.api.cursor import CursorError, CursorPosition, cursor_page, decode_cursor, encode_cursor
from app.api.dependencies import CurrentIdentity
from app.api.pagination import Pagination, page
from app.common.phone import normalize_iranian_mobile
from app.common.time import utc_now
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.catalog.models import Offer, Product
from app.modules.diary.models import DiaryEntry
from app.modules.food_estimation.models import FoodEstimate
from app.modules.garden.models import GardenReward
from app.modules.households.access import (
    HouseholdAccessError,
    require_household_membership,
    require_pet_access,
)
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit, ReorderSnooze
from app.modules.inventory.service import InventoryError, InventoryService
from app.modules.journeys.models import JourneyCheckIn, JourneyDefinition, PetJourney
from app.modules.journeys.service import JourneyError, JourneyService
from app.modules.notifications.models import Notification, NotificationPreference
from app.modules.pets.models import Pet
from app.modules.replenishment.service import assess_reorder, should_break_reorder_snooze
from app.modules.today.service import build_today
from app.modules.wallet.models import WalletAccount, WalletCredit

router = APIRouter(prefix="/pet-life", tags=["pet-life"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
PaginationDependency = Annotated[Pagination, Depends()]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)]


class HouseholdBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AddressBody(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    recipient_name: str = Field(min_length=1, max_length=200)
    recipient_mobile: str = Field(min_length=10, max_length=32)
    province: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    address_line: str = Field(min_length=5, max_length=1000)
    postal_code: str | None = Field(default=None, max_length=20)


class PetBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    species: str = Field(pattern=r"^(dog|cat)$")
    birth_date: date | None = None


class ExternalInventoryBody(BaseModel):
    label: str = Field(min_length=1, max_length=300)
    product_id: UUID | None = None
    initial_quantity_grams: int | None = Field(default=None, gt=0)


class AssignmentItem(BaseModel):
    pet_id: UUID
    share_basis_points: int | None = Field(default=None, gt=0, le=10_000)
    daily_portion_grams: int | None = Field(default=None, gt=0)


class AssignmentsBody(BaseModel):
    assignments: list[AssignmentItem] = Field(min_length=1, max_length=20)


class RemainingGramsInput(BaseModel):
    mode: Literal["grams"]
    grams: int = Field(gt=0)


class RemainingLevelInput(BaseModel):
    mode: Literal["level"]
    level: Literal["full", "more_than_half", "less_than_half", "near_empty"]


RemainingInput = Annotated[
    RemainingGramsInput | RemainingLevelInput, Field(discriminator="mode")
]


class OpenInventoryBody(BaseModel):
    remaining_grams: int | None = Field(default=None, gt=0)
    remaining: RemainingInput | None = None
    daily_portion_grams: int | None = Field(default=None, gt=0)
    feeding_context: Literal["exclusive", "mixed", "unknown"] = "exclusive"

    @model_validator(mode="after")
    def validate_remaining_input(self) -> "OpenInventoryBody":
        if self.remaining_grams is None and self.remaining is None:
            raise ValueError("remaining quantity is required")
        if self.remaining_grams is not None and self.remaining is not None:
            raise ValueError("send either legacy remaining_grams or remaining, not both")
        return self


class ReorderSnoozeBody(BaseModel):
    hours: int = Field(default=72, ge=1, le=72)


class JourneyStartBody(BaseModel):
    definition_id: UUID


class JourneyCompleteBody(BaseModel):
    memory_title_fa: str = Field(min_length=1, max_length=300)


class JourneyCheckInBody(BaseModel):
    check_in_key: str = Field(min_length=1, max_length=100)
    answer_key: str = Field(min_length=1, max_length=100)


class JourneyStopBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class GardenPlacementBody(BaseModel):
    quadrant: int = Field(ge=1, le=4)
    position_x: int = Field(ge=0, le=1000)
    position_y: int = Field(ge=0, le=1000)


class ReorderBody(BaseModel):
    remaining_low_days: int | None = Field(default=None, ge=0)
    remaining_high_days: int | None = Field(default=None, ge=0)
    latest_delivery_days: int = Field(ge=0, le=90)
    safety_buffer_days: int = Field(default=2, ge=0, le=30)


class NotificationPreferenceBody(BaseModel):
    enabled: bool
    quiet_start_local: time | None = None
    quiet_end_local: time | None = None


class IdResponse(BaseModel):
    id: UUID


@router.post("/households", response_model=IdResponse, status_code=status.HTTP_201_CREATED)
async def create_household(
    body: HouseholdBody, identity: CurrentIdentity, session: SessionDependency
) -> IdResponse:
    household = Household(name=body.name)
    session.add(household)
    await session.flush()
    session.add(
        HouseholdMembership(
            household_id=household.id,
            identity_id=identity.id,
            role="owner",
        )
    )
    await session.commit()
    return IdResponse(id=household.id)


@router.post(
    "/households/{household_id}/addresses",
    response_model=IdResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_address(
    household_id: UUID,
    body: AddressBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> IdResponse:
    await _household_access(session, identity.id, household_id)
    try:
        mobile = normalize_iranian_mobile(body.recipient_mobile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_mobile_number") from exc
    address = HouseholdAddress(
        household_id=household_id,
        label=body.label,
        recipient_name=body.recipient_name,
        recipient_mobile_e164=mobile,
        province=body.province,
        city=body.city,
        address_line=body.address_line,
        postal_code=body.postal_code,
        active=True,
    )
    session.add(address)
    await session.commit()
    return IdResponse(id=address.id)


@router.get("/households/{household_id}/addresses", response_model=list[AddressResponse])
async def list_addresses(
    household_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[AddressResponse]:
    await _household_access(session, identity.id, household_id)
    addresses = list(
        (
            await session.scalars(
                select(HouseholdAddress)
                .where(
                    HouseholdAddress.household_id == household_id,
                    HouseholdAddress.active.is_(True),
                )
                .order_by(HouseholdAddress.created_at)
            )
        ).all()
    )
    return [
        AddressResponse(
            id=item.id,
            label=item.label,
            recipient_name=item.recipient_name,
            recipient_mobile=item.recipient_mobile_e164,
            province=item.province,
            city=item.city,
            address_line=item.address_line,
            postal_code=item.postal_code,
        )
        for item in addresses
    ]


@router.post(
    "/households/{household_id}/pets",
    response_model=IdResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pet(
    household_id: UUID,
    body: PetBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> IdResponse:
    await _household_access(session, identity.id, household_id)
    pet = Pet(
        household_id=household_id,
        name=body.name,
        species=body.species,
        birth_date=body.birth_date,
        status="active",
    )
    session.add(pet)
    await session.commit()
    return IdResponse(id=pet.id)


@router.get("/households/{household_id}/pets", response_model=list[PetSummary])
async def list_household_pets(
    household_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[PetSummary]:
    await _household_access(session, identity.id, household_id)
    pets = list(
        (
            await session.scalars(
                select(Pet)
                .where(Pet.household_id == household_id, Pet.status == "active")
                .order_by(Pet.created_at, Pet.id)
            )
        ).all()
    )
    return [PetSummary(id=pet.id, name=pet.name, species=pet.species) for pet in pets]


@router.post(
    "/households/{household_id}/inventory/external",
    response_model=IdResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_external_inventory(
    household_id: UUID,
    body: ExternalInventoryBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> IdResponse:
    await _household_access(session, identity.id, household_id)
    unit = InventoryUnit(
        household_id=household_id,
        product_id=body.product_id,
        source="external_purchase",
        state="unopened",
        label=body.label,
        initial_quantity_grams=body.initial_quantity_grams,
        remaining_quantity_grams=body.initial_quantity_grams,
    )
    session.add(unit)
    await session.commit()
    return IdResponse(id=unit.id)


@router.put("/inventory/{unit_id}/assignments", status_code=status.HTTP_204_NO_CONTENT)
async def replace_assignments(
    unit_id: UUID,
    body: AssignmentsBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    unit = await session.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    if len({item.pet_id for item in body.assignments}) != len(body.assignments):
        raise HTTPException(status_code=422, detail="duplicate_pet_assignment")
    known_shares = [item.share_basis_points for item in body.assignments if item.share_basis_points]
    if known_shares and len(known_shares) == len(body.assignments) and sum(known_shares) != 10_000:
        raise HTTPException(status_code=422, detail="known_shares_must_total_10000")
    for item in body.assignments:
        pet = await _pet_access(session, identity.id, item.pet_id)
        if pet.household_id != unit.household_id:
            raise HTTPException(status_code=422, detail="pet_and_inventory_household_mismatch")
    existing = list(
        (
            await session.scalars(
                select(ConsumptionAssignment).where(
                    ConsumptionAssignment.inventory_unit_id == unit.id
                )
            )
        ).all()
    )
    for assignment in existing:
        await session.delete(assignment)
    for item in body.assignments:
        session.add(
            ConsumptionAssignment(
                inventory_unit_id=unit.id,
                pet_id=item.pet_id,
                share_basis_points=item.share_basis_points,
                daily_portion_grams=item.daily_portion_grams,
            )
        )
    await session.commit()


@router.post("/inventory/{unit_id}/open", response_model=FoodEstimateResponse)
async def open_inventory(
    unit_id: UUID,
    body: OpenInventoryBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> FoodEstimateResponse:
    unit = await session.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    remaining = await _remaining_facts(session, unit, body, settings)
    try:
        estimate = await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit.id,
            remaining_grams=remaining["remaining_grams"],
            remaining_low_grams=remaining["remaining_low_grams"],
            remaining_high_grams=remaining["remaining_high_grams"],
            remaining_input_mode=remaining["remaining_input_mode"],
            remaining_provenance=remaining["remaining_provenance"],
            feeding_context=body.feeding_context,
            daily_portion_grams=body.daily_portion_grams,
        )
    except InventoryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _estimate_response(estimate)


@router.post("/inventory/{unit_id}/estimate/correct", response_model=FoodEstimateResponse)
async def correct_estimate(
    unit_id: UUID,
    body: OpenInventoryBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> FoodEstimateResponse:
    unit = await session.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    remaining = await _remaining_facts(session, unit, body, settings)
    active = list(
        (
            await session.scalars(
                select(FoodEstimate).where(
                    FoodEstimate.inventory_unit_id == unit.id,
                    FoodEstimate.status == "active",
                )
            )
        ).all()
    )
    for estimate in active:
        estimate.status = "corrected"
    try:
        corrected = await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit.id,
            remaining_grams=remaining["remaining_grams"],
            remaining_low_grams=remaining["remaining_low_grams"],
            remaining_high_grams=remaining["remaining_high_grams"],
            remaining_input_mode=remaining["remaining_input_mode"],
            remaining_provenance=remaining["remaining_provenance"],
            feeding_context=body.feeding_context,
            daily_portion_grams=body.daily_portion_grams,
        )
    except InventoryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _estimate_response(corrected)


@router.post("/inventory/{unit_id}/exhaust", status_code=status.HTTP_204_NO_CONTENT)
async def exhaust_inventory(
    unit_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> None:
    unit = await session.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    if unit.state != "opened":
        raise HTTPException(status_code=409, detail="only_opened_inventory_can_be_exhausted")
    unit.state = "exhausted"
    unit.remaining_quantity_grams = 0
    estimates = list(
        (
            await session.scalars(
                select(FoodEstimate).where(
                    FoodEstimate.inventory_unit_id == unit.id,
                    FoodEstimate.status == "active",
                )
            )
        ).all()
    )
    for estimate in estimates:
        estimate.status = "exhausted"
    await session.commit()


@router.get("/inventory/{unit_id}", response_model=InventoryDetailResponse)
async def inventory_detail(
    unit_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> InventoryDetailResponse:
    unit = await session.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    assignments = list(
        (
            await session.execute(
                select(ConsumptionAssignment, Pet)
                .join(Pet, Pet.id == ConsumptionAssignment.pet_id)
                .where(ConsumptionAssignment.inventory_unit_id == unit.id)
                .order_by(Pet.created_at, Pet.id)
            )
        ).all()
    )
    active = await session.scalar(
        select(FoodEstimate)
        .where(FoodEstimate.inventory_unit_id == unit.id, FoodEstimate.status == "active")
        .order_by(FoodEstimate.calculated_at.desc())
        .limit(1)
    )
    known = bool(assignments) and all(
        item.share_basis_points is not None for item, _ in assignments
    )
    return InventoryDetailResponse(
        id=unit.id,
        household_id=unit.household_id,
        product_id=unit.product_id,
        label=unit.label,
        source=unit.source,
        state=unit.state,
        initial_quantity_grams=unit.initial_quantity_grams,
        remaining_quantity_grams=unit.remaining_quantity_grams,
        remaining_low_grams=unit.remaining_low_grams,
        remaining_high_grams=unit.remaining_high_grams,
        delivered_at=unit.delivered_at,
        opened_at=unit.opened_at,
        exact_expiry_date=unit.exact_expiry_date,
        sourcing_confirmed_at=unit.sourcing_confirmed_at,
        supplier_country=unit.supplier_country_snapshot,
        authenticity=unit.authenticity_basis,
        assignments=[
            InventoryAssignmentResponse(
                pet=PetSummary(id=pet.id, name=pet.name, species=pet.species),
                share_basis_points=item.share_basis_points,
                daily_portion_grams=item.daily_portion_grams,
            )
            for item, pet in assignments
        ],
        shares_known=known,
        active_estimate=_estimate_response(active) if active is not None else None,
    )


@router.put("/inventory/{unit_id}/reorder-snooze", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_snooze(
    unit_id: UUID,
    body: ReorderSnoozeBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    unit = await session.scalar(
        select(InventoryUnit).where(InventoryUnit.id == unit_id).with_for_update()
    )
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    active = await session.scalar(
        select(FoodEstimate)
        .where(FoodEstimate.inventory_unit_id == unit.id, FoodEstimate.status == "active")
        .order_by(FoodEstimate.calculated_at.desc())
        .limit(1)
    )
    now = utc_now()
    snooze = await session.scalar(
        select(ReorderSnooze).where(
            ReorderSnooze.inventory_unit_id == unit.id, ReorderSnooze.identity_id == identity.id
        ).with_for_update()
    )
    if snooze is None:
        snooze = ReorderSnooze(
            inventory_unit_id=unit.id,
            household_id=unit.household_id,
            identity_id=identity.id,
            snoozed_from=now,
            snoozed_until=now + timedelta(hours=body.hours),
            baseline_low_days=active.low_days if active else None,
        )
        session.add(snooze)
    elif snooze.snoozed_until <= now:
        snooze.snoozed_from = now
        snooze.snoozed_until = now + timedelta(hours=body.hours)
        snooze.baseline_low_days = active.low_days if active else None
    await session.commit()


@router.post("/inventory/{unit_id}/reorder-assessment", response_model=ReorderAssessmentResponse)
async def inventory_reorder_assessment(
    unit_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReorderAssessmentResponse:
    unit = await session.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    await _household_access(session, identity.id, unit.household_id)
    active = await session.scalar(
        select(FoodEstimate)
        .where(FoodEstimate.inventory_unit_id == unit.id, FoodEstimate.status == "active")
        .order_by(FoodEstimate.calculated_at.desc())
        .limit(1)
    )
    now = utc_now()
    snooze = await session.scalar(
        select(ReorderSnooze)
        .where(
            ReorderSnooze.inventory_unit_id == unit.id,
            ReorderSnooze.identity_id == identity.id,
            ReorderSnooze.snoozed_until > now,
        )
        .order_by(ReorderSnooze.snoozed_until.desc())
        .limit(1)
    )
    latest_delivery_days = (settings.delivery_commitment_hours + 23) // 24
    options = await _reorder_options(session, unit)
    provenance = [
        FoodEstimateProvenanceRow(
            key="estimate", source="server", value="active" if active else None
        ),
        FoodEstimateProvenanceRow(
            key="delivery_policy_hours",
            source="policy",
            value=settings.delivery_commitment_hours,
        ),
        FoodEstimateProvenanceRow(key="offer_options", source="catalog", value=len(options)),
    ]
    if snooze is not None:
        if not should_break_reorder_snooze(
            baseline_low_days=snooze.baseline_low_days,
            current_low_days=active.low_days if active else None,
            latest_delivery_days=latest_delivery_days,
            safety_buffer_days=settings.reorder_safety_buffer_days or 0,
            worsening_days=settings.reorder_snooze_early_break_worsening_days,
        ):
            return ReorderAssessmentResponse(
                recommendation="snoozed",
                outcome="snoozed",
                risk_gap_days=None,
                remaining_low_days=active.low_days if active else None,
                remaining_high_days=active.high_days if active else None,
                latest_delivery_days=latest_delivery_days,
                safety_buffer_days=settings.reorder_safety_buffer_days,
                snoozed_until=snooze.snoozed_until,
                provenance=provenance,
                options=options,
            )
    if settings.reorder_safety_buffer_days is None:
        return ReorderAssessmentResponse(
            recommendation="policy_blocked",
            outcome="policy_blocked",
            risk_gap_days=None,
            remaining_low_days=active.low_days if active else None,
            remaining_high_days=active.high_days if active else None,
            latest_delivery_days=latest_delivery_days,
            safety_buffer_days=None,
            provenance=[
                *provenance,
                FoodEstimateProvenanceRow(key="safety_buffer_days", source="policy", value=None),
            ],
            options=options,
        )
    if active is None or active.low_days is None or active.high_days is None or not options:
        return ReorderAssessmentResponse(
            recommendation="insufficient_facts",
            outcome="insufficient_facts",
            risk_gap_days=None,
            remaining_low_days=active.low_days if active else None,
            remaining_high_days=active.high_days if active else None,
            latest_delivery_days=latest_delivery_days,
            safety_buffer_days=settings.reorder_safety_buffer_days,
            provenance=provenance,
            options=options,
        )
    try:
        assessment = assess_reorder(
            remaining_low_days=active.low_days,
            remaining_high_days=active.high_days,
            latest_delivery_days=latest_delivery_days,
            safety_buffer_days=settings.reorder_safety_buffer_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ReorderAssessmentResponse(
        recommendation=assessment.recommendation,
        outcome="order_now" if assessment.recommendation == "order_now" else "not_yet",
        risk_gap_days=assessment.risk_gap_days,
        remaining_low_days=assessment.remaining_low_days,
        remaining_high_days=assessment.remaining_high_days,
        latest_delivery_days=assessment.latest_delivery_days,
        safety_buffer_days=assessment.safety_buffer_days,
        provenance=provenance,
        options=options,
    )


@router.post("/pets/{pet_id}/journeys", response_model=IdResponse)
async def start_journey(
    pet_id: UUID,
    body: JourneyStartBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> IdResponse:
    if not settings.care_journey_delivery_enabled:
        raise HTTPException(status_code=409, detail="care_journey_delivery_disabled")
    await _pet_access(session, identity.id, pet_id)
    try:
        journey = await JourneyService().start(
            session, pet_id=pet_id, definition_id=body.definition_id
        )
    except JourneyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return IdResponse(id=journey.id)


@router.get("/pets/{pet_id}/journey-offers", response_model=list[JourneyOfferResponse])
async def journey_offers(
    pet_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> list[JourneyOfferResponse]:
    pet = await _pet_access(session, identity.id, pet_id)
    if not settings.care_journey_delivery_enabled:
        raise HTTPException(status_code=409, detail="care_journey_delivery_disabled")
    now = utc_now()
    definitions = list(
        (
            await session.scalars(
                select(JourneyDefinition)
                .where(JourneyDefinition.approval_status == "approved")
                .order_by(JourneyDefinition.key, JourneyDefinition.version.desc())
            )
        ).all()
    )
    offers = [
        definition
        for definition in definitions
        if _journey_definition_deliverable(definition, pet.species, now)
    ]
    return [
        JourneyOfferResponse(
            definition_id=item.id,
            key=item.key,
            version=item.version,
            title_fa=item.title_fa,
            summary_fa=_content_str(item.content, "summary_fa"),
            duration_days=_content_int(item.content, "duration_days"),
        )
        for item in offers
    ]


@router.get(
    "/journey-definitions/{definition_id}",
    response_model=JourneyDefinitionResponse,
)
async def journey_definition_detail(
    definition_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> JourneyDefinitionResponse:
    _ = identity
    if not settings.care_journey_delivery_enabled:
        raise HTTPException(status_code=409, detail="care_journey_delivery_disabled")
    definition = await session.get(JourneyDefinition, definition_id)
    if (
        definition is None
        or definition.approval_status != "approved"
        or definition.approved_at is None
        or not _journey_definition_deliverable(definition, None, utc_now())
    ):
        raise HTTPException(status_code=404, detail="journey_definition_not_found")
    return JourneyDefinitionResponse(
        id=definition.id,
        key=definition.key,
        version=definition.version,
        title_fa=definition.title_fa,
        summary_fa=_content_str(definition.content, "summary_fa"),
        content=_public_journey_content(definition.content),
        approved_at=definition.approved_at,
    )


@router.get("/journeys/{journey_id}", response_model=JourneyDetailResponse)
async def journey_detail(
    journey_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> JourneyDetailResponse:
    if not settings.care_journey_delivery_enabled:
        raise HTTPException(status_code=409, detail="care_journey_delivery_disabled")
    journey = await _owned_journey(session, identity.id, journey_id)
    check_ins = list(
        (
            await session.scalars(
                select(JourneyCheckIn)
                .where(JourneyCheckIn.journey_id == journey.id)
                .order_by(JourneyCheckIn.submitted_at, JourneyCheckIn.id)
            )
        ).all()
    )
    definition = await session.get(JourneyDefinition, journey.definition_id)
    content = journey.definition_snapshot or (definition.content if definition else {})
    return JourneyDetailResponse(
        id=journey.id,
        pet_id=journey.pet_id,
        definition_id=journey.definition_id,
        definition_version=journey.definition_version or (definition.version if definition else 1),
        status=journey.status,
        started_at=journey.started_at,
        ended_at=journey.ended_at,
        title_fa=definition.title_fa if definition else "",
        steps=_content_list(content, "steps"),
        check_ins=[
            JourneyCheckInResponse(
                id=item.id,
                journey_id=item.journey_id,
                check_in_key=item.check_in_key,
                answer_key=item.answer_key,
                submitted_at=item.submitted_at,
            )
            for item in check_ins
        ],
    )


@router.post("/journeys/{journey_id}/check-ins", response_model=JourneyCheckInResponse)
async def journey_check_in(
    journey_id: UUID,
    body: JourneyCheckInBody,
    idempotency_key: IdempotencyKey,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> JourneyCheckInResponse:
    if not settings.care_journey_delivery_enabled:
        raise HTTPException(status_code=409, detail="care_journey_delivery_disabled")
    journey = await session.scalar(
        select(PetJourney).where(PetJourney.id == journey_id).with_for_update()
    )
    if journey is None:
        raise HTTPException(status_code=404, detail="journey_not_found")
    await _pet_access(session, identity.id, journey.pet_id)
    if journey.status != "active":
        raise HTTPException(status_code=409, detail="journey_not_active")
    existing = await session.scalar(
        select(JourneyCheckIn).where(
            JourneyCheckIn.journey_id == journey.id,
            JourneyCheckIn.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return JourneyCheckInResponse(
            id=existing.id,
            journey_id=existing.journey_id,
            check_in_key=existing.check_in_key,
            answer_key=existing.answer_key,
            submitted_at=existing.submitted_at,
        )
    content = journey.definition_snapshot
    if content is None:
        definition = await session.get(JourneyDefinition, journey.definition_id)
        content = definition.content if definition else {}
    if not _valid_check_in(content, body.check_in_key, body.answer_key):
        raise HTTPException(status_code=422, detail="invalid_journey_check_in")
    check_in = JourneyCheckIn(
        journey_id=journey.id,
        check_in_key=body.check_in_key,
        answer_key=body.answer_key,
        submitted_by_identity_id=identity.id,
        submitted_at=utc_now(),
        idempotency_key=idempotency_key,
    )
    session.add(check_in)
    await session.flush()
    completed = _completion_requirements_met(
        content,
        {
            item.check_in_key
            for item in (
                await session.scalars(
                    select(JourneyCheckIn).where(JourneyCheckIn.journey_id == journey.id)
                )
            ).all()
        },
    )
    diary = reward = None
    if completed:
        diary, reward = await JourneyService().complete(
            session,
            journey_id=journey.id,
            memory_title_fa=_content_str(content, "completion_memory_title_fa") or "خاطره مسیر",
        )
    else:
        await session.commit()
    return JourneyCheckInResponse(
        id=check_in.id,
        journey_id=check_in.journey_id,
        check_in_key=check_in.check_in_key,
        answer_key=check_in.answer_key,
        submitted_at=check_in.submitted_at,
        completed=completed,
        diary_entry_id=diary.id if diary else None,
        garden_reward_id=reward.id if reward else None,
    )


@router.post("/journeys/{journey_id}/pause", status_code=status.HTTP_204_NO_CONTENT)
async def pause_journey(
    journey_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> None:
    journey = await _owned_journey(session, identity.id, journey_id)
    if journey.status != "active":
        raise HTTPException(status_code=409, detail="journey_cannot_be_paused")
    journey.status = "paused"
    await session.commit()


@router.post("/journeys/{journey_id}/resume", status_code=status.HTTP_204_NO_CONTENT)
async def resume_journey(
    journey_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> None:
    journey = await _owned_journey(session, identity.id, journey_id)
    if journey.status != "paused":
        raise HTTPException(status_code=409, detail="journey_cannot_be_resumed")
    journey.status = "active"
    await session.commit()


@router.post("/journeys/{journey_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_journey(
    journey_id: UUID,
    body: JourneyStopBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    journey = await _owned_journey(session, identity.id, journey_id)
    if journey.status not in ("active", "paused"):
        raise HTTPException(status_code=409, detail="journey_cannot_be_stopped")
    journey.status = "stopped"
    journey.ended_at = utc_now()
    journey.stop_reason = body.reason
    await session.commit()


@router.post("/journeys/{journey_id}/complete", response_model=JourneyCompletionResponse)
async def complete_journey(
    journey_id: UUID,
    body: JourneyCompleteBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> JourneyCompletionResponse:
    if not settings.care_journey_delivery_enabled:
        raise HTTPException(status_code=409, detail="care_journey_delivery_disabled")
    await _owned_journey(session, identity.id, journey_id)
    try:
        diary, reward = await JourneyService().complete(
            session,
            journey_id=journey_id,
            memory_title_fa=body.memory_title_fa,
        )
    except JourneyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JourneyCompletionResponse(diary_entry_id=diary.id, garden_reward_id=reward.id)


@router.get("/pets/{pet_id}/diary", response_model=list[DiaryListItem])
async def list_diary(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[DiaryListItem]:
    await _pet_access(session, identity.id, pet_id)
    entries = list(
        (
            await session.scalars(
                select(DiaryEntry)
                .where(DiaryEntry.pet_id == pet_id)
                .order_by(DiaryEntry.happened_at.desc())
            )
        ).all()
    )
    return [
        DiaryListItem(
            id=item.id,
            entry_type=item.entry_type,
            title_fa=item.title_fa,
            happened_at=item.happened_at,
        )
        for item in entries
    ]


@router.get("/pets/{pet_id}/diary/{entry_id}", response_model=DiaryEntryDetailResponse)
async def diary_detail(
    pet_id: UUID,
    entry_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> DiaryEntryDetailResponse:
    await _pet_access(session, identity.id, pet_id)
    entry = await session.get(DiaryEntry, entry_id)
    if entry is None or entry.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="diary_entry_not_found")
    reward = await session.scalar(
        select(GardenReward).where(GardenReward.diary_entry_id == entry.id).limit(1)
    )
    return DiaryEntryDetailResponse(
        id=entry.id,
        entry_type=entry.entry_type,
        title_fa=entry.title_fa,
        note_fa=entry.note_fa,
        happened_at=entry.happened_at,
        source_type=entry.source_type,
        source_reference=entry.source_id,
        linked_garden_object=(
            GardenObjectResponse(
                id=reward.id,
                object_key=reward.object_key,
                state=reward.state,
                diary_entry_id=reward.diary_entry_id,
                quadrant=reward.quadrant,
                position_x=reward.position_x,
                position_y=reward.position_y,
            )
            if reward
            else None
        ),
    )


@router.get("/pets/{pet_id}/garden", response_model=GardenStateResponse)
async def list_garden(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> GardenStateResponse:
    await _pet_access(session, identity.id, pet_id)
    rewards = list(
        (
            await session.scalars(
                select(GardenReward)
                .where(GardenReward.pet_id == pet_id)
                .order_by(GardenReward.created_at)
            )
        ).all()
    )
    objects = [
        GardenObjectResponse(
            id=item.id,
            object_key=item.object_key,
            state=item.state,
            diary_entry_id=item.diary_entry_id,
            quadrant=item.quadrant,
            position_x=item.position_x,
            position_y=item.position_y,
        )
        for item in rewards
    ]
    return GardenStateResponse(
        pet_id=pet_id,
        unlocked_quadrants=[1],
        visible_slot_count=12,
        slot_rules={
            "source": "server_milestone_rules",
            "xp_enabled": False,
            "decay_enabled": False,
        },
        objects=objects,
        next_eligibility={"reason_key": "server_derived_milestones_only"},
    )


@router.put("/garden/{reward_id}/placement", status_code=status.HTTP_204_NO_CONTENT)
async def place_garden_reward(
    reward_id: UUID,
    body: GardenPlacementBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    reward = await session.get(GardenReward, reward_id)
    if reward is None:
        raise HTTPException(status_code=404, detail="garden_reward_not_found")
    await _pet_access(session, identity.id, reward.pet_id)
    reward.state = "placed"
    reward.quadrant = body.quadrant
    reward.position_x = body.position_x
    reward.position_y = body.position_y
    reward.placed_at = utc_now()
    await session.commit()


@router.delete("/garden/{reward_id}/placement", status_code=status.HTTP_204_NO_CONTENT)
async def store_garden_reward(
    reward_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    reward = await session.scalar(
        select(GardenReward).where(GardenReward.id == reward_id).with_for_update()
    )
    if reward is None:
        raise HTTPException(status_code=404, detail="garden_reward_not_found")
    await _pet_access(session, identity.id, reward.pet_id)
    reward.state = "stored"
    reward.quadrant = None
    reward.position_x = None
    reward.position_y = None
    reward.placed_at = None
    await session.commit()


@router.post("/reorder/assess", response_model=ReorderAssessmentResponse)
async def reorder_assessment(body: ReorderBody, _: CurrentIdentity) -> ReorderAssessmentResponse:
    try:
        assessment = assess_reorder(**body.model_dump())
        return ReorderAssessmentResponse(
            recommendation=assessment.recommendation,
            outcome=(
                "insufficient_facts"
                if assessment.recommendation == "insufficient_information"
                else assessment.recommendation
            ),
            risk_gap_days=assessment.risk_gap_days,
            remaining_low_days=assessment.remaining_low_days,
            remaining_high_days=assessment.remaining_high_days,
            latest_delivery_days=assessment.latest_delivery_days,
            safety_buffer_days=assessment.safety_buffer_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/pets/{pet_id}/today", response_model=TodayResponse)
async def get_today(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> TodayResponse:
    await _pet_access(session, identity.id, pet_id)
    return TodayResponse.model_validate(await build_today(session, pet_id=pet_id))


@router.get("/households/{household_id}/wallet", response_model=WalletSummaryResponse)
async def wallet_balance(
    household_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> WalletSummaryResponse:
    await _household_access(session, identity.id, household_id)
    account = await session.scalar(
        select(WalletAccount).where(WalletAccount.household_id == household_id)
    )
    if account is None:
        return WalletSummaryResponse(available_balance_irr=0)
    balance = await session.scalar(
        select(func.coalesce(func.sum(WalletCredit.remaining_amount_irr), 0)).where(
            WalletCredit.wallet_account_id == account.id,
            WalletCredit.expires_at > utc_now(),
        )
    )
    return WalletSummaryResponse(available_balance_irr=int(balance or 0))


@router.get("/households/{household_id}/inventory", response_model=list[InventoryListItem])
async def list_household_inventory(
    household_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[InventoryListItem]:
    await _household_access(session, identity.id, household_id)
    units = list(
        (
            await session.scalars(
                select(InventoryUnit)
                .where(InventoryUnit.household_id == household_id)
                .order_by(InventoryUnit.created_at.desc())
            )
        ).all()
    )
    return [
        InventoryListItem(
            id=unit.id,
            label=unit.label,
            source=unit.source,
            state=unit.state,
            exact_expiry_date=unit.exact_expiry_date,
            supplier_country=unit.supplier_country_snapshot,
            authenticity=unit.authenticity_basis,
        )
        for unit in units
    ]


@router.put(
    "/notifications/preferences/{event_key}/sms",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_sms_preference(
    event_key: str,
    body: NotificationPreferenceBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    if (body.quiet_start_local is None) != (body.quiet_end_local is None):
        raise HTTPException(status_code=422, detail="quiet_hours_require_start_and_end")
    preference = await session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.identity_id == identity.id,
            NotificationPreference.channel == "sms",
            NotificationPreference.event_key == event_key,
        )
    )
    if preference is None:
        preference = NotificationPreference(
            identity_id=identity.id,
            channel="sms",
            event_key=event_key,
            enabled=body.enabled,
        )
        session.add(preference)
    preference.enabled = body.enabled
    preference.quiet_start_local = body.quiet_start_local
    preference.quiet_end_local = body.quiet_end_local
    await session.commit()


@router.get("/notifications", response_model=OffsetPage[NotificationListItem])
async def notification_inbox(
    identity: CurrentIdentity, session: SessionDependency, pagination: PaginationDependency
) -> OffsetPage[NotificationListItem]:
    filters = (
        Notification.recipient_identity_id == identity.id,
        Notification.channel == "in_app",
    )
    total = int(await session.scalar(select(func.count(Notification.id)).where(*filters)) or 0)
    notifications = list(
        (
            await session.scalars(
                select(Notification)
                .where(*filters)
                .order_by(Notification.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    )
    items = [
        NotificationListItem(
            id=item.id,
            event_key=item.event_key,
            payload=item.payload,
            created_at=item.created_at,
            read_at=item.read_at,
        )
        for item in notifications
    ]
    return OffsetPage[NotificationListItem].model_validate(
        page(items, total=total, pagination=pagination)
    )


@router.get("/notifications/feed", response_model=CursorPage[NotificationListItem])
async def notification_feed(
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> CursorPage[NotificationListItem]:
    filters = (
        Notification.recipient_identity_id == identity.id,
        Notification.channel == "in_app",
    )
    query = select(Notification).where(*filters)
    if cursor is not None:
        try:
            position = decode_cursor(cursor, settings.jwt_secret)
        except CursorError as exc:
            raise HTTPException(status_code=422, detail="invalid_cursor") from exc
        query = query.where(
            or_(
                Notification.created_at < position.created_at,
                and_(
                    Notification.created_at == position.created_at,
                    Notification.id < position.item_id,
                ),
            )
        )
    rows = list(
        (
            await session.scalars(
                query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(
                    limit + 1
                )
            )
        ).all()
    )
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last = visible[-1]
        next_cursor = encode_cursor(CursorPosition(last.created_at, last.id), settings.jwt_secret)
    items = [
        NotificationListItem(
            id=item.id,
            event_key=item.event_key,
            payload=item.payload,
            created_at=item.created_at,
            read_at=item.read_at,
        )
        for item in visible
    ]
    return CursorPage[NotificationListItem].model_validate(
        cursor_page(items, next_cursor=next_cursor)
    )


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> None:
    notification = await session.get(Notification, notification_id, with_for_update=True)
    if (
        notification is None
        or notification.recipient_identity_id != identity.id
        or notification.channel != "in_app"
    ):
        raise HTTPException(status_code=404, detail="notification_not_found")
    notification.read_at = notification.read_at or utc_now()
    await session.commit()


async def _household_access(session: AsyncSession, identity_id: UUID, household_id: UUID) -> None:
    try:
        await require_household_membership(
            session, identity_id=identity_id, household_id=household_id
        )
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="household_not_found") from exc


async def _pet_access(session: AsyncSession, identity_id: UUID, pet_id: UUID) -> Pet:
    try:
        return await require_pet_access(session, identity_id=identity_id, pet_id=pet_id)
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="pet_not_found") from exc


async def _owned_journey(session: AsyncSession, identity_id: UUID, journey_id: UUID) -> PetJourney:
    journey = await session.get(PetJourney, journey_id)
    if journey is None:
        raise HTTPException(status_code=404, detail="journey_not_found")
    await _pet_access(session, identity_id, journey.pet_id)
    return journey


async def _reorder_options(session: AsyncSession, unit: InventoryUnit) -> list[dict[str, Any]]:
    if unit.product_id is None:
        return []
    offers = list(
        (
            await session.scalars(
                select(Offer)
                .where(
                    Offer.product_id == unit.product_id,
                    Offer.status.in_(("active", "unavailable")),
                )
                .order_by(Offer.status, Offer.created_at, Offer.id)
            )
        ).all()
    )
    return [
        {
            "offer_id": offer.id,
            "sku": offer.sku,
            "available": (
                offer.status == "active"
                and offer.stock_posture == "sourced_after_payment"
                and offer.sourcing_capacity_status == "open"
            ),
            "reason_key": (
                None
                if offer.status == "active"
                and offer.stock_posture == "sourced_after_payment"
                and offer.sourcing_capacity_status == "open"
                else "offer_unavailable_or_capacity_paused"
            ),
        }
        for offer in offers
    ]


async def _remaining_facts(
    session: AsyncSession,
    unit: InventoryUnit,
    body: OpenInventoryBody,
    settings: Settings,
) -> dict[str, Any]:
    if body.remaining is None:
        assert body.remaining_grams is not None
        return {
            "remaining_grams": body.remaining_grams,
            "remaining_low_grams": body.remaining_grams,
            "remaining_high_grams": body.remaining_grams,
            "remaining_input_mode": "grams",
            "remaining_provenance": {
                "contract_version": 0,
                "source_field": "remaining_grams",
            },
        }
    if body.remaining.mode == "grams":
        return {
            "remaining_grams": body.remaining.grams,
            "remaining_low_grams": body.remaining.grams,
            "remaining_high_grams": body.remaining.grams,
            "remaining_input_mode": "grams",
            "remaining_provenance": {
                "contract_version": 1,
                "source_field": "remaining.grams",
            },
        }
    if not settings.semantic_level_estimation_enabled:
        raise HTTPException(status_code=409, detail="semantic_level_policy_disabled")
    nominal_quantity_grams = unit.initial_quantity_grams
    if nominal_quantity_grams is None and unit.product_id is not None:
        nominal_quantity_grams = await session.scalar(
            select(Product.nominal_quantity_grams).where(Product.id == unit.product_id)
        )
    if nominal_quantity_grams is None:
        raise HTTPException(status_code=409, detail="semantic_level_nominal_quantity_required")
    level_bounds = {
        "near_empty": (0, 25),
        "less_than_half": (25, 50),
        "more_than_half": (50, 75),
        "full": (75, 100),
    }
    low_percent, high_percent = level_bounds[body.remaining.level]
    low_grams = (nominal_quantity_grams * low_percent) // 100
    high_grams = (nominal_quantity_grams * high_percent) // 100
    return {
        "remaining_grams": None,
        "remaining_low_grams": low_grams,
        "remaining_high_grams": high_grams,
        "remaining_input_mode": "level",
        "remaining_provenance": {
            "contract_version": 1,
            "source_field": "remaining.level",
            "level": body.remaining.level,
            "nominal_quantity_grams": nominal_quantity_grams,
            "low_percent": low_percent,
            "high_percent": high_percent,
        },
    }


def _estimate_response(estimate: FoodEstimate) -> FoodEstimateResponse:
    return FoodEstimateResponse(
        id=estimate.id,
        inventory_unit_id=estimate.inventory_unit_id,
        scope=estimate.scope,
        pet_id=estimate.pet_id,
        low_days=estimate.low_days,
        high_days=estimate.high_days,
        min_days=estimate.low_days,
        max_days=estimate.high_days,
        confidence={"high": "high", "medium": "mid", "low": "unknown"}[estimate.confidence],
        basis={"key": estimate.basis},
        calculated_at=estimate.calculated_at,
        last_confirmed_at=estimate.last_confirmed_at,
        provenance=[
            FoodEstimateProvenanceRow(key=key, source="estimate", value=value)
            for key, value in (estimate.provenance or {}).items()
            if isinstance(value, (str, int, float)) or value is None
        ],
    )


def _content_str(content: dict[str, object], key: str) -> str | None:
    value = content.get(key)
    return value if isinstance(value, str) else None


def _content_int(content: dict[str, object], key: str) -> int | None:
    value = content.get(key)
    return value if isinstance(value, int) else None


def _content_list(content: dict[str, object], key: str) -> list[dict[str, Any]]:
    value = content.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _public_journey_content(content: dict[str, object]) -> dict[str, Any]:
    allowed = {
        "summary_fa",
        "eligibility",
        "duration_days",
        "active_from",
        "active_until",
        "steps",
        "completion_requires",
        "exception_behavior",
        "garden_object_key",
        "professional_approval_ref",
    }
    return {key: value for key, value in content.items() if key in allowed}


def _journey_definition_deliverable(
    definition: JourneyDefinition,
    species: str | None,
    now: Any,
) -> bool:
    content = definition.content
    if not isinstance(content.get("professional_approval_ref"), str):
        return False
    from_raw = content.get("active_from")
    until_raw = content.get("active_until")
    if isinstance(from_raw, str) and from_raw and now.isoformat() < from_raw:
        return False
    if isinstance(until_raw, str) and until_raw and now.isoformat() >= until_raw:
        return False
    eligible_species = content.get("eligible_species")
    if (
        species is not None
        and isinstance(eligible_species, list)
        and species not in eligible_species
    ):
        return False
    return bool(_content_list(content, "steps"))


def _valid_check_in(content: dict[str, object], check_in_key: str, answer_key: str) -> bool:
    for step in _content_list(content, "steps"):
        if step.get("key") != check_in_key:
            continue
        answers = step.get("allowed_answers")
        return isinstance(answers, list) and answer_key in answers
    return False


def _completion_requirements_met(content: dict[str, object], submitted_keys: set[str]) -> bool:
    required = content.get("completion_requires")
    if isinstance(required, list):
        required_keys = {str(item) for item in required if isinstance(item, str)}
    else:
        required_keys = {
            str(step["key"])
            for step in _content_list(content, "steps")
            if isinstance(step.get("key"), str)
        }
    return bool(required_keys) and required_keys.issubset(submitted_keys)
