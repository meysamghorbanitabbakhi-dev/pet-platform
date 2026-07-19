from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from app.common.time import utc_now
from app.db.session import SessionFactory, close_database
from app.modules.households.models import Household, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.notifications.models import Notification, NotificationPreference
from app.modules.notifications.service import enqueue_wallet_credit_notification
from app.modules.orders.models import Order
from app.modules.system.event_registry import event_disposition
from app.modules.system.models import OutboxEvent
from app.modules.system.outbox import OutboxDispatcher
from app.modules.wallet.jobs import process_overdue_orders
from app.modules.wallet.models import WalletAccount, WalletCredit, WalletDebit
from app.modules.wallet.service import WalletError, debit_wallet, grant_late_delivery_credit
from sqlalchemy import func, select

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class OrderSeed:
    token: str
    identity_id: uuid.UUID
    household_id: uuid.UUID
    order_id: uuid.UUID


def _address_snapshot() -> dict[str, object]:
    return {
        "label": "خانه",
        "recipient_name": "مالک خانه",
        "recipient_mobile_e164": "+989121234567",
        "province": "تهران",
        "city": "تهران",
        "address_line": "خیابان ولیعصر",
    }


async def _seed_order(
    *,
    merchandise_total_irr: int = 10_000_000,
    status: str = "sourcing",
    paid_at: datetime | None,
    delivery_commitment_at: datetime | None,
    delivered_at: datetime | None = None,
) -> OrderSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98915{token[:7]}", status="active"
        )
        household = Household(name=f"hh-late-credit-{token}")
        session.add_all([identity, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=identity.id, role="owner")
        )
        order = Order(
            customer_identity_id=identity.id,
            household_id=household.id,
            status=status,
            currency="IRR",
            merchandise_total_irr=merchandise_total_irr,
            checkout_idempotency_key=f"late-credit-{token}",
            paid_at=paid_at,
            delivery_commitment_at=delivery_commitment_at,
            delivered_at=delivered_at,
            delivery_address_snapshot=_address_snapshot(),
        )
        session.add(order)
        await session.commit()
        return OrderSeed(
            token=token,
            identity_id=identity.id,
            household_id=household.id,
            order_id=order.id,
        )


async def _credit_count(order_id: uuid.UUID) -> int:
    async with SessionFactory() as session:
        return (
            await session.execute(
                select(func.count(WalletCredit.id)).where(
                    WalletCredit.source_type == "late_delivery",
                    WalletCredit.source_id == str(order_id),
                )
            )
        ).scalar_one()


async def test_on_time_delivery_never_grants_a_credit() -> None:
    now = utc_now()
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=34),
        delivered_at=now - timedelta(hours=40),  # delivered before the commitment deadline
        status="delivered",
    )
    created = await process_overdue_orders(SessionFactory)
    assert await _credit_count(seed.order_id) == 0
    assert created == 0


async def test_overdue_and_still_undelivered_grants_correct_amount_and_expiry() -> None:
    now = utc_now()
    seed = await _seed_order(
        merchandise_total_irr=12_345_678,
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=10),
        delivered_at=None,
        status="sourcing",
    )
    created = await process_overdue_orders(SessionFactory)
    assert created == 1
    async with SessionFactory() as session:
        credit = await session.scalar(
            select(WalletCredit).where(
                WalletCredit.source_type == "late_delivery",
                WalletCredit.source_id == str(seed.order_id),
            )
        )
    assert credit is not None
    assert credit.original_amount_irr == (12_345_678 * 500) // 10_000
    assert credit.remaining_amount_irr == credit.original_amount_irr
    # three calendar months, not a fixed 90*24h -- this repo's own _add_months helper
    expected_expiry_month = (credit.created_at.month - 1 + 3) % 12 + 1
    assert credit.expires_at.month == expected_expiry_month


async def test_overdue_but_delivered_after_the_deadline_still_grants_credit() -> None:
    now = utc_now()
    commitment = now - timedelta(hours=20)
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=commitment,
        delivered_at=commitment + timedelta(hours=5),  # delivered, but after the deadline
        status="delivered",
    )
    created = await process_overdue_orders(SessionFactory)
    assert created == 1
    assert await _credit_count(seed.order_id) == 1


@pytest.mark.parametrize("excluded_status", ["failed", "cancelled"])
async def test_failed_and_cancelled_orders_are_excluded_even_when_overdue(
    excluded_status: str,
) -> None:
    now = utc_now()
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=10),
        delivered_at=None,
        status=excluded_status,
    )
    created = await process_overdue_orders(SessionFactory)
    assert created == 0
    assert await _credit_count(seed.order_id) == 0


async def test_direct_grant_call_is_exactly_once_on_replay() -> None:
    now = utc_now()
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=10),
        delivered_at=None,
    )
    async with SessionFactory() as session:
        first = await grant_late_delivery_credit(session, order_id=seed.order_id)
        await session.commit()
    async with SessionFactory() as session:
        second = await grant_late_delivery_credit(session, order_id=seed.order_id)
        await session.commit()
    assert first.id == second.id
    assert await _credit_count(seed.order_id) == 1


async def test_concurrent_grant_calls_produce_exactly_one_credit() -> None:
    now = utc_now()
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=10),
        delivered_at=None,
    )

    async def _attempt() -> None:
        async with SessionFactory() as session:
            try:
                await grant_late_delivery_credit(session, order_id=seed.order_id)
                await session.commit()
            except WalletError:
                await session.rollback()

    await asyncio.gather(*(_attempt() for _ in range(8)))
    assert await _credit_count(seed.order_id) == 1


async def test_process_overdue_orders_does_not_duplicate_an_already_credited_order() -> None:
    now = utc_now()
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=10),
        delivered_at=None,
    )
    async with SessionFactory() as session:
        await grant_late_delivery_credit(session, order_id=seed.order_id)
        await session.commit()

    created = await process_overdue_orders(SessionFactory)
    assert created == 0
    assert await _credit_count(seed.order_id) == 1


async def test_fifo_debit_draws_the_earliest_expiring_credit_first() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        household = Household(name=f"hh-fifo-{token}")
        session.add(household)
        await session.flush()
        account = WalletAccount(household_id=household.id)
        session.add(account)
        await session.flush()
        now = utc_now()
        early = WalletCredit(
            wallet_account_id=account.id,
            original_amount_irr=1000,
            remaining_amount_irr=1000,
            expires_at=now + timedelta(days=30),
            source_type="late_delivery",
            source_id=f"early-{token}",
        )
        late = WalletCredit(
            wallet_account_id=account.id,
            original_amount_irr=1000,
            remaining_amount_irr=1000,
            expires_at=now + timedelta(days=90),
            source_type="late_delivery",
            source_id=f"late-{token}",
        )
        session.add_all([early, late])
        await session.commit()
        account_id, early_id, late_id = account.id, early.id, late.id

    async with SessionFactory() as session:
        await debit_wallet(
            session,
            wallet_account_id=account_id,
            amount_irr=600,
            idempotency_key=f"debit-{token}",
        )

    async with SessionFactory() as session:
        early_after = await session.get(WalletCredit, early_id)
        late_after = await session.get(WalletCredit, late_id)
    assert early_after is not None and late_after is not None
    assert early_after.remaining_amount_irr == 400  # the sooner-expiring credit was drawn down
    assert late_after.remaining_amount_irr == 1000  # the later credit is untouched


async def test_fifo_debit_spans_into_the_next_credit_when_the_first_is_insufficient() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        household = Household(name=f"hh-span-{token}")
        session.add(household)
        await session.flush()
        account = WalletAccount(household_id=household.id)
        session.add(account)
        await session.flush()
        now = utc_now()
        early = WalletCredit(
            wallet_account_id=account.id,
            original_amount_irr=300,
            remaining_amount_irr=300,
            expires_at=now + timedelta(days=30),
            source_type="late_delivery",
            source_id=f"early-{token}",
        )
        late = WalletCredit(
            wallet_account_id=account.id,
            original_amount_irr=1000,
            remaining_amount_irr=1000,
            expires_at=now + timedelta(days=90),
            source_type="late_delivery",
            source_id=f"late-{token}",
        )
        session.add_all([early, late])
        await session.commit()
        account_id, early_id, late_id = account.id, early.id, late.id

    async with SessionFactory() as session:
        await debit_wallet(
            session,
            wallet_account_id=account_id,
            amount_irr=500,
            idempotency_key=f"debit-{token}",
        )

    async with SessionFactory() as session:
        early_after = await session.get(WalletCredit, early_id)
        late_after = await session.get(WalletCredit, late_id)
    assert early_after is not None and late_after is not None
    assert early_after.remaining_amount_irr == 0
    assert late_after.remaining_amount_irr == 800  # 300 from early + 200 from late = 500


async def test_debit_replay_via_idempotency_key_does_not_double_debit() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        household = Household(name=f"hh-replay-{token}")
        session.add(household)
        await session.flush()
        account = WalletAccount(household_id=household.id)
        session.add(account)
        await session.flush()
        session.add(
            WalletCredit(
                wallet_account_id=account.id,
                original_amount_irr=1000,
                remaining_amount_irr=1000,
                expires_at=utc_now() + timedelta(days=30),
                source_type="late_delivery",
                source_id=f"credit-{token}",
            )
        )
        await session.commit()
        account_id = account.id

    key = f"debit-{token}"
    async with SessionFactory() as session:
        first = await debit_wallet(
            session, wallet_account_id=account_id, amount_irr=400, idempotency_key=key
        )
    async with SessionFactory() as session:
        second = await debit_wallet(
            session, wallet_account_id=account_id, amount_irr=400, idempotency_key=key
        )
    assert first.id == second.id
    async with SessionFactory() as session:
        debit_count = (
            await session.execute(
                select(func.count(WalletDebit.id)).where(
                    WalletDebit.wallet_account_id == account_id
                )
            )
        ).scalar_one()
        credit = await session.scalar(
            select(WalletCredit).where(WalletCredit.wallet_account_id == account_id)
        )
    assert debit_count == 1
    assert credit is not None and credit.remaining_amount_irr == 600


async def test_debit_raises_and_applies_nothing_when_balance_is_insufficient() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        household = Household(name=f"hh-insufficient-{token}")
        session.add(household)
        await session.flush()
        account = WalletAccount(household_id=household.id)
        session.add(account)
        await session.flush()
        session.add(
            WalletCredit(
                wallet_account_id=account.id,
                original_amount_irr=100,
                remaining_amount_irr=100,
                expires_at=utc_now() + timedelta(days=30),
                source_type="late_delivery",
                source_id=f"credit-{token}",
            )
        )
        await session.commit()
        account_id, credit_amount_before = account.id, 100

    async with SessionFactory() as session:
        with pytest.raises(WalletError):
            await debit_wallet(
                session,
                wallet_account_id=account_id,
                amount_irr=1000,
                idempotency_key=f"debit-{token}",
            )

    async with SessionFactory() as session:
        credit = await session.scalar(
            select(WalletCredit).where(WalletCredit.wallet_account_id == account_id)
        )
        debit_count = (
            await session.execute(
                select(func.count(WalletDebit.id)).where(
                    WalletDebit.wallet_account_id == account_id
                )
            )
        ).scalar_one()
    assert credit is not None and credit.remaining_amount_irr == credit_amount_before
    assert debit_count == 0


async def test_expired_credit_is_not_available_for_debit() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        household = Household(name=f"hh-expired-{token}")
        session.add(household)
        await session.flush()
        account = WalletAccount(household_id=household.id)
        session.add(account)
        await session.flush()
        session.add(
            WalletCredit(
                wallet_account_id=account.id,
                original_amount_irr=500,
                remaining_amount_irr=500,
                expires_at=utc_now() - timedelta(days=1),  # already expired
                source_type="late_delivery",
                source_id=f"credit-{token}",
            )
        )
        await session.commit()
        account_id = account.id

    async with SessionFactory() as session:
        with pytest.raises(WalletError):
            await debit_wallet(
                session,
                wallet_account_id=account_id,
                amount_irr=100,
                idempotency_key=f"debit-{token}",
            )


async def test_notification_created_when_customer_visible_and_skipped_when_not() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98916{token[:7]}", status="active"
        )
        household = Household(name=f"hh-notify-{token}")
        session.add_all([identity, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=identity.id, role="owner")
        )
        await session.commit()
        household_id, order_id = household.id, uuid.uuid4()

    payload = {
        "order_id": str(order_id),
        "household_id": str(household_id),
        "amount_irr": 50000,
        "expires_at": utc_now().isoformat(),
    }
    await enqueue_wallet_credit_notification(SessionFactory, payload, customer_visible=False)
    async with SessionFactory() as session:
        count_hidden = (
            await session.execute(
                select(func.count(Notification.id)).where(Notification.source_id == str(order_id))
            )
        ).scalar_one()
    assert count_hidden == 0

    await enqueue_wallet_credit_notification(SessionFactory, payload, customer_visible=True)
    async with SessionFactory() as session:
        notifications = list(
            (
                await session.scalars(
                    select(Notification).where(Notification.source_id == str(order_id))
                )
            ).all()
        )
    channels = {n.channel for n in notifications}
    assert channels == {"in_app", "sms"}
    for notification in notifications:
        assert notification.destination_kind == "order"
        assert notification.destination_id == order_id


async def test_notification_respects_sms_preference_and_stays_in_app_only() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98917{token[:7]}", status="active"
        )
        household = Household(name=f"hh-pref-{token}")
        session.add_all([identity, household])
        await session.flush()
        session.add_all(
            [
                HouseholdMembership(
                    household_id=household.id, identity_id=identity.id, role="owner"
                ),
                NotificationPreference(
                    identity_id=identity.id,
                    channel="sms",
                    event_key="wallet.late_delivery_credit_granted",
                    enabled=False,
                ),
            ]
        )
        await session.commit()
        household_id, order_id = household.id, uuid.uuid4()

    payload = {
        "order_id": str(order_id),
        "household_id": str(household_id),
        "amount_irr": 50000,
        "expires_at": utc_now().isoformat(),
    }
    await enqueue_wallet_credit_notification(SessionFactory, payload, customer_visible=True)
    async with SessionFactory() as session:
        notifications = list(
            (
                await session.scalars(
                    select(Notification).where(Notification.source_id == str(order_id))
                )
            ).all()
        )
    by_channel = {n.channel: n.status for n in notifications}
    assert by_channel["in_app"] == "sent"
    assert by_channel["sms"] == "suppressed"


async def test_notification_is_idempotent_on_replay() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        household = Household(name=f"hh-idem-{token}")
        session.add_all([identity, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=identity.id, role="owner")
        )
        await session.commit()
        household_id, order_id = household.id, uuid.uuid4()

    payload = {
        "order_id": str(order_id),
        "household_id": str(household_id),
        "amount_irr": 50000,
        "expires_at": utc_now().isoformat(),
    }
    await enqueue_wallet_credit_notification(SessionFactory, payload, customer_visible=True)
    await enqueue_wallet_credit_notification(SessionFactory, payload, customer_visible=True)
    async with SessionFactory() as session:
        count = (
            await session.execute(
                select(func.count(Notification.id)).where(Notification.source_id == str(order_id))
            )
        ).scalar_one()
    assert count == 2  # exactly one in_app + one sms, not four


async def test_outbox_event_flows_through_dispatcher_into_a_real_notification() -> None:
    assert event_disposition("wallet.late_delivery_credit_granted") == "handler"
    now = utc_now()
    seed = await _seed_order(
        paid_at=now - timedelta(hours=400),
        delivery_commitment_at=now - timedelta(hours=10),
        delivered_at=None,
    )
    async with SessionFactory() as session:
        credit = await grant_late_delivery_credit(session, order_id=seed.order_id)
        await session.commit()
        credit_id = credit.id

    async with SessionFactory() as session:
        pending = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "wallet.late_delivery_credit_granted",
                OutboxEvent.aggregate_id == str(credit_id),
            )
        )
    assert pending is not None
    assert pending.status == "pending"
    assert pending.disposition == "handler"

    dispatcher = OutboxDispatcher(SessionFactory, batch_size=10)
    dispatcher.register(
        "wallet.late_delivery_credit_granted",
        lambda payload: enqueue_wallet_credit_notification(
            SessionFactory, payload, customer_visible=True
        ),
    )
    processed = await dispatcher.dispatch_batch()
    assert processed >= 1

    async with SessionFactory() as session:
        refreshed = await session.get(OutboxEvent, pending.id)
        notifications = list(
            (
                await session.scalars(
                    select(Notification).where(
                        Notification.source_id == str(seed.order_id),
                        Notification.event_key == "wallet.late_delivery_credit_granted",
                    )
                )
            ).all()
        )
    assert refreshed is not None
    assert refreshed.status == "published"
    assert {n.channel for n in notifications} == {"in_app", "sms"}
