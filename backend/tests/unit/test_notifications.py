from datetime import UTC, datetime, time
from uuid import uuid4

from app.modules.notifications.models import NotificationPreference
from app.modules.notifications.service import _inside_quiet_hours


def test_cross_midnight_quiet_hours_use_iran_time() -> None:
    preference = NotificationPreference(
        identity_id=uuid4(),
        channel="sms",
        event_key="wallet.late_delivery_credit_granted",
        enabled=True,
        quiet_start_local=time(22, 0),
        quiet_end_local=time(8, 0),
    )
    # 20:00 UTC is 23:30 in Iran during the current fixed UTC+03:30 zone.
    assert _inside_quiet_hours(preference, datetime(2026, 7, 16, 20, 0, tzinfo=UTC)) is True
    assert _inside_quiet_hours(preference, datetime(2026, 7, 16, 8, 0, tzinfo=UTC)) is False


def test_missing_quiet_hours_never_defer() -> None:
    preference = NotificationPreference(
        identity_id=uuid4(),
        channel="sms",
        event_key="event",
        enabled=True,
    )
    assert _inside_quiet_hours(preference, datetime.now(UTC)) is False
