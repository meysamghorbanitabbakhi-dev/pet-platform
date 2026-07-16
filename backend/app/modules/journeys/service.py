from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.diary.models import DiaryEntry
from app.modules.garden.models import GardenReward
from app.modules.journeys.models import JourneyDefinition, PetJourney
from app.modules.system.outbox import DomainEvent, add_outbox_event


class JourneyError(Exception):
    pass


class JourneyService:
    async def start(
        self, session: AsyncSession, *, pet_id: UUID, definition_id: UUID
    ) -> PetJourney:
        definition = await session.get(JourneyDefinition, definition_id)
        if definition is None or definition.approval_status != "approved":
            raise JourneyError("journey content is not approved")
        journey = PetJourney(
            pet_id=pet_id,
            definition_id=definition.id,
            status="active",
            started_at=utc_now(),
        )
        session.add(journey)
        await session.commit()
        return journey

    async def complete(
        self,
        session: AsyncSession,
        *,
        journey_id: UUID,
        memory_title_fa: str,
    ) -> tuple[DiaryEntry, GardenReward]:
        journey = await session.scalar(
            select(PetJourney).where(PetJourney.id == journey_id).with_for_update()
        )
        if journey is None or journey.status not in ("active", "paused"):
            raise JourneyError("journey cannot be completed")
        definition = await session.get(JourneyDefinition, journey.definition_id)
        object_key = definition.content.get("garden_object_key") if definition else None
        if not isinstance(object_key, str) or not object_key:
            raise JourneyError("approved journey has no configured Garden reward")
        now = utc_now()
        journey.status = "completed"
        journey.ended_at = now
        diary = DiaryEntry(
            pet_id=journey.pet_id,
            entry_type="journey_completion",
            title_fa=memory_title_fa,
            happened_at=now,
            source_type="journey",
            source_id=str(journey.id),
        )
        session.add(diary)
        await session.flush()
        reward = GardenReward(
            pet_id=journey.pet_id,
            diary_entry_id=diary.id,
            source_type="journey_completion",
            source_id=str(journey.id),
            object_key=object_key,
            state="revealed",
        )
        session.add(reward)
        await session.flush()
        add_outbox_event(
            session,
            DomainEvent(
                event_type="journey.completed",
                aggregate_type="pet_journey",
                aggregate_id=str(journey.id),
                payload={
                    "pet_id": str(journey.pet_id),
                    "diary_entry_id": str(diary.id),
                    "garden_reward_id": str(reward.id),
                },
            ),
        )
        await session.commit()
        return diary, reward
