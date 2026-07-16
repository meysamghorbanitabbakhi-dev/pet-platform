import json
from pathlib import Path

import httpx
import pytest
from app.core.config import get_settings
from app.main import create_app, get_storage


@pytest.mark.asyncio
async def test_liveness_and_policy_contract(tmp_path: Path) -> None:
    settings = get_settings()
    original_media_root = settings.media_root
    settings.media_root = tmp_path
    get_storage.cache_clear()
    try:
        application = create_app()
        async with application.router.lifespan_context(application):
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                live = await client.get("/health/live")
                policies = await client.get("/api/v1/system/policies")

        assert live.status_code == 200
        assert live.json() == {"status": "alive"}
        assert policies.status_code == 200
        assert policies.json()["delivery_commitment_hours"] == 366
        assert policies.json()["currency_code"] == "IRR"
        assert policies.json()["customer_display_currency_code"] == "IRR"
        assert policies.json()["customer_display_unit"] == "TOMAN"
        assert policies.json()["irr_per_customer_display_unit"] == 10
        assert policies.json()["late_credit_enabled"] is False
        assert policies.json()["late_credit_customer_visible"] is False
        assert policies.json()["reserve_now_enabled"] is False
        assert policies.json()["cancel_after_sourcing_enabled"] is False
        assert policies.json()["refund_self_service_enabled"] is False
        assert policies.json()["replacement_self_service_enabled"] is False
        assert policies.json()["substitution_self_service_enabled"] is False
        assert policies.json()["delay_compensation_customer_visible"] is False
        assert policies.json()["availability_subscriptions_enabled"] is True
        assert policies.json()["concierge_requests_enabled"] is True
        assert policies.json()["care_journey_delivery_enabled"] is True
        assert policies.json()["push_notifications_enabled"] is False
        assert policies.json()["semantic_level_estimation_enabled"] is True
        assert policies.json()["reorder_safety_buffer_days"] == 3
        assert policies.json()["reorder_snooze_early_break_worsening_days"] == 2
    finally:
        settings.media_root = original_media_root
        get_storage.cache_clear()


@pytest.mark.asyncio
async def test_gate_b1_routes_are_exposed() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        schema = (await client.get("/openapi.json")).json()
    paths = schema["paths"]
    assert "/api/v1/auth/session/refresh" in paths
    assert "/api/v1/catalog/offers" in paths
    assert "/api/v1/checkout/orders" in paths
    assert "/api/v1/orders/{order_id}/payments/zarinpal" in paths
    assert "/api/v1/payments/zarinpal/callback" in paths
    assert "/api/v1/operator/offers" in paths
    assert "/api/v1/operator/payments/{attempt_id}/reconcile" in paths
    assert "/api/v1/pet-life/households" in paths
    assert "/api/v1/pet-life/inventory/{unit_id}/open" in paths
    assert "/api/v1/pet-life/journeys/{journey_id}/complete" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/diary" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/garden" in paths
    assert "/api/v1/pet-life/reorder/assess" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/today" in paths
    assert "/api/v1/pet-life/households/{household_id}/wallet" in paths
    assert "/api/v1/operator/orders/{order_id}/fulfillment" in paths
    assert "/api/v1/operator/orders/{order_id}/late-credit" in paths
    assert "/api/v1/operator/journey-definitions/{definition_id}/approve" in paths
    assert "/api/v1/orders" in paths
    assert "/api/v1/orders/{order_id}/journey" in paths
    assert "/api/v1/operator/orders/{order_id}/resolutions" in paths
    assert "/api/v1/operator/customers/{identity_id}/overview" in paths
    assert "/api/v1/operator/suppliers/{supplier_id}/assurances" in paths
    assert "/api/v1/operator/offers/{offer_id}/reference-evidence" in paths
    assert "/api/v1/operator/order-lines/{line_id}/confirm-sourced" in paths
    assert "/api/v1/operator/notification-templates" in paths
    assert "/api/v1/pet-life/notifications/preferences/{event_key}/sms" in paths
    assert "/api/v1/pet-life/households/{household_id}/inventory" in paths
    assert "/api/v1/pet-life/households/{household_id}/addresses" in paths
    assert "/api/v1/pet-life/notifications" in paths
    assert "/api/v1/pet-life/notifications/{notification_id}/read" in paths
    assert "/api/v1/operator/evidence-files" in paths
    assert "/api/v1/operator/evidence-files/{evidence_id}" in paths
    assert "/api/v1/operator/offers/{offer_id}/capacity" in paths
    assert "/api/v1/operator/telemetry" in paths
    assert "/api/v1/operator/audit/export" in paths
    assert "/api/v1/privacy/export" in paths
    assert "/api/v1/privacy/requests" in paths
    assert "/api/v1/operator/privacy/requests" in paths
    assert "/api/v1/operator/privacy/requests/{request_id}/disable" in paths
    assert "/api/v1/orders/feed" in paths
    assert "/api/v1/pet-life/notifications/feed" in paths
    assert "/api/v1/operator/webhooks/failed" in paths
    assert "/api/v1/operator/webhooks/{event_id}/replay" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/profile" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/measurements" in paths
    assert (
        "/api/v1/pet-life/pets/{pet_id}/measurements/{measurement_id}/corrections" in paths
    )
    assert "/api/v1/pet-life/pets/{pet_id}/weight-trend" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/measurement-reminders" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/consents" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/consents/{consent_id}/withdraw" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/assets" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/assets/{asset_id}" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/body-assessments" in paths
    assert "/api/v1/operator/body-assessments/{assessment_id}/confirm" in paths
    assert "/api/v1/operator/knowledge-releases/validate" in paths
    assert "/api/v1/operator/knowledge-releases/import" in paths
    assert "/api/v1/operator/knowledge-releases" in paths
    assert "/api/v1/operator/knowledge-claims/{claim_id}/review" in paths
    assert "/api/v1/operator/knowledge-releases/{release_id}/publish" in paths
    assert "/api/v1/operator/knowledge-claims/{claim_id}/withdraw" in paths
    assert "/api/v1/operator/knowledge-releases/{release_id}/withdraw" in paths
    assert "/api/v1/knowledge/breeds" in paths
    assert "/api/v1/knowledge/search" in paths
    assert "/api/v1/knowledge/breeds/{breed_id}" in paths
    assert "/api/v1/knowledge/pets/{pet_id}" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/breed-selection" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/breed-selection/history" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/profile-completeness" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/care-guidance" in paths
    assert (
        "/api/v1/pet-life/pets/{pet_id}/care-guidance/{guidance_id}/preference" in paths
    )
    assert "/api/v1/operator/knowledge-review-tasks" in paths
    assert "/api/v1/operator/knowledge-claims/{claim_id}/benchmark" in paths
    assert (
        "/api/v1/pet-life/pets/{pet_id}/measurements/{measurement_id}/reference-comparison"
        in paths
    )
    assert "/api/v1/operator/knowledge-releases/{release_id}/batch-approve" in paths
    assert "/api/v1/operator/knowledge-releases/{release_id}/guidance/import" in paths
    assert "/api/v1/operator/knowledge-releases/{release_id}/reconciliation" in paths
    assert (
        "/api/v1/operator/knowledge-releases/{release_id}/materialize-benchmarks" in paths
    )
    assert "/api/v1/operator/knowledge-activation-runs" in paths
    assert "/api/v1/operator/knowledge-activation-runs/{run_id}" in paths
    assert "/api/v1/operator/knowledge-activation-runs/{run_id}/preflight" in paths
    assert "/api/v1/operator/knowledge-activation-runs/{run_id}/execute" in paths
    assert "/api/v1/operator/knowledge-activation-runs/{run_id}/rollback" in paths


def test_checked_openapi_artifact_matches_application() -> None:
    artifact = Path(__file__).parents[2] / "docs" / "api" / "openapi.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == create_app().openapi()


@pytest.mark.asyncio
async def test_api_errors_use_stable_envelope() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/not-a-route", headers={"X-Request-ID": "test-rid"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "details": None,
            "request_id": "test-rid",
        }
    }


@pytest.mark.asyncio
async def test_security_headers_body_limit_and_metrics() -> None:
    settings = get_settings()
    original_limit = settings.max_request_body_bytes
    settings.max_request_body_bytes = 1024
    try:
        application = create_app()
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            live = await client.get("/health/live")
            oversized = await client.post(
                "/api/v1/auth/otp/request",
                content=b"x" * 1025,
                headers={"content-type": "application/json"},
            )
            metrics_response = await client.get("/internal/metrics")

        assert live.headers["x-content-type-options"] == "nosniff"
        assert live.headers["x-frame-options"] == "DENY"
        assert live.headers["cache-control"] == "no-store"
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "request_body_too_large"
        assert oversized.json()["error"]["request_id"]
        assert metrics_response.status_code == 200
        assert "pet_platform_http_requests_total" in metrics_response.text
    finally:
        settings.max_request_body_bytes = original_limit
