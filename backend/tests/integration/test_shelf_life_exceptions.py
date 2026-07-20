from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.households.models import Household
from app.modules.identity.models import AuthIdentity
from app.modules.inventory.projection import project_delivered_order
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.refund_attestation import RefundAttestationError, attest_refund
from app.modules.orders.shelf_life_exceptions import (
    ShelfLifeException,
    ShelfLifeExceptionError,
    accept_shelf_life_exception,
    decline_shelf_life_exception,
    expire_stale_shelf_life_exceptions,
    propose_shelf_life_exception,
)
from app.modules.system.models import OperatorAuditLog
from app.modules.trust.files import EvidenceFile
from app.modules.trust.models import SourcedUnitEvidence, SupplierAssurance
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
class LineSeed:
    token: str
    operator_id: uuid.UUID
    customer_id: uuid.UUID
    household_id: uuid.UUID
    order_id: uuid.UUID
    order_line_id: uuid.UUID
    offer_id: uuid.UUID
    supplier_id: uuid.UUID
    minimum_shelf_life_months: int
    line_total_irr: int


async def _seed_unsourced_line(
    *, minimum_shelf_life_months: int = 6, quantity: int = 2, with_assurance: bool = True
) -> LineSeed:
    """A paid, in-sourcing order with one line that has no
    SourcedUnitEvidence yet -- the state right before an operator would
    call confirm-sourced or propose a shelf-life exception."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        supplier = Supplier(
            internal_name=f"sle-supplier-{token}", country_code="FR", active=True
        )
        product = Product(name_fa=f"محصول انقضا {token}", status="active")
        household = Household(name=f"hh-sle-{token}")
        session.add_all([operator, customer, supplier, product, household])
        await session.flush()
        if with_assurance:
            assurance_evidence = EvidenceFile(
                storage_key=f"assurances/{token}.pdf",
                original_filename="assurance.pdf",
                media_type="application/pdf",
                size_bytes=32,
                checksum_sha256="3" * 64,
                uploaded_by_operator_id=operator.id,
            )
            session.add(assurance_evidence)
            await session.flush()
            session.add(
                SupplierAssurance(
                    supplier_id=supplier.id,
                    version=1,
                    evidence_file_id=assurance_evidence.id,
                    valid_from=date(2020, 1, 1),
                    valid_until=None,
                    active=True,
                    recorded_by_operator_id=operator.id,
                )
            )
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"SLE-{token}",
            title_fa=f"پیشنهاد انقضا {token}",
            unit_label_fa="کیسه",
            price_irr=2_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            minimum_shelf_life_months=minimum_shelf_life_months,
        )
        session.add(offer)
        await session.flush()
        now = utc_now()
        unit_price = offer.price_irr
        order = Order(
            customer_identity_id=customer.id,
            household_id=household.id,
            status="sourcing",
            currency="IRR",
            merchandise_total_irr=unit_price * quantity,
            checkout_idempotency_key=f"sle-{token}",
            paid_at=now,
            delivery_commitment_at=now,
            delivery_address_snapshot={
                "label": "x",
                "recipient_name": "x",
                "recipient_mobile_e164": "+989120000000",
                "province": "x",
                "city": "x",
                "address_line": "x",
            },
        )
        session.add(order)
        await session.flush()
        line = OrderLine(
            order_id=order.id,
            offer_id=offer.id,
            sku_snapshot=offer.sku,
            title_fa_snapshot=offer.title_fa,
            unit_label_fa_snapshot=offer.unit_label_fa,
            supplier_country_snapshot="FR",
            quantity=quantity,
            unit_price_irr=unit_price,
            line_total_irr=unit_price * quantity,
            created_at=now,
        )
        session.add(line)
        await session.commit()
        return LineSeed(
            token=token,
            operator_id=operator.id,
            customer_id=customer.id,
            household_id=household.id,
            order_id=order.id,
            order_line_id=line.id,
            offer_id=offer.id,
            supplier_id=supplier.id,
            minimum_shelf_life_months=minimum_shelf_life_months,
            line_total_irr=unit_price * quantity,
        )


async def _evidence_file(operator_id: uuid.UUID) -> uuid.UUID:
    async with SessionFactory() as session:
        evidence = EvidenceFile(
            storage_key=f"evidence/{uuid.uuid4()}/exception.pdf",
            original_filename="exception.pdf",
            media_type="application/pdf",
            size_bytes=32,
            checksum_sha256="2" * 64,
            uploaded_by_operator_id=operator_id,
        )
        session.add(evidence)
        await session.commit()
        return evidence.id


async def _propose(
    seed: LineSeed,
    *,
    short_by_months: int = 4,
    additional_discount_irr: int = 0,
    response_window_hours: int = 72,
) -> uuid.UUID:
    too_short_expiry = date.today() + timedelta(
        days=30 * (seed.minimum_shelf_life_months - short_by_months)
    )
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        line = await session.get(OrderLine, seed.order_line_id)
        order = await session.get(Order, seed.order_id)
        assert line is not None and order is not None
        exception = await propose_shelf_life_exception(
            session,
            order_line=line,
            order=order,
            minimum_shelf_life_months=seed.minimum_shelf_life_months,
            operator_id=seed.operator_id,
            proposed_exact_expiry_date=too_short_expiry,
            additional_discount_irr=additional_discount_irr,
            reason="supplier shipment arrived with shorter shelf life than contracted",
            evidence_file_id=evidence_id,
            response_window_hours=response_window_hours,
        )
        await session.commit()
        return exception.id


# --- service-level: propose ---------------------------------------------


async def test_propose_rejects_an_expiry_that_actually_meets_the_guarantee() -> None:
    seed = await _seed_unsourced_line(minimum_shelf_life_months=6)
    fine_expiry = date.today() + timedelta(days=365)
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        line = await session.get(OrderLine, seed.order_line_id)
        order = await session.get(Order, seed.order_id)
        assert line is not None and order is not None
        with pytest.raises(ShelfLifeExceptionError):
            await propose_shelf_life_exception(
                session,
                order_line=line,
                order=order,
                minimum_shelf_life_months=seed.minimum_shelf_life_months,
                operator_id=seed.operator_id,
                proposed_exact_expiry_date=fine_expiry,
                additional_discount_irr=0,
                reason="should not need an exception",
                evidence_file_id=evidence_id,
            )


async def test_propose_rejects_a_second_exception_for_the_same_line() -> None:
    seed = await _seed_unsourced_line()
    await _propose(seed)
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        line = await session.get(OrderLine, seed.order_line_id)
        order = await session.get(Order, seed.order_id)
        assert line is not None and order is not None
        with pytest.raises(ShelfLifeExceptionError):
            await propose_shelf_life_exception(
                session,
                order_line=line,
                order=order,
                minimum_shelf_life_months=seed.minimum_shelf_life_months,
                operator_id=seed.operator_id,
                proposed_exact_expiry_date=date.today() + timedelta(days=30),
                additional_discount_irr=0,
                reason="second attempt should be rejected",
                evidence_file_id=evidence_id,
            )


async def test_propose_rejects_a_line_that_is_already_sourced() -> None:
    seed = await _seed_unsourced_line()
    async with SessionFactory() as session:
        line = await session.get(OrderLine, seed.order_line_id)
        assert line is not None
        session.add(
            SourcedUnitEvidence(
                order_line_id=line.id,
                exact_expiry_date=date.today() + timedelta(days=400),
                supplier_country_snapshot="FR",
                authenticity_basis="supplier_verified",
                supplier_assurance_id=(
                    await session.scalar(
                        select(SupplierAssurance).where(
                            SupplierAssurance.supplier_id == seed.supplier_id
                        )
                    )
                ).id,
                confirmed_at=utc_now(),
                recorded_by_operator_id=seed.operator_id,
            )
        )
        await session.commit()
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        line = await session.get(OrderLine, seed.order_line_id)
        order = await session.get(Order, seed.order_id)
        assert line is not None and order is not None
        with pytest.raises(ShelfLifeExceptionError):
            await propose_shelf_life_exception(
                session,
                order_line=line,
                order=order,
                minimum_shelf_life_months=seed.minimum_shelf_life_months,
                operator_id=seed.operator_id,
                proposed_exact_expiry_date=date.today() + timedelta(days=30),
                additional_discount_irr=0,
                reason="already sourced, should be rejected",
                evidence_file_id=evidence_id,
            )


# --- service-level: accept / decline --------------------------------------


async def test_accept_creates_sourced_unit_evidence_and_no_refund_when_discount_is_zero() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed, additional_discount_irr=0)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        result = await accept_shelf_life_exception(
            session,
            exception=exception,
            order_line=line,
            supplier_id=seed.supplier_id,
            customer_identity_id=seed.customer_id,
        )
        await session.commit()
    assert result.status == "accepted"
    assert result.refund_status == "not_applicable"
    assert result.refund_amount_irr is None
    async with SessionFactory() as session:
        evidence = await session.scalar(
            select(SourcedUnitEvidence).where(
                SourcedUnitEvidence.order_line_id == seed.order_line_id
            )
        )
        line = await session.get(OrderLine, seed.order_line_id)
    assert evidence is not None
    assert evidence.authenticity_basis == "shelf_life_exception_accepted"
    assert line is not None and line.excluded_from_delivery_at is None


async def test_accept_with_a_discount_marks_the_discount_amount_owed() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed, additional_discount_irr=150_000)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        result = await accept_shelf_life_exception(
            session,
            exception=exception,
            order_line=line,
            supplier_id=seed.supplier_id,
            customer_identity_id=seed.customer_id,
        )
        await session.commit()
    assert result.refund_status == "owed"
    assert result.refund_amount_irr == 150_000


async def test_accept_is_idempotent_on_replay() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)

    async def _accept_once() -> ShelfLifeException:
        async with SessionFactory() as session:
            exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
            line = await session.get(OrderLine, seed.order_line_id)
            assert exception is not None and line is not None
            result = await accept_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                supplier_id=seed.supplier_id,
                customer_identity_id=seed.customer_id,
            )
            await session.commit()
            return result

    first = await _accept_once()
    second = await _accept_once()
    assert first.responded_at == second.responded_at

    async with SessionFactory() as session:
        count = len(
            (
                await session.scalars(
                    select(SourcedUnitEvidence).where(
                        SourcedUnitEvidence.order_line_id == seed.order_line_id
                    )
                )
            ).all()
        )
    assert count == 1  # replay never creates a second evidence row


async def test_accept_without_active_supplier_assurance_is_rejected() -> None:
    seed = await _seed_unsourced_line(with_assurance=False)
    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        with pytest.raises(ShelfLifeExceptionError):
            await accept_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                supplier_id=seed.supplier_id,
                customer_identity_id=seed.customer_id,
            )


async def test_decline_marks_full_line_refund_owed_and_excludes_from_delivery() -> None:
    seed = await _seed_unsourced_line(quantity=3)
    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        result = await decline_shelf_life_exception(
            session, exception=exception, order_line=line, customer_identity_id=seed.customer_id
        )
        await session.commit()
    assert result.status == "declined"
    assert result.refund_status == "owed"
    assert result.refund_amount_irr == seed.line_total_irr
    async with SessionFactory() as session:
        line = await session.get(OrderLine, seed.order_line_id)
    assert line is not None and line.excluded_from_delivery_at is not None


async def test_decline_is_idempotent_on_replay() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)

    async def _decline_once() -> ShelfLifeException:
        async with SessionFactory() as session:
            exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
            line = await session.get(OrderLine, seed.order_line_id)
            assert exception is not None and line is not None
            result = await decline_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                customer_identity_id=seed.customer_id,
            )
            await session.commit()
            return result

    first = await _decline_once()
    second = await _decline_once()
    assert first.responded_at == second.responded_at


async def test_accept_and_decline_both_reject_once_the_other_already_resolved_it() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        await decline_shelf_life_exception(
            session, exception=exception, order_line=line, customer_identity_id=seed.customer_id
        )
        await session.commit()
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        with pytest.raises(ShelfLifeExceptionError):
            await accept_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                supplier_id=seed.supplier_id,
                customer_identity_id=seed.customer_id,
            )


async def test_response_after_the_deadline_expires_instead_of_accepting() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed, response_window_hours=0)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        with pytest.raises(ShelfLifeExceptionError, match="expired"):
            await accept_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                supplier_id=seed.supplier_id,
                customer_identity_id=seed.customer_id,
            )
        await session.commit()
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id)
        line = await session.get(OrderLine, seed.order_line_id)
    assert exception is not None and exception.status == "expired"
    assert exception.refund_status == "owed" and exception.refund_amount_irr == seed.line_total_irr
    assert line is not None and line.excluded_from_delivery_at is not None


# --- scheduler sweep -------------------------------------------------------


async def test_expiry_sweep_expires_only_exceptions_past_their_deadline() -> None:
    fresh_seed = await _seed_unsourced_line()
    stale_seed = await _seed_unsourced_line()
    fresh_id = await _propose(fresh_seed, response_window_hours=72)
    stale_id = await _propose(stale_seed, response_window_hours=0)

    await expire_stale_shelf_life_exceptions(SessionFactory)

    async with SessionFactory() as session:
        fresh = await session.get(ShelfLifeException, fresh_id)
        stale = await session.get(ShelfLifeException, stale_id)
    assert fresh is not None and fresh.status == "proposed"
    assert stale is not None and stale.status == "expired"
    assert stale.refund_status == "owed"


async def test_expiry_sweep_does_not_touch_an_already_resolved_exception() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)  # normal window: declined well before its deadline
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        await decline_shelf_life_exception(
            session, exception=exception, order_line=line, customer_identity_id=seed.customer_id
        )
        # Simulate the deadline having since passed. The sweep's WHERE
        # clause filters on respond_by, so without this the row would
        # never even be examined and the test would prove nothing.
        exception.respond_by = utc_now() - timedelta(hours=1)
        await session.commit()
        responded_at_before = exception.responded_at

    await expire_stale_shelf_life_exceptions(SessionFactory)

    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id)
    assert exception is not None
    assert exception.status == "declined"  # not overwritten to 'expired'
    assert exception.responded_at == responded_at_before


# --- delivery projection skips excluded lines ------------------------------


async def test_delivery_projection_skips_a_declined_line_but_still_delivers_the_rest() -> None:
    seed = await _seed_unsourced_line(quantity=1)
    # A second, normally-sourced line on the same order.
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        good_line = OrderLine(
            order_id=seed.order_id,
            offer_id=offer.id,
            sku_snapshot=offer.sku,
            title_fa_snapshot=offer.title_fa,
            unit_label_fa_snapshot=offer.unit_label_fa,
            supplier_country_snapshot="FR",
            quantity=1,
            unit_price_irr=offer.price_irr,
            line_total_irr=offer.price_irr,
            created_at=utc_now(),
        )
        session.add(good_line)
        await session.flush()
        assurance = await session.scalar(
            select(SupplierAssurance).where(SupplierAssurance.supplier_id == seed.supplier_id)
        )
        assert assurance is not None
        session.add(
            SourcedUnitEvidence(
                order_line_id=good_line.id,
                exact_expiry_date=date.today() + timedelta(days=400),
                supplier_country_snapshot="FR",
                authenticity_basis="supplier_verified",
                supplier_assurance_id=assurance.id,
                confirmed_at=utc_now(),
                recorded_by_operator_id=seed.operator_id,
            )
        )
        await session.commit()
        good_line_id = good_line.id

    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        bad_line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and bad_line is not None
        await decline_shelf_life_exception(
            session, exception=exception, order_line=bad_line, customer_identity_id=seed.customer_id
        )
        order = await session.get(Order, seed.order_id)
        assert order is not None
        order.status = "delivered"
        order.delivered_at = utc_now()
        await session.commit()

    async with SessionFactory() as session:
        units = await project_delivered_order(
            session, order_id=seed.order_id, household_id=seed.household_id
        )
        await session.commit()
    assert len(units) == 1
    assert units[0].order_line_id == good_line_id


# --- refund attestation -----------------------------------------------------


async def test_attest_refund_transitions_owed_to_attested_and_is_idempotent() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        await decline_shelf_life_exception(
            session, exception=exception, order_line=line, customer_identity_id=seed.customer_id
        )
        await session.commit()
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        assert exception is not None
        attest_refund(
            exception, operator_id=seed.operator_id, evidence_id=evidence_id, reference="PAY-1"
        )
        await session.commit()
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id)
    assert exception is not None
    assert exception.refund_status == "operator_attested"
    assert exception.refund_reference == "PAY-1"

    # Replay is a no-op, not an error.
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        assert exception is not None
        attest_refund(
            exception, operator_id=seed.operator_id, evidence_id=evidence_id, reference="PAY-1"
        )
        await session.commit()


async def test_attest_refund_rejects_when_nothing_is_owed() -> None:
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed, additional_discount_irr=0)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        await accept_shelf_life_exception(
            session,
            exception=exception,
            order_line=line,
            supplier_id=seed.supplier_id,
            customer_identity_id=seed.customer_id,
        )
        await session.commit()
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        assert exception is not None
        with pytest.raises(RefundAttestationError):
            attest_refund(
                exception, operator_id=seed.operator_id, evidence_id=evidence_id, reference=None
            )


# --- concurrency: accept vs. decline ---------------------------------------


async def _race_accept(seed: LineSeed, exception_id: uuid.UUID) -> str:
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        try:
            await accept_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                supplier_id=seed.supplier_id,
                customer_identity_id=seed.customer_id,
            )
        except ShelfLifeExceptionError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "accepted"


async def _race_decline(seed: LineSeed, exception_id: uuid.UUID) -> str:
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        try:
            await decline_shelf_life_exception(
                session,
                exception=exception,
                order_line=line,
                customer_identity_id=seed.customer_id,
            )
        except ShelfLifeExceptionError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "declined"


async def test_concurrent_accept_and_decline_never_both_succeed() -> None:
    accept_wins = 0
    decline_wins = 0
    for _ in range(15):
        seed = await _seed_unsourced_line()
        exception_id = await _propose(seed)

        accept_result, decline_result = await asyncio.gather(
            _race_accept(seed, exception_id), _race_decline(seed, exception_id)
        )
        outcomes = {accept_result, decline_result}
        # Exactly one side wins; the other must observe the resolved state
        # and back off, never both actually applying their own outcome.
        assert outcomes in ({"accepted", "rejected"}, {"declined", "rejected"})
        if accept_result == "accepted":
            accept_wins += 1
        else:
            decline_wins += 1

        async with SessionFactory() as session:
            exception = await session.get(ShelfLifeException, exception_id)
            evidence_count = len(
                (
                    await session.scalars(
                        select(SourcedUnitEvidence).where(
                            SourcedUnitEvidence.order_line_id == seed.order_line_id
                        )
                    )
                ).all()
            )
        assert exception is not None
        if exception.status == "accepted":
            assert evidence_count == 1
        else:
            assert exception.status == "declined"
            assert evidence_count == 0

    assert accept_wins > 0
    assert decline_wins > 0


# --- HTTP layer --------------------------------------------------------------


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[object, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def _audit_count(action: str, resource_id: str) -> int:
    async with SessionFactory() as session:
        return (
            await session.execute(
                select(func.count(OperatorAuditLog.id)).where(
                    OperatorAuditLog.action == action,
                    OperatorAuditLog.resource_id == resource_id,
                )
            )
        ).scalar_one()


async def test_http_hard_block_rejects_an_expiry_shorter_than_the_guarantee(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    seed = await _seed_unsourced_line(minimum_shelf_life_months=6)
    async with SessionFactory() as session:
        operator = await session.get(AuthIdentity, seed.operator_id)
    app.dependency_overrides[get_current_identity] = lambda: operator

    too_short = (date.today() + timedelta(days=30)).isoformat()
    response = await client.post(
        f"/api/v1/operator/order-lines/{seed.order_line_id}/confirm-sourced",
        json={"exact_expiry_date": too_short, "reason": "sourced but shelf life is short"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "shelf_life_guarantee_not_met"

    async with SessionFactory() as session:
        evidence = await session.scalar(
            select(SourcedUnitEvidence).where(
                SourcedUnitEvidence.order_line_id == seed.order_line_id
            )
        )
    assert evidence is None


async def test_http_operator_propose_and_customer_accept_flow(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    seed = await _seed_unsourced_line()
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        operator = await session.get(AuthIdentity, seed.operator_id)
        customer = await session.get(AuthIdentity, seed.customer_id)

    app.dependency_overrides[get_current_identity] = lambda: operator
    too_short = (date.today() + timedelta(days=60)).isoformat()
    proposed = await client.post(
        f"/api/v1/operator/order-lines/{seed.order_line_id}/shelf-life-exceptions",
        json={
            "proposed_exact_expiry_date": too_short,
            "additional_discount_irr": 100_000,
            "evidence_file_id": str(evidence_id),
            "reason": "supplier shipment shelf life shorter than contracted",
        },
    )
    assert proposed.status_code == 201
    exception_id = proposed.json()["id"]
    # Audited against the order line (the acted-upon resource), matching
    # confirm_sourced_unit's convention -- not the newly-created exception.
    assert (
        await _audit_count("shelf_life_exception.proposed", str(seed.order_line_id)) == 1
    )

    app.dependency_overrides[get_current_identity] = lambda: customer
    listed = await client.get(f"/api/v1/orders/{seed.order_id}/shelf-life-exceptions")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == exception_id
    assert listed.json()[0]["refund_auto_processed"] is False

    accepted = await client.post(
        f"/api/v1/orders/{seed.order_id}/shelf-life-exceptions/{exception_id}/accept"
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["refund_status"] == "owed"
    assert body["refund_amount_irr"] == 100_000


async def test_http_decline_is_non_enumerating_for_foreign_order(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        other_customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98917{seed.token[:7]}", status="active"
        )
        session.add(other_customer)
        await session.commit()
        other_customer_id = other_customer.id
    async with SessionFactory() as session:
        other_customer_obj = await session.get(AuthIdentity, other_customer_id)
    app.dependency_overrides[get_current_identity] = lambda: other_customer_obj

    nonexistent_order = await client.post(
        f"/api/v1/orders/{uuid.uuid4()}/shelf-life-exceptions/{exception_id}/decline"
    )
    foreign_order = await client.post(
        f"/api/v1/orders/{seed.order_id}/shelf-life-exceptions/{exception_id}/decline"
    )
    assert nonexistent_order.status_code == foreign_order.status_code == 404
    assert (
        nonexistent_order.json()["error"]["code"] == foreign_order.json()["error"]["code"]
    )


async def test_http_operator_attests_refund_for_a_declined_exception(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    seed = await _seed_unsourced_line()
    exception_id = await _propose(seed)
    async with SessionFactory() as session:
        exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
        line = await session.get(OrderLine, seed.order_line_id)
        assert exception is not None and line is not None
        await decline_shelf_life_exception(
            session, exception=exception, order_line=line, customer_identity_id=seed.customer_id
        )
        await session.commit()
    evidence_id = await _evidence_file(seed.operator_id)
    async with SessionFactory() as session:
        operator = await session.get(AuthIdentity, seed.operator_id)
    app.dependency_overrides[get_current_identity] = lambda: operator

    response = await client.post(
        f"/api/v1/operator/shelf-life-exceptions/{exception_id}/attest-refund",
        json={
            "evidence_file_id": str(evidence_id),
            "reference": "BANK-REF-1",
            "reason": "manually transferred refund to customer bank account",
        },
    )
    assert response.status_code == 200
    assert response.json()["refund_status"] == "operator_attested"
    assert await _audit_count("shelf_life_exception.refund_attested", str(exception_id)) == 1

    replay = await client.post(
        f"/api/v1/operator/shelf-life-exceptions/{exception_id}/attest-refund",
        json={
            "evidence_file_id": str(evidence_id),
            "reference": "BANK-REF-1",
            "reason": "retry after client timeout",
        },
    )
    assert replay.status_code == 200
    assert await _audit_count("shelf_life_exception.refund_attested", str(exception_id)) == 1
