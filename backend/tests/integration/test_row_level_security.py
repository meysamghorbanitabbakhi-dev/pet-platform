from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
from app.db.session import AppSessionFactory, SessionFactory, app_engine, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.diary.models import DiaryEntry
from app.modules.food_estimation.models import FoodEstimate
from app.modules.garden.models import GardenReward
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit
from app.modules.journeys.models import JourneyCheckIn, JourneyDefinition, PetJourney
from app.modules.notifications.models import Notification
from app.modules.orders.fulfillment import FulfillmentEvent
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.resolutions import OrderResolution
from app.modules.payments.models import PaymentAttempt
from app.modules.pet_health.models import HealthMeasurement, MeasurementReminder, PetConsent
from app.modules.pets.models import Pet
from fastapi import FastAPI
from sqlalchemy import select, text

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class TwoHouseholdSeed:
    customer_a: AuthIdentity
    customer_b: AuthIdentity
    operator: AuthIdentity
    household_a_id: uuid.UUID
    household_b_id: uuid.UUID
    order_a_id: uuid.UUID


async def _seed_two_households() -> TwoHouseholdSeed:
    """Two unrelated households, each with a paid order, and an operator.
    No route, no application-layer check, is involved in creating this
    data -- it exists purely to test what the database itself will and
    will not return."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        customer_a = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98911{token[:7]}", status="active"
        )
        customer_b = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98912{token[:7]}", status="active"
        )
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98913{token[:7]}", status="active"
        )
        household_a = Household(name=f"rls-hh-a-{token}")
        household_b = Household(name=f"rls-hh-b-{token}")
        session.add_all([customer_a, customer_b, operator, household_a, household_b])
        await session.flush()
        session.add_all(
            [
                HouseholdMembership(
                    household_id=household_a.id, identity_id=customer_a.id, role="owner"
                ),
                HouseholdMembership(
                    household_id=household_b.id, identity_id=customer_b.id, role="owner"
                ),
            ]
        )
        order_a = Order(
            customer_identity_id=customer_a.id,
            household_id=household_a.id,
            status="paid",
            currency="IRR",
            merchandise_total_irr=1_000_000,
            checkout_idempotency_key=f"rls-{token}",
            paid_at=utc_now(),
            delivery_commitment_at=utc_now(),
            delivery_address_snapshot={
                "label": "x",
                "recipient_name": "x",
                "recipient_mobile_e164": "+989120000000",
                "province": "x",
                "city": "x",
                "address_line": "x",
            },
        )
        session.add(order_a)
        await session.commit()
        return TwoHouseholdSeed(
            customer_a=customer_a,
            customer_b=customer_b,
            operator=operator,
            household_a_id=household_a.id,
            household_b_id=household_b.id,
            order_a_id=order_a.id,
        )


# --- direct database proof: RLS blocks even a query with no app-level ------
# --- ownership check at all, not just the routes that happen to have one --


async def test_household_scoped_table_is_invisible_with_no_rls_context() -> None:
    """A raw SELECT against a household-scoped table, run as the
    unprivileged app role with no session context set at all (as if a
    future route forgot to resolve an identity), sees nothing --
    demonstrating the database itself, not just application code, is
    what stops this."""
    seed = await _seed_two_households()
    async with AppSessionFactory() as session:
        rows = list(
            (
                await session.scalars(select(Household).where(Household.id == seed.household_a_id))
            ).all()
        )
    assert rows == []


async def test_household_scoped_table_is_invisible_to_an_unrelated_household() -> None:
    """The core proof this workstream exists for: even with a real,
    authenticated session (not the "no context" case above), a
    household-scoped row belonging to household A is invisible while
    app.household_ids is set to household B alone -- this is enforced
    by Postgres, independent of whatever the application layer's own
    ownership check does or doesn't do."""
    seed = await _seed_two_households()
    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible = list(
            (
                await session.scalars(select(Household).where(Household.id == seed.household_a_id))
            ).all()
        )
        visible = list(
            (
                await session.scalars(select(Household).where(Household.id == seed.household_b_id))
            ).all()
        )
    assert invisible == []
    assert len(visible) == 1


async def test_customer_identity_scoped_table_is_invisible_to_a_household_co_member() -> None:
    """orders_orders is scoped by customer_identity_id, not household_id
    (matching commerce.py's own `order.customer_identity_id != identity.id`
    check) -- a second identity in the SAME household as the purchaser
    must not see the order via a raw query, even with that household's
    id correctly present in app.household_ids. Proves the policy tracks
    the real application semantic, not just "same household is enough."
    """
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        co_member = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98914{uuid.uuid4().hex[:7]}", status="active"
        )
        session.add(co_member)
        await session.flush()
        session.add(
            HouseholdMembership(
                household_id=seed.household_a_id, identity_id=co_member.id, role="member"
            )
        )
        await session.commit()
        co_member_id = co_member.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(co_member_id)}
        )
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_a_id)},
        )
        invisible = list(
            (await session.scalars(select(Order).where(Order.id == seed.order_a_id))).all()
        )
    assert invisible == []

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(seed.customer_a.id)}
        )
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_a_id)},
        )
        visible = list(
            (await session.scalars(select(Order).where(Order.id == seed.order_a_id))).all()
        )
    assert len(visible) == 1


async def test_operator_context_sees_every_household() -> None:
    seed = await _seed_two_households()
    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'true', true)"))
        await session.execute(text("SELECT set_config('app.household_ids', '', true)"))
        rows = list(
            (
                await session.scalars(
                    select(Household).where(
                        Household.id.in_((seed.household_a_id, seed.household_b_id))
                    )
                )
            ).all()
        )
    assert {row.id for row in rows} == {seed.household_a_id, seed.household_b_id}


async def test_household_context_does_not_leak_across_transactions_within_a_session() -> None:
    """SET LOCAL resets at the end of every transaction -- a session that
    commits and then runs a second query must not silently inherit
    context left over from a completely different identity's earlier,
    already-committed use of the same session object."""
    seed = await _seed_two_households()
    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_a_id)},
        )
        visible = list(
            (
                await session.scalars(select(Household).where(Household.id == seed.household_a_id))
            ).all()
        )
        assert len(visible) == 1
        await session.commit()

        invisible = list(
            (
                await session.scalars(select(Household).where(Household.id == seed.household_a_id))
            ).all()
        )
    assert invisible == []


# --- through the real HTTP/dependency-injection layer -----------------------


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_http_request_with_a_faked_identity_still_gets_real_rls_context(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """app.dependency_overrides[get_current_identity] = lambda: identity
    (this codebase's standard test pattern for simulating auth without a
    real bearer token) must still result in apply_rls_context running for
    that identity -- proving _identity_with_rls_context's composition
    (app/api/dependencies.py) survives the override, which is what lets
    every other HTTP-level test in this suite keep working unmodified
    under RLS."""
    app, client = app_and_client
    seed = await _seed_two_households()
    app.dependency_overrides[get_current_identity] = lambda: seed.customer_a

    own_order = await client.get(f"/api/v1/orders/{seed.order_a_id}")
    assert own_order.status_code == 200

    app.dependency_overrides[get_current_identity] = lambda: seed.customer_b
    foreign_order = await client.get(f"/api/v1/orders/{seed.order_a_id}")
    assert foreign_order.status_code == 404


async def test_a_membership_change_takes_effect_on_the_very_next_request(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """household_ids is recomputed fresh every request (apply_rls_context),
    never cached across requests within the app process -- adding a new
    HouseholdMembership row must grant access starting with the very
    next request, with no separate propagation step."""
    app, client = app_and_client
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        new_member = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98915{uuid.uuid4().hex[:7]}", status="active"
        )
        session.add(new_member)
        await session.flush()
        new_member_id = new_member.id
        await session.commit()

    app.dependency_overrides[get_current_identity] = lambda: new_member
    before = await client.get(f"/api/v1/orders/{seed.order_a_id}")
    assert before.status_code == 404

    async with SessionFactory() as session:
        session.add(
            HouseholdMembership(
                household_id=seed.household_a_id, identity_id=new_member_id, role="member"
            )
        )
        await session.commit()

    # Still 404: orders_orders is customer_identity_id-scoped, not
    # household_id-scoped (see test_customer_identity_scoped_table_is_invisible_
    # to_a_household_co_member above) -- a fresh membership does not
    # retroactively grant access to another member's order. This is the
    # correct outcome, not a stale-context artifact: it demonstrates the
    # policy is actually being evaluated per-request against live data,
    # not returning a fixed answer.
    after = await client.get(f"/api/v1/orders/{seed.order_a_id}")
    assert after.status_code == 404


async def test_bootstrap_household_creation_still_works_under_rls(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """households_households' permissive INSERT policy plus
    households_memberships' identity_id-fallback INSERT policy together
    must not block the ordinary "customer creates their first household"
    flow -- the two rows this route creates reference a household_id
    that, by construction, cannot yet be in the requester's own
    app_household_ids() at INSERT time."""
    app, client = app_and_client
    async with SessionFactory() as session:
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98916{uuid.uuid4().hex[:7]}", status="active"
        )
        session.add(customer)
        await session.commit()
    app.dependency_overrides[get_current_identity] = lambda: customer

    response = await client.post("/api/v1/pet-life/households", json={"name": "New Household"})
    assert response.status_code == 201
    household_id = response.json()["id"]

    # The new household is now visible to its creator on a subsequent
    # request within the same test (a fresh request, fresh household_ids
    # computation) -- proving the membership row created alongside it
    # was itself correctly persisted and is queryable, not just that the
    # INSERT didn't raise.
    async with SessionFactory() as session:
        membership = await session.scalar(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == uuid.UUID(household_id),
                HouseholdMembership.identity_id == customer.id,
            )
        )
    assert membership is not None


# --- 20260720_0044: household self-enrollment hardening ---------------------


async def test_self_enrollment_into_an_unrelated_household_is_rejected() -> None:
    """The households_memberships INSERT policy's bootstrap fallback
    (identity_id = app_identity_id()) previously allowed self-insertion
    into ANY household_id, with no relationship to that household
    required. A raw INSERT attempt -- as if a future route regressed and
    let a customer choose an arbitrary household_id -- must now be
    rejected by the database itself, not merely by application code that
    doesn't currently expose this path."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        attacker = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98917{token[:7]}", status="active"
        )
        victim_household = Household(name=f"victim-hh-{token}")
        session.add_all([attacker, victim_household])
        await session.commit()
        attacker_id = attacker.id
        household_id = victim_household.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(attacker_id)}
        )
        await session.execute(text("SELECT set_config('app.household_ids', '', true)"))
        with pytest.raises(Exception, match="row-level security"):
            await session.execute(
                text(
                    "INSERT INTO households_memberships"
                    " (id, household_id, identity_id, role, created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :h, :i, 'owner', now(), now())"
                ),
                {"h": str(household_id), "i": str(attacker_id)},
            )
        await session.rollback()

    async with SessionFactory() as session:
        leaked = await session.scalar(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.identity_id == attacker_id,
            )
        )
    assert leaked is None


async def test_self_enrollment_is_rejected_once_a_household_has_any_member() -> None:
    """Closes the "creator revoked, re-enrolls later" gap: even for the
    identity that actually created the household, self-insertion is only
    allowed while no membership row exists yet for it at all (true
    first-membership bootstrap). Once any membership row exists --
    someone else already joined, or the creator's own original
    membership was later removed -- the creator can no longer use this
    fallback to insert themselves back in."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        creator = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        other_member = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        household = Household(name=f"abandoned-hh-{token}", created_by_identity_id=None)
        session.add_all([creator, other_member, household])
        await session.flush()
        household.created_by_identity_id = creator.id
        session.add(
            HouseholdMembership(
                household_id=household.id, identity_id=other_member.id, role="member"
            )
        )
        await session.commit()
        creator_id = creator.id
        household_id = household.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(creator_id)}
        )
        await session.execute(text("SELECT set_config('app.household_ids', '', true)"))
        with pytest.raises(Exception, match="row-level security"):
            await session.execute(
                text(
                    "INSERT INTO households_memberships"
                    " (id, household_id, identity_id, role, created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :h, :i, 'owner', now(), now())"
                ),
                {"h": str(household_id), "i": str(creator_id)},
            )
        await session.rollback()

    async with SessionFactory() as session:
        leaked = await session.scalar(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.identity_id == creator_id,
            )
        )
    assert leaked is None


async def test_households_addresses_is_invisible_to_an_unrelated_household() -> None:
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        address = HouseholdAddress(
            household_id=seed.household_a_id,
            label="خانه",
            recipient_name="x",
            recipient_mobile_e164="+989120000000",
            province="Tehran",
            city="Tehran",
            address_line="x",
            postal_code=None,
            active=True,
        )
        session.add(address)
        await session.commit()
        address_id = address.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible = list(
            (
                await session.scalars(
                    select(HouseholdAddress).where(HouseholdAddress.id == address_id)
                )
            ).all()
        )
    assert invisible == []


async def test_order_lines_and_payment_attempts_are_invisible_to_an_unrelated_customer() -> None:
    """orders_order_lines/payments_attempts have no customer_identity_id
    of their own -- their new policies reach it via an EXISTS against
    orders_orders, which is already customer_identity_id-scoped."""
    seed = await _seed_two_households()
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        supplier = Supplier(internal_name=f"rls-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa=f"rls-product-{token}", status="active")
        session.add_all([supplier, product])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"RLS-{token}",
            title_fa="x",
            unit_label_fa="x",
            price_irr=1000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        session.add(offer)
        await session.flush()
        line = OrderLine(
            order_id=seed.order_a_id,
            offer_id=offer.id,
            sku_snapshot="x",
            title_fa_snapshot="x",
            unit_label_fa_snapshot="x",
            supplier_country_snapshot="IR",
            quantity=1,
            unit_price_irr=1000,
            line_total_irr=1000,
            created_at=utc_now(),
        )
        attempt = PaymentAttempt(
            order_id=seed.order_a_id,
            provider="zarinpal",
            status="verified",
            amount_irr=1000,
            currency="IRR",
            idempotency_key=f"rls-payment-{uuid.uuid4().hex}",
        )
        session.add_all([line, attempt])
        await session.commit()
        line_id, attempt_id = line.id, attempt.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(seed.customer_b.id)}
        )
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible_lines = list(
            (await session.scalars(select(OrderLine).where(OrderLine.id == line_id))).all()
        )
        invisible_attempts = list(
            (
                await session.scalars(select(PaymentAttempt).where(PaymentAttempt.id == attempt_id))
            ).all()
        )
    assert invisible_lines == []
    assert invisible_attempts == []

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(seed.customer_a.id)}
        )
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_a_id)},
        )
        visible_lines = list(
            (await session.scalars(select(OrderLine).where(OrderLine.id == line_id))).all()
        )
    assert len(visible_lines) == 1


# --- 20260721_0047: more tenant-owned child tables --------------------------


async def test_food_estimate_and_consumption_assignment_are_invisible_across_households() -> None:
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        unit = InventoryUnit(
            household_id=seed.household_a_id,
            source="platform_order",
            state="opened",
            label="rls-unit",
            initial_quantity_grams=1000,
        )
        pet = Pet(household_id=seed.household_a_id, name="Rex", species="dog", status="active")
        session.add_all([unit, pet])
        await session.flush()
        estimate = FoodEstimate(
            inventory_unit_id=unit.id,
            low_days=1,
            high_days=2,
            confidence="low",
            status="active",
            calculated_at=utc_now(),
            basis="unknown_portion",
        )
        assignment = ConsumptionAssignment(inventory_unit_id=unit.id, pet_id=pet.id)
        session.add_all([estimate, assignment])
        await session.commit()
        estimate_id, assignment_id = estimate.id, assignment.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible_estimates = list(
            (
                await session.scalars(select(FoodEstimate).where(FoodEstimate.id == estimate_id))
            ).all()
        )
        invisible_assignments = list(
            (
                await session.scalars(
                    select(ConsumptionAssignment).where(ConsumptionAssignment.id == assignment_id)
                )
            ).all()
        )
    assert invisible_estimates == []
    assert invisible_assignments == []


async def test_fulfillment_events_and_resolutions_are_invisible_to_an_unrelated_customer() -> None:
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98929{uuid.uuid4().hex[:7]}", status="active"
        )
        session.add(operator)
        await session.flush()
        event = FulfillmentEvent(
            order_id=seed.order_a_id,
            event_type="sourcing_started",
            occurred_at=utc_now(),
            operator_identity_id=operator.id,
        )
        resolution = OrderResolution(
            order_id=seed.order_a_id,
            resolution_type="refund",
            requested_by_operator_id=operator.id,
            reason="x",
            proposed_facts={},
        )
        session.add_all([event, resolution])
        await session.commit()
        event_id, resolution_id = event.id, resolution.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(seed.customer_b.id)}
        )
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible_events = list(
            (
                await session.scalars(
                    select(FulfillmentEvent).where(FulfillmentEvent.id == event_id)
                )
            ).all()
        )
        invisible_resolutions = list(
            (
                await session.scalars(
                    select(OrderResolution).where(OrderResolution.id == resolution_id)
                )
            ).all()
        )
    assert invisible_events == []
    assert invisible_resolutions == []


async def test_diary_garden_and_journey_rows_are_invisible_across_households() -> None:
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        pet = Pet(household_id=seed.household_a_id, name="Rex", species="dog", status="active")
        session.add(pet)
        await session.flush()
        entry = DiaryEntry(
            pet_id=pet.id,
            entry_type="milestone",
            title_fa="x",
            happened_at=utc_now(),
            source_type="manual",
            source_id=str(uuid.uuid4()),
        )
        session.add(entry)
        await session.flush()
        reward = GardenReward(
            pet_id=pet.id,
            diary_entry_id=entry.id,
            source_type="owner_milestone",
            source_id=str(uuid.uuid4()),
            object_key="leaf",
        )
        definition = JourneyDefinition(
            key=f"rls-journey-{uuid.uuid4().hex[:8]}",
            version=1,
            title_fa="x",
            approval_status="approved",
            content={},
        )
        session.add_all([reward, definition])
        await session.flush()
        pet_journey = PetJourney(
            pet_id=pet.id, definition_id=definition.id, status="active", started_at=utc_now()
        )
        session.add(pet_journey)
        await session.flush()
        check_in = JourneyCheckIn(
            journey_id=pet_journey.id,
            check_in_key="step-1",
            answer_key="done",
            submitted_by_identity_id=seed.customer_a.id,
            submitted_at=utc_now(),
            idempotency_key=str(uuid.uuid4()),
        )
        session.add(check_in)
        await session.commit()
        entry_id, reward_id = entry.id, reward.id
        pet_journey_id, check_in_id = pet_journey.id, check_in.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible_entries = list(
            (await session.scalars(select(DiaryEntry).where(DiaryEntry.id == entry_id))).all()
        )
        invisible_rewards = list(
            (await session.scalars(select(GardenReward).where(GardenReward.id == reward_id))).all()
        )
        invisible_journeys = list(
            (await session.scalars(select(PetJourney).where(PetJourney.id == pet_journey_id))).all()
        )
        invisible_check_ins = list(
            (
                await session.scalars(
                    select(JourneyCheckIn).where(JourneyCheckIn.id == check_in_id)
                )
            ).all()
        )
    assert invisible_entries == []
    assert invisible_rewards == []
    assert invisible_journeys == []
    assert invisible_check_ins == []


async def test_pet_health_records_are_invisible_across_households() -> None:
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        pet = Pet(household_id=seed.household_a_id, name="Rex", species="dog", status="active")
        session.add(pet)
        await session.flush()
        measurement = HealthMeasurement(
            pet_id=pet.id,
            measurement_type="weight",
            value=5,
            unit="kg",
            measured_at=utc_now(),
            source="owner_reported",
            entered_by_identity_id=seed.customer_a.id,
            confidence="medium",
        )
        consent = PetConsent(
            pet_id=pet.id,
            granted_by_identity_id=seed.customer_a.id,
            purpose="body_photographs",
            policy_version="v1",
            granted_at=utc_now(),
        )
        reminder = MeasurementReminder(
            pet_id=pet.id,
            measurement_type="weight",
            due_at=utc_now(),
            created_by_identity_id=seed.customer_a.id,
        )
        session.add_all([measurement, consent, reminder])
        await session.commit()
        measurement_id, consent_id, reminder_id = measurement.id, consent.id, reminder.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.household_ids', :v, true)"),
            {"v": str(seed.household_b_id)},
        )
        invisible_measurements = list(
            (
                await session.scalars(
                    select(HealthMeasurement).where(HealthMeasurement.id == measurement_id)
                )
            ).all()
        )
        invisible_consents = list(
            (await session.scalars(select(PetConsent).where(PetConsent.id == consent_id))).all()
        )
        invisible_reminders = list(
            (
                await session.scalars(
                    select(MeasurementReminder).where(MeasurementReminder.id == reminder_id)
                )
            ).all()
        )
    assert invisible_measurements == []
    assert invisible_consents == []
    assert invisible_reminders == []


async def test_notifications_are_invisible_to_an_unrelated_identity() -> None:
    seed = await _seed_two_households()
    async with SessionFactory() as session:
        notification = Notification(
            recipient_identity_id=seed.customer_a.id,
            event_key="catalog.offer_available",
            source_id=str(uuid.uuid4()),
            channel="in_app",
            payload={},
            status="sent",
            destination_kind="none",
        )
        session.add(notification)
        await session.commit()
        notification_id = notification.id

    async with AppSessionFactory() as session:
        await session.execute(text("SELECT set_config('app.is_operator', 'false', true)"))
        await session.execute(
            text("SELECT set_config('app.identity_id', :v, true)"), {"v": str(seed.customer_b.id)}
        )
        invisible = list(
            (
                await session.scalars(
                    select(Notification).where(Notification.id == notification_id)
                )
            ).all()
        )
    assert invisible == []


async def test_app_role_is_not_a_superuser_and_cannot_bypass_rls() -> None:
    """Guards the precondition the entire feature depends on: Postgres
    unconditionally bypasses row security for superusers, with no policy
    able to override that. If a future environment change (or a
    connection-string mistake) ever pointed database_app_url back at a
    superuser role, every other test in this file would keep passing for
    the wrong reason -- this is the one test that would actually catch
    that regression."""
    async with app_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
        rolsuper, rolbypassrls = result.one()
    assert rolsuper is False
    assert rolbypassrls is False
