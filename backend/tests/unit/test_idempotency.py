from app.modules.system.idempotency import canonical_request_hash


def test_request_hash_is_stable_across_key_order() -> None:
    first = {"order_id": "123", "amount_irr": 500_000, "items": [2, 1]}
    second = {"items": [2, 1], "amount_irr": 500_000, "order_id": "123"}

    assert canonical_request_hash(first) == canonical_request_hash(second)


def test_request_hash_changes_when_financial_input_changes() -> None:
    first = {"order_id": "123", "amount_irr": 500_000}
    second = {"order_id": "123", "amount_irr": 500_001}

    assert canonical_request_hash(first) != canonical_request_hash(second)
