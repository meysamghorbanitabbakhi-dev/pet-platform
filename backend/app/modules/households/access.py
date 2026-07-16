from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.households.models import HouseholdMembership
from app.modules.pets.models import Pet


class HouseholdAccessError(Exception):
    pass


async def require_household_membership(
    session: AsyncSession, *, identity_id: UUID, household_id: UUID
) -> HouseholdMembership:
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.identity_id == identity_id,
            HouseholdMembership.household_id == household_id,
        )
    )
    if membership is None:
        raise HouseholdAccessError("household access denied")
    return membership


async def require_pet_access(session: AsyncSession, *, identity_id: UUID, pet_id: UUID) -> Pet:
    pet = await session.get(Pet, pet_id)
    if pet is None:
        raise HouseholdAccessError("pet not found")
    await require_household_membership(
        session, identity_id=identity_id, household_id=pet.household_id
    )
    return pet
