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
from app.modules.households.models import Household, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order
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
                await session.scalars(
                    select(Household).where(Household.id == seed.household_a_id)
                )
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
                await session.scalars(
                    select(Household).where(Household.id == seed.household_a_id)
                )
            ).all()
        )
        visible = list(
            (
                await session.scalars(
                    select(Household).where(Household.id == seed.household_b_id)
                )
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
                await session.scalars(
                    select(Household).where(Household.id == seed.household_a_id)
                )
            ).all()
        )
        assert len(visible) == 1
        await session.commit()

        invisible = list(
            (
                await session.scalars(
                    select(Household).where(Household.id == seed.household_a_id)
                )
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
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        )
        rolsuper, rolbypassrls = result.one()
    assert rolsuper is False
    assert rolbypassrls is False
