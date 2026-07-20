from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.households.models import Household
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order
from app.modules.payments.models import PaymentAttempt
from app.modules.reporting.kpi import KPI_REGISTRY
from app.modules.reporting.service import compute_all_kpis, compute_kpi
from app.modules.sourcing.models import SourcingJob
from app.modules.wallet.models import (
    WalletAccount,
    WalletCredit,
    WalletDebit,
    WalletDebitAllocation,
)
from fastapi import FastAPI

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)

# A far-future base date: nothing else in this suite (or a live background
# worker) ever dates real data in 2030, so windows built from it are immune
# to pollution from the shared dev database's "now"-dated activity. Each
# fixture invocation additionally gets its OWN day offset (see
# reporting_seed below) so that separate test functions -- each getting a
# fresh, function-scoped, never-rolled-back seed -- don't pollute each
# other's windows either.
_BASE = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class ReportingSeed:
    operator: AuthIdentity
    customer: AuthIdentity
    paid_order_id: uuid.UUID
    unpaid_order_id: uuid.UUID
    window_start: datetime
    window_end: datetime


@pytest.fixture()
async def reporting_seed() -> ReportingSeed:
    token = uuid.uuid4().hex[:10]
    # A unique day offset per invocation (0..9999) keeps each test
    # function's data in its own non-overlapping window.
    day_offset = uuid.uuid4().int % 9999
    window_start = _BASE + timedelta(days=day_offset)
    window_end = window_start + timedelta(days=1)
    inside = window_start + timedelta(hours=1)
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98925{token[:7]}", status="active"
        )
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98926{token[:7]}", status="active"
        )
        supplier = Supplier(internal_name=f"kpi-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa=f"kpi-product-{token}", status="active")
        household = Household(name=f"kpi-hh-{token}")
        session.add_all([operator, customer, supplier, product, household])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"KPI-{token}",
            title_fa="پیشنهاد گزارش",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            minimum_shelf_life_months=6,
        )
        session.add(offer)
        await session.flush()

        commitment = inside + timedelta(hours=48)
        paid_order = Order(
            customer_identity_id=customer.id,
            household_id=household.id,
            status="delivered",
            currency="IRR",
            merchandise_total_irr=2_500_000,
            checkout_idempotency_key=f"kpi-paid-{token}",
            delivery_address_snapshot={"line": "kpi test address"},
            paid_at=inside,
            delivery_commitment_at=commitment,
            delivered_at=inside + timedelta(hours=10),
            created_at=inside,
        )
        unpaid_order = Order(
            customer_identity_id=customer.id,
            household_id=household.id,
            status="awaiting_payment",
            currency="IRR",
            merchandise_total_irr=1_500_000,
            checkout_idempotency_key=f"kpi-unpaid-{token}",
            delivery_address_snapshot={"line": "kpi test address"},
            created_at=inside,
        )
        session.add_all([paid_order, unpaid_order])
        await session.flush()

        verified_attempt = PaymentAttempt(
            order_id=paid_order.id,
            status="verified",
            amount_irr=2_500_000,
            idempotency_key=f"kpi-attempt-verified-{token}",
            verified_at=inside,
            created_at=inside,
        )
        failed_attempt = PaymentAttempt(
            order_id=unpaid_order.id,
            status="failed",
            amount_irr=1_500_000,
            idempotency_key=f"kpi-attempt-failed-{token}",
            created_at=inside,
        )
        sourcing_job = SourcingJob(order_id=paid_order.id, status="failed", created_at=inside)
        session.add_all([verified_attempt, failed_attempt, sourcing_job])

        wallet_account = WalletAccount(household_id=household.id)
        session.add(wallet_account)
        await session.flush()
        credit = WalletCredit(
            wallet_account_id=wallet_account.id,
            original_amount_irr=200_000,
            remaining_amount_irr=100_000,
            expires_at=inside + timedelta(days=90),
            source_type="late_delivery_credit",
            source_id=f"kpi-credit-{token}",
            created_at=inside,
        )
        session.add(credit)
        await session.flush()
        debit = WalletDebit(
            wallet_account_id=wallet_account.id,
            amount_irr=100_000,
            idempotency_key=f"kpi-debit-{token}",
            created_at=inside,
        )
        session.add(debit)
        await session.flush()
        allocation = WalletDebitAllocation(
            wallet_debit_id=debit.id, wallet_credit_id=credit.id, amount_irr=100_000
        )
        session.add(allocation)

        await session.commit()
        return ReportingSeed(
            operator=operator,
            customer=customer,
            paid_order_id=paid_order.id,
            unpaid_order_id=unpaid_order.id,
            window_start=window_start,
            window_end=window_end,
        )


def test_kpi_registry_has_a_compute_function_for_every_key() -> None:
    # Guards against a registry entry silently missing its computation --
    # service.py asserts this at import time too; this test makes the
    # invariant visible as a normal, discoverable test result.
    from app.modules.reporting.service import _COMPUTE

    assert set(_COMPUTE) == set(KPI_REGISTRY)


async def test_conversion_and_payment_success(reporting_seed: ReportingSeed) -> None:
    async with SessionFactory() as session:
        conversion = await compute_kpi(
            session,
            "conversion",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
        payment_success = await compute_kpi(
            session,
            "payment_success",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
    assert conversion.computable
    assert conversion.numerator == 1
    assert conversion.denominator == 2
    assert conversion.value == pytest.approx(0.5)

    assert payment_success.computable
    assert payment_success.numerator == 1
    assert payment_success.denominator == 2
    assert payment_success.value == pytest.approx(0.5)


async def test_sourcing_failure_and_delivery_within_commitment(
    reporting_seed: ReportingSeed,
) -> None:
    async with SessionFactory() as session:
        sourcing_failure = await compute_kpi(
            session,
            "sourcing_failure",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
        delivery = await compute_kpi(
            session,
            "delivery_within_commitment",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
    assert sourcing_failure.computable
    assert sourcing_failure.numerator == 1
    assert sourcing_failure.denominator == 1
    assert sourcing_failure.value == pytest.approx(1.0)

    assert delivery.computable
    assert delivery.numerator == 1
    assert delivery.denominator == 1
    assert delivery.value == pytest.approx(1.0)


async def test_late_credit_issuance_and_redemption(reporting_seed: ReportingSeed) -> None:
    async with SessionFactory() as session:
        issuance = await compute_kpi(
            session,
            "late_credit_issuance",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
        redemption = await compute_kpi(
            session,
            "late_credit_redemption",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
    assert issuance.computable
    assert issuance.numerator == pytest.approx(200_000.0)
    assert issuance.denominator == pytest.approx(1.0)

    assert redemption.computable
    assert redemption.numerator == pytest.approx(100_000.0)
    assert redemption.denominator == pytest.approx(200_000.0)
    assert redemption.value == pytest.approx(0.5)


async def test_gmv_matches_paid_order_total(reporting_seed: ReportingSeed) -> None:
    async with SessionFactory() as session:
        gmv = await compute_kpi(
            session,
            "gmv",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
    assert gmv.computable
    assert gmv.numerator == pytest.approx(2_500_000.0)
    assert gmv.denominator == pytest.approx(1.0)


async def test_margin_is_honestly_reported_as_not_computable(
    reporting_seed: ReportingSeed,
) -> None:
    async with SessionFactory() as session:
        margin = await compute_kpi(
            session,
            "margin",
            window_start=reporting_seed.window_start,
            window_end=reporting_seed.window_end,
        )
    assert margin.computable is False
    assert margin.data_limitation is not None
    assert "cost" in margin.data_limitation.lower()


async def test_compute_all_kpis_returns_every_registered_key(
    reporting_seed: ReportingSeed,
) -> None:
    async with SessionFactory() as session:
        results = await compute_all_kpis(
            session, window_start=reporting_seed.window_start, window_end=reporting_seed.window_end
        )
    assert {result.key for result in results} == set(KPI_REGISTRY)
    for result in results:
        if result.computable:
            assert result.denominator is not None and result.denominator >= 0
            if result.numerator is not None and result.denominator not in (None, 0):
                assert result.numerator <= result.denominator or result.unit == "irr_total"


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_http_operator_kpis_endpoint_returns_every_kpi(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], reporting_seed: ReportingSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: reporting_seed.operator

    response = await client.get(
        "/api/v1/operator/kpis",
        params={
            "window_start": reporting_seed.window_start.isoformat(),
            "window_end": reporting_seed.window_end.isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert {item["key"] for item in body} == set(KPI_REGISTRY)
    conversion = next(item for item in body if item["key"] == "conversion")
    assert conversion["numerator"] == 1
    assert conversion["denominator"] == 2
    margin = next(item for item in body if item["key"] == "margin")
    assert margin["computable"] is False


async def test_http_operator_kpis_rejects_inverted_window(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], reporting_seed: ReportingSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: reporting_seed.operator

    response = await client.get(
        "/api/v1/operator/kpis",
        params={
            "window_start": reporting_seed.window_end.isoformat(),
            "window_end": reporting_seed.window_start.isoformat(),
        },
    )
    assert response.status_code == 422


async def test_http_operator_kpis_requires_operator_role(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], reporting_seed: ReportingSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: reporting_seed.customer

    response = await client.get(
        "/api/v1/operator/kpis",
        params={
            "window_start": reporting_seed.window_start.isoformat(),
            "window_end": reporting_seed.window_end.isoformat(),
        },
    )
    assert response.status_code == 403
