from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    ContextPetSummary,
    CustomerCapabilitiesResponse,
    HouseholdSummary,
    MeContextResponse,
    MeIdentityResponse,
    OnboardingRequirementsResponse,
)
from app.api.dependencies import CurrentIdentity
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.pets.models import Pet

router = APIRouter(prefix="/me", tags=["me"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/context", response_model=MeContextResponse)
async def context(
    identity: CurrentIdentity, session: SessionDependency, settings: SettingsDependency
) -> MeContextResponse:
    memberships = list(
        (
            await session.execute(
                select(HouseholdMembership, Household)
                .join(Household, Household.id == HouseholdMembership.household_id)
                .where(HouseholdMembership.identity_id == identity.id)
                .order_by(HouseholdMembership.created_at, Household.id)
            )
        ).all()
    )
    household_ids = [household.id for _, household in memberships]
    pets = []
    if household_ids:
        pets = list(
            (
                await session.scalars(
                    select(Pet)
                    .where(Pet.household_id.in_(household_ids), Pet.status == "active")
                    .order_by(Pet.household_id, Pet.created_at, Pet.id)
                )
            ).all()
        )
    pet_counts: dict[UUID, int] = {}
    address_counts: dict[UUID, int] = {}
    if household_ids:
        pet_counts = {
            household_id: count
            for household_id, count in (
                await session.execute(
                    select(Pet.household_id, func.count(Pet.id))
                    .where(Pet.household_id.in_(household_ids), Pet.status == "active")
                    .group_by(Pet.household_id)
                )
            )
            .tuples()
            .all()
        }
        address_counts = {
            household_id: count
            for household_id, count in (
                await session.execute(
                    select(HouseholdAddress.household_id, func.count(HouseholdAddress.id))
                    .where(
                        HouseholdAddress.household_id.in_(household_ids),
                        HouseholdAddress.active.is_(True),
                    )
                    .group_by(HouseholdAddress.household_id)
                )
            )
            .tuples()
            .all()
        }
    default_household_id = household_ids[0] if len(household_ids) == 1 else None
    return MeContextResponse(
        identity=MeIdentityResponse(
            id=identity.id, mobile_e164=identity.mobile_e164, identity_type="customer"
        ),
        households=[
            HouseholdSummary(
                id=household.id,
                name=household.name,
                role=membership.role,
                pet_count=pet_counts.get(household.id, 0),
                active_address_count=address_counts.get(household.id, 0),
            )
            for membership, household in memberships
        ],
        default_household_id=default_household_id,
        pets=[
            ContextPetSummary(
                id=pet.id, household_id=pet.household_id, name=pet.name, species=pet.species
            )
            for pet in pets
        ],
        onboarding=OnboardingRequirementsResponse(
            needs_household=not household_ids,
            needs_pet=bool(household_ids) and not pets,
            needs_address=bool(household_ids) and not any(address_counts.values()),
        ),
        capabilities=CustomerCapabilitiesResponse(
            availability_subscriptions_enabled=settings.availability_subscriptions_enabled,
            concierge_requests_enabled=settings.concierge_requests_enabled,
            care_journey_delivery_enabled=settings.care_journey_delivery_enabled,
        ),
    )
