from uuid import uuid4

from app.modules.orders.resolutions import OrderResolution


def test_unapproved_resolution_is_non_executable_by_default() -> None:
    resolution = OrderResolution(
        order_id=uuid4(),
        resolution_type="refund",
        state="awaiting_policy",
        requested_by_operator_id=uuid4(),
        reason="Customer reported a sourcing failure",
        proposed_facts={"amount_irr": 100_000},
    )
    assert resolution.state == "awaiting_policy"
    assert resolution.approved_policy_version is None
