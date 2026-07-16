import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from app.modules.catalog.models import CatalogAvailabilitySubscription
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order, OrderDelayAcknowledgement
from app.modules.support.models import CustomerRequest
from sqlalchemy import UniqueConstraint

ROOT = Path(__file__).parents[2]
FIXTURE = json.loads((ROOT / "fixtures" / "demo" / "v2-frontend.json").read_text())


K9_ACCEPTANCE = {f"K9-T{index}" for index in range(1, 15)}
FIXTURE_SCENARIOS = {f"K9-T{index}" for index in range(1, 12)}
CLASSIFICATIONS = {"endpoint-backed", "frontend-local", "policy-gated", "deferred"}


def _paths() -> dict[str, object]:
    return create_app().openapi()["paths"]


def _split_operation(operation: str) -> tuple[str, str]:
    method, path = operation.split(" ", 1)
    return method.lower(), path


def test_k9_t1_through_t11_fixture_chains_are_endpoint_backed() -> None:
    paths = _paths()
    assert set(FIXTURE["scenarios"]) == FIXTURE_SCENARIOS
    for scenario_id, scenario in FIXTURE["scenarios"].items():
        assert scenario_id in FIXTURE_SCENARIOS
        assert scenario["chain"], scenario_id
        assert scenario["assertions"], scenario_id
        for operation in scenario["chain"]:
            method, path = _split_operation(operation)
            assert path in paths, operation
            assert method in paths[path], operation


def test_k9_t12_policy_gates_are_disabled_and_non_executable() -> None:
    settings = Settings()
    assert settings.reserve_now_enabled is False
    assert settings.cancel_after_sourcing_enabled is False
    assert settings.refund_self_service_enabled is False
    assert settings.replacement_self_service_enabled is False
    assert settings.substitution_self_service_enabled is False
    assert settings.delay_compensation_customer_visible is False
    assert settings.semantic_level_estimation_enabled is False
    assert settings.reorder_safety_buffer_days is None
    paths = _paths()
    forbidden_fragments = ("reserve", "refund", "replacement", "substitution", "compensation")
    customer_paths = [path for path in paths if not path.startswith("/api/v1/operator/")]
    assert not any(fragment in path for fragment in forbidden_fragments for path in customer_paths)


def test_k9_t13_cross_household_resources_have_authorization_surfaces() -> None:
    paths = _paths()
    household_scoped_operations = [
        "GET /api/v1/pet-life/households/{household_id}/pets",
        "GET /api/v1/orders/{order_id}",
        "PUT /api/v1/orders/{order_id}/pet-plan",
        "GET /api/v1/pet-life/inventory/{unit_id}",
        "POST /api/v1/pet-life/inventory/{unit_id}/reorder-assessment",
        "PUT /api/v1/pet-life/inventory/{unit_id}/reorder-snooze",
        "POST /api/v1/orders/{order_id}/delay-acknowledgements",
        "GET /api/v1/customer-requests/{request_id}",
        "GET /api/v1/pet-life/journeys/{journey_id}",
        "GET /api/v1/pet-life/pets/{pet_id}/diary/{entry_id}",
        "DELETE /api/v1/pet-life/garden/{reward_id}/placement",
    ]
    for operation in household_scoped_operations:
        method, path = _split_operation(operation)
        assert path in paths
        assert method in paths[path]
    route_sources = (
        (ROOT / "app" / "api" / "routes" / "commerce.py").read_text(encoding="utf-8")
        + (ROOT / "app" / "api" / "routes" / "pet_life.py").read_text(encoding="utf-8")
        + (ROOT / "app" / "api" / "routes" / "customer_requests.py").read_text(
            encoding="utf-8"
        )
    )
    assert "_household_access" in route_sources
    assert "_pet_access" in route_sources
    assert "status_code=404" in route_sources


def test_k9_t14_replay_sensitive_operations_expose_idempotency_or_unique_effects() -> None:
    paths = _paths()
    idempotent_operations = [
        "POST /api/v1/checkout/orders",
        "POST /api/v1/customer-requests",
        "POST /api/v1/orders/{order_id}/delay-acknowledgements",
        "POST /api/v1/pet-life/journeys/{journey_id}/check-ins",
    ]
    for operation in idempotent_operations:
        method, path = _split_operation(operation)
        params = paths[path][method].get("parameters", [])
        assert any(param["name"] == "Idempotency-Key" for param in params), operation
    unique_sets = {
        Order: {"checkout_idempotency_key"},
        CustomerRequest: {"identity_id", "idempotency_key"},
        OrderDelayAcknowledgement: {"identity_id", "order_id", "idempotency_key"},
        CatalogAvailabilitySubscription: {"identity_id", "offer_id", "activation_cycle"},
    }
    for model, columns in unique_sets.items():
        table_constraints = [
            {column.name for column in constraint.columns}
            for constraint in model.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        assert any(columns <= constraint_columns for constraint_columns in table_constraints)


def test_frontend_intent_audit_has_zero_unexplained_intents() -> None:
    paths = _paths()
    intents = FIXTURE["frontend_intents"]
    assert intents
    assert {item["classification"] for item in intents} <= CLASSIFICATIONS
    assert all(item["classification"] != "unexplained" for item in intents)
    for item in intents:
        endpoint = item["endpoint"]
        if item["classification"] == "endpoint-backed":
            assert endpoint is not None, item
            method, path = _split_operation(endpoint)
            assert path in paths, item
            assert method in paths[path], item


def test_k9_examples_cover_every_new_customer_operation() -> None:
    examples = json.loads((ROOT / "docs" / "api" / "examples.json").read_text(encoding="utf-8"))
    expected = {
        "me_context",
        "household_pets",
        "offer_detail",
        "order_detail",
        "order_pet_plan_request",
        "inventory_detail",
        "inventory_open_exact_grams_request",
        "reorder_assessment",
        "reorder_snooze_request",
        "today_unknown_estimate",
        "availability_subscription",
        "customer_request",
        "delay_acknowledgement",
        "journey_offer",
        "journey_definition",
        "journey_check_in",
        "diary_detail",
        "garden_state",
        "garden_placement_request",
    }
    assert expected <= set(examples)


def test_k9_acceptance_manifest_covers_all_required_scenarios() -> None:
    progress = (ROOT / "GATE_K9_PROGRESS.md").read_text(encoding="utf-8")
    for scenario_id in K9_ACCEPTANCE:
        assert scenario_id in progress
    assert "zero unexplained intents" in progress
    assert "1da656bcd5e08310596a5c77e5cad4f421e74691" in progress


def test_fixture_contains_no_supplier_identity_or_secret_material() -> None:
    forbidden_keys = {"supplier_id", "supplier_name", "password", "secret", "token"}
    seen_keys: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            seen_keys.update(str(key) for key in value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(FIXTURE)
    assert forbidden_keys.isdisjoint(seen_keys)
    assert FIXTURE["catalog"]["supplier_identity_exposed"] is False
    assert AuthIdentity.__tablename__ == "identity_auth_identities"
